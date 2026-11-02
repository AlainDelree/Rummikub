"""Tests du garde-fou « échec franc sans solveur exact » (issue #223, point 1)
et de ses relais dans tous les scripts qui font jouer Avancé/Expert/Champion
du Monde (issue #224, qui étend la liste de #223) — l'incident qui a motivé
cette issue : une campagne de comparaison lancée depuis un terminal pointant
vers un AUTRE interpréteur Python, sans ``highspy``/``numpy``, tournant à vide
sans que rien ne le signale.

Ne touche à AUCUN comportement du jeu : ces tests ne couvrent que les
scripts de mesure."""

import runpy
import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[1]
_SCRIPTS = _RACINE / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from rummikub.moteur import solveur_exact as se  # noqa: E402

import _verif_solveur_exact as V  # noqa: E402
import comparer_niveaux_ia as M  # noqa: E402
import simulation_ia as M_simulation  # noqa: E402
import profil_joueur as M_profil  # noqa: E402
import calibrer_niveaux as M_calibrer  # noqa: E402
import verifier_simplicite_expert as M_simplicite  # noqa: E402
import generer_corpus_positions_222 as M_corpus  # noqa: E402
import match_solveurs as M_match  # noqa: E402


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


# --------------------------------------------------------------------------- #
# Relais dans les scripts étendus par l'issue #224 (point 2) : chacun doit
# s'arrêter FRANCHEMENT (code non nul, message nommant l'interpréteur) quand
# le solveur exact n'est pas importable — sans aucune simulation longue,
# ``se.DISPONIBLE`` est monkeypatché AVANT tout calcul.
# --------------------------------------------------------------------------- #

def test_simulation_ia_s_arrete_sans_solveur_exact(monkeypatch, capsys):
    monkeypatch.setattr(se, "DISPONIBLE", False)
    with pytest.raises(SystemExit) as exc:
        M_simulation.main(["simulation_ia.py", "--joueurs", "2"])
    assert exc.value.code != 0
    assert sys.executable in capsys.readouterr().err


def test_profil_joueur_s_arrete_sans_solveur_exact(monkeypatch, capsys):
    monkeypatch.setattr(se, "DISPONIBLE", False)
    with pytest.raises(SystemExit) as exc:
        M_profil.main(["profil_joueur.py", "--niveau", "Débutant",
                       "--donnes", "1"])
    assert exc.value.code != 0
    assert sys.executable in capsys.readouterr().err


def test_calibrer_niveaux_s_arrete_sans_solveur_exact(monkeypatch, capsys):
    monkeypatch.setattr(se, "DISPONIBLE", False)
    with pytest.raises(SystemExit) as exc:
        M_calibrer.main(["calibrer_niveaux.py", "--niveau", "Débutant",
                         "--donnes", "1", "--perturbations", "0",
                         "--oublis", "0.0"])
    assert exc.value.code != 0
    assert sys.executable in capsys.readouterr().err


def test_verifier_simplicite_expert_s_arrete_sans_solveur_exact(
        monkeypatch, capsys):
    monkeypatch.setattr(se, "DISPONIBLE", False)
    with pytest.raises(SystemExit) as exc:
        M_simplicite.main(["verifier_simplicite_expert.py", "--donnes", "1"])
    assert exc.value.code != 0
    assert sys.executable in capsys.readouterr().err


def test_generer_corpus_positions_222_s_arrete_sans_solveur_exact(
        monkeypatch, capsys):
    monkeypatch.setattr(se, "DISPONIBLE", False)
    with pytest.raises(SystemExit) as exc:
        M_corpus.main(["generer_corpus_positions_222.py", "--cible", "1"])
    assert exc.value.code != 0
    assert sys.executable in capsys.readouterr().err


def test_match_solveurs_s_arrete_sans_solveur_exact(
        monkeypatch, capsys, tmp_path):
    """Le garde-fou (modèle exact maison) s'arrête AVANT même le contrôle de
    la bibliothèque externe ``rummikub-solver`` (#212) — qui, lui, reste
    indépendant (voir ``test_match_solveurs.py``)."""
    monkeypatch.setattr(M_match.solveur_maison, "DISPONIBLE", False)
    with pytest.raises(SystemExit) as exc:
        M_match.main(["match_solveurs.py", "--donnes", "1", "--sortie",
                     str(tmp_path / "sortie.txt")])
    assert exc.value.code != 0
    assert sys.executable in capsys.readouterr().err


def test_campagne_186_s_arrete_sans_solveur_exact(monkeypatch, capsys):
    """``_campagne_186.py`` exécute son garde-fou au niveau MODULE (script
    historique sans fonction ``main``) : on le charge avec ``runpy`` sous
    dépendances absentes."""
    monkeypatch.setattr(se, "DISPONIBLE", False)
    monkeypatch.setattr(sys, "argv", ["_campagne_186.py", "--donnes", "1"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(_SCRIPTS / "_campagne_186.py"), run_name="__main__")
    assert exc.value.code != 0
    assert sys.executable in capsys.readouterr().err


