"""Tests de l'échelle des six niveaux et de l'affaiblissement paramétré
(issue #213) : perturbation maximale, taux d'oubli, reproductibilité, repli
sans dépendances, et niveau « Champion du Monde ».
"""

import copy
import json
from pathlib import Path

import pytest

from rummikub.config import NIVEAUX
from rummikub.moteur import niveaux
from rummikub.moteur import ia
from rummikub.moteur.ia import (
    jouer_ia, jouer_niveau_bride, _coup_selon_perturbation, NIVEAUX_IA,
    SOLVEUR_EXACT, SOLVEUR_RECHERCHE, SOLVEUR_AVANCE,
)
from rummikub.moteur.partie import creer_partie
from rummikub.moteur.solveur import mesurer_perturbation
from rummikub.moteur.validation import valider_plateau
from rummikub.moteur.tuiles import tuile_depuis_dict

_DONNEES = Path(__file__).resolve().parent / "donnees"


class _RngFixe:
    """RNG factice : ``random()`` renvoie toujours ``valeur`` (pour forcer ou
    empêcher le déclenchement de l'oubli de façon déterministe)."""
    def __init__(self, valeur):
        self.valeur = valeur

    def random(self):
        return self.valeur


def _partie_2j(niveau="Débutant", graine_ia=None):
    return creer_partie(
        [{"nom": "Humain", "est_ia": False, "niveau": None},
         {"nom": "Bot", "est_ia": True, "niveau": niveau}],
        {"nb_manches": 1, "valeur_joker_penalite": 30,
         "mise_initiale_min": 30, "graine_ia": graine_ia})


def _etat_joker_recuperable(niveau="Facile"):
    """Plateau : suite rouge 4-5-(joker). La récupération du joker (coup riche,
    4 tuiles) exige de RÉARRANGER le plateau ; l'extension par le rouge 7 (1
    tuile) ne déplace rien. Repris de tests/test_ia.py."""
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


# --------------------------------------------------------------------------- #
# L'échelle et le nouveau niveau
# --------------------------------------------------------------------------- #

def test_echelle_a_six_niveaux_avec_champion():
    assert NIVEAUX == ["Débutant", "Facile", "Intermédiaire", "Avancé",
                       "Expert", "Champion du Monde"]
    assert list(NIVEAUX_IA) == NIVEAUX
    assert set(niveaux.BRIDAGES) == set(NIVEAUX)


def test_champion_du_monde_action_valide():
    etat = _partie_2j("Champion du Monde")
    etat["index_joueur_actuel"] = 1
    res = jouer_ia(etat, 1)
    assert res["action"] in ("jouer", "piocher", "passer")


def test_niveau_inconnu_retombe_debutant():
    # Une partie sauvegardée avec un libellé disparu reste jouable.
    assert niveaux.bridage_pour("Niveau fantôme") is niveaux.BRIDAGES["Débutant"]
    etat = _partie_2j("Niveau fantôme")
    etat["index_joueur_actuel"] = 1
    res = jouer_ia(etat, 1)
    assert res["action"] in ("jouer", "piocher", "passer")


# --------------------------------------------------------------------------- #
# Paramètre : perturbation maximale du plateau
# --------------------------------------------------------------------------- #

def test_perturbation_max_nulle_ne_deplace_aucune_tuile():
    etat = _etat_joker_recuperable()
    coup = _coup_selon_perturbation(etat, 1, perturbation_max=0,
                                    budget_temps=None, on_repli=None)
    assert coup["action"] == "jouer"
    # L'extension simple (rouge 7), aucune recomposition du plateau.
    assert set(coup["ids_tuiles"]) == {"rouge_7_a"}
    deplacees, _ = mesurer_perturbation(etat["plateau"], coup["nouveau_plateau"])
    assert deplacees == 0


def test_perturbation_max_illimitee_recupere_le_joker():
    etat = _etat_joker_recuperable()
    coup = _coup_selon_perturbation(etat, 1, perturbation_max=None,
                                    budget_temps=None, on_repli=None)
    assert coup["action"] == "jouer"
    # Sans limite, le solveur complet récupère le joker (4 tuiles posées).
    assert set(coup["ids_tuiles"]) == {
        "rouge_6_b", "noir_9_a", "bleu_9_a", "rouge_7_a"}


@pytest.mark.parametrize("pmax", [0, 1, 2, 3, 5])
def test_perturbation_respecte_la_borne(pmax):
    """Quelle que soit la borne, le coup choisi ne déplace jamais plus de
    ``pmax`` tuiles du plateau (soit le coup sans réarrangement, 0 déplacée,
    soit le coup complet s'il tient dans la borne)."""
    etat = _etat_joker_recuperable()
    coup = _coup_selon_perturbation(etat, 1, perturbation_max=pmax,
                                    budget_temps=None, on_repli=None)
    if coup["action"] == "jouer":
        deplacees, _ = mesurer_perturbation(etat["plateau"],
                                            coup["nouveau_plateau"])
        assert deplacees <= pmax
        plateau = [[tuile_depuis_dict(d) for d in c]
                   for c in coup["nouveau_plateau"]]
        assert valider_plateau(plateau)["valide"]


