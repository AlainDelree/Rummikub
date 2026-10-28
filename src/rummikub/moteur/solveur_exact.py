"""Modèle exact maison du coup d'un tour — niveau Expert (issue #206, suite #204).

Remplace la recherche arborescente de ``moteur/solveur.py`` (conservée comme
repli, voir ``ia.jouer_niveau_expert``) par une **programmation linéaire en
nombres entiers** (den Hertog & Hulshof, *The Computer Journal*, 2006) résolue
par **HiGHS** (``highspy``, licence MIT) avec ``numpy`` seul — **sans** ``cvxpy``
ni ``scipy`` (voir le rapport de #204 : « voie (b) », ~3× plus léger que la
bibliothèque complète). Aucun des niveaux inférieurs ne change.

Modèle
------
Le plateau et la main forment un seul « sac ». On cherche quelles
**combinaisons** (ensembles valides : suites ≥3 d'une couleur, groupes de 3–4
couleurs distinctes, jokers en remplacement) former pour que **toutes** les
tuiles du plateau restent posées, en posant **le plus grand nombre possible**
de tuiles de la main.

On raisonne sur des « emplacements » ``(couleur, valeur)`` et le joker, jamais
sur les tuiles physiques (comme ``solveur.py``) : il existe au plus 2 tuiles
réelles par emplacement (deux jeux) et 2 jokers. Pour chaque **ensemble valide
possible** ``s`` (énumérés une fois pour toutes, indépendamment de l'état —
:data:`_SETS`), une variable entière ``x_s ∈ {0,1,2}`` compte combien de copies
en placer. Pour chaque type de tuile ``i`` (52 réels + joker), soit ``t_i`` le
nombre présent sur le plateau et ``r_i`` le nombre en main :

    t_i ≤ Σ_s a_{s,i} · x_s ≤ t_i + r_i          (contrainte de conservation)

La borne basse ``t_i`` force **toutes** les tuiles du plateau à rester dans une
combinaison ; la borne haute ``t_i + r_i`` interdit d'utiliser plus de tuiles
qu'on n'en a. Le nombre de tuiles de la main posées pour le type ``i`` vaut
``Σ_s a_{s,i} x_s − t_i`` ; aucune variable supplémentaire n'est donc nécessaire
— tous les objectifs ci-dessous sont linéaires en les seules ``x_s``.

Critères de départage (lexicographiques, résolus par passes successives — le
nombre de tuiles posées reste TOUJOURS le premier critère) :

1. **tuiles posées** : max ``Σ_s taille_s · x_s`` (≡ max tuiles de la main
   posées, à nombre de tuiles du plateau constant) ;
2. **simplicité / perturbation minimale** (#199) : min des tuiles du plateau
   déplacées, puis des combinaisons modifiées — voir ``cover`` ci-dessous ;
3. **points posés** : max ``Σ_s points_réels_s · x_s`` ;
4. **économie de jokers** : min ``Σ_s jokers_s · x_s`` (ne pas poser un joker
   de la main si une solution équivalente s'en passe).

Chaque passe fixe par une contrainte d'égalité l'optimum (entier, donc exact)
de la passe précédente, puis optimise le critère suivant : optimisation
lexicographique exacte, sans coefficients géants (qui, avec la tolérance de gap
du MIP, risqueraient de perdre un critère secondaire).

Perturbation (variables ``cover``)
----------------------------------
Pour chaque combinaison **flexible** ``o`` déjà posée avant ce tour, une binaire
``cover_o`` vaut 1 si les tuiles de ``o`` restent groupées dans un même ensemble
placé (``o`` reconduite telle quelle, ou étendue par des tuiles de la main) :

    cover_o ≤ Σ_{s ⊇ o} x_s                       (o couverte ⇒ un sur-ensemble placé)
    Σ_{o ⊆ s} cover_o ≤ x_s                        (une copie de s couvre ≤ 1 original)

Les ``cover_o`` n'entrent dans aucune contrainte de conservation : elles ne
peuvent donc pas réduire le nombre de tuiles posées (critère 1), seulement
servir de départage. ``déplacées = TT − Σ taille_o·cover_o`` (TT = total des
tuiles du plateau) ; la passe 2 maximise ``Σ (K·taille_o + 1)·cover_o`` (K grand
devant le nombre d'originaux), ce qui minimise d'abord les tuiles déplacées,
puis le nombre de combinaisons perturbées. Le cas de David tour 31
(``cas_expert_coup_simple_david_tour31.json``) est ainsi joué en un seul geste
(extension directe d'un groupe plutôt que fragmentation). Approximation
documentée : la couverture d'un original par un sur-ensemble est une borne
optimiste (l'acheminement exact des tuiles physiques est un problème de flot) —
suffisant pour un départage, jamais pour fausser le critère 1.

Mise initiale
-------------
Tant que la mise initiale n'est pas faite, le plateau ne peut pas être modifié :
seules des combinaisons faites avec ses propres tuiles sont autorisées, et leur
total de points doit atteindre le minimum du réglage. Le modèle gèle alors tout
le plateau (reconduit à l'identique, hors du modèle), ne forme des ensembles
qu'à partir de la main (``t_i = 0``), et ajoute la contrainte
``Σ_s points_s · x_s ≥ mise_min`` (points de position, joker compris). Un test
le vérifie (``tests/test_solveur_exact_maison.py``).

Vérifications
-------------
Toute combinaison renvoyée est remise dans l'ordre (suites ordonnées, jokers aux
bons endroits, comme l'adaptateur de #204) **puis revalidée par
``valider_combinaison``** ; la conservation des tuiles du plateau est contrôlée.
Un résultat qui échouerait à l'un des deux contrôles n'est jamais renvoyé comme
coup (``resoudre_coup_exact`` renvoie ``None`` → repli).

Reproductibilité & budget
-------------------------
HiGHS est configuré ``threads=1``, ``random_seed=0``, sortie muette, avec une
limite de temps ferme (budget de production d'Expert, 1,5 s par défaut). Les
résultats sont reproductibles.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from itertools import combinations

# L'import de highspy/numpy est OPTIONNEL : ce module reste importable même en
# leur absence (DISPONIBLE=False), pour que ``jouer_niveau_expert`` se replie
# proprement sur ``solveur.py`` sans jamais lever (voir ia.py).
try:
    import highspy  # type: ignore
    import numpy as np  # type: ignore
    DISPONIBLE = True
    _ERREUR_IMPORT = None
except Exception as _exc:  # pragma: no cover - dépend de l'environnement
    highspy = None  # type: ignore
    np = None  # type: ignore
    DISPONIBLE = False
    _ERREUR_IMPORT = _exc

from rummikub.config import COULEURS, VALEUR_MIN, VALEUR_MAX, NB_JOKERS, \
    MISE_INITIALE_MIN
from rummikub.moteur.tuiles import Tuile, tuile_depuis_dict
from rummikub.moteur.partie import plateau_depuis_dict, _plateau_vers_dict
from rummikub.moteur.validation import valider_combinaison


MESSAGE_INSTALLATION = (
    "Le solveur exact d'Expert a besoin de « highspy » (solveur HiGHS, licence "
    "MIT) et « numpy » (licence BSD). Installez-les :\n"
    "    pip install highspy numpy\n"
    "Ils figurent dans requirements.txt. En leur absence, Expert se replie "
    "automatiquement sur sa recherche arborescente (moteur/solveur.py)."
)


class SolveurExactIndisponible(ImportError):
    """Levée par :func:`exiger_disponible` si ``highspy`` ou ``numpy`` manque."""


class BudgetExactDepasse(Exception):
    """Levée quand la limite de temps est épuisée sans solution exploitable
    (budget nul, ou plateau trop lourd pour le temps alloué) — l'appelant se
    replie alors sur un autre niveau pour ce tour (voir ``ia.py``)."""


def exiger_disponible() -> None:
    if not DISPONIBLE:
        raise SolveurExactIndisponible(MESSAGE_INSTALLATION) from _ERREUR_IMPORT


# --------------------------------------------------------------------------- #
# Indexation des types de tuile (52 réels + joker)
# --------------------------------------------------------------------------- #

_COULEUR_IDX = {c: i for i, c in enumerate(COULEURS)}
_NV = VALEUR_MAX - VALEUR_MIN + 1
_NC = len(COULEURS)
_TYPE_JOKER = _NC * _NV           # dernier index : le joker
_NTYPES = _TYPE_JOKER + 1


def _type_idx(couleur: str, valeur: int) -> int:
    return _COULEUR_IDX[couleur] * _NV + (valeur - VALEUR_MIN)


def _aspect_token(tok) -> object:
    """Apparence d'un token pour la mesure de perturbation : ``"joker"`` ou
    ``(couleur, valeur)`` — même convention que ``solveur._multisets_originaux``."""
    return "joker" if tok[0] == "J" else (tok[1], tok[2])


# --------------------------------------------------------------------------- #
# Énumération, une fois pour toutes, de tous les ensembles valides possibles
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class _Ensemble:
    """Un ensemble valide possible (suite ou groupe), indépendant de l'état."""
    tokens: tuple                 # tokens ordonnés : ("T", couleur, valeur) | ("J",)
    counts: tuple                 # ((type_idx, compte), ...) trié — colonne ILP
    njok: int                     # nombre de jokers
    taille: int                   # nombre de tuiles
    preal: int                    # somme des valeurs des tuiles RÉELLES
    pfull: int                    # somme des valeurs de position (joker compris)
    aspects: frozenset            # multiset d'aspects {(aspect, compte)} (perturbation)


