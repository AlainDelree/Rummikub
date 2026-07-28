import random
NOMS = ["Alice","Bruno","Clara","David","Emma","Félix","Gaëlle","Hugo",
        "Inès","Jules","Karine","Léo","Marie","Nathan","Olivia"]


def choisir(exclure=None):
    """Nom aléatoire pour un joueur IA.

    `exclure` peut être None, une chaîne (un seul nom à éviter) ou une
    collection de noms (prénom humain + IA déjà présentes). Si tous les noms
    sont exclus, on repart de la liste complète pour toujours renvoyer un nom.
    """
    if exclure is None:
        exclus = set()
    elif isinstance(exclure, str):
        exclus = {exclure}
    else:
        exclus = set(exclure)
    pool = [n for n in NOMS if n not in exclus]
    if not pool:
        pool = list(NOMS)
    return random.choice(pool)
