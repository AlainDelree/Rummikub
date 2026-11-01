"""Tests de ``scripts/valider_bas_echelle.py`` par DUELS uniquement (issue
#220, suite #216/#217) : le relevé des tuiles restantes en défaite et son
option ``--donnes-profil`` sont retirés, la limite de temps est réellement
ferme, et les résultats partiels restent lisibles à tout moment."""

import subprocess
import sys
import time
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import valider_bas_echelle as M  # noqa: E402

# Budget minuscule : Débutant/Facile/Intermédiaire restent rapides (quelques
# dixièmes de seconde) sans dépendre de la vitesse de la machine de CI.
_BUDGET_RAPIDE = 0.02
_MAX_TOURS_RAPIDE = 10


def _main_worker(args: list[str]) -> int:
    """Appelle ``main`` directement en mode ``--_worker`` : exécute la
    logique du tournoi EN DIRECT (pas de sous-processus), pour des tests
    rapides du comportement interne."""
    return M.main(["valider_bas_echelle.py", *args, "--_worker"])


# --------------------------------------------------------------------------- #
# Option retirée (point 6 de l'issue #220)
# --------------------------------------------------------------------------- #

def test_donnes_profil_retiree():
    with pytest.raises(SystemExit) as exc:
        M.main(["valider_bas_echelle.py", "--donnes-profil", "10"])
    assert exc.value.code == 2


def test_aucune_trace_du_relevé_de_profil():
    # Les symboles qui portaient le relevé « tuiles restantes en défaite »
    # (miroir) ont bien disparu du module.
    assert not hasattr(M, "NIVEAUX_PROFIL")
    assert not hasattr(M, "mesurer_tuiles_restantes")


# --------------------------------------------------------------------------- #
# Tournoi complet (rapide) : termine normalement, résultats lisibles
# --------------------------------------------------------------------------- #

def test_tournoi_complet_termine_normalement(tmp_path):
    sortie = tmp_path / "resultats.txt"
    code = _main_worker([
        "--donnes", "3", "--seed", "0", "--paire", "deb-fac",
        "--max-tours", str(_MAX_TOURS_RAPIDE),
        "--budget-solveur", str(_BUDGET_RAPIDE),
        "--sortie", str(sortie),
    ])
    assert code == M.CODE_TERMINE
    contenu = sortie.read_text(encoding="utf-8")
    assert "TERMINÉ NORMALEMENT" in contenu
    assert "Machine :" in contenu and "Python" in contenu
    assert "[3/3 donnes]" in contenu


# --------------------------------------------------------------------------- #
# Limite de temps ferme : s'arrête, résultats PARTIELS lisibles (point 3 et 6)
# --------------------------------------------------------------------------- #

def test_limite_temps_arrete_avec_resultats_partiels(tmp_path):
    sortie = tmp_path / "partiel.txt"
    debut = time.monotonic()
    code = _main_worker([
        "--donnes", "500", "--seed", "0", "--paire", "deb-fac",
        "--max-tours", str(_MAX_TOURS_RAPIDE),
        "--budget-solveur", str(_BUDGET_RAPIDE),
        "--limite-temps", "0.5",
        "--sortie", str(sortie),
    ])
    duree = time.monotonic() - debut

    assert code == M.CODE_LIMITE_TEMPS
    assert duree < 30  # arrêt borné, largement avant les 500 donnes demandées
    contenu = sortie.read_text(encoding="utf-8")
    assert "ARRÊTÉ SUR LA LIMITE DE TEMPS" in contenu
    assert "Paire incomplète" in contenu
    assert "[partiel]" in contenu
    # Pas de 500/500 : le tournoi n'est PAS allé au bout.
    assert "[500/500 donnes]" not in contenu


# --------------------------------------------------------------------------- #
# Intégration complète (processus réel, sans --_worker) : garde-fou externe,
# aucun processus résiduel (point 2 et 6 de l'issue).
# --------------------------------------------------------------------------- #

@pytest.mark.lent
def test_processus_complet_sans_limite_puis_reste_rien(tmp_path):
    sortie = tmp_path / "integration.txt"
    script = _SCRIPTS / "valider_bas_echelle.py"
    debut = time.monotonic()
    resultat = subprocess.run(
        [sys.executable, str(script),
         "--donnes", "300", "--seed", "0", "--paire", "deb-fac",
         "--max-tours", str(_MAX_TOURS_RAPIDE),
         "--budget-solveur", str(_BUDGET_RAPIDE),
         "--limite-temps", "0.5",
         "--sortie", str(sortie)],
        capture_output=True, text=True, timeout=60)
    duree = time.monotonic() - debut

    assert resultat.returncode == M.CODE_LIMITE_TEMPS
    assert duree < 30
    contenu = sortie.read_text(encoding="utf-8")
    assert "ARRÊTÉ SUR LA LIMITE DE TEMPS" in contenu
