#!/usr/bin/env python3
"""Mesure du volume de calcul du solveur exact d'Expert (``highspy``/HiGHS,
``moteur/solveur_exact.py`` — issue #222).

``mip_max_nodes`` (nombre de nœuds de branch-and-bound) est, d'après les
petits essais de l'issue #222 (voir CONTEXTE.md), le seul réglage HiGHS qui
borne de façon FIABLE le volume de travail du MIP par cette interface :
``simplex_iteration_limit``, bien qu'accepté sans erreur par l'API, n'a AUCUN
effet mesurable sur une résolution MIP (confirmé par deux essais indépendants,
dont un MIP synthétique qui ne s'arrête jamais malgré la limite). Ce module
l'applique au modèle EXACT réellement utilisé en production (``resoudre_exact``)
par un monkeypatch TEMPORAIRE, restreint à la durée de l'appel, de la seule
fonction qui construit l'objet HiGHS (``solveur_exact._nouveau_highs``) : le
code de production n'est jamais modifié, seul l'objet HiGHS qu'il construit
reçoit une option supplémentaire pour la durée de la mesure. ``threads=1`` /
``random_seed=0`` (déjà réglés en production, voir ``_nouveau_highs``) sont
conservés tels quels — c'est ce qui rend le calcul déterministe (vérifié par
l'issue #222)."""

from __future__ import annotations

import contextlib
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rummikub.moteur import solveur_exact as se  # noqa: E402


@contextlib.contextmanager
def limite_noeuds(mip_max_nodes: int | None):
    """Monkeypatch temporaire de ``solveur_exact._nouveau_highs`` : ajoute
    l'option ``mip_max_nodes`` (sans effet si ``None``) et comptabilise, sur
    l'objet HiGHS créé, le nombre de nœuds et d'itérations simplex CUMULÉS
    sur tous les appels ``h.run()`` (une résolution du modèle exact enchaîne
    plusieurs passes lexicographiques, donc plusieurs appels — voir
    ``solveur_exact._resoudre_modele``). Restaure la fonction d'origine à la
    sortie, y compris en cas d'exception."""
    original = se._nouveau_highs
    compteur = {"noeuds": 0, "simplex_iters": 0, "appels_run": 0}

    def _fabrique(time_limit):
        h = original(time_limit)
        if mip_max_nodes is not None:
            h.setOptionValue("mip_max_nodes", int(mip_max_nodes))
        run_original = h.run

        def _run_compte():
            resultat = run_original()
            try:
                info = h.getInfo()
                compteur["noeuds"] += int(info.mip_node_count)
                compteur["simplex_iters"] += int(info.simplex_iteration_count)
            except Exception:
                pass
            compteur["appels_run"] += 1
            return resultat

        h.run = _run_compte
        return h

    se._nouveau_highs = _fabrique
    try:
        yield compteur
    finally:
        se._nouveau_highs = original


def resoudre_avec_limite(etat: dict, idx: int, mip_max_nodes: int | None,
                         budget_temps: float) -> dict:
    """Résout ``etat``/``idx`` avec ``resoudre_exact`` (interface de
    production), sous la limite de nœuds ``mip_max_nodes`` (``None`` =
    illimité, seulement ``budget_temps`` comme garde-fou). Ne lève jamais :
    retourne un statut explicite plutôt que de propager l'exception, pour que
    la mesure continue sur le reste du corpus."""
    debut = time.monotonic()
    with limite_noeuds(mip_max_nodes) as compteur:
        try:
            res = se.resoudre_exact(etat, idx, budget_temps=budget_temps)
            statut = "optimal" if res.optimal else "faisable"
            nb_tuiles = res.nb_tuiles
            ids_tuiles = tuple(sorted(res.ids_tuiles))
        except se.BudgetExactDepasse:
            statut, nb_tuiles, ids_tuiles = "echec_volume_ou_temps", None, None
        except se.SolveurExactIndisponible:
            statut, nb_tuiles, ids_tuiles = "indisponible", None, None
    duree = time.monotonic() - debut
    return {
        "statut": statut,
        "nb_tuiles": nb_tuiles,
        "ids_tuiles": ids_tuiles,
        "noeuds": compteur["noeuds"],
        "simplex_iters": compteur["simplex_iters"],
        "appels_run": compteur["appels_run"],
        "duree_s": duree,
    }
