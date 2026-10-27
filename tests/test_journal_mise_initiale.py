"""Tests du nouveau champ ``mises_initiales`` du journal (issue #202) : pour
chaque action, la liste (alignée sur les joueurs) de l'état « mise initiale
faite » de chaque joueur, afin de relier correctement une partie reprise."""

import json

from rummikub import config
from rummikub.persistance import journal as Journal
from rummikub.persistance import stockage as Stockage
from rummikub.ui.api import Api


def _tuile(id_, valeur, couleur, est_joker=False):
    return {"id": id_, "valeur": valeur, "couleur": couleur, "est_joker": est_joker}


def _etat(mise0, mise1, tour=3):
    return {
        "id": "partie_test", "phase": "jeu", "tour_numero": tour,
        "index_joueur_actuel": 0,
        "joueurs": [
            {"nom": "Alain", "est_ia": False, "chevalet": [_tuile("r8", 8, "rouge")],
             "mise_initiale_faite": mise0, "score_manche": 0, "score_cumul": 0},
            {"nom": "Bot", "est_ia": True, "niveau": "Expert", "chevalet": [],
             "mise_initiale_faite": mise1, "score_manche": 0, "score_cumul": 0},
        ],
        "pioche": [], "plateau": [],
        "gagnant_manche_index": None, "terminee": False,
    }


def test_mises_initiales_reflete_etat_des_joueurs():
    assert Journal._mises_initiales(_etat(True, False)) == [True, False]
    assert Journal._mises_initiales(_etat(False, False)) == [False, False]
    assert Journal._mises_initiales(_etat(True, True)) == [True, True]
    # Robuste à un état sans joueurs.
    assert Journal._mises_initiales({}) == []


def test_logger_action_ecrit_mises_initiales(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RACINE_DATA", tmp_path)
    monkeypatch.setattr(config, "LOG_PARTIES", True)
    monkeypatch.setattr(Journal, "_journaux", {})

    # Première action : seul le joueur 0 a fait sa mise initiale.
    Journal.logger_action(_etat(True, False), "pose", auteur_index=0,
                          nb_tuiles_posees=3)
    # Seconde action (même partie) : les deux l'ont désormais faite.
    Journal.logger_action(_etat(True, True), "pose", auteur_index=1,
                          nb_tuiles_posees=3)

    fichiers = list((tmp_path / "logs_parties").glob("partie_*.json"))
    assert len(fichiers) == 1
    journal = json.loads(fichiers[0].read_text(encoding="utf-8"))
    actions = journal["actions"]
    assert len(actions) == 2
    assert actions[0]["mises_initiales"] == [True, False]
    assert actions[1]["mises_initiales"] == [True, True]


def test_integration_api_journalise_mises_initiales(tmp_path, monkeypatch):
    """Par ``ui/api.py`` : une pose humaine journalise bien le drapeau de chaque
    joueur. Le joueur 0 (humain) a déjà fait sa mise, pose une 4e tuile rouge."""
    monkeypatch.setattr(config, "RACINE_DATA", tmp_path)
    monkeypatch.setattr(config, "LOG_PARTIES", True)
    monkeypatch.setattr(Journal, "_journaux", {})
    monkeypatch.setattr(Stockage, "sauvegarder_partie", lambda etat: None)

    r1, r2, r3 = _tuile("r1", 1, "rouge"), _tuile("r2", 2, "rouge"), _tuile("r3", 3, "rouge")
    r4 = _tuile("r4", 4, "rouge")

    class _FakeApp:
        def __init__(self, etat):
            self.etat_jeu = etat

    etat = {
        "id": "p1", "phase": "jeu", "tour_numero": 4, "index_joueur_actuel": 0,
        "joueurs": [
            {"nom": "Alain", "est_ia": False, "chevalet": [r4],
             "mise_initiale_faite": True, "score_manche": 0, "score_cumul": 0},
            {"nom": "Bot", "est_ia": True, "niveau": "Expert", "chevalet": [],
             "mise_initiale_faite": False, "score_manche": 0, "score_cumul": 0},
        ],
        "pioche": [], "plateau": [[r1, r2, r3]],
        "plateau_debut_tour": None, "chevalet_debut_tour": [], "index_debut_tour": 0,
        "tour_debut_tour": 4, "historique": [], "dernier_coup_ia": None,
        "manche_terminee": False, "gagnant_manche_index": None,
        "config": {"nb_manches": 1, "valeur_joker_penalite": 30, "mise_initiale_min": 30},
    }
    api = Api(_FakeApp(etat))
    res = api.jeu_jouer_coup({"ids_tuiles": ["r4"],
                              "nouveau_plateau": [[r1, r2, r3, r4]]})
    assert res["ok"] is True, res.get("erreur")

    fichiers = list((tmp_path / "logs_parties").glob("partie_*.json"))
    journal = json.loads(fichiers[0].read_text(encoding="utf-8"))
    derniere = journal["actions"][-1]
    # Le joueur 1 (IA) n'a pas posé : son drapeau reste False.
    assert derniere["mises_initiales"] == [True, False]
