"""Tests de lecture des journaux de parties et du bilan par niveau d'IA
(issue #185) : voir ``persistance/journal.py`` et ``persistance/bilan.py``."""

import json
import random

import pytest

from rummikub import config
from rummikub.moteur.partie import creer_partie, piocher
from rummikub.persistance import journal as Journal
from rummikub.persistance.bilan import (
    calculer_bilan, charger_journal, charger_toutes_parties,
    extraire_partie, lister_journaux,
)


# --------------------------------------------------------------------------- #
# Fixtures : journaux d'exemple construits à la main.
# --------------------------------------------------------------------------- #

def _joueur(nom, est_ia, niveau=None):
    return {"nom": nom, "est_ia": est_ia, "niveau": niveau}


def _action(tour, auteur_index, action, nb_tuiles_posees=0, termine=False,
           gagnant_index=None, mains=None):
    return {
        "horodatage": "2026-10-20T10:00:00",
        "action": action,
        "tour": tour,
        "auteur_index": auteur_index,
        "nb_tuiles_posees": nb_tuiles_posees,
        "termine": termine,
        "gagnant_index": gagnant_index,
        "mains_joueurs": mains or [],
        "plateau": [],
        "pioche": [],
        "sac_restant": 0,
    }


def _journal_partie_terminee(debut="2026-10-20T10:00:00", niveau_ia="Expert",
                             gagnant_index=0, nb_tours=6):
    """Partie à 2 joueurs (humain index 0, IA index 1), 6 tours : alternance
    pose/pioche/passe, l'IA pioche au tour 2 (début) et passe au tour 6 (fin)."""
    mains_fin = [{"nom": "Alain", "tuiles": []},
                {"nom": "Bot", "tuiles": [{"id": "rouge_1_a"}]}]
    actions = [
        _action(1, 0, "pose", nb_tuiles_posees=3),
        _action(2, 1, "pioche"),
        _action(3, 0, "pose", nb_tuiles_posees=2),
        _action(4, 1, "pose", nb_tuiles_posees=1),
        _action(5, 0, "pose", nb_tuiles_posees=4),
        _action(nb_tours, 1, "passe", termine=True,
               gagnant_index=gagnant_index, mains=mains_fin),
    ]
    return {
        "partie_id": "abc123",
        "debut": debut,
        "joueurs": [_joueur("Alain", False), _joueur("Bot", True, niveau_ia)],
        "actions": actions,
    }


def _journal_abandonne():
    """Dernière action sans ``termine: True`` : partie abandonnée en cours."""
    return {
        "partie_id": "def456",
        "debut": "2026-10-21T09:00:00",
        "joueurs": [_joueur("Alain", False), _joueur("Bot", True, "Expert")],
        "actions": [_action(1, 0, "pose", nb_tuiles_posees=3),
                    _action(2, 1, "pioche")],
    }


def _journal_ancien_format():
    """Format d'avant #185 : joueurs = liste de noms, pas de champ ``termine``
    ni ``auteur_index`` sur les actions. Doit être lu sans planter."""
    return {
        "partie_id": "old789",
        "debut": "2026-01-01T08:00:00",
        "joueurs": ["Alain", "Bot"],
        "actions": [
            {"horodatage": "2026-01-01T08:00:00", "action": "pose",
             "tour": 1, "joueur_actuel": 1, "mains_joueurs": [],
             "plateau": [], "pioche": [], "sac_restant": 50},
        ],
    }


# --------------------------------------------------------------------------- #
# Lecture de fichiers.
# --------------------------------------------------------------------------- #

def test_charger_journal_fichier_absent(tmp_path):
    assert charger_journal(tmp_path / "inexistant.json") is None


def test_charger_journal_json_invalide(tmp_path):
    f = tmp_path / "partie_20260101_000000.json"
    f.write_text("{ceci n'est pas du json", encoding="utf-8")
    assert charger_journal(f) is None


def test_charger_journal_contenu_non_dict(tmp_path):
    f = tmp_path / "partie_20260101_000001.json"
    f.write_text("[1, 2, 3]", encoding="utf-8")
    assert charger_journal(f) is None


def test_lister_journaux_dossier_absent(tmp_path):
    assert lister_journaux(tmp_path / "n_existe_pas") == []


def test_lister_journaux_tri(tmp_path):
    (tmp_path / "partie_20260101_000000.json").write_text("{}", encoding="utf-8")
    (tmp_path / "partie_20260102_000000.json").write_text("{}", encoding="utf-8")
    (tmp_path / "autrechose.json").write_text("{}", encoding="utf-8")
    noms = [p.name for p in lister_journaux(tmp_path)]
    assert noms == ["partie_20260101_000000.json", "partie_20260102_000000.json"]


# --------------------------------------------------------------------------- #
# Normalisation d'une partie (extraire_partie).
# --------------------------------------------------------------------------- #

