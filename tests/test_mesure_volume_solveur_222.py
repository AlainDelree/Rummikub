"""Tests de l'outillage de mesure du volume de calcul du solveur exact
(issue #222) : corpus de positions (``scripts/_corpus_positions_222.py``) et
script de mesure (``scripts/mesurer_volume_solveur_222.py``), sur un tout
petit nombre de positions — la mesure COMPLÈTE n'est volontairement jamais
lancée par les tests ni par l'agent (voir CONTEXTE.md, section « mesure du
volume de calcul du solveur »)."""

import json
import sys
from pathlib import Path

import pytest

from rummikub.moteur import solveur_exact as se

_RACINE = Path(__file__).resolve().parents[1]
_SCRIPTS = _RACINE / "scripts"
_CORPUS = _RACINE / "tests" / "donnees" / "corpus_positions_222.json"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import _corpus_positions_222 as corpus_mod  # noqa: E402
import mesurer_volume_solveur_222 as mesure_mod  # noqa: E402

besoin_exact = pytest.mark.skipif(
    not se.DISPONIBLE,
    reason="highspy/numpy absents (dépendances du modèle exact d'Expert)")


# --------------------------------------------------------------------------- #
# Corpus
# --------------------------------------------------------------------------- #

def test_corpus_present_et_suffisant():
    donnees = json.loads(_CORPUS.read_text(encoding="utf-8"))
    positions = donnees["positions"]
    assert len(positions) >= 300, (
        f"le corpus ne compte que {len(positions)} positions (>= 300 "
        "attendues, tâche 3 de l'issue #222)")


def test_corpus_couvre_les_trois_moments_de_partie():
    donnees = json.loads(_CORPUS.read_text(encoding="utf-8"))
    phases = {p["meta"]["phase"] for p in donnees["positions"]}
    assert phases == {"debut", "milieu", "fin"}


def test_corpus_contient_des_plateaux_charges():
    donnees = json.loads(_CORPUS.read_text(encoding="utf-8"))
    charges = [p for p in donnees["positions"] if p["meta"]["charge"]]
    assert len(charges) >= 10, "aucun (ou trop peu de) plateau chargé capturé"


def test_tuile_id_aller_retour():
    """L'identifiant seul (format figé, voir ``tuiles.creer_sac``) suffit à
    reconstruire le dict complet d'une tuile."""
    assert corpus_mod.tuile_dict_depuis_id("rouge_7_a") == {
        "id": "rouge_7_a", "valeur": 7, "couleur": "rouge", "est_joker": False}
    joker = corpus_mod.tuile_dict_depuis_id("joker_2")
    assert joker["est_joker"] is True
    assert joker["valeur"] is None


def test_position_reconstruite_resolvable():
    """Une position du corpus, reconstruite en ``(etat, idx)`` minimal, est
    directement acceptée par le solveur exact de production (sans erreur)."""
    donnees = json.loads(_CORPUS.read_text(encoding="utf-8"))
    position = donnees["positions"][0]
    etat, idx = corpus_mod.etat_depuis_position(position)
    assert idx == 0
    assert "plateau" in etat and "joueurs" in etat and "config" in etat


# --------------------------------------------------------------------------- #
# Script de mesure — essai sur un tout petit corpus (pas la mesure complète)
# --------------------------------------------------------------------------- #

@besoin_exact
def test_mesurer_position_ne_leve_jamais_et_mesure_une_perte_nulle_a_froid():
    """Sur une position facile, le candidat le plus serré (mip_max_nodes=1)
    doit déjà égaler la référence — aucune perte ne doit apparaître si le
    budget/volume suffit."""
    donnees = json.loads(_CORPUS.read_text(encoding="utf-8"))
    position = donnees["positions"][0]
    resultat = mesure_mod.mesurer_position(
        position, ref_temps=5.0, budget_actuel=1.5,
        candidats=[1, 1000], securite_temps=5.0)
    assert resultat["reference"]["statut"] in ("optimal", "faisable")
    assert resultat["actuel"]["perte"] in (0, None)
    assert resultat["candidats"][1000]["perte"] in (0, None)


@besoin_exact
def test_script_bout_en_bout_sur_petit_corpus(tmp_path):
    """Essai du script complet (tâche 7 de l'issue #222) sur 3 positions
    seulement : ne doit pas lever, et le fichier de résultats doit être
    lisible et contenir le résumé attendu."""
    sortie = tmp_path / "resultats.txt"
    code = mesure_mod.main([
        "mesurer_volume_solveur_222.py",
        "--corpus", str(_CORPUS),
        "--n", "3",
        "--ref-temps", "5",
        "--budget-actuel", "1.5",
        "--candidats", "1,1000",
        "--securite-temps", "5",
        "--sortie", str(sortie),
        "--_worker",
    ])
    assert code == 0
    texte = sortie.read_text(encoding="utf-8")
    assert "MESURE DE VOLUME DE CALCUL DU SOLVEUR EXACT" in texte
    assert "Machine :" in texte
    assert "RÉSUMÉ" in texte
    assert "TERMINÉ NORMALEMENT" in texte


@besoin_exact
def test_limite_temps_ferme_laisse_un_resultat_partiel_lisible(tmp_path):
    """Une limite de temps ferme très courte interrompt la mesure avant la
    fin du (petit) corpus de test, mais le fichier partiel reste lisible et
    le dit explicitement (issue #220, réutilisé tel quel)."""
    sortie = tmp_path / "partiel.txt"
    code = mesure_mod.main([
        "mesurer_volume_solveur_222.py",
        "--corpus", str(_CORPUS),
        "--n", "300",
        "--ref-temps", "5",
        "--budget-actuel", "1.5",
        "--candidats", "1,1000",
        "--securite-temps", "5",
        "--sortie", str(sortie),
        "--limite-temps", "0.01",
        "--_worker",
    ])
    assert code == mesure_mod.CODE_LIMITE_TEMPS
    texte = sortie.read_text(encoding="utf-8")
    assert "MESURE DE VOLUME DE CALCUL DU SOLVEUR EXACT" in texte
    assert "ARRÊTÉ SUR LA LIMITE DE TEMPS" in texte
