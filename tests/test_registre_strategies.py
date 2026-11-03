"""Tests du registre unique des stratégies multi-tours de Champion du Monde
(issue #228, point 1) : identifiants, cohérence avec ``BRIDAGES``, et
extension par une seule entrée (sans toucher au reste du code)."""

import pytest

from rummikub.moteur import niveaux


def test_registre_contient_les_sept_strategies_existantes():
    assert set(niveaux.STRATEGIES) == {
        "verif_finition", "garde_joker", "reserve_tuile", "retenue_debut",
        "petits_chiffres", "chances_prochain_tour", "placement_joker"}
    vf = niveaux.STRATEGIES["verif_finition"]
    assert vf.niveaux == ("Expert", "Champion du Monde")
    assert vf.active_par_defaut is True
    gj = niveaux.STRATEGIES["garde_joker"]
    assert gj.niveaux == ("Champion du Monde",)
    assert gj.active_par_defaut is True
    # Les deux stratégies de #229 et celle de #230 sont réservées à Champion
    # du Monde et DÉSACTIVÉES par défaut (à l'étude, non validées par les
    # tests/campagnes).
    rt = niveaux.STRATEGIES["reserve_tuile"]
    assert rt.niveaux == ("Champion du Monde",)
    assert rt.active_par_defaut is False
    rd = niveaux.STRATEGIES["retenue_debut"]
    assert rd.niveaux == ("Champion du Monde",)
    assert rd.active_par_defaut is False
    pc = niveaux.STRATEGIES["petits_chiffres"]
    assert pc.niveaux == ("Champion du Monde",)
    assert pc.active_par_defaut is False
    cpt = niveaux.STRATEGIES["chances_prochain_tour"]
    assert cpt.niveaux == ("Champion du Monde",)
    assert cpt.active_par_defaut is False
    pj = niveaux.STRATEGIES["placement_joker"]
    assert pj.niveaux == ("Champion du Monde",)
    assert pj.active_par_defaut is False


def test_strategies_champion_valides():
    assert set(niveaux.strategies_champion_valides()) == {
        "verif_finition", "garde_joker", "reserve_tuile", "retenue_debut",
        "petits_chiffres", "chances_prochain_tour", "placement_joker"}


def test_strategies_champion_par_defaut_reproduit_bridages_champion():
    """Ce que #228 exige explicitement : la liste par défaut reproduit à
    l'identique l'état actuel de Champion du Monde (aucun changement de
    comportement du jeu)."""
    assert set(niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT) == {
        "verif_finition", "garde_joker"}
    reconstruit = niveaux.bridage_champion_personnalise(
        niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)
    assert reconstruit == niveaux.BRIDAGES["Champion du Monde"]


def test_valider_noms_strategies_leve_sur_nom_inconnu():
    with pytest.raises(ValueError, match="bidon"):
        niveaux.valider_noms_strategies(["garde_joker", "bidon"])
    # Le message liste les noms valides (point 2 de l'issue).
    with pytest.raises(ValueError, match="garde_joker"):
        niveaux.valider_noms_strategies(["bidon"])


def test_valider_noms_strategies_ok_sur_noms_connus():
    niveaux.valider_noms_strategies(["garde_joker", "verif_finition"])
    niveaux.valider_noms_strategies([])


def test_bridage_champion_personnalise_aucune_strategie():
    b = niveaux.bridage_champion_personnalise([])
    assert b.verif_finition is False
    assert b.garder_joker_fin_partie is False
    # Jamais bridé sur perturbation/oubli : Champion du Monde garde le
    # solveur complet quel que soit le jeu de stratégies actives.
    assert b.perturbation_max is None
    assert b.taux_oubli == 0.0


def test_bridage_champion_personnalise_une_seule_strategie():
    b = niveaux.bridage_champion_personnalise(["verif_finition"])
    assert b.verif_finition is True
    assert b.garder_joker_fin_partie is False


def test_bridage_champion_personnalise_leve_sur_nom_inconnu():
    with pytest.raises(ValueError):
        niveaux.bridage_champion_personnalise(["bidon"])


def test_ajouter_une_strategie_fictive_au_registre_sans_toucher_au_reste(monkeypatch):
    """Démonstration directe du point 7 de l'issue : ajouter une stratégie
    ne demande qu'UNE entrée au registre — ``strategies_champion_valides``
    la reflète immédiatement, sans modifier aucune autre fonction."""
    fictive = niveaux.Strategie(
        id="fictive", description="Stratégie fictive de test.",
        niveaux=("Champion du Monde",), active_par_defaut=False)
    monkeypatch.setitem(niveaux.STRATEGIES, "fictive", fictive)
    assert "fictive" in niveaux.strategies_champion_valides()
    # Pas encore dans la liste par défaut du jeu (non validée par les tests) :
    assert "fictive" not in niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT
    b = niveaux.bridage_champion_personnalise(["fictive"])
    # Une stratégie inconnue du constructeur de Bridage (champ non câblé)
    # n'a, par construction, aucun effet sur le Bridage produit — seul son
    # appartenance au registre est vérifiée ici.
    assert b == niveaux.bridage_champion_personnalise([])