def test_extraire_partie_terminee():
    partie = extraire_partie(_journal_partie_terminee())
    assert partie is not None
    assert partie["gagnant_index"] == 0
    assert partie["nb_tours"] == 6
    assert partie["joueurs"][0] == {"nom": "Alain", "est_ia": False, "niveau": None}
    assert partie["joueurs"][1] == {"nom": "Bot", "est_ia": True, "niveau": "Expert"}
    assert partie["tuiles_restantes"] == {"Alain": 0, "Bot": 1}
    # 6 décisions (pose/pioche/passe), aucune annulation à dédoublonner ici.
    assert len(partie["decisions"]) == 6


def test_extraire_partie_abandonnee_exclue():
    assert extraire_partie(_journal_abandonne()) is None


def test_extraire_partie_ancien_format_exclue_sans_planter():
    # Pas de "termine" sur la dernière action -> traité comme non terminé.
    assert extraire_partie(_journal_ancien_format()) is None


def test_extraire_partie_entree_non_dict():
    assert extraire_partie("pas un dict") is None
    assert extraire_partie({"actions": []}) is None


def test_extraire_partie_dedoublonne_apres_annulation():
    """Une pose annulée puis remplacée par une pioche sur le même tour ne doit
    compter qu'une fois (la dernière décision pour ce tour, voir #185)."""
    data = _journal_partie_terminee()
    # Le joueur 0 pose au tour 1, puis annule et pioche à la place.
    data["actions"].insert(1, _action(1, 0, "annulation"))
    data["actions"].insert(2, _action(1, 0, "pioche"))
    partie = extraire_partie(data)
    decisions_tour_1 = [d for d in partie["decisions"] if d["tour"] == 1]
    assert len(decisions_tour_1) == 1
    assert decisions_tour_1[0]["action"] == "pioche"


# --------------------------------------------------------------------------- #
# Calcul du bilan.
# --------------------------------------------------------------------------- #

def test_calculer_bilan_victoire_et_defaite():
    victoire = extraire_partie(_journal_partie_terminee(gagnant_index=0))
    defaite = extraire_partie(_journal_partie_terminee(
        debut="2026-10-22T10:00:00", gagnant_index=1))
    bilan = calculer_bilan([victoire, defaite])

    assert set(bilan.keys()) == {"Expert"}
    s = bilan["Expert"]
    assert s["parties"] == 2
    assert s["victoires_humain"] == 1
    assert s["defaites_humain"] == 1
    assert s["taux_victoire_humain"] == 0.5
    assert s["marge_moyenne_victoire"] == 1       # tuiles restantes de l'IA
    assert s["marge_moyenne_defaite"] == 0        # tuiles restantes de l'humain
    assert s["tours_moyens"] == 6


def test_calculer_bilan_part_pioche_ou_passe_et_moment():
    partie = extraire_partie(_journal_partie_terminee())
    bilan = calculer_bilan([partie])
    s = bilan["Expert"]
    # Décisions de l'IA (auteur_index=1) : tour 2 pioche (début), tour 4 pose,
    # tour 6 passe (fin) -> 2 décisions IA sur 3 sont pioche/passe.
    assert s["part_pioche_ou_passe"] == pytest.approx(2 / 3)
    rep = s["repartition_moment_pioche_ou_passe"]
    assert rep["debut"] == pytest.approx(0.5)
    assert rep["fin"] == pytest.approx(0.5)
    assert rep["milieu"] == 0


def test_calculer_bilan_ignore_none():
    assert calculer_bilan([None, None]) == {}


def test_calculer_bilan_filtre_nom_joueur():
    autre_joueur = _journal_partie_terminee()
    autre_joueur["joueurs"][0]["nom"] = "Quelqu'un d'autre"
    partie = extraire_partie(autre_joueur)
    bilan = calculer_bilan([partie], nom_joueur="Alain")
    assert bilan == {}
    bilan2 = calculer_bilan([partie], nom_joueur="Quelqu'un d'autre")
    assert bilan2["Expert"]["parties"] == 1


def test_calculer_bilan_filtre_periode():
    partie = extraire_partie(_journal_partie_terminee(debut="2026-10-20T10:00:00"))
    assert calculer_bilan([partie], depuis="2026-10-21") == {}
    assert calculer_bilan([partie], jusqu="2026-10-19") == {}
    assert calculer_bilan([partie], depuis="2026-10-01", jusqu="2026-10-31") != {}


def test_charger_toutes_parties_dossier_mixte(tmp_path):
    """Dossier avec une partie valide, une abandonnée, un ancien format et un
    fichier JSON corrompu : seule la partie valide doit être retenue."""
    (tmp_path / "partie_20260101_000000.json").write_text(
        json.dumps(_journal_partie_terminee()), encoding="utf-8")
    (tmp_path / "partie_20260102_000000.json").write_text(
        json.dumps(_journal_abandonne()), encoding="utf-8")
    (tmp_path / "partie_20260103_000000.json").write_text(
        json.dumps(_journal_ancien_format()), encoding="utf-8")
    (tmp_path / "partie_20260104_000000.json").write_text(
        "{corrompu", encoding="utf-8")

    parties = charger_toutes_parties(tmp_path)
    assert len(parties) == 1
    assert parties[0]["partie_id"] == "abc123"