def _counts_depuis_tokens(tokens):
    comptes = {}
    njok = 0
    preal = 0
    pfull = 0
    aspects = {}
    for i, tok in enumerate(tokens):
        if tok[0] == "J":
            njok += 1
            comptes[_TYPE_JOKER] = comptes.get(_TYPE_JOKER, 0) + 1
            aspects["joker"] = aspects.get("joker", 0) + 1
        else:
            _, c, v = tok
            comptes[_type_idx(c, v)] = comptes.get(_type_idx(c, v), 0) + 1
            preal += v
            aspects[(c, v)] = aspects.get((c, v), 0) + 1
    return comptes, njok, preal, aspects


def _pfull_tokens(tokens):
    """Somme des valeurs de position (le joker prend la valeur de sa place) :
    valeurs consécutives pour une suite, valeur commune pour un groupe. Déduit
    la base depuis la première tuile réelle et sa position."""
    reels = [(i, tok) for i, tok in enumerate(tokens) if tok[0] == "T"]
    i0, t0 = reels[0]
    base = t0[2] - i0
    # Suite : toutes les positions réelles valident base + i == valeur.
    if all(tok[2] == base + i for i, tok in reels):
        return sum(base + i for i in range(len(tokens)))
    # Sinon groupe : toutes les positions à la valeur commune.
    return t0[2] * len(tokens)


