"""Tests de la validation SEC-003 des chemins du flag Actualise (issue #234,
miroir Scrabble #482) : ``rummikub.actualise.valider_chemin_actualise``.

La racine autorisée est paramétrable (argument ``racine``), ce qui rend ces
tests exécutables sous Linux malgré la racine de production ``C:\\Actualise``.
"""
from pathlib import Path

from rummikub.actualise import valider_chemin_actualise


def _creer(chemin: Path, contenu: str = "") -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(contenu, encoding="utf-8")
    return chemin


def test_chemin_valide_sous_la_racine_est_accepte(tmp_path):
    racine = tmp_path / "Actualise"
    cible = _creer(racine / "updater_rummikub.bat", "echo ok")
    resultat = valider_chemin_actualise(str(cible), racine=racine)
    assert resultat == cible.resolve()


def test_chemin_exe_sous_la_racine_est_accepte(tmp_path):
    racine = tmp_path / "Actualise"
    cible = _creer(racine / "ActualiseUI.exe")
    resultat = valider_chemin_actualise(str(cible), racine=racine)
    assert resultat == cible.resolve()


def test_chemin_inexistant_est_rejete(tmp_path):
    racine = tmp_path / "Actualise"
    racine.mkdir()
    absent = racine / "updater_rummikub.bat"
    assert valider_chemin_actualise(str(absent), racine=racine) is None


def test_mauvaise_extension_est_rejetee(tmp_path):
    racine = tmp_path / "Actualise"
    cible = _creer(racine / "updater_rummikub.sh", "echo ok")
    assert valider_chemin_actualise(str(cible), racine=racine) is None


def test_chemin_hors_de_la_racine_est_rejete(tmp_path):
    racine = tmp_path / "Actualise"
    racine.mkdir()
    ailleurs = _creer(tmp_path / "Ailleurs" / "updater.bat", "echo ok")
    assert valider_chemin_actualise(str(ailleurs), racine=racine) is None


def test_chemin_qui_s_echappe_par_dot_dot_est_rejete(tmp_path):
    racine = tmp_path / "Actualise"
    racine.mkdir()
    ailleurs = _creer(tmp_path / "Ailleurs" / "updater.bat", "echo ok")
    # Construit un chemin syntaxiquement sous la racine mais qui s'en évade
    # via ``..`` une fois résolu.
    evasion = racine / ".." / "Ailleurs" / "updater.bat"
    assert valider_chemin_actualise(str(evasion), racine=racine) is None
    assert ailleurs.exists()  # inchangé : aucune action n'a été tentée


def test_chemin_vide_ou_none_est_rejete(tmp_path):
    racine = tmp_path / "Actualise"
    assert valider_chemin_actualise(None, racine=racine) is None
    assert valider_chemin_actualise("", racine=racine) is None


def test_racine_par_defaut_utilisee_si_non_fournie(tmp_path, monkeypatch):
    import rummikub.actualise as mod
    racine = tmp_path / "Actualise"
    cible = _creer(racine / "updater.bat", "echo ok")
    monkeypatch.setattr(mod, "RACINE_ACTUALISE", racine)
    assert valider_chemin_actualise(str(cible)) == cible.resolve()
