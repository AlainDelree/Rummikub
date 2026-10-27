#!/usr/bin/env python3
"""Adaptateur vers le solveur EXACT de la bibliothèque libre ``rummikub-solver``
(PyPI, licence MIT — issue #204, suite de #201).

Contexte
--------
Le solveur d'Expert du jeu (``moteur/solveur.py``) est à la fois le joueur et
le juge de l'analyse des coups ratés : s'il manque un coup, l'analyse ne le
voit pas non plus (ses résultats sont une BORNE BASSE, voir
``persistance/coups_rates.py``). Il existe une solution EXACTE et connue du
problème de l'optimum d'un tour : la programmation linéaire en nombres entiers
(den Hertog et Hulshof, *The Computer Journal*, 2006), implémentée dans
``rummikub-solver`` (dépend de ``cvxpy-base`` et ``numpy`` ; extra ``highs``
pour le solveur HiGHS, licence MIT). Ce module convertit un état de NOS
fichiers de référence vers la bibliothèque, appelle sa résolution exacte, et
renvoie — reconstruits dans NOTRE domaine (tuiles ``moteur/tuiles.Tuile``) —
le nombre de tuiles posées, les combinaisons proposées REMISES DANS L'ORDRE
(suites, place des jokers), la durée du calcul, et le résultat des deux
contrôles indépendants exigés par l'issue : chaque combinaison vérifiée par
``valider_combinaison`` et conservation des tuiles du plateau.

Dépendance de DÉVELOPPEMENT seulement
-------------------------------------
La bibliothèque N'EST PAS ajoutée à ``requirements.txt`` ni au build Windows
(voir CONTEXTE.md §14). Ce module s'importe sans erreur même si elle est
absente : :data:`DISPONIBLE` vaut alors ``False`` et :func:`exiger_disponible`
lève :class:`SolveurExactIndisponible` avec un message d'installation. Tous
les tests/scripts qui en dépendent se sautent proprement (comme les tests
Playwright, voir ``tests/test_solveur_exact.py``).

Correspondance des couleurs
----------------------------
L'énumération ``Colour`` de la bibliothèque, limitée aux 4 premières couleurs,
est ``BLACK, BLUE, ORANGE, RED``. Elle correspond à nos couleurs ainsi :

    noir -> BLACK   bleu -> BLUE   jaune -> ORANGE   rouge -> RED

La bibliothèque code chaque tuile par un entier ``couleur_index * 13 + valeur``
(``couleur_index`` : noir=0, bleu=1, jaune=2, rouge=3 ; valeur 1..13) et le
joker par l'entier ``53`` (``13 * 4 + 1``) — même convention que son
``RuleSet`` standard (13 numéros, 2 exemplaires, 4 couleurs, 2 jokers,
longueur minimale 3, mise initiale 30), identique à notre jeu.

Remise dans l'ordre (cœur de l'adaptateur)
------------------------------------------
La bibliothèque renvoie des ensembles NON ORDONNÉS : un joker peut y figurer à
une position qui ne correspond pas à sa valeur dans une suite (voir le rapport
de clôture #204). :func:`_ordonner_combinaison` reconstruit donc, pour chaque
ensemble :
  - un GROUPE (toutes les tuiles réelles de même valeur) : l'ordre est
    indifférent pour ``valider_groupe`` ;
  - une SUITE (tuiles réelles de valeurs distinctes, même couleur) : les
    tuiles réelles sont triées par valeur, un joker est inséré dans CHAQUE
    trou, et les jokers restants sont placés aux extrémités (en haut si la
    place le permet, sinon en bas) — exactement l'ordre qu'attend
    ``valider_suite``.

Caveat documenté (mode « mise initiale »)
-----------------------------------------
En mode INITIAL (mise initiale pas encore faite), la bibliothèque place
d'abord un meld d'ouverture depuis la seule main, PUIS réarrange table + main
pour poser davantage — ce second temps touche le plateau, ce que les règles du
jeu interdisent avant la mise initiale. Le maximum exact renvoyé pour un cas
« avant mise » est donc un plafond théorique, pas forcément jouable tel quel ;
quasi tous les cas de référence sont « après mise » (mise faite), où ce caveat
ne s'applique pas. Signalé dans le résultat (``mise_faite``).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

# L'import de la bibliothèque est optionnel : ce module reste importable même
# absente (DISPONIBLE=False), pour que scripts et tests se sautent proprement.
try:
    from rummikub_solver import RuleSet, SolverMode, MILPSolver  # type: ignore
    DISPONIBLE = True
    _ERREUR_IMPORT = None
except Exception as _exc:  # pragma: no cover - dépend de l'environnement
    RuleSet = SolverMode = MILPSolver = None  # type: ignore
    DISPONIBLE = False
    _ERREUR_IMPORT = _exc

from rummikub.config import VALEUR_MAX
from rummikub.moteur.tuiles import Tuile, tuile_depuis_dict
from rummikub.moteur.partie import plateau_depuis_dict, _plateau_vers_dict
from rummikub.moteur.validation import valider_combinaison


MESSAGE_INSTALLATION = (
    "La bibliothèque « rummikub-solver » (solveur exact, licence MIT) est "
    "absente. C'est une dépendance de DÉVELOPPEMENT seulement — elle n'est ni "
    "dans requirements.txt ni dans le build Windows. Pour l'installer dans un "
    "environnement de développement (Python 3.11+) :\n"
    "    python -m venv .venv-solveur-exact\n"
    "    .venv-solveur-exact/bin/pip install 'rummikub-solver[highs]'\n"
    "puis lancer les scripts/tests avec ce Python. Voir CONTEXTE.md §14."
)


class SolveurExactIndisponible(ImportError):
    """Levée par :func:`exiger_disponible` quand la bibliothèque est absente."""


def exiger_disponible() -> None:
    """Lève :class:`SolveurExactIndisponible` (message d'installation) si la
    bibliothèque n'est pas importable — à appeler avant toute résolution."""
    if not DISPONIBLE:
        raise SolveurExactIndisponible(MESSAGE_INSTALLATION) from _ERREUR_IMPORT


# --------------------------------------------------------------------------- #
# Correspondance tuiles <-> entiers de la bibliothèque
# --------------------------------------------------------------------------- #

_COULEUR_VERS_IDX = {"noir": 0, "bleu": 1, "jaune": 2, "rouge": 3}
_IDX_VERS_COULEUR = {i: c for c, i in _COULEUR_VERS_IDX.items()}
_INT_JOKER = 13 * 4 + 1  # 53, identique au RuleSet standard de la bibliothèque


def tuile_vers_int(t: Tuile) -> int:
    """Entier de la bibliothèque pour une de nos tuiles."""
    if t.est_joker:
        return _INT_JOKER
    return _COULEUR_VERS_IDX[t.couleur] * 13 + t.valeur


def int_vers_aspect(valeur_int: int):
    """``('joker', None, None)`` ou ``('reel', couleur, valeur)`` depuis un
    entier de la bibliothèque."""
    if valeur_int == _INT_JOKER:
        return ("joker", None, None)
    idx = (valeur_int - 1) // 13
    val = (valeur_int - 1) % 13 + 1
    return ("reel", _IDX_VERS_COULEUR[idx], val)


# --------------------------------------------------------------------------- #
# Remise dans l'ordre d'un ensemble renvoyé par la bibliothèque
# --------------------------------------------------------------------------- #

def _ordonner_combinaison(aspects: list) -> tuple[list, str]:
    """Remet un ensemble (liste d'aspects, voir :func:`int_vers_aspect`) dans
    un ordre valide pour ``valider_combinaison``. Retourne
    ``(aspects_ordonnes, type)`` où ``type`` vaut ``"groupe"`` ou ``"suite"``.
    """
    reels = [(c, v) for (nature, c, v) in aspects if nature == "reel"]
    njok = sum(1 for (nature, _, _) in aspects if nature == "joker")
    valeurs = {v for (_, v) in reels}

    # Groupe : au moins deux tuiles réelles de MÊME valeur (couleurs
    # distinctes). L'ordre est indifférent pour valider_groupe.
    if len(reels) >= 2 and len(valeurs) == 1:
        ordonnes = [("reel", c, v) for (c, v) in reels] + [("joker", None, None)] * njok
        return ordonnes, "groupe"

    # Suite : tuiles réelles de valeurs distinctes, même couleur. Trie par
    # valeur, comble chaque trou par un joker, place le reste aux extrémités.
    reels_tries = sorted(reels, key=lambda cv: cv[1])
    seq: list = []
    jok_restants = njok
    for i, (c, v) in enumerate(reels_tries):
        seq.append(("reel", c, v))
        if i < len(reels_tries) - 1:
            trou = reels_tries[i + 1][1] - v - 1
            for _ in range(trou):
                seq.append(("joker", None, None))
                jok_restants -= 1
    vmax = reels_tries[-1][1] if reels_tries else VALEUR_MAX
    ajout_haut = min(max(0, jok_restants), VALEUR_MAX - vmax)
    seq = seq + [("joker", None, None)] * ajout_haut
    jok_restants -= ajout_haut
    seq = [("joker", None, None)] * max(0, jok_restants) + seq
    return seq, "suite"


# --------------------------------------------------------------------------- #
# Reconstruction des tuiles physiques (ids réels, conservation du plateau)
# --------------------------------------------------------------------------- #

def _reconstruire(plateau: list, chevalet: list, combos_aspects: list):
    """Rattache à chaque aspect une TUILE physique réelle (son ``id``), en
    puisant d'abord dans le plateau puis dans le chevalet — même principe que
    ``moteur/solveur._reconstruire``. Retourne ``(nouveau_plateau, ids_main,
    reste)`` où ``reste`` (tuiles non consommées) sert au contrôle de
    conservation."""
    pools: dict = {}
    jok_plateau, jok_main = deque(), deque()

    def ranger(t: Tuile, depuis_plateau: bool):
        if t.est_joker:
            (jok_plateau if depuis_plateau else jok_main).append(t)
            return
        p, m = pools.setdefault((t.couleur, t.valeur), ([], []))
        (p if depuis_plateau else m).append(t)

    for combo in plateau:
        for t in combo:
            ranger(t, True)
    for t in chevalet:
        ranger(t, False)

    ids_main: list = []
    _jok_compteur = [0]

    def _joker_synthetique():
        _jok_compteur[0] += 1
        return Tuile(f"joker_manquant_{_jok_compteur[0]}", None, "noir", est_joker=True)

    nouveau_plateau: list = []
    for aspects in combos_aspects:
        combo_tuiles: list = []
        for (nature, c, v) in aspects:
            if nature == "reel":
                p, m = pools.get((c, v), ([], []))
                if p:
                    t = p.pop()
                elif m:
                    t = m.pop()
                    ids_main.append(t.id)
                else:
                    # Ne devrait jamais arriver (la bibliothèque conserve les
                    # tuiles) ; tuile synthétique pour ne pas masquer l'anomalie.
                    t = Tuile(f"manquante_{c}_{v}", v, c)
                combo_tuiles.append(t)
            else:
                if jok_plateau:
                    t = jok_plateau.pop()
                elif jok_main:
                    t = jok_main.pop()
                    ids_main.append(t.id)
                else:
                    t = _joker_synthetique()
                combo_tuiles.append(t)
        nouveau_plateau.append(combo_tuiles)

    reste_reel = [t for (p, _m) in pools.values() for t in p]
    reste = {"tuiles_plateau_non_utilisees": reste_reel,
             "jokers_plateau_non_utilises": list(jok_plateau)}
    return nouveau_plateau, ids_main, reste


# --------------------------------------------------------------------------- #
# Résultat et résolution
# --------------------------------------------------------------------------- #

@dataclass
class ResultatExact:
    """Résultat d'une résolution exacte, reconstruit dans notre domaine."""
    nb_tuiles: int                       # tuiles de la main effectivement posées
    duree: float                         # durée du calcul (s)
    ids_tuiles: list = field(default_factory=list)      # ids des tuiles posées
    combinaisons: list = field(default_factory=list)    # [[Tuile ordonnées], ...]
    nouveau_plateau: list = field(default_factory=list)  # [[dict], ...]
    free_jokers: int = 0                 # jokers libres (voir ProposedSolution)
    mise_faite: bool = True              # cf. caveat mode INITIAL
    toutes_valides: bool = True          # toutes les combos passent valider_combinaison
    combos_invalides: list = field(default_factory=list)  # (index, raison)
    conservation_ok: bool = True         # aucune tuile du plateau perdue
    backend: str = "HIGHS"

    @property
    def valide_globalement(self) -> bool:
        return self.toutes_valides and self.conservation_ok


def _backend_defaut():
    """Backend exact préféré : HiGHS si installé (extra ``highs``), sinon
    SCIPY (également bâti sur HiGHS, toujours présent avec cvxpy)."""
    supportes = MILPSolver.supported()
    if MILPSolver.HIGHS in supportes:
        return MILPSolver.HIGHS
    if MILPSolver.SCIPY in supportes:
        return MILPSolver.SCIPY
    return next(iter(supportes), None)


def resoudre_exact(etat: dict, idx: int, backend=None) -> ResultatExact:
    """Résout l'état ``etat`` (même format que ``moteur/solveur.resoudre_coup``)
    pour le joueur ``idx`` avec le solveur EXACT, et renvoie un
    :class:`ResultatExact` entièrement reconstruit dans notre domaine, avec les
    deux contrôles indépendants (validation + conservation) déjà effectués.

    Lève :class:`SolveurExactIndisponible` si la bibliothèque est absente.
    """
    exiger_disponible()

    joueur = etat["joueurs"][idx]
    mise_faite = bool(joueur.get("mise_initiale_faite", True))
    plateau = plateau_depuis_dict(etat.get("plateau", []))
    chevalet = [tuile_depuis_dict(d) if isinstance(d, dict) else d
                for d in joueur["chevalet"]]
    mise_min = etat.get("config", {}).get("mise_initiale_min", 30)

    if backend is None:
        backend = _backend_defaut()

    ruleset = RuleSet(numbers=13, repeats=2, colours=4, jokers=2, min_len=3,
                      min_initial_value=mise_min, solver_backend=backend)
    state = ruleset.new_game()
    state.add_table(*[tuile_vers_int(t) for combo in plateau for t in combo])
    state.add_rack(*[tuile_vers_int(t) for t in chevalet])
    state.initial = not mise_faite

    mode = SolverMode.INITIAL if not mise_faite else SolverMode.TILE_COUNT

    debut = time.monotonic()
    proposition = ruleset.solve(state, mode=mode)
    duree = time.monotonic() - debut

    backend_nom = getattr(backend, "value", str(backend))
    if proposition is None or not proposition.tiles:
        return ResultatExact(nb_tuiles=0, duree=duree, mise_faite=mise_faite,
                             backend=backend_nom)

    combos_aspects = []
    for ensemble in proposition.sets:
        aspects = [int_vers_aspect(int(t)) for t in ensemble]
        ordonnes, _type = _ordonner_combinaison(aspects)
        combos_aspects.append(ordonnes)

    nouveau_plateau, ids_main, reste = _reconstruire(plateau, chevalet, combos_aspects)

    # Contrôle 1 : chaque combinaison est valide selon notre propre validateur.
    toutes_valides = True
    combos_invalides = []
    for i, combo in enumerate(nouveau_plateau):
        r = valider_combinaison(combo)
        if not r["valide"]:
            toutes_valides = False
            combos_invalides.append((i, r["raison"]))

    # Contrôle 2 : aucune tuile RÉELLE du plateau n'a été perdue (les jokers
    # restants sont les free_jokers annoncés par la bibliothèque).
    conservation_ok = not reste["tuiles_plateau_non_utilisees"]

    return ResultatExact(
        nb_tuiles=len(proposition.tiles),
        duree=duree,
        ids_tuiles=ids_main,
        combinaisons=nouveau_plateau,
        nouveau_plateau=_plateau_vers_dict(nouveau_plateau),
        free_jokers=proposition.free_jokers,
        mise_faite=mise_faite,
        toutes_valides=toutes_valides,
        combos_invalides=combos_invalides,
        conservation_ok=conservation_ok,
        backend=backend_nom,
    )


def resoudre_coup_exact(etat: dict, idx: int, budget_temps=None, backend=None):
    """Version « drop-in » à la signature de ``moteur/solveur.resoudre_coup``,
    pour servir de JUGE exact à ``scripts/analyser_coups_rates.py --juge-exact``.
    ``budget_temps`` est accepté et IGNORÉ (le solveur exact n'a pas de budget :
    il trouve l'optimum). Retourne ``{"action", "ids_tuiles", "nouveau_plateau"}``
    ou ``None`` si aucune tuile n'est posable (ou mise initiale non atteignable).
    """
    resultat = resoudre_exact(etat, idx, backend=backend)
    if resultat.nb_tuiles == 0 or not resultat.ids_tuiles:
        return None
    return {"action": "jouer", "ids_tuiles": resultat.ids_tuiles,
            "nouveau_plateau": resultat.nouveau_plateau}
