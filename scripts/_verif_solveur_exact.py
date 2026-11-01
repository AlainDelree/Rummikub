#!/usr/bin/env python3
"""Vérification de la disponibilité du solveur exact (``highspy``/``numpy``)
pour les scripts de mesure qui font jouer Avancé, Expert ou Champion du
Monde — issue #223.

**Incident à l'origine de ce module** : une campagne de comparaison Avancé
contre Expert (lancée pour mesurer la vérification de finition, #221) a
tourné à vide. Le terminal utilisé par Alain pointait par défaut vers un
AUTRE interpréteur Python, sans ``highspy`` ni ``numpy`` installés : Expert
s'est replié sur Avancé à CHAQUE tour (766 sur 766) sans que rien ne le
signale, et le rapport a même étiqueté ces replis « coup légitimement
impossible, aucun rapport avec la vitesse » — ce qui était faux. Toute la
mesure a porté sur un Expert qui n'était, en réalité, jamais Expert.

Les scripts de mesure listés par l'issue (``comparer_niveaux_ia.py``,
``valider_bas_echelle.py``, ``echelle_niveaux.py``, et tout autre script qui
fait jouer Avancé/Expert/Champion du Monde) doivent donc échouer FRANCHEMENT
(code de sortie non nul, message explicite nommant l'interpréteur utilisé)
si le solveur exact n'est pas importable — sauf si l'appelant a
explicitement choisi ``--sans-exact`` (désactivation volontaire et assumée,
jamais concernée par ce garde-fou)."""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version_installee

from rummikub.moteur import solveur_exact

PAQUETS_REQUIS = ("highspy", "numpy")


def version_installee(nom_paquet: str) -> str | None:
    """Version installée de ``nom_paquet`` dans CET interpréteur, ou ``None``
    s'il n'est pas installé (ou non importable)."""
    try:
        return _version_installee(nom_paquet)
    except PackageNotFoundError:
        return None


def entete_dependances(sans_exact: bool = False) -> list[str]:
    """Lignes d'en-tête à inclure dans tout rapport/fichier de résultats
    (issue #223, point 1) : interpréteur Python réellement utilisé, et
    versions de ``highspy``/``numpy`` — ou leur absence, VOLONTAIRE si
    ``sans_exact`` (``--sans-exact``)."""
    lignes = [f"Interpréteur Python : {sys.executable}"]
    if sans_exact:
        lignes.append("Solveur exact (highspy/numpy) : désactivé "
                      "volontairement (--sans-exact)")
        return lignes
    versions = {p: version_installee(p) or "ABSENT" for p in PAQUETS_REQUIS}
    lignes.append("Solveur exact : " + ", ".join(
        f"{p} {v}" for p, v in versions.items()))
    return lignes


def exiger_solveur_exact_ou_quitter(sans_exact: bool = False) -> None:
    """Arrête le script (code de sortie 1) si le solveur exact
    (``highspy`` + ``numpy``) n'est pas importable dans CET interpréteur,
    SAUF si ``sans_exact`` (désactivation volontaire et assumée, via
    ``--sans-exact``). Message en français indiquant l'interpréteur
    réellement utilisé et ce qui manque — voir l'incident documenté en tête
    de ce module. N'a AUCUN effet sur le comportement du jeu : ce garde-fou
    ne concerne que les scripts de mesure."""
    if sans_exact or solveur_exact.DISPONIBLE:
        return
    manquants = [p for p in PAQUETS_REQUIS if version_installee(p) is None]
    if not manquants:
        # Importable en théorie (paquets installés) mais l'import a échoué
        # pour une autre raison (ex. incompatibilité binaire) : on le dit
        # sans deviner la cause précise.
        manquants = list(PAQUETS_REQUIS)
    print(
        "ERREUR : solveur exact indisponible dans cet interpréteur — ce "
        "script fait jouer Avancé/Expert/Champion du Monde et SUPPOSE le "
        "solveur exact disponible (sauf --sans-exact, non demandé ici).\n"
        f"Interpréteur Python utilisé : {sys.executable}\n"
        f"Paquet(s) manquant(s) ou non importable(s) : {', '.join(manquants)}\n"
        "Installez-les dans CET interpréteur (pip install highspy numpy — "
        "voir requirements.txt), ou relancez avec --sans-exact pour comparer "
        "explicitement SANS le solveur exact (incident #223 : une campagne "
        "lancée avec un autre interpréteur par défaut, sans highspy/numpy, "
        "a tourné à vide sans que rien ne le signale — voir CONTEXTE.md).",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":  # pragma: no cover - usage interactif seulement
    exiger_solveur_exact_ou_quitter()
    print("Solveur exact disponible.")
    for ligne in entete_dependances():
        print(ligne)
