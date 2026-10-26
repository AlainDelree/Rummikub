"""Vérification croisée du solveur de réarrangement global (``solveur.py``)
contre une recherche exhaustive indépendante (issue #193, point 5).

Le solveur (``moteur/solveur.py``) gèle certaines combinaisons et borne la
largeur des suites candidates pour rester praticable sur un plateau de jeu
réel (voir sa docstring) : ces simplifications ne sont PAS prouvées exactes
dans tous les cas, seulement sur les scénarios couverts par ses tests. Ce
module fournit une seconde implémentation, volontairement simple et lente
(force brute sans aucune des optimisations du solveur), utilisée uniquement
pour vérifier — sur de petites positions où elle reste praticable — que le
solveur ne manque jamais le maximum réel de tuiles posables.

Ne modifie jamais le solveur : un écart constaté ici est à signaler dans un
rapport (voir ``scripts/verifier_solveur_exhaustif.py``), pas à corriger
automatiquement.
"""

import random
from itertools import combinations

from rummikub.config import COULEURS, VALEUR_MIN, VALEUR_MAX
from rummikub.moteur.tuiles import Tuile
from rummikub.moteur.validation import valider_combinaison

# Taille de combinaison maximale explorée par la recherche exhaustive : les
# positions vérifiées ici sont volontairement petites (voir
# ``generer_position_aleatoire``), une suite ou un groupe n'y dépassera
# jamais cette taille — borne large, pas une approximation.
_TAILLE_COMBO_MAX = 8


def _toutes_combinaisons_valides(tuiles: list[Tuile]) -> list:
    """Tous les sous-ensembles de ``tuiles`` (taille 3 à ``_TAILLE_COMBO_MAX``)
    qui forment une suite ou un groupe valide. Coûteux (combinatoire en
    C(n, k)) : volontairement non optimisé, voir docstring du module."""
    valides = []
    n = len(tuiles)
    for taille in range(3, min(n, _TAILLE_COMBO_MAX) + 1):
        for combo in combinations(range(n), taille):
            sous = [tuiles[i] for i in combo]
            if valider_combinaison(sous)["valide"]:
                valides.append(frozenset(t.id for t in sous))
    return valides


def _peut_partitionner(restant: frozenset, combos_valides: list, memo: dict) -> bool:
    """Vrai si ``restant`` (ensemble d'ids) peut être intégralement découpé
    en combinaisons valides de ``combos_valides``. Recherche récursive
    mémoïsée (mémoïsation locale à un appel de
    :func:`max_tuiles_posables_exhaustif` — pas partagée entre positions)."""
    if not restant:
        return True
    if restant in memo:
        return memo[restant]
    for combo in combos_valides:
        if combo <= restant and _peut_partitionner(restant - combo, combos_valides, memo):
            memo[restant] = True
            return True
    memo[restant] = False
    return False


def max_tuiles_posables_exhaustif(plateau: list, chevalet: list) -> int:
    """Nombre maximal de tuiles du CHEVALET posables en conservant
    intégralement les tuiles du PLATEAU (même contrainte que
    ``solveur.resoudre_coup``), par force brute : essaie, du plus grand au
    plus petit, chaque sous-ensemble du chevalet et vérifie si
    (plateau + sous-ensemble) peut être partitionné en combinaisons
    valides.

    ``plateau`` : liste de combinaisons (listes de :class:`Tuile`).
    ``chevalet`` : liste de :class:`Tuile`.

    Volontairement lent (pensé pour de petites positions, voir
    ``generer_position_aleatoire`` — pas pour un plateau de partie réelle)."""
    tuiles_plateau = [t for combo in plateau for t in combo]
    for k in range(len(chevalet), -1, -1):
        for sous_main in combinations(chevalet, k):
            tuiles = tuiles_plateau + list(sous_main)
            combos_valides = _toutes_combinaisons_valides(tuiles)
            ids = frozenset(t.id for t in tuiles)
            if _peut_partitionner(ids, combos_valides, {}):
                return k
    return 0


def generer_position_aleatoire(rng: random.Random, *, max_tuiles_plateau: int = 4,
                                max_tuiles_main: int = 5) -> dict:
    """Petite position aléatoire (``rng`` déjà initialisé avec une graine
    fixe pour la reproductibilité) : un plateau de 0 à ``max_tuiles_plateau``
    tuiles (une seule combinaison valide, suite ou groupe, ou aucune) et une
    main de 1 à ``max_tuiles_main`` tuiles piochées au hasard dans le reste du
    jeu (jokers compris, rarement). Assez petite pour que la recherche
    exhaustive reste praticable (voir ``_TAILLE_COMBO_MAX`` et le budget du
    solveur dans les appelants).

    Retourne ``{"plateau": [[Tuile,...]] , "chevalet": [Tuile,...]}``."""
    utilises = set()

    def _tuile_libre(valeur, couleur, serie):
        return Tuile(f"{couleur}_{valeur}_{serie}", valeur, couleur)

    plateau = []
    taille_plateau = rng.choice([0, 3, 3, 4])
    if taille_plateau:
        couleur = rng.choice(COULEURS)
        if rng.random() < 0.5:
            # Groupe : même valeur, couleurs distinctes.
            valeur = rng.randint(VALEUR_MIN, VALEUR_MAX)
            couleurs_groupe = rng.sample(COULEURS, taille_plateau)
            combo = [_tuile_libre(valeur, c, "a") for c in couleurs_groupe]
        else:
            # Suite : même couleur, valeurs consécutives.
            v1 = rng.randint(VALEUR_MIN, VALEUR_MAX - taille_plateau + 1)
            combo = [_tuile_libre(v1 + i, couleur, "a") for i in range(taille_plateau)]
        for t in combo:
            utilises.add(t.id)
        plateau.append(combo)

    chevalet = []
    taille_main = rng.randint(1, max_tuiles_main)
    essais = 0
    while len(chevalet) < taille_main and essais < 200:
        essais += 1
        if rng.random() < 0.08:
            n = rng.choice([1, 2])
            t = Tuile(f"joker_{n}", None, rng.choice(["rouge", "noir"]), est_joker=True)
        else:
            couleur = rng.choice(COULEURS)
            valeur = rng.randint(VALEUR_MIN, VALEUR_MAX)
            serie = rng.choice(["a", "b"])
            t = _tuile_libre(valeur, couleur, serie)
        if t.id in utilises:
            continue
        utilises.add(t.id)
        chevalet.append(t)

    return {"plateau": plateau, "chevalet": chevalet}
