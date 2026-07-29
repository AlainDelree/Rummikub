import random

# Prénoms des joueurs « ordinateur », séparés par genre afin de pouvoir
# accorder le prénom à l'avatar (cf. web/genres.js côté interface).
NOMS_M = ["Bruno", "David", "Félix", "Hugo", "Jules", "Léo", "Nathan"]
NOMS_F = ["Alice", "Clara", "Emma", "Gaëlle", "Inès", "Karine", "Marie", "Olivia"]

# Liste complète (rétro-compatibilité : ancien symbole public NOMS).
NOMS = NOMS_M + NOMS_F


def choisir(exclure=None, genre=None):
    """Nom aléatoire pour un joueur IA.

    `exclure` peut être None, une chaîne (un seul nom à éviter) ou une
    collection de noms (prénom humain + IA déjà présentes).

    `genre` restreint le tirage :
      - "M" → prénom masculin (NOMS_M),
      - "F" → prénom féminin (NOMS_F),
      - None / autre → indifférent (NOMS complet).

    Si tous les noms du genre demandé sont exclus, on repart de la liste
    complète de ce genre pour toujours renvoyer un nom.
    """
    if exclure is None:
        exclus = set()
    elif isinstance(exclure, str):
        exclus = {exclure}
    else:
        exclus = set(exclure)

    if genre == "M":
        base = NOMS_M
    elif genre == "F":
        base = NOMS_F
    else:
        base = NOMS

    pool = [n for n in base if n not in exclus]
    if not pool:
        pool = list(base)
    return random.choice(pool)
