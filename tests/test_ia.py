"""Tests des cinq niveaux d'IA."""

from rummikub.moteur.ia import jouer_ia, NIVEAUX_IA
from rummikub.moteur.partie import creer_partie


def _partie_2j(niveau="Débutant"):
    return creer_partie(
        [{"nom": "Humain", "est_ia": False, "niveau": None},
         {"nom": "Bot", "est_ia": True, "niveau": niveau}],
        {"nb_manches": 1, "valeur_joker_penalite": 30,
         "mise_initiale_min": 30})


def test_ia_debutant_ne_plante_pas():
    etat = _partie_2j("Débutant")
    etat["index_joueur_actuel"] = 1
    res = jouer_ia(etat, 1)
    assert res["action"] in ("jouer", "piocher", "passer")


def test_tous_niveaux_ne_plantent_pas():
    for n in NIVEAUX_IA:
        etat = _partie_2j(n)
        etat["index_joueur_actuel"] = 1
        res = jouer_ia(etat, 1)
        assert res["action"] in ("jouer", "piocher", "passer"), \
            f"Niveau {n} a retourné action invalide"


def test_debutant_action_valide():
    etat = _partie_2j("Débutant")
    etat["index_joueur_actuel"] = 1
    res = jouer_ia(etat, 1)
    assert "action" in res and "ids_tuiles" in res


def test_expert_action_valide():
    etat = _partie_2j("Expert")
    etat["index_joueur_actuel"] = 1
    res = jouer_ia(etat, 1)
    assert res["action"] in ("jouer", "piocher", "passer")


def test_ia_jouer_coup_valide():
    """Si l'IA choisit 'jouer', le plateau proposé doit être valide."""
    from rummikub.moteur.validation import valider_plateau
    from rummikub.moteur.tuiles import tuile_depuis_dict
    for n in NIVEAUX_IA:
        etat = _partie_2j(n)
        etat["index_joueur_actuel"] = 1
        etat["joueurs"][1]["mise_initiale_faite"] = True
        res = jouer_ia(etat, 1)
        if res["action"] == "jouer" and res["nouveau_plateau"]:
            plateau = [[tuile_depuis_dict(d) for d in c]
                       for c in res["nouveau_plateau"]]
            r = valider_plateau(plateau)
            assert r["valide"], f"Niveau {n} : plateau IA invalide"
