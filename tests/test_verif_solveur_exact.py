"""Tests du garde-fou « échec franc sans solveur exact » (issue #223, point 1)
et de ses relais dans ``scripts/comparer_niveaux_ia.py`` — l'incident qui a
motivé cette issue : une campagne de comparaison lancée depuis un terminal
pointant vers un AUTRE interpréteur Python, sans ``highspy``/``numpy``,
tournant à vide sans que rien ne le signale.

Ne touche à AUCUN comportement du jeu : ces tests ne couvrent que les
scripts de mesure."""

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from rummikub.moteur import solveur_exact as se  # noqa: E402

import _verif_solveur_exact as V  # noqa: E402
import comparer_niveaux_ia as M  # noqa: E402


# --------------------------------------------------------------------------- #
# Garde-fou lui-même (``_verif_solveur_exact.py``)
# --------------------------------------------------------------------------- #

def test_disponible_ne_fait_rien():
    """Solveur exact disponible (cas normal de cet environnement de test) :
    aucun arrêt, quel que soit ``sans_exact``."""
    assert se.DISPONIBLE, "ce test suppose highspy/numpy installés ici"
    V.exiger_solveur_exact_ou_quitter(sans_exact=False)
    V.exiger_solveur_exact_ou_quitter(sans_exact=True)


def test_indisponible_arrete_avec_code_non_nul_et_nomme_interpreteur(
        monkeypatch, capsys):
    """Simule l'absence de highspy/numpy (incident #223) : le script doit
    s'arrêter FRANCHEMENT (code de sortie non nul) avec un message qui NOMME
    l'interpréteur Python réellement utilisé — pour qu'Alain puisse
    identifier immédiatement le mauvais terminal/venv, contrairement à
    l'incident d'origine."""
    monkeypatch.setattr(se, "DISPONIBLE", False)
    with pytest.raises(SystemExit) as exc:
        V.exiger_solveur_exact_ou_quitter(sans_exact=False)
    assert exc.value.code != 0
    message = capsys.readouterr().err
    assert sys.executable in message
    assert "highspy" in message or "numpy" in message


def test_indisponible_mais_sans_exact_ne_s_arrete_pas(monkeypatch):
    """``--sans-exact`` est une désactivation VOLONTAIRE et assumée : jamais
    concernée par ce garde-fou, même si les dépendances manquent réellement."""
    monkeypatch.setattr(se, "DISPONIBLE", False)
    V.exiger_solveur_exact_ou_quitter(sans_exact=True)  # ne lève pas


def test_entete_dependances_nomme_interpreteur_et_versions():
    lignes = V.entete_dependances(sans_exact=False)
    assert any(sys.executable in l for l in lignes)
    assert any("highspy" in l and "numpy" in l for l in lignes)


def test_entete_dependances_sans_exact_dit_volontaire():
    lignes = V.entete_dependances(sans_exact=True)
    assert any("volontairement" in l for l in lignes)
    assert not any("ABSENT" in l for l in lignes)


# --------------------------------------------------------------------------- #
# Relais dans comparer_niveaux_ia.py (point 1) : main() s'arrête pareil
# --------------------------------------------------------------------------- #

def test_main_s_arrete_sans_solveur_exact(monkeypatch, capsys):
    monkeypatch.setattr(M.solveur_exact, "DISPONIBLE", False)
    with pytest.raises(SystemExit) as exc:
        M.main(["comparer_niveaux_ia.py", "--niveau-a", "Avancé",
               "--niveau-b", "Expert", "--donnes", "1"])
    assert exc.value.code != 0
    assert sys.executable in capsys.readouterr().err