# --------------------------------------------------------------------------- #
# Partie reprise répartie sur plusieurs fichiers (issue #202).
# --------------------------------------------------------------------------- #

def _journal_reprise_partie1():
    """Premier fichier d'une partie reprise : NON terminé (le jeu a été fermé
    avant la fin). Analysé seul, il serait pris pour une partie abandonnée."""
    return {
        "partie_id": "reprise1", "debut": "2026-10-26T10:00:00",
        "joueurs": [_joueur("Alain", False), _joueur("Bot", True, "Expert")],
        "actions": [
            _action(1, 0, "pose", nb_tuiles_posees=3),
            _action(2, 1, "pioche"),
            _action(3, 0, "pose", nb_tuiles_posees=2),
        ],
    }


def _journal_reprise_partie2():
    """Second fichier de la MÊME partie (même ``partie_id``), repris plus tard
    et terminé au tour 6."""
    mains_fin = [{"nom": "Alain", "tuiles": []},
                 {"nom": "Bot", "tuiles": [{"id": "rouge_1_a"}, {"id": "bleu_2_a"}]}]
    return {
        "partie_id": "reprise1", "debut": "2026-10-26T11:30:00",
        "joueurs": [_joueur("Alain", False), _joueur("Bot", True, "Expert")],
        "actions": [
            _action(4, 1, "pioche"),
            _action(5, 0, "pose", nb_tuiles_posees=4),
            _action(6, 1, "passe", termine=True, gagnant_index=0, mains=mains_fin),
        ],
    }


def test_premier_fichier_reprise_seul_est_abandonne():
    # Référence : analysé isolément, le premier fichier est non terminé.
    assert extraire_partie(_journal_reprise_partie1()) is None


def test_charger_toutes_parties_relie_une_partie_reprise(tmp_path):
    """Deux fichiers d'une même partie reprise -> UNE seule partie comptée,
    avec son nombre de tours réel et toutes les décisions (point 4)."""
    (tmp_path / "partie_20261026_100000.json").write_text(
        json.dumps(_journal_reprise_partie1()), encoding="utf-8")
    (tmp_path / "partie_20261026_113000.json").write_text(
        json.dumps(_journal_reprise_partie2()), encoding="utf-8")

    parties = charger_toutes_parties(tmp_path)
    assert len(parties) == 1
    partie = parties[0]
    assert partie["partie_id"] == "reprise1"
    assert partie["gagnant_index"] == 0
    assert partie["nb_tours"] == 6                      # tours réels des 2 fichiers.
    assert len(partie["decisions"]) == 6                # toutes les décisions.
    assert partie["tuiles_restantes"] == {"Alain": 0, "Bot": 2}

    bilan = calculer_bilan(parties)
    assert bilan["Expert"]["parties"] == 1              # comptée une seule fois.
    assert bilan["Expert"]["victoires_humain"] == 1
    assert bilan["Expert"]["tours_moyens"] == 6


# --------------------------------------------------------------------------- #
# Intégration réelle : journal.logger_action -> bilan (même format exact).
# --------------------------------------------------------------------------- #

def test_integration_logger_action_vers_bilan(tmp_path, monkeypatch):
    """Fait jouer une vraie partie 2 joueurs via le moteur (pioche jusqu'à
    épuisement du sac, qui termine la manche par la règle « pioche vide »),
    journalise chaque coup comme le fait ``ui/api.py``, puis vérifie que le
    bilan le lit correctement : garantit que journal.py et bilan.py restent
    d'accord sur le format."""
    monkeypatch.setattr(config, "RACINE_DATA", tmp_path)
    monkeypatch.setattr(config, "LOG_PARTIES", True)
    monkeypatch.setattr(Journal, "_journaux", {})

    random.seed(42)
    etat = creer_partie(
        [{"nom": "Alain", "est_ia": False, "niveau": None},
         {"nom": "Bot", "est_ia": True, "niveau": "Expert"}],
        {"nb_manches": 1, "valeur_joker_penalite": 30, "mise_initiale_min": 30})

    garde_fou = 0
    while not etat.get("terminee") and garde_fou < 200:
        idx = etat["index_joueur_actuel"]
        res = piocher(etat)
        etat = res["etat"]
        Journal.logger_action(etat, "pioche", auteur_index=idx)
        garde_fou += 1

    assert etat.get("terminee") is True

    dossier = tmp_path / "logs_parties"
    parties = charger_toutes_parties(dossier)
    assert len(parties) == 1
    partie = parties[0]
    assert partie["joueurs"] == [
        {"nom": "Alain", "est_ia": False, "niveau": None},
        {"nom": "Bot", "est_ia": True, "niveau": "Expert"},
    ]
    assert partie["gagnant_index"] in (0, 1)
    assert partie["nb_tours"] == garde_fou

    bilan = calculer_bilan(parties)
    assert bilan["Expert"]["parties"] == 1