def _enumerer_groupes():
    ensembles = []
    for v in range(VALEUR_MIN, VALEUR_MAX + 1):
        for taille in (3, 4):
            for njok in (0, 1):  # un groupe accepte au plus 1 joker (validation)
                nb_reel = taille - njok
                if nb_reel < 2 or nb_reel > _NC:
                    continue
                for couleurs in combinations(COULEURS, nb_reel):
                    tokens = tuple(("T", c, v) for c in couleurs) \
                        + tuple(("J",) for _ in range(njok))
                    ensembles.append(tokens)
    return ensembles


def _patrons_jokers(longueur):
    """Positions de jokers possibles dans une suite de ``longueur`` : 0, 1 ou 2
    jokers, jamais deux adjacents, jamais tous jokers (validation)."""
    patrons = [frozenset()]
    for p in range(longueur):
        patrons.append(frozenset({p}))
    for a, b in combinations(range(longueur), 2):
        if b - a >= 2:  # non adjacents
            patrons.append(frozenset({a, b}))
    # Pas de patron « tout joker » possible avec ≤2 jokers et longueur ≥3.
    return patrons


# Longueur maximale des suites énumérées : ``2·min_len − 1 = 5`` (min_len = 3).
# Une suite plus longue est TOUJOURS partitionnable en suites de longueur 3 à
# 5 (6=3+3, 7=3+4, 8=4+4, …) : la contrainte de conservation force alors le
# modèle à la recomposer en plusieurs ensembles courts, sans jamais perdre une
# tuile du plateau ni un placement optimal. Même borne que la bibliothèque
# ``rummikub-solver`` (``_runs`` : lengths ``min_len`` à ``2·min_len``
# exclus) — c'est elle qui rend le modèle petit (≈750 ensembles) et donc
# rapide (voir le rapport de #206). Vérifié par la comparaison exhaustive
# indépendante (``verif_solveur``) et par les cas de référence.
_MIN_LEN_SUITE = 3
_MAX_LEN_SUITE = 2 * _MIN_LEN_SUITE - 1


def _enumerer_suites():
    ensembles = []
    for c in COULEURS:
        for v1 in range(VALEUR_MIN, VALEUR_MAX + 1):
            v2_max = min(VALEUR_MAX, v1 + _MAX_LEN_SUITE - 1)
            for v2 in range(v1 + 2, v2_max + 1):  # longueur 3 à 5
                longueur = v2 - v1 + 1
                for jokers in _patrons_jokers(longueur):
                    if len(jokers) > NB_JOKERS:
                        continue
                    if len(jokers) == longueur:
                        continue  # au moins une tuile réelle
                    tokens = tuple(
                        ("J",) if (i in jokers) else ("T", c, v1 + i)
                        for i in range(longueur))
                    ensembles.append(tokens)
    return ensembles


