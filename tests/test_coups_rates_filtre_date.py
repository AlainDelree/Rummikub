"""Tests du filtre par date sur le nom de fichier des journaux (point 2 de
l'issue #198) : voir ``persistance/coups_rates.py::filtrer_journaux_depuis``.

Permet de limiter l'analyse des coups ratés aux journaux (nommés
``partie_AAAAMMJJ_HHMMSS.json``, voir ``persistance/journal.py``) joués à
partir d'une date donnée — typiquement pour isoler les parties jouées avec
la dernière version d'une IA plutôt qu'un mélange de versions successives.
"""

from pathlib import Path

import pytest

from rummikub.persistance.coups_rates import filtrer_journaux_depuis


@pytest.fixture
def journaux(tmp_path: Path) -> list[Path]:
    return [
        tmp_path / "partie_20261001_090000.json",
        tmp_path / "partie_20261015_120000.json",
        tmp_path / "partie_20261027_153000.json",
    ]


def test_sans_depuis_retourne_tous_les_journaux_inchanges(journaux):
    assert filtrer_journaux_depuis(journaux, None) == journaux
    assert filtrer_journaux_depuis(journaux, "") == journaux


def test_depuis_garde_la_date_exacte_et_les_plus_recentes(journaux):
    retenus = filtrer_journaux_depuis(journaux, "20261015")
    assert retenus == journaux[1:]


def test_depuis_exclut_toutes_les_dates_plus_anciennes(journaux):
    retenus = filtrer_journaux_depuis(journaux, "20261028")
    assert retenus == []


def test_depuis_avant_la_plus_ancienne_garde_tout(journaux):
    retenus = filtrer_journaux_depuis(journaux, "20260101")
    assert retenus == journaux


def test_nom_de_fichier_hors_format_attendu_est_exclu_par_prudence(journaux, tmp_path):
    """Un journal qui ne suit pas le format ``partie_AAAAMMJJ_HHMMSS.json``
    (ex. ancien format, ou renommé à la main) est exclu dès qu'un filtre est
    demandé : sans date fiable à comparer, on ne peut pas garantir qu'il
    s'agit d'une partie récente."""
    hors_format = tmp_path / "partie_sans_date.json"
    chemins = journaux + [hors_format]
    retenus = filtrer_journaux_depuis(chemins, "20261001")
    assert hors_format not in retenus
