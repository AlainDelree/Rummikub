"""Validation des combinaisons Rummikub : suites, groupes, plateau."""

from rummikub.moteur.tuiles import Tuile
from rummikub.config import VALEUR_MIN, VALEUR_MAX


def valider_suite(tuiles: list[Tuile]) -> dict:
    """
    Suite : ≥3 tuiles, même couleur (hors jokers), valeurs consécutives 1–13.
    Un joker comble un manque mais pas deux jokers adjacents sans tuile réelle.
    Retourne {"valide": bool, "points": int, "raison": str|None}
    points = somme des valeurs (joker prend la valeur de la position comblée)
    raison (si invalide) explique pourquoi ce n'est pas une suite valide.
    """
    def invalide(raison):
        return {"valide": False, "points": 0, "raison": raison}

    n = len(tuiles)
    if n < 3:
        return invalide("moins de 3 tuiles")

    # Même couleur pour toutes les tuiles réelles.
    couleurs = {t.couleur for t in tuiles if not t.est_joker}
    if len(couleurs) > 1:
        return invalide("couleurs différentes dans une suite (toutes les "
                         "tuiles doivent être de la même couleur)")

    # Il faut au moins une tuile réelle pour ancrer la séquence.
    reels = [(i, t) for i, t in enumerate(tuiles) if not t.est_joker]
    if not reels:
        return invalide("aucune tuile réelle (que des jokers)")

    # Pas deux jokers adjacents.
    for i in range(n - 1):
        if tuiles[i].est_joker and tuiles[i + 1].est_joker:
            return invalide("deux jokers adjacents dans une suite")

    # Valeur de départ déduite de la première tuile réelle et de sa position.
    i0, t0 = reels[0]
    base = t0.valeur - i0

    points = 0
    for i, t in enumerate(tuiles):
        val = base + i
        if val < VALEUR_MIN or val > VALEUR_MAX:
            return invalide("suite hors limites (les valeurs doivent rester "
                             "entre 1 et 13)")
        if not t.est_joker and t.valeur != val:
            return invalide("tuiles non consécutives dans la suite")
        points += val

    return {"valide": True, "points": points, "raison": None}


def valider_groupe(tuiles: list[Tuile]) -> dict:
    """
    Groupe : 3 ou 4 tuiles, même valeur, couleurs toutes différentes.
    Un joker remplace une couleur manquante. Pas deux jokers dans un groupe.
    Retourne {"valide": bool, "points": int, "raison": str|None}
    raison (si invalide) explique pourquoi ce n'est pas un groupe valide.
    """
    def invalide(raison):
        return {"valide": False, "points": 0, "raison": raison}

    n = len(tuiles)
    if n < 3 or n > 4:
        return invalide("un groupe doit contenir 3 ou 4 tuiles")

    reels = [t for t in tuiles if not t.est_joker]
    jokers = [t for t in tuiles if t.est_joker]
    if len(jokers) > 1:
        return invalide("plus d'un joker dans un groupe")
    if not reels:
        return invalide("aucune tuile réelle (que des jokers)")

    # Même valeur pour toutes les tuiles réelles.
    valeurs = {t.valeur for t in reels}
    if len(valeurs) > 1:
        return invalide("valeurs différentes dans un groupe (toutes les "
                         "tuiles doivent avoir la même valeur)")
    valeur = reels[0].valeur

    # Couleurs toutes différentes (parmi les tuiles réelles).
    couleurs = [t.couleur for t in reels]
    if len(set(couleurs)) != len(couleurs):
        return invalide("couleurs en double dans un groupe (chaque couleur "
                         "ne peut apparaître qu'une fois)")

    # Le joker prend la valeur du groupe.
    points = valeur * n
    return {"valide": True, "points": points, "raison": None}


def _raison_combinaison_invalide(tuiles: list[Tuile], r_suite: dict,
                                  r_groupe: dict) -> str:
    """Choisit l'explication la plus pertinente selon le type probablement
    visé (suite ou groupe), déduit de la couleur/valeur commune des tuiles
    réelles de la combinaison."""
    if len(tuiles) < 3:
        return "moins de 3 tuiles"

    reels = [t for t in tuiles if not t.est_joker]
    couleurs = {t.couleur for t in reels}
    valeurs = {t.valeur for t in reels}
    meme_couleur = len(couleurs) <= 1
    meme_valeur = len(valeurs) <= 1

    if meme_valeur and not meme_couleur:
        return r_groupe["raison"]
    if meme_couleur and not meme_valeur:
        return r_suite["raison"]
    if meme_couleur and meme_valeur:
        if r_suite["raison"] == r_groupe["raison"]:
            return r_suite["raison"]
        return (f"ni suite valide ({r_suite['raison']}) "
                f"ni groupe valide ({r_groupe['raison']})")
    return ("tuiles incompatibles : ni une suite (couleur commune requise) "
            "ni un groupe (valeur commune requise)")


def valider_combinaison(tuiles: list[Tuile]) -> dict:
    """
    Essaie suite puis groupe.
    Retourne {"valide": bool, "type": "suite"|"groupe"|None, "points": int,
              "raison": str|None} — raison explique l'échec si invalide.
    """
    r_suite = valider_suite(tuiles)
    if r_suite["valide"]:
        return {"valide": True, "type": "suite", "points": r_suite["points"],
                "raison": None}
    r_groupe = valider_groupe(tuiles)
    if r_groupe["valide"]:
        return {"valide": True, "type": "groupe", "points": r_groupe["points"],
                "raison": None}
    raison = _raison_combinaison_invalide(tuiles, r_suite, r_groupe)
    return {"valide": False, "type": None, "points": 0, "raison": raison}


def valider_plateau(combinaisons: list[list[Tuile]]) -> dict:
    """
    Chaque combinaison doit avoir ≥3 tuiles et être valide.
    Retourne {"valide": bool, "erreurs": [str], "combos_invalides": [[id,...],...]}
    combos_invalides liste, pour chaque combinaison fautive, les ids de ses
    tuiles (dans l'ordre), afin que l'interface puisse l'entourer sur le tapis.
    """
    erreurs: list[str] = []
    combos_invalides: list[list[str]] = []
    for idx, combo in enumerate(combinaisons):
        if len(combo) < 3:
            erreurs.append(f"Combinaison {idx} : moins de 3 tuiles")
            combos_invalides.append([t.id for t in combo])
            continue
        r = valider_combinaison(combo)
        if not r["valide"]:
            erreurs.append(f"Combinaison {idx} : {r['raison']}")
            combos_invalides.append([t.id for t in combo])
    return {"valide": len(erreurs) == 0, "erreurs": erreurs,
            "combos_invalides": combos_invalides}
