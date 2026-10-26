import pytest
from rummikub.moteur.tuiles import Tuile, creer_sac, distribuer
from rummikub.moteur.validation import (valider_suite, valider_groupe,
                                         valider_combinaison, valider_plateau)
from rummikub.moteur.partie import (creer_partie, jouer_tour, piocher,
                                     backup_debut_tour, annuler_tour)


def t(v, c): return Tuile(f"{c}_{v}_a", v, c)
def j(n=1):  return Tuile(f"joker_{n}", None, None, est_joker=True)


def test_sac_106():
    assert len(creer_sac()) == 106


def test_distribution_3_joueurs():
    d = distribuer(creer_sac(), 3)
    assert all(len(c) == 14 for c in d["chevalets"])
    assert len(d["pioche"]) == 106 - 42


def test_distribution_4_joueurs():
    d = distribuer(creer_sac(), 4)
    assert len(d["pioche"]) == 106 - 56


def test_suite_valide():
    r = valider_suite([t(5, "rouge"), t(6, "rouge"), t(7, "rouge")])
    assert r["valide"] and r["points"] == 18


def test_suite_invalide_couleur():
    assert not valider_suite([t(5, "rouge"), t(6, "bleu"), t(7, "rouge")])["valide"]


def test_suite_trop_courte():
    assert not valider_suite([t(5, "rouge"), t(6, "rouge")])["valide"]


def test_suite_avec_joker_interne():
    r = valider_suite([t(5, "rouge"), j(), t(7, "rouge")])
    assert r["valide"] and r["points"] == 18


def test_suite_avec_joker_extension():
    r = valider_suite([t(5, "rouge"), t(6, "rouge"), t(7, "rouge"), j()])
    assert r["valide"] and r["points"] == 5 + 6 + 7 + 8


def test_groupe_valide():
    r = valider_groupe([t(7, "rouge"), t(7, "bleu"), t(7, "jaune")])
    assert r["valide"] and r["points"] == 21


def test_groupe_doublon_couleur():
    assert not valider_groupe([t(7, "rouge"), t(7, "rouge"), t(7, "jaune")])["valide"]


def test_groupe_5_tuiles():
    assert not valider_groupe([t(7, c) for c in ["rouge", "bleu", "jaune", "noir", "rouge"]])["valide"]


def test_groupe_avec_joker():
    r = valider_groupe([t(7, "rouge"), t(7, "bleu"), j()])
    assert r["valide"] and r["points"] == 21


def test_valider_combinaison_suite():
    r = valider_combinaison([t(5, "rouge"), t(6, "rouge"), t(7, "rouge")])
    assert r["valide"] and r["type"] == "suite"


def test_valider_combinaison_groupe():
    r = valider_combinaison([t(7, "rouge"), t(7, "bleu"), t(7, "jaune")])
    assert r["valide"] and r["type"] == "groupe"


def test_valider_combinaison_invalide():
    r = valider_combinaison([t(7, "rouge"), t(9, "rouge")])
    assert not r["valide"] and r["type"] is None


def test_valider_plateau_valide():
    r = valider_plateau([[t(5, "rouge"), t(6, "rouge"), t(7, "rouge")]])
    assert r["valide"] and r["erreurs"] == []


def test_valider_plateau_invalide():
    r = valider_plateau([[t(7, "rouge"), t(9, "rouge")]])
    assert not r["valide"]


def test_creer_partie_106_tuiles():
    etat = creer_partie(
        [{"nom": "A", "est_ia": False}, {"nom": "B", "est_ia": True, "niveau": "Facile"}],
        {"nb_manches": 1, "valeur_joker_penalite": 30, "mise_initiale_min": 30})
    total = (sum(len(j["chevalet"]) for j in etat["joueurs"])
             + len(etat["pioche"]))
    assert total == 106


def test_piocher():
    etat = creer_partie(
        [{"nom": "A", "est_ia": False}, {"nom": "B", "est_ia": True, "niveau": "Facile"}],
        {"nb_manches": 1, "valeur_joker_penalite": 30, "mise_initiale_min": 30})
    before = len(etat["joueurs"][0]["chevalet"])
    res = piocher(etat, 1)
    assert res["ok"]
    assert len(res["etat"]["joueurs"][0]["chevalet"]) == before + 1


def test_annuler_tour():
    etat = creer_partie(
        [{"nom": "A", "est_ia": False}, {"nom": "B", "est_ia": True, "niveau": "Facile"}],
        {"nb_manches": 1, "valeur_joker_penalite": 30, "mise_initiale_min": 30})
    backup_debut_tour(etat)
    nb_avant = len(etat["joueurs"][0]["chevalet"])
    piocher(etat, 3)
    annuler_tour(etat)
    assert len(etat["joueurs"][0]["chevalet"]) == nb_avant


def test_jouer_tour_refuse_si_des_tuiles_du_plateau_disparaissent():
    """Issue #187 : jouer_tour doit refuser tout coup dont le plateau
    résultant ne contient plus toutes les tuiles présentes en début de
    tour, même si chaque combinaison proposée est individuellement valide
    (ex. une combinaison déjà posée, amputée par erreur du plateau
    résultant)."""
    etat = creer_partie(
        [{"nom": "A", "est_ia": False}, {"nom": "B", "est_ia": True, "niveau": "Facile"}],
        {"nb_manches": 1, "valeur_joker_penalite": 30, "mise_initiale_min": 30})
    combo_a = [t(5, "rouge"), t(6, "rouge"), t(7, "rouge")]
    combo_b = [t(7, "bleu"), t(7, "jaune"), t(7, "noir")]
    etat["plateau"] = [[x.as_dict() for x in combo_a],
                       [x.as_dict() for x in combo_b]]
    etat["index_joueur_actuel"] = 0
    etat["joueurs"][0]["mise_initiale_faite"] = True
    etat["joueurs"][0]["chevalet"] = [t(1, "noir").as_dict(),
                                      t(2, "noir").as_dict(),
                                      t(3, "noir").as_dict()]

    # Plateau proposé : combo_a conservée, mais combo_b a disparu (remplacée
    # par une nouvelle combinaison valide formée depuis la main seule) —
    # exactement le symptôme du bug #187 (coup individuellement valide,
    # mais qui perd des tuiles déjà posées).
    nouveau_plateau = [[x.as_dict() for x in combo_a],
                       [t(1, "noir").as_dict(), t(2, "noir").as_dict(),
                        t(3, "noir").as_dict()]]
    res = jouer_tour(etat, ["noir_1_a", "noir_2_a", "noir_3_a"], nouveau_plateau)

    assert res["ok"] is False
    assert "disparu" in res["erreur"]
    assert set(res["tuiles_disparues"]) == {"bleu_7_a", "jaune_7_a", "noir_7_a"}
    # Le plateau d'origine ne doit pas avoir été modifié par le coup refusé.
    assert etat["plateau"] == [[x.as_dict() for x in combo_a],
                               [x.as_dict() for x in combo_b]]
