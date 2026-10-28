"""Pas-à-pas CONDENSÉ (issue #207) sur des coups RÉELS du modèle exact.

Les cas ``tests/donnees/cas_expert_*.json`` et ``reference_*.json`` donnent
l'état AVANT un coup ; le coup du modèle exact est reconstruit ici avec
``scripts/solveur_exact.py`` (dépendance de DÉVELOPPEMENT, bibliothèque
``rummikub-solver`` — voir CONTEXTE.md §14), puis on vérifie que son découpage
condensé respecte les propriétés de l'issue #207, point 5 : même plateau final,
cadre vide à la fin, aucune tuile à deux endroits, nombre d'étapes borné par
« combinaisons modifiées + 4 », et strictement plus court que le détaillé.

Ces tests se sautent proprement si la bibliothèque n'est pas installée (comme
``tests/test_solveur_exact.py``). Pour les exécuter :

    python -m venv .venv-solveur-exact
    .venv-solveur-exact/bin/pip install 'rummikub-solver[highs]' pytest
    .venv-solveur-exact/bin/python -m pytest tests/test_condense_solveur.py
"""

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("rummikub_solver")

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import solveur_exact  # noqa: E402
from rummikub.moteur.description_coup import (  # noqa: E402
    etapes_coup_ia, mesurer_coup_ia)

_DONNEES = Path(__file__).resolve().parent / "donnees"


def _cas():
    return (sorted(_DONNEES.glob("cas_expert_*.json"))
            + sorted(_DONNEES.glob("reference_*.json")))


def _coup_exact(data):
    """Plateau avant/après du coup du modèle exact pour un cas donné."""
    coup = solveur_exact.resoudre_coup_exact(
        data["etat"], data["idx"], budget_temps=12.0)
    if coup is None or coup["action"] != "jouer":
        return None
    return data["etat"]["plateau"], coup["nouveau_plateau"]


def _ids_plateau(plateau):
    return [d["id"] for combo in plateau for d in combo]


def _verifier(avant, apres):
    condense = etapes_coup_ia(avant, apres)              # condense=True
    detaille = etapes_coup_ia(avant, apres, condense=False)
    assert condense[0]["titre"] == "Départ"
    # Aucune tuile à deux endroits à aucune étape.
    for etape in condense:
        combines = _ids_plateau(etape["plateau"]) + \
            [c["tuile"]["id"] for c in etape["cadre"]]
        assert len(combines) == len(set(combines))
    # Dernière étape : cadre vide, plateau == plateau d'après.
    assert condense[-1]["cadre"] == []
    sig = lambda p: sorted(sorted(d["id"] for d in c) for c in p if c)
    assert sig(condense[-1]["plateau"]) == sig(apres)
    # Borne de l'issue #207 (point 1) : étapes <= combinaisons modifiées + 4,
    # toujours au plus le détaillé.
    mesure = mesurer_coup_ia(avant, apres)
    assert len(condense) <= mesure["nb_combinaisons_modifiees"] \
        + mesure["nb_combinaisons_creees"] + 4
    assert len(condense) <= len(detaille)
    return condense


@pytest.mark.parametrize("chemin", _cas(), ids=lambda p: p.stem)
def test_condense_coup_exact_proprietes(chemin):
    data = json.loads(chemin.read_text(encoding="utf-8"))
    plateaux = _coup_exact(data)
    if plateaux is None:
        pytest.skip("le modèle exact ne pose aucune tuile sur ce cas")
    _verifier(*plateaux)


def test_condense_bruno_tour57_moins_de_onze_etapes():
    """Le coup du modèle exact de Bruno au tour 57 (27 étapes en détaillé)
    se parcourt en moins de 11 étapes une fois condensé (issue #207)."""
    data = json.loads((_DONNEES / "cas_expert_bruno_tour57.json")
                      .read_text(encoding="utf-8"))
    plateaux = _coup_exact(data)
    assert plateaux is not None
    condense = _verifier(*plateaux)
    assert len(condense) < 11
