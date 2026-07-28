import pytest
from rummikub.moteur.tuiles import creer_sac, distribuer
from rummikub.moteur.validation import valider_combinaison, valider_suite, valider_groupe
from rummikub.moteur.tuiles import Tuile

def t(v, c): return Tuile(f"{c}_{v}_a", v, c)
def j(n=1):  return Tuile(f"joker_{n}", None, None, est_joker=True)

def test_sac_106():
    assert len(creer_sac()) == 106

def test_distribution():
    d = distribuer(creer_sac(), 3)
    assert all(len(c) == 14 for c in d["chevalets"])
    assert len(d["pioche"]) == 106 - 42

def test_suite_valide():
    r = valider_suite([t(5,"rouge"), t(6,"rouge"), t(7,"rouge")])
    assert r["valide"] and r["points"] == 18

def test_suite_invalide_couleur_mixte():
    assert not valider_suite([t(5,"rouge"), t(6,"bleu"), t(7,"rouge")])["valide"]

def test_suite_trop_courte():
    assert not valider_suite([t(5,"rouge"), t(6,"rouge")])["valide"]

def test_suite_avec_joker():
    assert valider_suite([t(5,"rouge"), j(), t(7,"rouge")])["valide"]

def test_groupe_valide():
    r = valider_groupe([t(7,"rouge"), t(7,"bleu"), t(7,"jaune")])
    assert r["valide"] and r["points"] == 21

def test_groupe_doublon_couleur():
    assert not valider_groupe([t(7,"rouge"), t(7,"rouge"), t(7,"jaune")])["valide"]

def test_groupe_5_tuiles():
    assert not valider_groupe([t(7,c) for c in ["rouge","bleu","jaune","noir","rouge"]])["valide"]

def test_valider_combinaison_suite():
    r = valider_combinaison([t(5,"rouge"), t(6,"rouge"), t(7,"rouge")])
    assert r["valide"] and r["type"] == "suite"

def test_valider_combinaison_groupe():
    r = valider_combinaison([t(7,"rouge"), t(7,"bleu"), t(7,"jaune")])
    assert r["valide"] and r["type"] == "groupe"

def test_valider_combinaison_invalide():
    r = valider_combinaison([t(7,"rouge"), t(9,"rouge")])
    assert not r["valide"] and r["type"] is None