def _construire_sets():
    sets = []
    for tokens in _enumerer_groupes() + _enumerer_suites():
        comptes, njok, preal, aspects = _counts_depuis_tokens(tokens)
        pfull = _pfull_tokens(tokens)
        sets.append(_Ensemble(
            tokens=tokens,
            counts=tuple(sorted(comptes.items())),
            njok=njok,
            taille=len(tokens),
            preal=preal,
            pfull=pfull,
            aspects=frozenset(aspects.items()),
        ))
    return sets


# Énumérés une seule fois (indépendants de l'état). ~quelques milliers.
_SETS = _construire_sets()


# --------------------------------------------------------------------------- #
# Reconstruction des tuiles physiques (ids réels, conservation du plateau)
# --------------------------------------------------------------------------- #

def _reconstruire(plateau_pool, chevalet, combos_tokens):
    """Rattache à chaque token une TUILE physique réelle (son ``id``), en
    puisant d'abord dans ``plateau_pool`` (tuiles du plateau) puis dans
    ``chevalet`` — même principe que ``solveur._reconstruire``. Retourne
    ``(combos_tuiles, ids_main, reste_plateau)``."""
    pools = {}
    jok_plateau, jok_main = deque(), deque()

    def ranger(t, depuis_plateau):
        if t.est_joker:
            (jok_plateau if depuis_plateau else jok_main).append(t)
            return
        p, m = pools.setdefault((t.couleur, t.valeur), ([], []))
        (p if depuis_plateau else m).append(t)

    for combo in plateau_pool:
        for t in combo:
            ranger(t, True)
    for t in chevalet:
        ranger(t, False)

    ids_main = []
    _jok_compteur = [0]

    def _joker_synthetique():
        _jok_compteur[0] += 1
        return Tuile(f"joker_manquant_{_jok_compteur[0]}", None, "noir", est_joker=True)

    combos_tuiles = []
    for tokens in combos_tokens:
        combo = []
        for tok in tokens:
            if tok[0] == "T":
                _, c, v = tok
                p, m = pools.get((c, v), ([], []))
                if p:
                    t = p.pop()
                elif m:
                    t = m.pop()
                    ids_main.append(t.id)
                else:  # ne devrait jamais arriver (conservation garantie)
                    t = Tuile(f"manquante_{c}_{v}", v, c)
                combo.append(t)
            else:
                if jok_plateau:
                    t = jok_plateau.pop()
                elif jok_main:
                    t = jok_main.pop()
                    ids_main.append(t.id)
                else:
                    t = _joker_synthetique()
                combo.append(t)
        combos_tuiles.append(combo)

    reste_reel = [t for (p, _m) in pools.values() for t in p]
    return combos_tuiles, ids_main, reste_reel


# --------------------------------------------------------------------------- #
# Résultat
# --------------------------------------------------------------------------- #

@dataclass
class ResultatExact:
    """Résultat d'une résolution exacte, reconstruit dans notre domaine."""
    nb_tuiles: int                       # tuiles de la main effectivement posées
    duree: float                         # durée du calcul (s)
    ids_tuiles: list = field(default_factory=list)
    combinaisons: list = field(default_factory=list)    # [[Tuile ordonnées], ...]
    nouveau_plateau: list = field(default_factory=list)  # [[dict], ...]
    points: int = 0
    jokers_main: int = 0
    perturbation: tuple = (0, 0)         # (tuiles déplacées, combos modifiées)
    mise_faite: bool = True
    toutes_valides: bool = True
    combos_invalides: list = field(default_factory=list)
    conservation_ok: bool = True
    optimal: bool = True                 # optimum prouvé (sinon : limite de temps)
    backend: str = "HIGHS"

    @property
    def valide_globalement(self) -> bool:
        return self.toutes_valides and self.conservation_ok


# --------------------------------------------------------------------------- #
# Construction et résolution du modèle ILP
# --------------------------------------------------------------------------- #

def _comptes_etat(tuiles):
    """``{type_idx: compte}`` pour une liste de Tuile."""
    comptes = {}
    for t in tuiles:
        idx = _TYPE_JOKER if t.est_joker else _type_idx(t.couleur, t.valeur)
        comptes[idx] = comptes.get(idx, 0) + 1
    return comptes


