"""Test d'intégration de la correction #201 dans ``ui/api.py:jeu_jouer_coup`` :
le journal doit désormais distinguer les tuiles RÉELLEMENT sorties de la
main (``nb_tuiles_posees``) des tuiles du plateau déplacées ce tour sans
venir de la main (``nb_tuiles_deplacees``), plutôt que de tout compter comme
« posé » (voir ``persistance/coups_rates.py``, section #201, pour le détail
du bug corrigé).
"""

import json

from rummikub import config
from rummikub.persistance import journal as Journal
from rummikub.persistance import stockage as Stockage
from rummikub.ui.api import Api


class _FakeApp:
    def __init__(self, etat):
        self.etat_jeu = etat


def _tuile(id_, valeur, couleur, est_joker=False):
    return {"id": id_, "valeur": valeur, "couleur": couleur, "est_joker": est_joker}


def test_jeu_jouer_coup_distingue_posees_et_deplacees(tmp_path, monkeypatch):
    """Le plateau porte deux combinaisons déjà posées (suite rouge 5-6-7 et
    suite rouge 9-10-11). Le joueur ne joue qu'UNE tuile de sa main (rouge
    8) mais, en la plaçant, fusionne les deux combinaisons en une seule
    (rouge 5 à 11) : les 3 tuiles de la seconde combinaison sont donc
    DÉPLACÉES (reprises du tapis), pas posées depuis la main — comme le fait
    ``jeu.js:prendreTuileTapis``, qui alimente ``tuilesCeTour`` (-> envoyé
    comme ``ids_tuiles``) avec les deux catégories mélangées."""
    monkeypatch.setattr(config, "RACINE_DATA", tmp_path)
    monkeypatch.setattr(config, "LOG_PARTIES", True)
    monkeypatch.setattr(Journal, "_journaux", {})
    monkeypatch.setattr(Stockage, "sauvegarder_partie", lambda etat: None)

    r5, r6, r7 = _tuile("r5", 5, "rouge"), _tuile("r6", 6, "rouge"), _tuile("r7", 7, "rouge")
    r8 = _tuile("r8", 8, "rouge")
    r9, r10, r11 = _tuile("r9", 9, "rouge"), _tuile("r10", 10, "rouge"), _tuile("r11", 11, "rouge")
    filler = _tuile("noir_1_a", 1, "noir")  # reste en main, non joué ce tour.

    etat = {
        "id": "partie_test", "phase": "jeu", "tour_numero": 3,
        "index_joueur_actuel": 0,
        "joueurs": [
            {"nom": "Alain", "est_ia": False, "chevalet": [r8, filler],
             "mise_initiale_faite": True, "score_manche": 0, "score_cumul": 0},
            {"nom": "Bot", "est_ia": True, "niveau": "Expert", "chevalet": [],
             "mise_initiale_faite": True, "score_manche": 0, "score_cumul": 0},
        ],
        "pioche": [],
        "plateau": [[r5, r6, r7], [r9, r10, r11]],
        "plateau_debut_tour": None, "chevalet_debut_tour": [], "index_debut_tour": 0,
        "tour_debut_tour": 3, "historique": [], "dernier_coup_ia": None,
        "manche_terminee": False, "gagnant_manche_index": None,
        "config": {"nb_manches": 1, "valeur_joker_penalite": 30, "mise_initiale_min": 30},
    }

    api = Api(_FakeApp(etat))
    data = {
        "ids_tuiles": ["r8", "r9", "r10", "r11"],  # 1 tuile de la main + 3 déplacées.
        "nouveau_plateau": [[r5, r6, r7, r8, r9, r10, r11]],
    }
    res = api.jeu_jouer_coup(data)
    assert res["ok"] is True, res.get("erreur")

    fichiers = list((tmp_path / "logs_parties").glob("partie_*.json"))
    assert len(fichiers) == 1
    journal = json.loads(fichiers[0].read_text(encoding="utf-8"))
    derniere = journal["actions"][-1]
    assert derniere["action"] == "pose"
    assert derniere["nb_tuiles_posees"] == 1
    assert derniere["nb_tuiles_deplacees"] == 3