# --------------------------------------------------------------------------- #
# Paramètre : taux d'oubli
# --------------------------------------------------------------------------- #

def test_oubli_declenche_pioche_coup_non_gagnant():
    etat = _etat_joker_recuperable("Facile")  # main de 4 tuiles, coup non gagnant
    coup = jouer_niveau_bride(etat, 1, "Facile", rng=_RngFixe(0.0))
    assert coup["action"] == "piocher"
    assert coup.get("oubli") is True


def test_sans_oubli_le_coup_est_joue():
    etat = _etat_joker_recuperable("Facile")
    coup = jouer_niveau_bride(etat, 1, "Facile", rng=_RngFixe(0.999))
    assert coup["action"] == "jouer"


def test_oubli_100pct_pioche_toujours(monkeypatch):
    monkeypatch.setitem(niveaux.BRIDAGES, "Facile",
                        niveaux.Bridage(perturbation_max=0, taux_oubli=1.0))
    etat = _etat_joker_recuperable("Facile")
    # Main de 4 tuiles, coup non gagnant → oubli effectif > 0, tirage 0.0 → pioche.
    coup = jouer_niveau_bride(etat, 1, "Facile", rng=_RngFixe(0.0))
    assert coup["action"] == "piocher"


def test_coup_gagnant_jamais_oublie(monkeypatch):
    """Un coup qui vide le chevalet n'est jamais oublié, même à 100 % d'oubli."""
    monkeypatch.setitem(niveaux.BRIDAGES, "Débutant",
                        niveaux.Bridage(perturbation_max=None, taux_oubli=1.0))
    etat = _partie_2j("Débutant")
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = []
    # Main = exactement un groupe de 3 → le poser vide le chevalet (victoire).
    bot["chevalet"] = [
        {"id": "rouge_7_a", "valeur": 7, "couleur": "rouge", "est_joker": False},
        {"id": "bleu_7_a", "valeur": 7, "couleur": "bleu", "est_joker": False},
        {"id": "noir_7_a", "valeur": 7, "couleur": "noir", "est_joker": False},
    ]
    coup = jouer_niveau_bride(etat, 1, "Débutant", rng=_RngFixe(0.0))
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_7_a", "bleu_7_a", "noir_7_a"}


def test_oubli_decroit_quand_la_main_est_petite():
    # Jamais d'oubli avec une seule tuile en main, quel que soit le taux.
    assert niveaux.taux_oubli_effectif(0.9, 1) == 0.0
    # Plein taux au-dessus du seuil, décroissance linéaire en dessous.
    assert niveaux.taux_oubli_effectif(0.3, niveaux.SEUIL_OUBLI) == pytest.approx(0.3)
    assert niveaux.taux_oubli_effectif(0.3, 4) < 0.3


# --------------------------------------------------------------------------- #
# Reproductibilité sous graine
# --------------------------------------------------------------------------- #

def test_reproductibilite_meme_graine():
    etat = _partie_2j("Intermédiaire", graine_ia=12345)
    etat["index_joueur_actuel"] = 1
    etat["joueurs"][1]["mise_initiale_faite"] = True
    r1 = jouer_ia(copy.deepcopy(etat), 1)
    r2 = jouer_ia(copy.deepcopy(etat), 1)
    assert r1["action"] == r2["action"]
    assert r1.get("ids_tuiles") == r2.get("ids_tuiles")


# --------------------------------------------------------------------------- #
# Champion du Monde atteint le maximum exact
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("fichier", [
    "reference_victoire_manquee_ines_tour85.json",
    "cas_expert_coup_simple_david_tour31.json",
])
def test_champion_atteint_le_maximum_exact(fichier):
    cas = json.loads((_DONNEES / fichier).read_text(encoding="utf-8"))
    etat = cas["etat"]
    idx = cas["idx"]
    etat.setdefault("config", {})["graine_ia"] = 0
    coup = jouer_niveau_bride(etat, idx, "Champion du Monde", budget_temps=10.0)
    assert coup["action"] == "jouer"
    assert len(coup["ids_tuiles"]) == cas["attendu_exact_tuiles"]


# --------------------------------------------------------------------------- #
# Repli propre sans highspy / numpy
# --------------------------------------------------------------------------- #

def test_repli_sans_dependances(monkeypatch):
    """Quand le modèle exact est indisponible, les niveaux se replient sans
    erreur sur la recherche arborescente (puis Avancé), et le mécanisme est
    tracé (``solveur`` ≠ ``exact``)."""
    monkeypatch.setattr("rummikub.moteur.solveur_exact.DISPONIBLE", False)
    etat = _etat_joker_recuperable("Champion du Monde")
    coup = jouer_niveau_bride(etat, 1, "Champion du Monde", rng=_RngFixe(0.999))
    assert coup["action"] in ("jouer", "piocher", "passer")
    if coup["action"] == "jouer":
        assert coup.get("solveur") in (SOLVEUR_RECHERCHE, SOLVEUR_AVANCE)
        assert coup.get("solveur") != SOLVEUR_EXACT
