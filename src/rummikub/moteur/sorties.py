"""Brique « Sorties » (issue #231, anciennement « tuiles vivantes ») : pour un
chevalet et un tapis donnés, calcule les « sorties » — les types de tuile
(valeur + couleur, jokers compris) qui, piochés au prochain tour, permettraient
de jouer — puis un score du chevalet, somme des probabilités de piocher
chacune de ces sorties (brique « Inconnues », #219).

Correction par rapport à l'idée initiale de « tuiles mortes » (CONTEXTE.md
§13, piste 9) : au Rummikub, les combinaisons du tapis sont réarrangeables, une
tuile posée n'est donc jamais « sortie » du jeu — seules les tuiles de la main
adverse et de la pioche me sont inconnues. La notion utile est donc inversée :
les « sorties » sont les tuiles qu'il ME reste à piocher pour pouvoir jouer.

Calcul DIRECT, sans appel au solveur exact (``solveur_exact.py``) : deux
règles énumérées à la main, jamais une résolution ILP, pour rester rapide.

1. **Règle de paire** (dans le chevalet) : pour chaque paire de tuiles RÉELLES
   du chevalet (jamais un joker — il n'a pas de couleur/valeur propres),
   même couleur à valeurs voisines (écart 1, extension d'un bout) ou espacées
   d'une (écart 2, tuile manquante au milieu), ou même valeur à couleurs
   différentes (groupe, troisième/quatrième couleur manquante) — plus le
   joker, toujours une sortie valide dès qu'un type réel l'est.
2. **Règle de rattachement** (au tapis) : pour chaque combinaison du tapis,
   tout type (réel ou joker) qui, ajouté en tête ou en queue, forme à nouveau
   une combinaison valide (``valider_combinaison`` — brute force sur les 52
   types réels + le joker, bornée par le nombre de combinaisons du tapis,
   jamais par la taille de la main).

Jamais de lecture de la main adverse : le score passe par
``inconnues.calculer_inconnues_depuis_etat``, qui ne lit que des TAILLES de
main (voir le garde-fou de ce module)."""

from __future__ import annotations

from rummikub.config import COULEURS, VALEUR_MIN, VALEUR_MAX
from rummikub.moteur import inconnues as _inconnues
from rummikub.moteur.tuiles import Tuile, tuile_depuis_dict
from rummikub.moteur.validation import valider_combinaison


def _to_tuile(t) -> Tuile:
    return t if isinstance(t, Tuile) else tuile_depuis_dict(t)


def _to_tuiles(tuiles) -> list:
    return [_to_tuile(t) for t in tuiles]


# Les 52 types réels (couleur, valeur) + le joker — énumérés une fois, réutilisés
# par ``_sorties_attachement`` pour la règle de rattachement au tapis.
_TYPES_REELS = [(c, v) for c in COULEURS for v in range(VALEUR_MIN, VALEUR_MAX + 1)]
_TOUS_LES_TYPES = _TYPES_REELS + [_inconnues.CLE_JOKER]


def _tuile_synthetique(cle: tuple) -> Tuile:
    """Tuile fictive (``id`` sans importance) représentant le TYPE ``cle`` —
    utilisée pour tester, via le validateur existant, si elle s'attache à une
    combinaison du tapis."""
    if cle == _inconnues.CLE_JOKER:
        return Tuile(id="_sortie_joker", valeur=None, couleur=None, est_joker=True)
    couleur, valeur = cle
    return Tuile(id="_sortie", valeur=valeur, couleur=couleur, est_joker=False)


