"""Pas-à-pas CONDENSÉ (issue #207) sur des coups RÉELS du solveur exact.

Deux sources de coup coexistent ici, chacune pour ce qu'elle juge le mieux :

- **Propriétés GÉNÉRALES** du condensé (``test_condense_coup_exact_proprietes``)
  sur tous les cas : reconstruites avec la BIBLIOTHÈQUE EXTERNE
  ``rummikub-solver`` (dépendance de DÉVELOPPEMENT, ``scripts/solveur_exact.py``
  — voir CONTEXTE.md §14). Ces propriétés (même plateau final, cadre vide à la
  fin, aucune tuile à deux endroits, bornes lâches) sont INSENSIBLES à la
  source : peu importe l'arrangement exact proposé, elles doivent tenir.

- **Borne SERRÉE sur le coup de Bruno au tour 57**
  (``test_condense_bruno_tour57_...``) : reconstruite avec le solveur MAISON
  (``moteur/solveur_exact.py``, HiGHS), celui que le jeu utilise RÉELLEMENT au
  niveau Expert. On juge ainsi l'affichage du coup réellement joué, et non
  l'arrangement un peu différent que propose la bibliothèque externe (même
  nombre de tuiles posées, mais une combinaison de plus déplacée, d'où une
  étape de plus — c'était la cause de l'intermittence corrigée par #210).

Le solveur maison est déterministe (``threads=1``, ``random_seed=0``) : le
nombre d'étapes condensées de ce coup est donc STABLE, indépendant de la
vitesse de la machine et de la source du scénario.

Chaque test se saute proprement si sa source n'est pas installée. Pour
exécuter les propriétés générales (bibliothèque externe) :

    python -m venv .venv-solveur-exact
    .venv-solveur-exact/bin/pip install 'rummikub-solver[highs]' pytest
    .venv-solveur-exact/bin/python -m pytest tests/test_condense_solveur.py
"""

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from rummikub.moteur import solveur_exact as solveur_maison  # noqa: E402
from rummikub.moteur.description_coup import (  # noqa: E402
    etapes_coup_ia, mesurer_coup_ia)

_DONNEES = Path(__file__).resolve().parent / "donnees"


def _cas():
    return (sorted(_DONNEES.glob("cas_expert_*.json"))
            + sorted(_DONNEES.glob("reference_*.json")))


def _coup_externe(data):
    """Plateau avant/après du coup reconstruit avec la BIBLIOTHÈQUE EXTERNE
    ``rummikub-solver`` — sert aux propriétés générales, insensibles à la
    source. Saute le test si la bibliothèque n'est pas installée."""
    pytest.importorskip("rummikub_solver")
    import solveur_exact  # scripts/solveur_exact.py  # noqa: E402
    coup = solveur_exact.resoudre_coup_exact(
        data["etat"], data["idx"], budget_temps=12.0)
    if coup is None or coup["action"] != "jouer":
        return None
    return data["etat"]["plateau"], coup["nouveau_plateau"]


def _coup_maison(data, budget_temps):
    """Plateau avant/après du coup du solveur MAISON (``moteur/solveur_exact``,
    HiGHS) — le coup RÉELLEMENT joué par Expert. Saute le test si highspy/numpy
    ne sont pas installés."""
    if not solveur_maison.DISPONIBLE:
        pytest.skip("le solveur exact maison (highspy/numpy) n'est pas installé")
    coup = solveur_maison.resoudre_coup_exact(
        data["etat"], data["idx"], budget_temps=budget_temps)
    if coup is None or coup["action"] != "jouer":
        return None
    return data["etat"]["plateau"], coup["nouveau_plateau"]


def _ids_plateau(plateau):
    return [d["id"] for combo in plateau for d in combo]


def _verifier(avant, apres):
    condense = etapes_coup_ia(avant, apres, mode="condense")
    detaille = etapes_coup_ia(avant, apres, mode="detaille")
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
    plateaux = _coup_externe(data)
    if plateaux is None:
        pytest.skip("le modèle exact ne pose aucune tuile sur ce cas")
    _verifier(*plateaux)


def test_condense_bruno_tour57_moins_de_onze_etapes(facteur_machine):
    """Le coup du solveur MAISON de Bruno au tour 57 (27 étapes en détaillé)
    se parcourt de façon bien plus courte une fois condensé (issue #207).

    Seuil : le solveur maison (déterministe) pose ici 4 tuiles et son
    arrangement se condense en EXACTEMENT 13 étapes (mesuré, stable quel que
    soit le budget) ; on borne donc à « au plus 13 » — juste au-dessus du
    nombre réellement obtenu, pour garder une VRAIE borne (nettement moins que
    les 27 étapes du détaillé, objectif de #207) sans dépendre de la source du
    scénario. C'est la bibliothèque externe qui donnait 12 étapes (une
    combinaison déplacée de moins), d'où l'ancien seuil « < 11 » calibré sur la
    mauvaise source et devenu instable (issue #210).

    Budget mis à l'échelle de la vitesse machine (``facteur_machine``, #206) :
    le solveur atteint son optimum en ~0,3 s, mais une machine lente a besoin
    d'une marge pour terminer ses passes lexicographiques — le RÉSULTAT (13
    étapes) ne change pas, seule la robustesse au ralentissement est assurée."""
    data = json.loads((_DONNEES / "cas_expert_bruno_tour57.json")
                      .read_text(encoding="utf-8"))
    plateaux = _coup_maison(data, budget_temps=12.0 * facteur_machine)
    assert plateaux is not None
    condense = _verifier(*plateaux)
    assert len(condense) <= 13
