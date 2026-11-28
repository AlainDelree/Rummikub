"""Tests de bout en bout du traitement du flag ``actualise_update.flag``
(issue #234, SEC-003) : ``main._lancer_actualise_ui_si_flag`` et
``rummikub.ui.application._handler_fermeture_actualise`` ne doivent lancer
AUCUN processus pour un chemin invalide, et lancer le processus validé SANS
passer par le shell.
"""
import json
import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parent.parent
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

import main as _main_module
from rummikub import actualise as _actualise_mod
from rummikub.ui import application as _application_module


class _PopenAppels:
    """Capture les appels à subprocess.Popen sans lancer de vrai processus."""

    def __init__(self):
        self.appels = []

    def __call__(self, args, **kwargs):
        self.appels.append((args, kwargs))

        class _Faux:
            pid = 4242
        return _Faux()


def _preparer_exe(dossier: Path, nom: str) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / nom
    cible.write_text("", encoding="utf-8")
    return cible


@pytest.fixture
def racine_actualise(tmp_path, monkeypatch):
    racine = tmp_path / "Actualise"
    monkeypatch.setattr(_actualise_mod, "RACINE_ACTUALISE", racine)
    return racine


@pytest.fixture
def dossier_install(tmp_path, monkeypatch):
    """Simule le dossier d'installation (parent de sys.executable)."""
    dossier = tmp_path / "install"
    dossier.mkdir()
    faux_exe = dossier / "Rummikub.exe"
    faux_exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "executable", str(faux_exe))
    return dossier


def _ecrire_flag(dossier_install: Path, data: dict) -> Path:
    flag = dossier_install / "actualise_update.flag"
    flag.write_text(json.dumps(data), encoding="utf-8")
    return flag


# --------------------------------------------------------------------------- #
# main._lancer_actualise_ui_si_flag
# --------------------------------------------------------------------------- #

def test_main_drapeau_absent_ne_lance_rien(dossier_install, monkeypatch):
    popen = _PopenAppels()
    monkeypatch.setattr(_main_module.subprocess, "Popen", popen)
    _main_module._lancer_actualise_ui_si_flag()
    assert popen.appels == []


def test_main_drapeau_illisible_ne_lance_rien_et_ne_plante_pas(
        dossier_install, monkeypatch):
    (dossier_install / "actualise_update.flag").write_text(
        "{ceci n'est pas du json", encoding="utf-8")
    popen = _PopenAppels()
    monkeypatch.setattr(_main_module.subprocess, "Popen", popen)
    _main_module._lancer_actualise_ui_si_flag()  # ne doit pas lever
    assert popen.appels == []


def test_main_chemins_valides_lancent_sans_shell(
        dossier_install, racine_actualise, monkeypatch):
    actualise_ui = _preparer_exe(racine_actualise, "ActualiseUI.exe")
    bat = _preparer_exe(racine_actualise, "updater_rummikub.bat")
    _ecrire_flag(dossier_install, {
        "actualise_ui": str(actualise_ui), "bat": str(bat)})
    popen = _PopenAppels()
    monkeypatch.setattr(_main_module.subprocess, "Popen", popen)
    _main_module._lancer_actualise_ui_si_flag()
    assert len(popen.appels) == 1
    args, kwargs = popen.appels[0]
    # Assertions de sécurité AVANT la comparaison de chemins : un défaut de
    # comparaison de chemins (voir plus bas) ne doit jamais les masquer.
    assert isinstance(args, list)
    assert kwargs.get("shell", False) is False
    # Comparaison par ``Path`` résolu, jamais par texte : sous Windows,
    # ``Path.as_posix()`` écrit des barres obliques (``C:/...``) alors que
    # les arguments passés à ``Popen`` gardent les barres inverses natives
    # (``C:\...``) — mêmes fichiers, textes différents.
    assert Path(args[0]).resolve() == actualise_ui.resolve()
    assert bat.resolve() in [Path(a).resolve() for a in args]


def test_main_chemin_hors_racine_ne_lance_rien(
        dossier_install, racine_actualise, tmp_path, monkeypatch):
    actualise_ui = _preparer_exe(racine_actualise, "ActualiseUI.exe")
    bat_hors_racine = _preparer_exe(tmp_path / "Ailleurs", "updater.bat")
    _ecrire_flag(dossier_install, {
        "actualise_ui": str(actualise_ui), "bat": str(bat_hors_racine)})
    popen = _PopenAppels()
    monkeypatch.setattr(_main_module.subprocess, "Popen", popen)
    _main_module._lancer_actualise_ui_si_flag()
    assert popen.appels == []


def test_main_mauvaise_extension_ne_lance_rien(
        dossier_install, racine_actualise, monkeypatch):
    actualise_ui = _preparer_exe(racine_actualise, "ActualiseUI.sh")
    bat = _preparer_exe(racine_actualise, "updater.bat")
    _ecrire_flag(dossier_install, {
        "actualise_ui": str(actualise_ui), "bat": str(bat)})
    popen = _PopenAppels()
    monkeypatch.setattr(_main_module.subprocess, "Popen", popen)
    _main_module._lancer_actualise_ui_si_flag()
    assert popen.appels == []


def test_main_chemin_inexistant_ne_lance_rien(
        dossier_install, racine_actualise, monkeypatch):
    bat = _preparer_exe(racine_actualise, "updater.bat")
    _ecrire_flag(dossier_install, {
        "actualise_ui": str(racine_actualise / "absent.exe"), "bat": str(bat)})
    popen = _PopenAppels()
    monkeypatch.setattr(_main_module.subprocess, "Popen", popen)
    _main_module._lancer_actualise_ui_si_flag()
    assert popen.appels == []


