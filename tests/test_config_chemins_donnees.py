"""Tests de la logique de chemins des données utilisateur (issue #258) :
mode développement (inchangé), Windows gelé simulé (inchangé), Linux gelé
simulé (nouveau, avec et sans ``XDG_DATA_HOME``)."""
from pathlib import Path

from rummikub.config import (
    RACINE_DATA, RACINE_PROJET, FICHIER_CFG,
    _calculer_racine_data_gelee,
)


def test_mode_developpement_inchange():
    """Hors mode gelé, les données restent à la racine du dépôt."""
    assert RACINE_DATA == RACINE_PROJET / "data"
    assert FICHIER_CFG == RACINE_PROJET / "config.json"


def test_windows_gele_avec_appdata():
    chemin = _calculer_racine_data_gelee(
        "win32", {"APPDATA": r"C:\Users\mamie\AppData\Roaming"}, Path("/home/mamie"))
    assert chemin == Path(r"C:\Users\mamie\AppData\Roaming") / "Rummikub"


def test_windows_gele_sans_appdata_repli_home():
    chemin = _calculer_racine_data_gelee("win32", {}, Path("/home/mamie"))
    assert chemin == Path("/home/mamie") / "Rummikub"


def test_linux_gele_avec_xdg_data_home():
    chemin = _calculer_racine_data_gelee(
        "linux", {"XDG_DATA_HOME": "/custom/xdg"}, Path("/home/mamie"))
    assert chemin == Path("/custom/xdg") / "rummikub"


def test_linux_gele_sans_xdg_data_home_repli_local_share():
    chemin = _calculer_racine_data_gelee("linux", {}, Path("/home/mamie"))
    assert chemin == Path("/home/mamie") / ".local" / "share" / "rummikub"


def test_linux_gele_xdg_data_home_vide_traite_comme_absente():
    """Une variable XDG_DATA_HOME définie mais vide (cas rencontré sur
    certains systèmes) ne doit pas produire un chemin invalide : repli sur
    ~/.local/share, comme si la variable n'existait pas."""
    chemin = _calculer_racine_data_gelee(
        "linux", {"XDG_DATA_HOME": ""}, Path("/home/mamie"))
    assert chemin == Path("/home/mamie") / ".local" / "share" / "rummikub"
