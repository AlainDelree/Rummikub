import random
NOMS = ["Alice","Bruno","Clara","David","Emma","Félix","Gaëlle","Hugo",
        "Inès","Jules","Karine","Léo","Marie","Nathan","Olivia"]
def choisir(exclure=None):
    pool = [n for n in NOMS if n != exclure]
    return random.choice(pool)
