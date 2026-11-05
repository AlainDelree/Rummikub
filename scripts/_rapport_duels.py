#!/usr/bin/env python3
"""Mise en forme commune des rapports de tournoi de duels (issue #220).

Partagé par ``scripts/echelle_niveaux.py`` et ``scripts/calibrer_echelle.py``
depuis que le seul critère de force retenu est le duel entre niveaux voisins
(CONTEXTE.md §16) : en-tête machine/Python (pour comparer des tournois lancés
sur des machines différentes) et verdict d'écart (« net » entre 60 et 75 %,
comportement déjà en vigueur dans ``echelle_niveaux.py`` avant #220, borne
haute resserrée de 80 à 75 % pour coller à la cible décidée par Alain)."""

from __future__ import annotations

import platform

from _verif_solveur_exact import entete_dependances

# Seuils d'un écart « net » entre deux niveaux voisins (issue #220 : 60–75 %,
# resserré depuis le 60–80 % d'origine de #213).
SEUIL_NET_BAS = 0.60
SEUIL_NET_HAUT = 0.75


def entete_machine() -> list[str]:
    """Lignes d'en-tête identifiant la machine, la version de Python, et le
    solveur exact disponible (issue #220, point 3 : ces tournois tournent
    désormais aussi sur un PC Windows plus lent qu'Alain utilise par ailleurs
    pendant ce temps ; dépendances ajoutées par #223, point 1 — ces deux
    scripts font jouer Avancé/Expert/Débutant-Facile-Intermédiaire via le
    solveur exact SANS option ``--sans-exact``, ``main`` refuse de démarrer
    s'il est indisponible, voir ``_verif_solveur_exact.py``)."""
    return [f"Machine : {platform.node()}  —  Python {platform.python_version()}",
           *entete_dependances()]


def verdict_ecart(taux: float, marge: float, identiques: bool = False) -> str:
    """Verdict textuel d'un écart de taux de victoire (IC 95 %) entre deux
    niveaux. ``identiques`` : les deux niveaux jouent EXACTEMENT le même
    moteur (égalité statistique ATTENDUE, pas un échec — #213 §2)."""
    if identiques:
        return "ÉGALITÉ ATTENDUE (solveur identique, #213 §2)"
    if abs(taux - 0.5) <= marge:
        return "non significatif"
    if SEUIL_NET_BAS <= taux <= SEUIL_NET_HAUT:
        return f"net ({int(SEUIL_NET_BAS * 100)}–{int(SEUIL_NET_HAUT * 100)} %)"
    if taux > SEUIL_NET_HAUT:
        return f"très net (>{int(SEUIL_NET_HAUT * 100)} %)"
    return f"significatif mais faible (<{int(SEUIL_NET_BAS * 100)} %)"


if __name__ == "__main__":  # pragma: no cover - usage interactif seulement
    print(__doc__)
