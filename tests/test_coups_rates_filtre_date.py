"""Tests du filtre par date sur le nom de fichier des journaux (point 2 de
l'issue #198) : voir ``persistance/coups_rates.py::filtrer_journaux_depuis``.

Permet de limiter l'analyse des coups ratés aux journaux (nommés
``partie_AAAAMMJJ_HHMMSS.json``, voir ``persistance/journal.py``) joués à
partir d'une date donnée — typiquement pour isoler les parties jouées avec
la dernière version d'une IA plutôt qu'un mélange de versions successives.
"""

from pathlib import Path

from rummikub.persistance.coups_rates import filtrer_journaux_depuis


def _chemin(nom: str) -> Path:
    return Path("/tmp/logs_parties") / nom


_JOURNAUX = [
    _chemin("partie_20261001_090000.json"),
    _chemin("partie_20261015_120000.json"),
    _chemin("partie_20261027_153000.json"),
]


def test_sans_depuis_retourne_tous_les_journaux_inchanges():
    assert filtrer_journaux_depuis(_JOURNAUX, None) == _JOURNAUX
    assert filtrer_journaux_depuis(_JOURNAUX, "") == _JOURNAUX


def test_depuis_garde_la_date_exacte_et_les_plus_recentes():
    retenus = filtrer_journaux_depuis(_JOURNAUX, "20261015")
    assert retenus == _JOURNAUX[1:]


def test_depuis_exclut_toutes_les_dates_plus_anciennes():
    retenus = filtrer_journaux_depuis(_JOURNAUX, "20261028")
    assert retenus == []


def test_depuis_avant_la_plus_ancienne_garde_tout():
    retenus = filtrer_journaux_depuis(_JOURNAUX, "20260101")
    assert retenus == _JOURNAUX


def test_nom_de_fichier_hors_format_attendu_est_exclu_par_prudence():
    """Un journal qui ne suit pas le format ``partie_AAAAMMJJ_HHMMSS.json``
    (ex. ancien format, ou renommé à la main) est exclu dès qu'un filtre est
    demandé : sans date fiable à comparer, on ne peut pas garantir qu'il
    s'agit d'une partie récente."""
    chemins = _JOURNAUX + [_chemin("partie_sans_date.json")]
    retenus = filtrer_journaux_depuis(chemins, "20261001")
    assert _chemin("partie_sans_date.json") not in retenus