def test_main_drapeau_permission_denied_ne_plante_pas_et_ne_lance_rien(
        dossier_install, monkeypatch):
    """Erreur de droits simulée sur le test d'existence du flag (issue #266) :
    ``PermissionError`` n'est pas capturée par ``Path.exists()`` lui-même —
    la fonction doit s'en protéger. Simulation indépendante des droits réels
    du système, valable sous Linux comme sous Windows."""
    _exists_original = Path.exists

    def _exists_refuse(self, *args, **kwargs):
        if self.name == "actualise_update.flag":
            raise PermissionError("acces refuse (simulation)")
        return _exists_original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "exists", _exists_refuse)
    popen = _PopenAppels()
    monkeypatch.setattr(_main_module.subprocess, "Popen", popen)
    _main_module._lancer_actualise_ui_si_flag()  # ne doit lever aucune exception
    assert popen.appels == []


def test_main_actualise_au_demarrage_permission_denied_ne_plante_pas(
        monkeypatch):
    """Même protection pour ``_lancer_actualise_au_demarrage`` : une erreur
    de droits sur le test d'existence du chemin fixe d'Actualise ne doit
    lever aucune exception ni lancer de sous-processus (issue #266)."""
    _chemin_actualise = str(Path(r"C:\Actualise\Actualise.exe"))
    _exists_original = Path.exists

    def _exists_refuse(self, *args, **kwargs):
        if str(self) == _chemin_actualise:
            raise PermissionError("acces refuse (simulation)")
        return _exists_original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "exists", _exists_refuse)
    popen = _PopenAppels()
    monkeypatch.setattr(_main_module.subprocess, "Popen", popen)
    _main_module._lancer_actualise_au_demarrage()  # ne doit lever aucune exception
    assert popen.appels == []


# --------------------------------------------------------------------------- #
# application._handler_fermeture_actualise
# --------------------------------------------------------------------------- #

def test_application_drapeau_absent_ne_lance_rien(dossier_install, monkeypatch):
    popen = _PopenAppels()
    monkeypatch.setattr(_application_module.subprocess, "Popen", popen)
    _application_module._handler_fermeture_actualise()
    assert popen.appels == []


def test_application_drapeau_illisible_ne_lance_rien(
        dossier_install, monkeypatch):
    (dossier_install / "actualise_update.flag").write_text(
        "pas du json valide {{{", encoding="utf-8")
    popen = _PopenAppels()
    monkeypatch.setattr(_application_module.subprocess, "Popen", popen)
    _application_module._handler_fermeture_actualise()
    assert popen.appels == []


def test_application_bat_valide_lance_sans_shell(
        dossier_install, racine_actualise, monkeypatch):
    bat = _preparer_exe(racine_actualise, "updater_rummikub.bat")
    flag = _ecrire_flag(dossier_install, {"bat": str(bat)})
    popen = _PopenAppels()
    monkeypatch.setattr(_application_module.subprocess, "Popen", popen)
    _application_module._handler_fermeture_actualise()
    assert len(popen.appels) == 1
    args, kwargs = popen.appels[0]
    assert args == [str(bat.resolve())]
    assert kwargs.get("shell", False) is False
    assert not flag.exists()  # le flag est retiré même après un lancement


def test_application_echec_suppression_flag_tolere_et_lance_tout_de_meme(
        dossier_install, racine_actualise, monkeypatch, capsys):
    """Simule un dossier d'installation non modifiable (droits non-admin,
    issue #265) : ``Path.unlink`` lève une erreur de droits, sans dépendre
    des permissions réelles du système de fichiers (fonctionne sous Linux
    comme sous Windows). La fermeture ne doit ni lever ni empêcher la
    tentative de lancer le bat de mise à jour."""
    bat = _preparer_exe(racine_actualise, "updater_rummikub.bat")
    flag = _ecrire_flag(dossier_install, {"bat": str(bat)})
    popen = _PopenAppels()
    monkeypatch.setattr(_application_module.subprocess, "Popen", popen)

    def _unlink_refuse(self, missing_ok=False):
        raise PermissionError("droits refuses (simule)")

    monkeypatch.setattr(Path, "unlink", _unlink_refuse)
    _application_module._handler_fermeture_actualise()  # ne doit pas lever
    assert len(popen.appels) == 1
    args, kwargs = popen.appels[0]
    assert args == [str(bat.resolve())]
    assert kwargs.get("shell", False) is False
    assert flag.exists()  # suppression échouée : le flag reste en place
    assert "Suppression du flag" in capsys.readouterr().err


def test_application_bat_hors_racine_ne_lance_rien(
        dossier_install, racine_actualise, tmp_path, monkeypatch):
    racine_actualise.mkdir(parents=True, exist_ok=True)
    bat_hors_racine = _preparer_exe(tmp_path / "Ailleurs", "updater.bat")
    _ecrire_flag(dossier_install, {"bat": str(bat_hors_racine)})
    popen = _PopenAppels()
    monkeypatch.setattr(_application_module.subprocess, "Popen", popen)
    _application_module._handler_fermeture_actualise()
    assert popen.appels == []


def test_application_bat_qui_s_echappe_par_dot_dot_ne_lance_rien(
        dossier_install, racine_actualise, tmp_path, monkeypatch):
    racine_actualise.mkdir(parents=True, exist_ok=True)
    bat_hors_racine = _preparer_exe(tmp_path / "Ailleurs", "updater.bat")
    evasion = racine_actualise / ".." / "Ailleurs" / "updater.bat"
    _ecrire_flag(dossier_install, {"bat": str(evasion)})
    popen = _PopenAppels()
    monkeypatch.setattr(_application_module.subprocess, "Popen", popen)
    _application_module._handler_fermeture_actualise()
    assert popen.appels == []
    assert bat_hors_racine.exists()
