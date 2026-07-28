"""Validation des combinaisons Rummikub : suites, groupes, plateau."""

from rummikub.moteur.tuiles import Tuile
from rummikub.config import VALEUR_MIN, VALEUR_MAX


def valider_suite(tuiles: list[Tuile]) -> dict:
    """
    Suite : ≥3 tuiles, même couleur (hors jokers), valeurs consécutives 1–13.
    Un joker comble un manque mais pas deux jokers adjacents sans tuile réelle.
    Retourne {"valide": bool, "points": int}
    points = somme des valeurs (joker prend la valeur de la position comblée)
    """
    invalide = {"valide": False, "points": 0}
    n = len(tuiles)
    if n < 3:
        return invalide

    # Même couleur pour toutes les tuiles réelles.
    couleurs = {t.couleur for t in tuiles if not t.est_joker}
    if len(couleurs) > 1:
        return invalide

    # Il faut au moins une tuile réelle pour ancrer la séquence.
    reels = [(i, t) for i, t in enumerate(tuiles) if not t.est_joker]
    if not reels:
        return invalide

    # Pas deux jokers adjacents.
    for i in range(n - 1):
        if tuiles[i].est_joker and tuiles[i + 1].est_joker:
            return invalide

    # Valeur de départ déduite de la première tuile réelle et de sa position.
    i0, t0 = reels[0]
    base = t0.valeur - i0

    points = 0
    for i, t in enumerate(tuiles):
        val = base + i
        if val < VALEUR_MIN or val > VALEUR_MAX:
            return invalide
        if not t.est_joker and t.valeur != val:
            return invalide
        points += val

    return {"valide": True, "points": points}


def valider_groupe(tuiles: list[Tuile]) -> dict:
    """
    Groupe : 3 ou 4 tuiles, même valeur, couleurs toutes différentes.
    Un joker remplace une couleur manquante. Pas deux jokers dans un groupe.
    Retourne {"valide": bool, "points": int}
    """
    invalide = {"valide": False, "points": 0}
    n = len(tuiles)
    if n < 3 or n > 4:
        return invalide

    reels = [t for t in tuiles if not t.est_joker]
    jokers = [t for t in tuiles if t.est_joker]
    if len(jokers) > 1:
        return invalide
    if not reels:
        return invalide

    # Même valeur pour toutes les tuiles réelles.
    valeurs = {t.valeur for t in reels}
    if len(valeurs) > 1:
        return invalide
    valeur = reels[0].valeur

    # Couleurs toutes différentes (parmi les tuiles réelles).
    couleurs = [t.couleur for t in reels]
    if len(set(couleurs)) != len(couleurs):
        return invalide

    # Le joker prend la valeur du groupe.
    points = valeur * n
    return {"valide": True, "points": points}


def valider_combinaison(tuiles: list[Tuile]) -> dict:
    """
    Essaie suite puis groupe.
    Retourne {"valide": bool, "type": "suite"|"groupe"|None, "points": int}
    """
    r = valider_suite(tuiles)
    if r["valide"]:
        return {"valide": True, "type": "suite", "points": r["points"]}
    r = valider_groupe(tuiles)
    if r["valide"]:
        return {"valide": True, "type": "groupe", "points": r["points"]}
    return {"valide": False, "type": None, "points": 0}


def valider_plateau(combinaisons: list[list[Tuile]]) -> dict:
    """
    Chaque combinaison doit avoir ≥3 tuiles et être valide.
    Retourne {"valide": bool, "erreurs": [str]}
    """
    erreurs: list[str] = []
    for idx, combo in enumerate(combinaisons):
        if len(combo) < 3:
            erreurs.append(f"Combinaison {idx} : moins de 3 tuiles")
            continue
        if not valider_combinaison(combo)["valide"]:
            erreurs.append(f"Combinaison {idx} : ni suite ni groupe valide")
    return {"valide": len(erreurs) == 0, "erreurs": erreurs}
