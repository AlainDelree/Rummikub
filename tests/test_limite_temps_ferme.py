"""Tests du garde-fou de limite de temps FERME (issue #220).

``scripts/_limite_temps_ferme.lancer_avec_limite_ferme`` relance un script en
sous-processus et le TERMINE (lui et son arbre) si la limite de temps,
augmentée d'une marge bornée, est dépassée. Testé ici directement sur de
petits scripts jetables (pas besoin de rejouer de vraies parties pour vérifier
le mécanisme de garde-fou lui-même)."""

import os
import sys
import time
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import _limite_temps_ferme as L  # noqa: E402


def _ecrire_script(tmp_path: Path, nom: str, code: str) -> Path:
    chemin = tmp_path / nom
    chemin.write_text(code, encoding="utf-8")
    return chemin


def test_relais_normal_sans_limite(tmp_path):
    # Script qui se termine immédiatement : sans limite de temps, le code de
    # sortie du sous-processus est simplement relayé.
    script = _ecrire_script(tmp_path, "ok.py", "import sys\nsys.exit(0)\n")
    code = L.lancer_avec_limite_ferme(script, [], limite_temps=None)
    assert code == L.CODE_TERMINE


def test_relais_erreur(tmp_path):
    script = _ecrire_script(tmp_path, "erreur.py", "import sys\nsys.exit(1)\n")
    code = L.lancer_avec_limite_ferme(script, [], limite_temps=None)
    assert code == L.CODE_ERREUR


def test_relais_code_limite_temps_deja_atteinte(tmp_path):
    # Le sous-processus s'arrête PROPREMENT de lui-même (il a détecté sa
    # propre limite) : le code CODE_LIMITE_TEMPS est relayé tel quel, sans que
    # le garde-fou externe n'ait besoin de tuer quoi que ce soit.
    script = _ecrire_script(
        tmp_path, "auto_stop.py",
        f"import sys\nsys.exit({L.CODE_LIMITE_TEMPS})\n")
    debut = time.monotonic()
    code = L.lancer_avec_limite_ferme(script, [], limite_temps=5.0,
                                      marge_arret_s=5.0,
                                      intervalle_sondage_s=0.05)
    duree = time.monotonic() - debut
    assert code == L.CODE_LIMITE_TEMPS
    assert duree < 2.0  # bien avant la limite : pas d'attente inutile


@pytest.mark.skipif(sys.platform == "win32",
                    reason="vérification PID POSIX seulement")
def test_processus_bloque_termine_dans_un_delai_borne(tmp_path):
    """Scénario pathologique visé par l'issue : une tâche qui ne se termine
    JAMAIS d'elle-même (boucle infinie, solveur bloqué...). Le garde-fou doit
    la terminer dans un délai BORNÉ (limite + marge), et ne laisser AUCUN
    processus actif derrière lui."""
    script = _ecrire_script(
        tmp_path, "bloque.py",
        "import time\nwhile True:\n    time.sleep(0.05)\n")

    limite_temps = 0.3
    marge = 0.5
    debut = time.monotonic()
    proc_pid = {}
    # On intercepte Popen pour récupérer le PID et vérifier qu'il n'existe
    # plus APRÈS l'appel (processus bien réclamé, pas de zombie oublié).
    import subprocess as _sp
    popen_original = _sp.Popen

    def _popen_espion(*a, **kw):
        p = popen_original(*a, **kw)
        proc_pid["pid"] = p.pid
        return p

    L_sp = L.subprocess
    ancien = L_sp.Popen
    L_sp.Popen = _popen_espion
    try:
        code = L.lancer_avec_limite_ferme(
            script, [], limite_temps=limite_temps, marge_arret_s=marge,
            intervalle_sondage_s=0.05)
    finally:
        L_sp.Popen = ancien
    duree = time.monotonic() - debut

    assert code == L.CODE_LIMITE_TEMPS
    # Délai borné : la limite + la marge + une petite tolérance de sondage.
    assert duree < limite_temps + marge + 2.0
    # Aucun processus résiduel : le PID ne doit plus exister.
    pid = proc_pid["pid"]
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_code_depuis_retour():
    assert L._code_depuis_retour(0) == L.CODE_TERMINE
    assert L._code_depuis_retour(L.CODE_LIMITE_TEMPS) == L.CODE_LIMITE_TEMPS
    assert L._code_depuis_retour(1) == L.CODE_ERREUR
    assert L._code_depuis_retour(42) == L.CODE_ERREUR
