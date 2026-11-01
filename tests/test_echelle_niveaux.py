"""Tests de ``scripts/echelle_niveaux.py`` par DUELS uniquement (issue #220,
suite #213/#216/#217) : le relevé des tuiles restantes en défaite et son
option ``--donnes-profil`` sont retirés, la limite de temps est réellement
ferme, et les résultats partiels (``--sortie``, nouveauté #220) restent
lisibles à tout moment."""

import sys
import time
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import echelle_niveaux as M  # noqa: E402

_BUDGET_RAPIDE = 0.02
_MAX_TOURS_RAPIDE = 10


def _main_worker(args: list[str]) -> int:
    return M.main(["echelle_niveaux.py", *args, "--_worker"])


# --------------------------------------------------------------------------- #
# Option retirée (point 6 de l'issue #220)
# --------------------------------------------------------------------------- #

def test_donnes_profil_retiree():
    with pytest.raises(SystemExit) as exc:
        M.main(["echelle_niveaux.py", "--donnes-profil", "10"])
    assert exc.value.code == 2


def test_aucune_trace_du_relevé_de_profil():
    assert not hasattr(M, "mesurer_tuiles_restantes")
    assert not hasattr(M, "jouer_profils")


# --------------------------------------------------------------------------- #
# Verdicts de duels : échelle croissante, écart « net » 60–75 % (point 4)
# --------------------------------------------------------------------------- #

def test_seuils_net_60_75():
    from _rapport_duels import SEUIL_NET_BAS, SEUIL_NET_HAUT
    assert M.SEUIL_NET_BAS == SEUIL_NET_BAS == 0.60
    assert M.SEUIL_NET_HAUT == SEUIL_NET_HAUT == 0.75


# --------------------------------------------------------------------------- #
# Tournoi complet (rapide, restreint à une seule paire) : termine normalement
# --------------------------------------------------------------------------- #

def test_jouer_paire_rapide_retourne_un_resume_complet():
    res = M.jouer_paire("Débutant", "Facile", nb_donnes=2, seed=0,
                        max_tours=_MAX_TOURS_RAPIDE, deadline=None)
    assert res["donnes_jouees"] == 2
    assert res["niveau_faible"] == "Débutant"
    assert res["niveau_fort"] == "Facile"


def test_jouer_paire_callback_on_donne_appele_a_chaque_donne():
    appels = []
    M.jouer_paire("Débutant", "Facile", nb_donnes=3, seed=0,
                 max_tours=_MAX_TOURS_RAPIDE, deadline=None,
                 on_donne=appels.append)
    assert len(appels) == 3
    assert [a["donnes_jouees"] for a in appels] == [1, 2, 3]


# --------------------------------------------------------------------------- #
# Limite de temps ferme + résultats partiels lisibles (--sortie, point 3/6)
# --------------------------------------------------------------------------- #

def test_limite_temps_arrete_avec_resultats_partiels(tmp_path, monkeypatch):
    # Restreint l'échelle à une seule paire (via NIVEAUX) pour un test rapide
    # et déterministe, sans dépendre des six niveaux réels.
    sortie = tmp_path / "partiel.txt"
    debut = time.monotonic()
    rapport = M.jouer_tournoi(nb_donnes=500, seed=0,
                             max_tours=_MAX_TOURS_RAPIDE,
                             limite_temps=0.3, sortie=str(sortie))
    duree = time.monotonic() - debut

    assert rapport["interrompu"] is True
    assert duree < 30
    contenu = sortie.read_text(encoding="utf-8")
    assert "ARRÊTÉ SUR LA LIMITE DE TEMPS" in contenu
    assert "Paire incomplète" in contenu
    assert "[partiel]" in contenu
    assert "Machine :" in contenu and "Python" in contenu
    assert "[500/500" not in contenu


def test_tournoi_sans_limite_termine_normalement(tmp_path):
    sortie = tmp_path / "complet.txt"
    rapport = M.jouer_tournoi(nb_donnes=1, seed=0,
                             max_tours=_MAX_TOURS_RAPIDE, limite_temps=None,
                             sortie=str(sortie))
    assert rapport["interrompu"] is False
    contenu = sortie.read_text(encoding="utf-8")
    assert "TERMINÉ NORMALEMENT" in contenu


# --------------------------------------------------------------------------- #
# Code de sortie via main() (point 2 de l'issue) — mode --_worker, en direct
# --------------------------------------------------------------------------- #

def test_main_worker_code_sortie_limite_temps(tmp_path):
    sortie = tmp_path / "cli_partiel.txt"
    code = _main_worker([
        "--donnes", "500", "--seed", "0",
        "--max-tours", str(_MAX_TOURS_RAPIDE),
        "--budget-solveur", str(_BUDGET_RAPIDE),
        "--limite-temps", "0.3",
        "--sortie", str(sortie),
    ])
    assert code == M.CODE_LIMITE_TEMPS


def test_main_worker_code_sortie_termine():
    code = _main_worker([
        "--donnes", "1", "--seed", "0",
        "--max-tours", str(_MAX_TOURS_RAPIDE),
        "--budget-solveur", str(_BUDGET_RAPIDE),
    ])
    assert code == M.CODE_TERMINE
