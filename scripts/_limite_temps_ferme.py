#!/usr/bin/env python3
"""Garde-fou de limite de temps FERME pour les tournois de validation (issue
#220, suite de #216/#217).

Partagé par ``scripts/echelle_niveaux.py`` et ``scripts/calibrer_echelle.py``.
Les deux boucles de tournoi s'arrêtent déjà PROPREMENT d'elles-mêmes dès que
``--limite-temps`` est dépassée (plus de nouvelle donne lancée, voir
``deadline`` dans chaque script) — mais une donne déjà EN COURS peut, dans un
cas pathologique (solveur bloqué, plateau qui se réarrange sans jamais finir),
prendre un temps imprévisible : #217 a ainsi dépassé sa limite de 5400 s de
244 s, puis le processus est resté vivant 30 minutes de plus, la machine au
repos, sans qu'Alain n'ait pu s'y fier et sans rien calculer.

Ce module fait exécuter le tournoi dans un SOUS-PROCESSUS (même interpréteur,
même script, relancé avec l'argument interne ``--_worker``) et TERMINE ce
sous-processus — et tout arbre de processus qu'il aurait créé — si
``limite_temps + MARGE_ARRET_S`` est dépassée : une borne FERME, quoi qu'il
arrive à l'intérieur. Fonctionne sous Linux (groupe de processus POSIX,
``SIGTERM`` puis ``SIGKILL``) et sous Windows (groupe de processus +
``taskkill /PID <pid> /T /F`` — jamais ``/IM`` par motif de nom, voir les
consignes du projet sur l'arrêt de processus).
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

# Codes de sortie de ``lancer_avec_limite_ferme`` ET des scripts appelants
# eux-mêmes quand ils se terminent en direct (sans limite de temps, ou en
# mode ``--_worker``) : la même convention s'applique aux deux niveaux.
CODE_TERMINE = 0          # terminé normalement (aucune limite dépassée)
CODE_ERREUR = 1           # sous-processus terminé en erreur
CODE_LIMITE_TEMPS = 3     # arrêté sur la limite de temps (soi-même ou tué)

MARGE_ARRET_S = 10.0
INTERVALLE_SONDAGE_S = 0.5


def lancer_avec_limite_ferme(
        script: Path, argv_sans_prog: list[str], limite_temps: float | None,
        marge_arret_s: float = MARGE_ARRET_S,
        intervalle_sondage_s: float = INTERVALLE_SONDAGE_S) -> int:
    """Relance ``script`` (même interpréteur que ``sys.executable``) en
    sous-processus avec ``argv_sans_prog`` + ``--_worker``, dans son propre
    groupe de processus. Sans ``limite_temps``, équivaut à un simple relais du
    code de sortie. Avec elle, surveille le temps écoulé par sondage et
    TERMINE le sous-processus (et son arbre) si ``limite_temps +
    marge_arret_s`` est dépassée malgré l'arrêt propre interne attendu."""
    cmd = [sys.executable, str(script), *argv_sans_prog, "--_worker"]
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    debut = time.monotonic()
    proc = subprocess.Popen(cmd, **kwargs)

    if limite_temps is None:
        return _code_depuis_retour(proc.wait())

    limite_dure = limite_temps + marge_arret_s
    while True:
        try:
            code = proc.wait(timeout=intervalle_sondage_s)
            return _code_depuis_retour(code)
        except subprocess.TimeoutExpired:
            if time.monotonic() - debut >= limite_dure:
                _terminer_arbre(proc)
                try:
                    proc.wait(timeout=marge_arret_s)
                except subprocess.TimeoutExpired:
                    pass  # au pire un zombie reste à réclamer par l'OS
                return CODE_LIMITE_TEMPS


def _code_depuis_retour(code: int) -> int:
    if code == CODE_LIMITE_TEMPS:
        return CODE_LIMITE_TEMPS
    return CODE_TERMINE if code == 0 else CODE_ERREUR


def _terminer_arbre(proc: subprocess.Popen) -> None:
    """Termine ``proc`` ET ses éventuels processus enfants, sur Linux et
    Windows (point 2 de l'issue #220). Toujours désigné par son PID précis
    (jamais par un motif de nom)."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True)
        return

    import os
    import signal
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


if __name__ == "__main__":  # pragma: no cover - usage interactif seulement
    print(__doc__)
