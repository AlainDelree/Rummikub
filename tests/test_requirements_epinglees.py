"""Vérifie que les dépendances directes de ``requirements.txt`` sont toutes
épinglées à une version exacte (``==``), pour un build reproductible (issue
#241, règle EXP-001 de Diagnostique_Programme) : sans épinglage, le script
de build installe la dernière version autorisée par les bornes, donc deux
builds à des dates différentes peuvent embarquer des versions différentes.

Les lignes de commentaire (``#...``), vides, ou d'options pip (``-r``,
``--...``) sont ignorées : le bloc d'inventaire des versions indirectes en
fin de fichier (information, non contraignant) est donc hors du périmètre
de ce test.
"""

from pathlib import Path

_REQUIREMENTS = Path(__file__).resolve().parents[1] / "requirements.txt"


def _lignes_dependances() -> list[str]:
    lignes = []
    for brute in _REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        ligne = brute.strip()
        if not ligne or ligne.startswith("#") or ligne.startswith("-"):
            continue
        lignes.append(ligne)
    return lignes


def test_au_moins_une_dependance_directe():
    assert _lignes_dependances(), "requirements.txt ne contient aucune dépendance"


def test_toutes_les_dependances_directes_sont_epinglees():
    non_epinglees = [
        ligne for ligne in _lignes_dependances() if "==" not in ligne
    ]
    assert not non_epinglees, (
        "dépendance(s) non épinglée(s) à une version exacte (==) dans "
        f"requirements.txt : {non_epinglees}"
    )
