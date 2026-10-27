"""Vérification de l'adaptateur vers le solveur EXACT de la bibliothèque
``rummikub-solver`` (``scripts/solveur_exact.py``, issue #204, suite de #201).

La bibliothèque est une dépendance de DÉVELOPPEMENT seulement (absente de
requirements.txt et du build Windows, voir CONTEXTE.md §14) : ces tests se
sautent proprement si elle n'est pas installée — comme les tests Playwright.
Pour les exécuter :

    python -m venv .venv-solveur-exact
    .venv-solveur-exact/bin/pip install 'rummikub-solver[highs]' pytest
    .venv-solveur-exact/bin/python -m pytest tests/test_solveur_exact.py
"""

import json
import sys
from pathlib import Path

import pytest

# Saute tout le module si la bibliothèque est absente (comme importorskip des
# tests Playwright) — la vérification exacte n'a alors aucun sens.
pytest.importorskip("rummikub_solver")

# L'adaptateur vit dans scripts/ (dépendance de dev, hors du paquet livré).
_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import solveur_exact  # noqa: E402
from rummikub.moteur.tuiles import Tuile  # noqa: E402
from rummikub.moteur.validation import valider_combinaison  # noqa: E402

_DONNEES = Path(__file__).resolve().parent / "donnees"


def _cas():
    return sorted(_DONNEES.glob("cas_expert_*.json")) + sorted(_DONNEES.glob("reference_*.json"))


# --------------------------------------------------------------------------- #
# Correspondance tuiles <-> entiers de la bibliothèque.
# --------------------------------------------------------------------------- #

def test_correspondance_couleurs_jaune_est_orange():
    # jaune = ORANGE (index 2) : valeur 7 -> 2*13 + 7 = 33.
    assert solveur_exact.tuile_vers_int(Tuile("jaune_7_a", 7, "jaune")) == 33
    assert solveur_exact.int_vers_aspect(33) == ("reel", "jaune", 7)


def test_correspondance_allers_retours_toutes_couleurs():
    for couleur in ("noir", "bleu", "jaune", "rouge"):
        for valeur in range(1, 14):
            n = solveur_exact.tuile_vers_int(Tuile(f"{couleur}_{valeur}_a", valeur, couleur))
            assert solveur_exact.int_vers_aspect(n) == ("reel", couleur, valeur)


def test_correspondance_joker():
    n = solveur_exact.tuile_vers_int(Tuile("joker_1", None, "rouge", est_joker=True))
    assert n == 53
    assert solveur_exact.int_vers_aspect(53) == ("joker", None, None)


# --------------------------------------------------------------------------- #
# Remise dans l'ordre des ensembles non ordonnés.
# --------------------------------------------------------------------------- #

def test_ordonner_suite_place_le_joker_dans_le_trou():
    # Ensemble non ordonné {rouge5, rouge7, joker} -> suite 5,6,7 avec joker au
    # milieu (valide pour valider_suite, qui interdit un joker ailleurs).
    aspects = [("reel", "rouge", 5), ("reel", "rouge", 7), ("joker", None, None)]
    ordonnes, type_ = solveur_exact._ordonner_combinaison(aspects)
    assert type_ == "suite"
    assert ordonnes == [("reel", "rouge", 5), ("joker", None, None), ("reel", "rouge", 7)]


def test_ordonner_groupe_indifferent():
    aspects = [("reel", "rouge", 8), ("reel", "bleu", 8), ("joker", None, None)]
    ordonnes, type_ = solveur_exact._ordonner_combinaison(aspects)
    assert type_ == "groupe"
    assert sorted(a[0] for a in ordonnes) == ["joker", "reel", "reel"]


def test_ordonner_joker_en_bout_reste_dans_les_limites():
    # Deux réels en 12,13 + un joker : pas de place en haut (13 est le max),
    # le joker doit se placer en bas (11,12,13).
    aspects = [("reel", "rouge", 12), ("reel", "rouge", 13), ("joker", None, None)]
    ordonnes, type_ = solveur_exact._ordonner_combinaison(aspects)
    assert type_ == "suite"
    assert ordonnes[0] == ("joker", None, None)
    assert ordonnes[1:] == [("reel", "rouge", 12), ("reel", "rouge", 13)]


# --------------------------------------------------------------------------- #
# Cas de référence : combinaisons valides, conservation, maximum exact.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("chemin", _cas(), ids=lambda p: p.name)
def test_cas_reference_valides_et_conserves(chemin):
    data = json.loads(chemin.read_text(encoding="utf-8"))
    res = solveur_exact.resoudre_exact(data["etat"], data["idx"])

    # Contrôle 1 : chaque combinaison proposée passe notre propre validateur.
    for combo in res.combinaisons:
        r = valider_combinaison(combo)
        assert r["valide"], f"{chemin.name} : combinaison invalide ({r['raison']}) : {combo}"
    assert res.toutes_valides
    # Contrôle 2 : aucune tuile réelle du plateau perdue.
    assert res.conservation_ok

    # Le maximum exact coïncide avec attendu_exact_tuiles (quand présent).
    if "attendu_exact_tuiles" in data:
        assert res.nb_tuiles == data["attendu_exact_tuiles"]


def test_non_regression_victoire_manquee_ines():
    """Cas pivot de la suite : Expert avec 2 tuiles en main n'en a posé qu'une ;
    le solveur exact en trouve 2 (victoire immédiate manquée)."""
    chemin = _DONNEES / "reference_victoire_manquee_ines_tour85.json"
    data = json.loads(chemin.read_text(encoding="utf-8"))
    res = solveur_exact.resoudre_exact(data["etat"], data["idx"])
    assert res.nb_tuiles == 2
    assert res.toutes_valides and res.conservation_ok


def test_bruno_tour57_quatre_tuiles_dont_rouge_12():
    """Bruno tour 57 : le solveur exact pose 4 tuiles (notre solveur 3) — la
    tuile supplémentaire est rouge_12, posée en scindant la suite rouge 6–10."""
    chemin = _DONNEES / "cas_expert_bruno_tour57.json"
    data = json.loads(chemin.read_text(encoding="utf-8"))
    res = solveur_exact.resoudre_exact(data["etat"], data["idx"])
    assert res.nb_tuiles == 4
    assert "rouge_12_b" in res.ids_tuiles


# --------------------------------------------------------------------------- #
# Interface « drop-in » pour le juge exact de l'analyse.
# --------------------------------------------------------------------------- #

def test_resoudre_coup_exact_forme_de_resoudre_coup():
    chemin = _DONNEES / "reference_victoire_manquee_ines_tour85.json"
    data = json.loads(chemin.read_text(encoding="utf-8"))
    coup = solveur_exact.resoudre_coup_exact(data["etat"], data["idx"], budget_temps=1.5)
    assert coup is not None
    assert coup["action"] == "jouer"
    assert len(coup["ids_tuiles"]) == 2
    assert isinstance(coup["nouveau_plateau"], list)