def _sorties_paire(a: Tuile, b: Tuile) -> set:
    """Sorties produites par une paire de tuiles RÉELLES du chevalet (voir
    règle 1 ci-dessus)."""
    cles = set()
    if a.couleur == b.couleur and a.valeur != b.valeur:
        lo, hi = (a, b) if a.valeur < b.valeur else (b, a)
        ecart = hi.valeur - lo.valeur
        if ecart == 1:
            room = False
            if lo.valeur - 1 >= VALEUR_MIN:
                cles.add((a.couleur, lo.valeur - 1))
                room = True
            if hi.valeur + 1 <= VALEUR_MAX:
                cles.add((a.couleur, hi.valeur + 1))
                room = True
            if room:
                cles.add(_inconnues.CLE_JOKER)
        elif ecart == 2:
            cles.add((a.couleur, lo.valeur + 1))
            cles.add(_inconnues.CLE_JOKER)
    elif a.valeur == b.valeur and a.couleur != b.couleur:
        for c in COULEURS:
            if c != a.couleur and c != b.couleur:
                cles.add((c, a.valeur))
        cles.add(_inconnues.CLE_JOKER)
    return cles


def _sorties_attachement(combo) -> set:
    """Sorties produites par le rattachement à une combinaison du tapis (voir
    règle 2 ci-dessus) : brute force sur les 53 types, bornée par le nombre de
    combinaisons du tapis — jamais le solveur exact."""
    tuiles_combo = _to_tuiles(combo)
    cles = set()
    for cle in _TOUS_LES_TYPES:
        candidate = _tuile_synthetique(cle)
        if (valider_combinaison(tuiles_combo + [candidate])["valide"]
                or valider_combinaison([candidate] + tuiles_combo)["valide"]):
            cles.add(cle)
    return cles


def sorties_chevalet(chevalet, plateau) -> set:
    """Ensemble des clés de type de tuile (``(couleur, valeur)`` ou
    ``inconnues.CLE_JOKER``) qui sont des « sorties » pour ce chevalet et ce
    tapis — voir les deux règles en tête de module."""
    reels = [t for t in _to_tuiles(chevalet) if not t.est_joker]
    cles = set()
    for i in range(len(reels)):
        for j in range(i + 1, len(reels)):
            cles |= _sorties_paire(reels[i], reels[j])
    for combo in plateau or []:
        cles |= _sorties_attachement(combo)
    return cles


def _etat_hypothetique(etat: dict, idx: int, chevalet, plateau) -> dict:
    """Copie superficielle de ``etat`` avec le chevalet du joueur ``idx`` et
    le tapis remplacés — jamais le contenu des autres joueurs ni la pioche,
    pour que ``inconnues.calculer_inconnues_depuis_etat`` reste fidèle à ce
    qu'un joueur sait réellement (aucune lecture de main adverse)."""
    joueur = dict(etat["joueurs"][idx])
    joueur["chevalet"] = chevalet
    joueurs2 = list(etat["joueurs"])
    joueurs2[idx] = joueur
    etat2 = dict(etat)
    etat2["joueurs"] = joueurs2
    etat2["plateau"] = plateau
    return etat2


def score_chevalet(chevalet, plateau, etat: dict, idx: int) -> float:
    """Score d'un chevalet (#231, point 3) : somme, sur toutes les sorties
    (:func:`sorties_chevalet`), de la probabilité de piocher ce type de tuile
    au prochain tour — approchée par le nombre d'exemplaires encore inconnus
    de ce type divisé par le nombre total de tuiles inconnues (brique
    « Inconnues », #219, ``etat``/``idx`` SEULEMENT pour reconstruire cette
    brique, jamais pour lire une main adverse). Une sortie dont tous les
    exemplaires sont déjà connus (donc indisponibles) contribue 0 — elle ne
    « compte » donc pas dans la somme."""
    etat_hyp = _etat_hypothetique(etat, idx, chevalet, plateau)
    inc = _inconnues.calculer_inconnues_depuis_etat(etat_hyp, idx)
    if inc.nb_total_inconnues == 0:
        return 0.0
    cles = sorties_chevalet(chevalet, plateau)
    return sum(inc.exemplaires_restants(cle) for cle in cles) / inc.nb_total_inconnues
