"""Tests de ``scripts/_rapport_duels.py`` (issue #220) : en-tête machine +
version Python + dépendances du solveur exact (#223), et verdict d'écart
entre 60 et 75 %."""

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import _rapport_duels as R  # noqa: E402


def test_entete_machine_contient_nom_et_version_python():
    lignes = R.entete_machine()
    assert "Machine :" in lignes[0]
    assert "Python" in lignes[0]


def test_entete_machine_contient_les_dependances_du_solveur_exact():
    """#223, point 1 : l'en-tête de tout rapport indique l'interpréteur et
    les versions de highspy/numpy."""
    lignes = R.entete_machine()
    assert any(sys.executable in l for l in lignes)
    assert any("highspy" in l and "numpy" in l for l in lignes)


def test_verdict_identiques():
    assert "ÉGALITÉ ATTENDUE" in R.verdict_ecart(0.5, 0.05, identiques=True)


def test_verdict_non_significatif():
    assert R.verdict_ecart(0.52, 0.10) == "non significatif"


def test_verdict_net_60_75():
    assert "net" in R.verdict_ecart(0.68, 0.05) and "très" not in R.verdict_ecart(0.68, 0.05)


def test_verdict_tres_net_au_dessus_de_75():
    assert "très net" in R.verdict_ecart(0.90, 0.05)


def test_verdict_significatif_mais_faible_sous_60():
    assert "faible" in R.verdict_ecart(0.55, 0.02)