def _ensemble_couvre(s: _Ensemble, aspects_o: dict) -> bool:
    """Vrai si l'ensemble ``s`` contient (comme multiset d'aspects) au moins
    autant de chaque aspect que la combinaison d'origine ``aspects_o`` — ``o``
    reste alors groupée dans ``s`` (reconduite ou étendue)."""
    sa = dict(s.aspects)
    for aspect, n in aspects_o.items():
        if sa.get(aspect, 0) < n:
            return False
    return True


def _nouveau_highs(time_limit):
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    h.setOptionValue("log_to_console", False)
    h.setOptionValue("threads", 1)
    h.setOptionValue("parallel", "off")
    h.setOptionValue("random_seed", 0)
    h.setOptionValue("presolve", "on")
    h.setOptionValue("mip_rel_gap", 0.0)
    h.setOptionValue("mip_abs_gap", 0.0)
    h.setOptionValue("time_limit", float(max(1e-3, time_limit)))
    return h


def _a_solution_primale(h) -> bool:
    try:
        info = h.getInfo()
        statut = getattr(info, "primal_solution_status", None)
        if statut is not None:
            # kSolutionStatusFeasible == 2 dans HiGHS.
            return int(statut) >= 2
    except Exception:
        pass
    return h.getModelStatus() == highspy.HighsModelStatus.kOptimal


