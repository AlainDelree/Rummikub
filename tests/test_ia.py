"""Tests des cinq niveaux d'IA."""

from rummikub.moteur.ia import jouer_ia
from rummikub.moteur.partie import creer_partie


def test_ia_debutant_ne_plante_pas():
    config_joueurs = [
        {"nom": "Humain", "est_ia": False, "niveau": None},
        {"nom": "Bot",    "est_ia": True,  "niveau": "Débutant"},
    ]
    etat = creer_partie(config_joueurs,
                        {"nb_manches": 1, "valeur_joker_penalite": 30,
                         "mise_initiale_min": 30})
    etat["index_joueur_actuel"] = 1
    res = jouer_ia(etat, 1)
    assert res["action"] in ("jouer", "piocher", "passer")


def test_tous_niveaux():
    niveaux = ["Débutant", "Facile", "Intermédiaire", "Avancé", "Expert"]
    for n in niveaux:
        config = [{"nom": "H", "est_ia": False, "niveau": None},
                  {"nom": "B", "est_ia": True, "niveau": n}]
        etat = creer_partie(config,
                            {"nb_manches": 1, "valeur_joker_penalite": 30,
                             "mise_initiale_min": 30})
        etat["index_joueur_actuel"] = 1
        res = jouer_ia(etat, 1)
        assert res["action"] in ("jouer", "piocher", "passer"), \
            f"Niveau {n} planté"
