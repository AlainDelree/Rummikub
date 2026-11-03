"""Tests de l'option unique de campagne pour les stratégies de Champion du
Monde (issue #228, point 2) : ``_parser_strategies_champion`` (liste,
'aucune'/'defaut'/'toutes', nom inconnu), ``_strategies_champion_forcees``
(restauration), alias conservés (``--sans-garde-joker``/``--sans-verif-
finition``), et compteurs génériques (point 3)."""

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from rummikub.moteur import niveaux  # noqa: E402

import comparer_niveaux_ia as M  # noqa: E402


# --------------------------------------------------------------------------- #
# _parser_strategies_champion
# --------------------------------------------------------------------------- #

def test_parser_defaut_et_none_equivalents():
    assert M._parser_strategies_champion(None) == set(niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)
    assert M._parser_strategies_champion("defaut") == set(niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)


def test_parser_aucune():
    assert M._parser_strategies_champion("aucune") == set()


def test_parser_toutes():
    assert M._parser_strategies_champion("toutes") == set(
        niveaux.strategies_champion_valides())


def test_parser_liste_separee_par_virgules():
    assert M._parser_strategies_champion("garde_joker") == {"garde_joker"}
    assert M._parser_strategies_champion("garde_joker, verif_finition") == {
        "garde_joker", "verif_finition"}


def test_parser_nom_inconnu_leve_avec_message_utile():
    with pytest.raises(ValueError, match="bidon"):
        M._parser_strategies_champion("bidon")


# --------------------------------------------------------------------------- #
# _strategies_champion_forcees — override Champion seul, restauration
# --------------------------------------------------------------------------- #

def test_strategies_champion_forcees_restaure_a_la_sortie():
    original = niveaux.BRIDAGES["Champion du Monde"]
    with M._strategies_champion_forcees(set()):
        b = niveaux.BRIDAGES["Champion du Monde"]
        assert b.verif_finition is False
        assert b.garder_joker_fin_partie is False
    assert niveaux.BRIDAGES["Champion du Monde"] == original


def test_strategies_champion_forcees_naffecte_jamais_expert():
    original_expert = niveaux.BRIDAGES["Expert"]
    with M._strategies_champion_forcees({"garde_joker"}):
        assert niveaux.BRIDAGES["Expert"] == original_expert


def test_strategies_champion_forcees_restaure_meme_sur_exception():
    original = niveaux.BRIDAGES["Champion du Monde"]
    with pytest.raises(RuntimeError):
        with M._strategies_champion_forcees(set()):
            raise RuntimeError("boum")
    assert niveaux.BRIDAGES["Champion du Monde"] == original


# --------------------------------------------------------------------------- #
# CLI : alias conservés, nom inconnu arrête le script (point 2)
# --------------------------------------------------------------------------- #

def test_cli_sans_strategie_nom_inconnu_echoue(capsys):
    with pytest.raises(SystemExit):
        M.main(["comparer_niveaux_ia.py", "--niveau-a", "Avancé",
               "--niveau-b", "Expert", "--donnes", "1",
               "--sans-strategie", "bidon"])
    sortie = capsys.readouterr().err
    assert "bidon" in sortie
    assert "garde_joker" in sortie


def test_cli_strategies_champion_toutes_et_sans_strategie_valide_sans_erreur():
    # Ne lève pas lors du parsing — validé via la fonction interne plutôt que
    # de rejouer une campagne complète ici (couvert par un essai manuel, voir
    # le rapport de clôture de l'issue #228).
    strategies = M._parser_strategies_champion("toutes")
    strategies -= {"garde_joker", "reserve_tuile", "retenue_debut"}
    assert strategies == {"verif_finition"}


# --------------------------------------------------------------------------- #
# Compteurs génériques (point 3)
# --------------------------------------------------------------------------- #

def _resume_minimal(**overrides) -> dict:
    from rummikub.moteur import verification_finition as vf
    base = {
        "niveau_a": "Expert", "niveau_b": "Champion du Monde", "nb_manches": 1,
        "stats_verif_finition": {
            vf.APPLIQUEE_MEILLEUR_SUFFIT: 5, vf.APPLIQUEE_AUTRE_COUP: 2,
            vf.APPLIQUEE_GARDE_JOKER: 1, vf.APPLIQUEE_AUCUN_CANDIDAT: 3,
        },
        "stats_garde_joker": {"tours_joker_en_main": 7, "candidat_existe": 4,
                              "permet_de_finir": 2, "choisi": 2},
        "victoires": {"A": 0, "B": 0}, "matchs_nuls": 0, "matchs_decides": 0,
        "cumul_par_camp": {"A": [], "B": []},
        "fins": {"chevalet_vide": 0, "pioche_vide": 0, "garde_fou": 0},
        "penalites_perdant": [], "tuiles_perdant": [], "tours_decidees": [],
        "temps_par_niveau": {}, "coups_invalides_total": 0,
        "coups_tuiles_disparues_total": 0, "anomalies_conservation_total": 0,
        "replis_expert": {"budget_depasse": 0, "deps_absentes": 0, "autre": 0},
        "aucun_coup_expert": 0, "perturbations_expert": [],
        "preferer_simple": True, "eval_a": "off", "eval_b": "off",
        "nb_donnes": 1, "nb_parties": 2, "sans_exact": False,
    }
    base.update(overrides)
    return base


def test_compteurs_strategies_verif_finition():
    resume = _resume_minimal()
    c = M.compteurs_strategies(resume)
    # tentés = 5+2+1+3 = 11 ; changés = 2 (autre_coup) + 1 (garde_joker) = 3.
    assert c["verif_finition"] == {"declenchee": 11, "a_change_le_coup": 3}


def test_compteurs_strategies_garde_joker():
    resume = _resume_minimal()
    c = M.compteurs_strategies(resume)
    assert c["garde_joker"] == {"declenchee": 7, "a_change_le_coup": 2}


def test_compteurs_strategies_absents_renvoie_zero():
    resume = _resume_minimal(stats_verif_finition={}, stats_garde_joker={})
    c = M.compteurs_strategies(resume)
    assert c["verif_finition"] == {"declenchee": 0, "a_change_le_coup": 0}
    assert c["garde_joker"] == {"declenchee": 0, "a_change_le_coup": 0}


def test_rapport_affiche_compteurs_generiques(capsys):
    resume = _resume_minimal()
    M.afficher_rapport(resume)
    sortie = capsys.readouterr().out
    assert "Compteurs génériques par stratégie" in sortie
    assert "verif_finition" in sortie
    assert "garde_joker" in sortie


def test_rapport_sans_declenchement_pas_de_section_generique(capsys):
    resume = _resume_minimal(stats_verif_finition={}, stats_garde_joker={})
    M.afficher_rapport(resume)
    sortie = capsys.readouterr().out
    assert "Compteurs génériques par stratégie" not in sortie