def _resoudre_modele(table_tiles, chevalet, mise_faite, mise_min,
                     flexibles_aspects, budget_temps, preferer_simple):
    """Construit et résout le modèle ILP lexicographique. Retourne
    ``(combos_tokens, optimal)`` où ``combos_tokens`` est la liste des ensembles
    placés (tokens ordonnés), ou lève :class:`BudgetExactDepasse`."""
    deadline = time.monotonic() + budget_temps

    comptes_table = _comptes_etat(table_tiles)
    comptes_main = _comptes_etat(chevalet)
    avail = {}
    for i in range(_NTYPES):
        a = comptes_table.get(i, 0) + comptes_main.get(i, 0)
        if a:
            avail[i] = a

    # Ensembles réalisables dans cet état (toutes leurs tuiles disponibles).
    faisables = []
    for s in _SETS:
        ub = 2
        ok = True
        for idx, n in s.counts:
            dispo = avail.get(idx, 0)
            if dispo < n:
                ok = False
                break
            ub = min(ub, dispo // n)
        if ok and ub > 0:
            faisables.append((s, ub))
    if not faisables:
        # Rien de posable (plateau vide et main sans combinaison) — mais s'il y
        # a des tuiles de plateau, elles doivent être reconductibles : alors au
        # moins leurs propres ensembles sont faisables, donc ce cas = main
        # seule sans combinaison possible.
        return [], True

    h = _nouveau_highs(deadline - time.monotonic())

    # Variables x_s (une par ensemble faisable), entières 0..ub.
    for _s, ub in faisables:
        h.addVariable(lb=0, ub=float(ub),
                      type=highspy.HighsVarType.kInteger, obj=0.0)
    n_x = len(faisables)

    # Contraintes de conservation : t_i ≤ Σ a_{s,i} x_s ≤ t_i + r_i.
    par_type = {}
    for j, (s, _ub) in enumerate(faisables):
        for idx, n in s.counts:
            par_type.setdefault(idx, []).append((j, n))
    for idx, termes in par_type.items():
        t_i = comptes_table.get(idx, 0)
        r_i = comptes_main.get(idx, 0)
        indices = np.array([j for j, _n in termes], dtype=np.int32)
        valeurs = np.array([float(n) for _j, n in termes], dtype=np.float64)
        h.addRow(float(t_i), float(t_i + r_i), len(termes), indices, valeurs)

    # Contrainte de mise initiale : Σ points_s x_s ≥ mise_min (points de
    # position, joker compris) — tous les ensembles sont faits de la main.
    if not mise_faite:
        indices = np.arange(n_x, dtype=np.int32)
        valeurs = np.array([float(s.pfull) for s, _ub in faisables],
                           dtype=np.float64)
        h.addRow(float(mise_min), highspy.kHighsInf, n_x, indices, valeurs)

    def _poser_objectif(couts, sens):
        n_cols = h.getNumCol()
        c = np.zeros(n_cols, dtype=np.float64)
        for idx, val in couts:
            c[idx] = val
        h.changeColsCost(n_cols, np.arange(n_cols, dtype=np.int32), c)
        h.changeObjectiveSense(sens)

    def _solve():
        """Retourne ``"optimal"`` / ``"faisable"`` (solution exploitable mais
        pas prouvée optimale, p. ex. limite de temps atteinte) /
        ``"infaisable"`` (prouvé sans solution — p. ex. mise initiale
        inatteignable) / ``"timeout"`` (budget épuisé sans solution)."""
        reste = deadline - time.monotonic()
        if reste <= 0:
            return "timeout"
        h.setOptionValue("time_limit", float(max(1e-3, reste)))
        h.run()
        st = h.getModelStatus()
        if st == highspy.HighsModelStatus.kOptimal:
            return "optimal"
        if _a_solution_primale(h):
            return "faisable"
        if st == highspy.HighsModelStatus.kInfeasible:
            return "infaisable"
        return "timeout"

    def _valeurs():
        return list(h.getSolution().col_value)

    def _warm(valeurs):
        """Fournit la solution précédente comme point de départ MIP (les
        nouvelles colonnes éventuelles sont complétées par 0). Accélère parfois
        la preuve d'optimalité des passes de départage."""
        try:
            sol = highspy.HighsSolution()
            n = h.getNumCol()
            v = list(valeurs) + [0.0] * (n - len(valeurs))
            sol.col_value = v[:n]
            h.setSolution(sol)
        except Exception:
            pass

    def _fixer(couts, valeur):
        """Fige Σ couts·vars = valeur (égalité) pour la passe suivante."""
        indices = np.array([idx for idx, _v in couts], dtype=np.int32)
        valeurs = np.array([float(v) for _idx, v in couts], dtype=np.float64)
        h.addRow(float(valeur), float(valeur), len(couts), indices, valeurs)

    def _ajouter_cover():
        """Ajoute les variables d'AFFECTATION de perturbation APRÈS la passe 1
        (pour ne pas alourdir le MIP du critère primaire).

        Pour chaque original flexible ``o`` et chaque ensemble ``s ⊇ o``, une
        variable ``m_{o,s} ∈ [0, 1]`` (continue : la structure est totalement
        unimodulaire, donc l'optimum est entier à ``x`` fixé) vaut 1 si les
        tuiles de ``o`` restent groupées dans une copie de ``s`` :

            Σ_s m_{o,s} ≤ 1                 (o affecté à au plus un ensemble)
            Σ_{o⊆s} m_{o,s} ≤ x_s           (une copie de s héberge ≤ 1 original)

        Retourne ``couts_pert = [(var_m, K·taille_o + 1), ...]`` : la passe 2
        maximise ``Σ couts_pert`` = min des tuiles déplacées (coef ``K·taille``),
        puis des combinaisons perturbées (coef ``+1``). ``K`` domine le nombre
        d'originaux pour que la minimisation des tuiles déplacées prime."""
        couvreurs = []
        for aspects_o in flexibles_aspects:
            idxs = [j for j, (s, _ub) in enumerate(faisables)
                    if _ensemble_couvre(s, aspects_o)]
            couvreurs.append(idxs)
        n_orig = len(flexibles_aspects)
        K = n_orig + 1
        base = h.getNumCol()
        # Index de variable m pour chaque paire (o, s) retenue.
        m_index = {}          # (k, j) -> index de colonne
        couts = []            # (index, K·taille_o + 1)
        par_orig = {}         # k -> [index des m_{o,s}]
        par_set = {}          # j -> [index des m_{o,s}]
        compteur = base
        for k, idxs in enumerate(couvreurs):
            taille_o = sum(flexibles_aspects[k].values())
            for j in idxs:
                h.addVariable(lb=0.0, ub=1.0,
                              type=highspy.HighsVarType.kContinuous, obj=0.0)
                m_index[(k, j)] = compteur
                couts.append((compteur, float(K * taille_o + 1)))
                par_orig.setdefault(k, []).append(compteur)
                par_set.setdefault(j, []).append(compteur)
                compteur += 1
        # Σ_s m_{o,s} ≤ 1 pour chaque original.
        for k, vars_m in par_orig.items():
            indices = np.array(vars_m, dtype=np.int32)
            valeurs = np.ones(len(vars_m), dtype=np.float64)
            h.addRow(-highspy.kHighsInf, 1.0, len(vars_m), indices, valeurs)
        # Σ_{o⊆s} m_{o,s} − x_s ≤ 0 pour chaque ensemble couvrant ≥1 original.
        for j, vars_m in par_set.items():
            indices = np.array(vars_m + [j], dtype=np.int32)
            valeurs = np.array([1.0] * len(vars_m) + [-1.0], dtype=np.float64)
            h.addRow(-highspy.kHighsInf, 0.0, len(vars_m) + 1, indices, valeurs)
        return couts

    # ---- Passe 1 : nombre de tuiles posées (critère primaire) ----
    couts_tuiles = [(j, float(s.taille)) for j, (s, _ub) in enumerate(faisables)]
    _poser_objectif(couts_tuiles, highspy.ObjSense.kMaximize)
    etat1 = _solve()
    if etat1 == "infaisable":
        # Aucune solution valide (p. ex. mise initiale inatteignable) : ce n'est
        # PAS un dépassement de budget — aucun coup, l'appelant piochera.
        return [], True
    if etat1 == "timeout":
        raise BudgetExactDepasse(
            "Aucune solution exacte dans le budget de temps imparti.")
    meilleures_valeurs = _valeurs()
    optimal = (etat1 == "optimal")

    # Si la passe 1 n'est pas prouvée optimale (limite de temps), on garde la
    # solution réalisable trouvée et on s'arrête là (pas de départage).
    if optimal:
        opt1 = round(h.getObjectiveValue())
        _fixer(couts_tuiles, opt1)

        # ---- Passe 2 : perturbation minimale ----
        if preferer_simple and flexibles_aspects and (deadline - time.monotonic()) > 0:
            couts_pert = _ajouter_cover()
            _warm(meilleures_valeurs)
            _poser_objectif(couts_pert, highspy.ObjSense.kMaximize)
            e2 = _solve()
            if e2 == "optimal":
                meilleures_valeurs = _valeurs()
                _fixer(couts_pert, round(h.getObjectiveValue()))
            elif e2 == "faisable":
                meilleures_valeurs = _valeurs()
                optimal = False

        # ---- Passe 3 : points posés, puis économie de jokers de la main ----
        # Une seule résolution : max Σ (W·points_s − jokers_s) x_s avec
        # W = jokers+1, qui maximise d'abord les points posés (chaque point
        # vaut plus que tout l'écart possible de jokers, borné par ``jokers``),
        # puis minimise les jokers de la main. Coefficients petits + gap nul →
        # optimum lexicographique exact en un seul solve (une passe de moins).
        if optimal and (deadline - time.monotonic()) > 0:
            W = NB_JOKERS + 1
            couts_pts_jok = [(j, float(W * s.preal - s.njok))
                             for j, (s, _ub) in enumerate(faisables)
                             if s.preal or s.njok]
            if couts_pts_jok:
                _warm(meilleures_valeurs)
                _poser_objectif(couts_pts_jok, highspy.ObjSense.kMaximize)
                e3 = _solve()
                if e3 in ("optimal", "faisable"):
                    meilleures_valeurs = _valeurs()

    # Décodage : combien de copies de chaque ensemble placer.
    combos_tokens = []
    for j, (s, _ub) in enumerate(faisables):
        copies = int(round(meilleures_valeurs[j]))
        for _ in range(copies):
            combos_tokens.append(s.tokens)
    return combos_tokens, optimal


# --------------------------------------------------------------------------- #
# API publique
# --------------------------------------------------------------------------- #

BUDGET_TEMPS_DEFAUT = 1.5


def resoudre_exact(etat: dict, idx: int, budget_temps: float = BUDGET_TEMPS_DEFAUT,
                   preferer_simple: bool = True) -> ResultatExact:
    """Résout l'état ``etat`` pour le joueur ``idx`` avec le modèle exact
    (HiGHS) et renvoie un :class:`ResultatExact` reconstruit dans notre domaine,
    avec les deux contrôles indépendants (validation + conservation) effectués.

    Lève :class:`SolveurExactIndisponible` si ``highspy``/``numpy`` manque, ou
    :class:`BudgetExactDepasse` si la limite de temps est épuisée sans solution.
    """
    exiger_disponible()
    if budget_temps <= 0:
        raise BudgetExactDepasse("Budget de temps nul.")

    joueur = etat["joueurs"][idx]
    mise_faite = bool(joueur.get("mise_initiale_faite", True))
    plateau = plateau_depuis_dict(etat.get("plateau", []))
    chevalet = [tuile_depuis_dict(d) if isinstance(d, dict) else d
                for d in joueur["chevalet"]]
    mise_min = etat.get("config", {}).get("mise_initiale_min", MISE_INITIALE_MIN)

    debut = time.monotonic()
    if mise_faite:
        table_tiles = [t for combo in plateau for t in combo]
        combos_figes = []
        # Perturbation : multiset d'aspects de chaque combinaison d'origine.
        flexibles_aspects = []
        for combo in plateau:
            asp = {}
            for t in combo:
                cle = "joker" if t.est_joker else (t.couleur, t.valeur)
                asp[cle] = asp.get(cle, 0) + 1
            flexibles_aspects.append(asp)
    else:
        # Mise initiale pas faite : plateau gelé, combinaisons faites de la
        # main seule, total ≥ mise_min (règle du jeu).
        table_tiles = []
        combos_figes = plateau
        flexibles_aspects = []

    combos_tokens, optimal = _resoudre_modele(
        table_tiles, chevalet, mise_faite, mise_min, flexibles_aspects,
        budget_temps, preferer_simple)
    duree = time.monotonic() - debut

    # Reconstruction physique : pool = plateau (hors gelées) + chevalet.
    pool_plateau = [] if not mise_faite else plateau
    combos_tuiles, ids_main, reste = _reconstruire(
        pool_plateau, chevalet, combos_tokens)

    nouveau_plateau_tuiles = combos_figes + combos_tuiles

    # Contrôle 1 : chaque combinaison est valide selon notre validateur.
    toutes_valides = True
    combos_invalides = []
    for i, combo in enumerate(nouveau_plateau_tuiles):
        r = valider_combinaison(combo)
        if not r["valide"]:
            toutes_valides = False
            combos_invalides.append((i, r["raison"]))

    # Contrôle 2 : aucune tuile réelle du plateau perdue.
    conservation_ok = not reste

    # Points réellement posés et jokers de la main utilisés.
    ids_poses = set(ids_main)
    points = 0
    jokers_main = 0
    for combo in combos_tuiles:
        valeurs = _valeurs_combo(combo)
        for t in combo:
            if t.id in ids_poses:
                if t.est_joker:
                    jokers_main += 1
                else:
                    points += valeurs.get(t.id, 0)

    perturbation = _perturbation_resultat(plateau if mise_faite else [],
                                          combos_tuiles)

    return ResultatExact(
        nb_tuiles=len(ids_main),
        duree=duree,
        ids_tuiles=ids_main,
        combinaisons=nouveau_plateau_tuiles,
        nouveau_plateau=_plateau_vers_dict(nouveau_plateau_tuiles),
        points=points,
        jokers_main=jokers_main,
        perturbation=perturbation,
        mise_faite=mise_faite,
        toutes_valides=toutes_valides,
        combos_invalides=combos_invalides,
        conservation_ok=conservation_ok,
        optimal=optimal,
        backend="HIGHS",
    )


def _valeurs_combo(combo):
    """Valeur effective de chaque tuile d'une combinaison (joker = valeur de sa
    position) — pour compter les points réellement posés."""
    valider = valider_combinaison(combo)
    valeurs = {}
    reels = [(i, t) for i, t in enumerate(combo) if not t.est_joker]
    if valider["type"] == "suite" and reels:
        i0, t0 = reels[0]
        base = t0.valeur - i0
        for i, t in enumerate(combo):
            valeurs[t.id] = base + i
    elif valider["type"] == "groupe" and reels:
        v = reels[0][1].valeur
        for t in combo:
            valeurs[t.id] = v
    else:
        for t in combo:
            valeurs[t.id] = t.valeur or 0
    return valeurs


def _perturbation_resultat(plateau_avant, combos_apres):
    """Mesure de perturbation (tuiles déplacées, combos modifiées) entre le
    plateau d'avant et les combinaisons reconstruites — réutilise la mesure de
    ``solveur.mesurer_perturbation`` (même convention #199)."""
    from rummikub.moteur.solveur import mesurer_perturbation
    avant = _plateau_vers_dict(plateau_avant)
    apres = _plateau_vers_dict(combos_apres)
    return mesurer_perturbation(avant, apres)


def resoudre_coup_exact(etat: dict, idx: int, budget_temps: float = BUDGET_TEMPS_DEFAUT,
                        preferer_simple: bool = True):
    """Version « drop-in » à la signature de ``solveur.resoudre_coup`` pour le
    niveau Expert et le juge exact.

    Retourne ``{"action": "jouer", "ids_tuiles": [...], "nouveau_plateau":
    [...]}`` ou ``None`` si aucune tuile n'est posable (ou mise initiale non
    atteignable), ou si le résultat échoue à l'un des deux contrôles
    (validation/conservation) — dans tous ces cas l'appelant se replie.

    Lève :class:`SolveurExactIndisponible` (dépendances absentes) ou
    :class:`BudgetExactDepasse` (temps épuisé sans solution)."""
    resultat = resoudre_exact(etat, idx, budget_temps=budget_temps,
                              preferer_simple=preferer_simple)
    if resultat.nb_tuiles == 0 or not resultat.ids_tuiles:
        return None
    if not resultat.valide_globalement:
        return None
    return {"action": "jouer", "ids_tuiles": resultat.ids_tuiles,
            "nouveau_plateau": resultat.nouveau_plateau}
