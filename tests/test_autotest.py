"""Tests de l'autotest en ligne de commande (``--autotest``, issue #208).

Couvre : le cas réussi (solveur exact présent et fonctionnel), la simulation de
dépendances absentes (``numpy``/``highspy``), des ressources web manquantes,
l'écriture du rapport dans un fichier, et surtout la garantie que ``--autotest``
**n'importe jamais** l'interface graphique (``pywebview``).

Les tests du cas réussi et des ressources manquantes exigent que
``highspy``/``numpy`` soient installés (sinon on ne dépasse pas l'étape des
dépendances) : ils sont sautés à défaut, comme ``test_solveur_exact_maison.py``.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from rummikub import autotest
from rummikub.moteur import solveur_exact as se

_RACINE = Path(__file__).resolve().parents[1]

besoin_exact = pytest.mark.skipif(
    not se.DISPONIBLE,
    reason="highspy/numpy absents (dépendances du solveur exact d'Expert)")


def _module_importable(nom):
    try:
        __import__(nom)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Cas réussi
# --------------------------------------------------------------------------- #

@besoin_exact
def test_autotest_succes(capsys):
    """Avec highspy/numpy présents, l'autotest résout la position intégrée,
    renvoie 0 et annonce le succès."""
    code = autotest.executer_autotest(argv=[])
    sortie = capsys.readouterr().out
    assert code == 0, sortie
    assert "Autotest reussi" in sortie
    assert "tuiles posees" in sortie
    # Les versions et ressources sont bien affichées.
    assert "numpy" in sortie and "highspy" in sortie
    assert "Ressources web : OK" in sortie


@besoin_exact
def test_autotest_pose_bien_les_six_tuiles():
    """La position intégrée doit poser exactement les 6 tuiles attendues
    (suite 5-6-7 + groupe de 10) — sinon le solveur exact est cassé."""
    etat, idx, attendu = autotest._position_integree()
    res = se.resoudre_exact(etat, idx, budget_temps=5.0)
    assert res.nb_tuiles == attendu == 6
    assert res.valide_globalement


# --------------------------------------------------------------------------- #
# Dépendances absentes (simulées)
# --------------------------------------------------------------------------- #

def test_autotest_numpy_absent(monkeypatch, capsys):
    """numpy introuvable -> code 1 et cause affichée (indépendant de
    l'environnement : on force l'échec d'import)."""
    monkeypatch.setitem(sys.modules, "numpy", None)
    code = autotest.executer_autotest(argv=[])
    sortie = capsys.readouterr().out
    assert code == 1
    assert "numpy introuvable" in sortie


@pytest.mark.skipif(not _module_importable("numpy"),
                    reason="numpy absent : l'étape numpy échouerait avant highspy")
def test_autotest_highspy_absent(monkeypatch, capsys):
    """highspy introuvable (numpy présent) -> code 1 et cause affichée."""
    monkeypatch.setitem(sys.modules, "highspy", None)
    code = autotest.executer_autotest(argv=[])
    sortie = capsys.readouterr().out
    assert code == 1
    assert "highspy introuvable" in sortie


# --------------------------------------------------------------------------- #
# Ressources web manquantes
# --------------------------------------------------------------------------- #

@besoin_exact
def test_autotest_ressources_manquantes(monkeypatch, capsys, tmp_path):
    """Dossier des ressources web absent -> code 1 et cause affichée."""
    import rummikub.config as config
    monkeypatch.setattr(config, "RACINE_WEB", tmp_path / "web_absent")
    code = autotest.executer_autotest(argv=[])
    sortie = capsys.readouterr().out
    assert code == 1
    assert "ressources web absent" in sortie.lower()


# --------------------------------------------------------------------------- #
# Rapport fichier + aucune donnée utilisateur modifiée
# --------------------------------------------------------------------------- #

def test_autotest_ecrit_le_rapport(tmp_path):
    """Un chemin de rapport après --autotest -> le compte rendu y est écrit,
    quel que soit le résultat (succès ou échec)."""
    rapport = tmp_path / "rapport.txt"
    autotest.executer_autotest(argv=["--autotest", str(rapport)])
    assert rapport.exists()
    contenu = rapport.read_text(encoding="utf-8")
    assert "Rummikub --autotest" in contenu


def test_autotest_sans_rapport_nerien_ecrit(tmp_path, monkeypatch):
    """Sans chemin de rapport, aucun fichier n'est créé dans le répertoire
    courant (ne modifie aucune donnée utilisateur)."""
    monkeypatch.chdir(tmp_path)
    autotest.executer_autotest(argv=[])
    assert list(tmp_path.iterdir()) == []


# --------------------------------------------------------------------------- #
# Garantie : --autotest n'importe PAS pywebview (ni l'UI)
# --------------------------------------------------------------------------- #

def test_autotest_nimporte_pas_pywebview(tmp_path):
    """Exécute réellement ``main.py --autotest`` et vérifie que ni ``pywebview``
    ni ``rummikub.ui.application`` ne sont chargés — c'est la raison d'être de
    l'option (ne jamais ouvrir de fenêtre ni charger le moteur graphique)."""
    rapport = tmp_path / "r.txt"
    code = (
        "import sys, runpy\n"
        f"sys.argv = ['main.py', '--autotest', {str(rapport)!r}]\n"
        "rc = 0\n"
        "try:\n"
        "    runpy.run_path('main.py', run_name='__main__')\n"
        "except SystemExit as e:\n"
        "    rc = e.code or 0\n"
        "print('PYWEBVIEW', 'pywebview' in sys.modules)\n"
        "print('UI', 'rummikub.ui.application' in sys.modules)\n"
        "sys.exit(rc)\n"
    )
    proc = subprocess.run([sys.executable, "-c", code],
                          cwd=_RACINE, capture_output=True, text=True)
    assert proc.returncode in (0, 1), proc.stderr
    assert "PYWEBVIEW False" in proc.stdout, proc.stdout + proc.stderr
    assert "UI False" in proc.stdout, proc.stdout + proc.stderr
