"""Validation des chemins déposés par Actualise dans ``actualise_update.flag``
avant tout lancement (issue #234, règle SEC-003 — miroir de l'issue #482 du
projet Scrabble).

Le flag contient deux chemins (``actualise_ui``, ``bat``) qui, avant cette
issue, étaient lancés sans aucune validation (le ``bat`` via le shell). Un
chemin n'est accepté que s'il remplit TOUTES ces conditions :
  - il existe ;
  - son extension est ``.bat`` ou ``.exe`` ;
  - une fois résolu (liens, ``..`` et casse normalisés via ``Path.resolve``),
    il est situé sous la racine Actualise autorisée (``C:\\Actualise`` par
    défaut, paramétrable via ``RACINE_ACTUALISE`` pour rendre la validation
    testable sous Linux).
Sinon, il est ignoré : aucune exception, aucun lancement.
"""
from __future__ import annotations

from pathlib import Path

EXTENSIONS_AUTORISEES = {".bat", ".exe"}

# Racine sous laquelle Actualise est autorisé à déposer un exécutable/bat
# (SEC-003). Module-level pour rester paramétrable depuis les tests (Linux) :
# passer explicitement ``racine=`` à ``valider_chemin_actualise`` ou
# monkeypatcher cet attribut.
RACINE_ACTUALISE = Path(r"C:\Actualise")


def valider_chemin_actualise(chemin, racine=None):
    """Valide un chemin exécutable du flag Actualise. Retourne le ``Path``
    résolu si les trois conditions SEC-003 sont réunies, sinon ``None``.
    Ne lève jamais d'exception (chemin absent, invalide, ou inaccessible)."""
    if not chemin:
        return None
    try:
        _p = Path(chemin)
        if not _p.exists():
            return None
        if _p.suffix.lower() not in EXTENSIONS_AUTORISEES:
            return None
        _racine = Path(racine) if racine is not None else RACINE_ACTUALISE
        _p_resolu = _p.resolve()
        _racine_resolue = _racine.resolve()
        _p_resolu.relative_to(_racine_resolue)
    except (OSError, ValueError):
        return None
    return _p_resolu
