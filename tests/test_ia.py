"""Tests des cinq niveaux d'IA."""

from rummikub.moteur.ia import (
    jouer_ia, jouer_niveau_avance, jouer_niveau_expert,
    jouer_niveau_facile, jouer_niveau_intermediaire, NIVEAUX_IA,
)
from rummikub.moteur.partie import creer_partie
from rummikub.moteur.validation import valider_plateau
from rummikub.moteur.tuiles import tuile_depuis_dict


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


def _etat_avec_joker_recuperable(niveau):
    """Plateau : suite rouge 4-5-(joker=6).

    Chevalet du bot : un rouge 6 (pour reprendre le joker), un noir 9 et un
    bleu 9 (ne forment un groupe complet qu'avec le joker libéré), et un
    rouge 7 qui permettrait l'extension la plus simple sans toucher au
    joker — c'est ce dernier coup, moins intéressant, que jouent Facile et
    Intermédiaire.
    """
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "rouge_4_a", "valeur": 4, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_5_a", "valeur": 5, "couleur": "rouge", "est_joker": False},
        {"id": "joker_1", "valeur": None, "couleur": None, "est_joker": True},
    ]]
    bot["chevalet"] = [
        {"id": "rouge_6_b", "valeur": 6, "couleur": "rouge", "est_joker": False},
        {"id": "noir_9_a", "valeur": 9, "couleur": "noir", "est_joker": False},
        {"id": "bleu_9_a", "valeur": 9, "couleur": "bleu", "est_joker": False},
        {"id": "rouge_7_a", "valeur": 7, "couleur": "rouge", "est_joker": False},
    ]
    return etat


def test_avance_prefere_recuperer_le_joker():
    """Avancé compare le coup évident à la récupération du joker et choisit
    la seconde, nettement meilleure ici (4 tuiles posées contre 1)."""
    etat = _etat_avec_joker_recuperable("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {
        "rouge_6_b", "noir_9_a", "bleu_9_a", "rouge_7_a"}
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]


def test_expert_prefere_recuperer_le_joker():
    etat = _etat_avec_joker_recuperable("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {
        "rouge_6_b", "noir_9_a", "bleu_9_a", "rouge_7_a"}


def test_facile_ne_recupere_pas_le_joker():
    """Facile/Intermédiaire restent inchangés : extension évidente (rouge 7)
    sans tenter d'échanger le joker du plateau."""
    etat = _etat_avec_joker_recuperable("Facile")
    coup = jouer_niveau_facile(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_7_a"}


def test_intermediaire_ne_recupere_pas_le_joker():
    etat = _etat_avec_joker_recuperable("Intermédiaire")
    coup = jouer_niveau_intermediaire(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_7_a"}
