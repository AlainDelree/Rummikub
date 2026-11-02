#!/usr/bin/env python3
"""Constitue le corpus de positions réelles de tour d'IA pour la mesure de
limites de volume de calcul du solveur (issue #222, tâche 3).

Joue plusieurs parties IA vs IA headless (réutilise la logique de
``scripts/simulation_ia.py`` : mêmes appels que ``Api.jeu_ia_jouer``), avec
plusieurs graines, plusieurs niveaux et 2 à 4 joueurs, et capture un instantané
AVANT chaque tour d'IA (plateau + chevalet du joueur au trait + mise initiale).
Chaque position est ensuite classée par moment de partie (début/milieu/fin,
par tiers de la partie où elle a été capturée) et marquée « chargée » si le
plateau compte au moins ``SEUIL_CHARGE`` tuiles.

Ce script NE MESURE RIEN : il ne fait qu'écrire le corpus de positions dans un
fichier JSON (``tests/donnees/corpus_positions_222.json`` par défaut), pour que
``scripts/mesurer_volume_solveur_222.py`` le rejoue à l'identique, y compris
sur une autre machine (positions figées, aucune dépendance au hasard à la
relecture — seule la GÉNÉRATION du corpus est aléatoire, sous graines fixes).

Le budget du solveur Expert est réduit pendant la génération (``--budget-ia``,
défaut 0.3 s) : cela ne change QUE la vitesse de génération du corpus (parties
jouées un peu moins finement), jamais le jeu réel ni les niveaux de
production — comparable à l'option ``--budget-solveur`` déjà utilisée par
``scripts/echelle_niveaux.py`` pour les mêmes raisons.

Usage :

    python scripts/generer_corpus_positions_222.py
    python scripts/generer_corpus_positions_222.py --cible 20 --sortie /tmp/corpus_test.json
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "src"
SCRIPTS = Path(__file__).resolve().parent
for p in (SRC, SCRIPTS):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from rummikub.config import NIVEAUX  # noqa: E402
from rummikub.moteur import ia as _ia  # noqa: E402
from rummikub.moteur.partie import (  # noqa: E402
    backup_debut_tour, creer_partie, piocher,
)
from simulation_ia import construire_joueurs, jouer_un_tour  # noqa: E402
from _corpus_positions_222 import (  # noqa: E402
    position_depuis_etat, nb_tuiles_plateau,
)
from _verif_solveur_exact import (  # noqa: E402
    entete_dependances, exiger_solveur_exact_ou_quitter,
)

# Seuil de tuiles posées à partir duquel un plateau est considéré « chargé »
# (tâche 3 de l'issue #222 : le corpus doit en couvrir explicitement).
SEUIL_CHARGE = 30

# Plans de partie (nb_joueurs, décalage de niveaux, manches, max_tours) : la
# combinaison fait varier le nombre de joueurs, le mélange de niveaux (donc la
# vitesse de jeu et la taille des mains) et la longueur de partie (manches
# multiples → plateaux plus chargés en fin de match).
_PLANS = [
    (2, 0, 1, 160),
    (2, 2, 1, 160),
    (3, 0, 1, 160),
    (3, 3, 1, 160),
    (4, 0, 1, 160),
    (4, 1, 1, 160),
    (2, 0, 2, 160),
    (4, 2, 2, 160),
    (3, 1, 1, 220),
    (2, 4, 1, 220),
]


def _niveaux_decales(nb_joueurs: int, decalage: int) -> list[str]:
    return [NIVEAUX[(i + decalage) % len(NIVEAUX)] for i in range(nb_joueurs)]


def _jouer_une_partie(seed: int, nb_joueurs: int, decalage: int,
                      nb_manches: int, max_tours: int,
                      plafond_positions: int) -> list[dict]:
    """Joue une partie complète (ou jusqu'à ``plafond_positions`` tours
    capturés) et retourne les instantanés brut (``etat`` complet + ``idx`` +
    ``tour_index``), SANS classement de phase (fait par l'appelant une fois
    le nombre total de tours de la partie connu)."""
    random.seed(seed)
    niveaux = _niveaux_decales(nb_joueurs, decalage)
    config_joueurs = construire_joueurs(nb_joueurs, niveaux)
    etat = creer_partie(config_joueurs, {"nb_manches": nb_manches})
    backup_debut_tour(etat)

    captures = []
    for numero_manche in range(1, nb_manches + 1):
        tours = 0
        while not etat["manche_terminee"]:
            tours += 1
            if tours > max_tours or len(captures) >= plafond_positions:
                break
            idx = etat["index_joueur_actuel"]
            captures.append({
                "etat": copy.deepcopy(etat), "idx": idx, "niveau": niveaux[idx],
                "tour_index": len(captures),
            })
            _anomalies, etat = jouer_un_tour(etat, idx)
            backup_debut_tour(etat)
        if len(captures) >= plafond_positions:
            break
        if numero_manche < nb_manches and not etat.get("manche_terminee"):
            break  # garde-fou anti-blocage atteint : pas de manche suivante
        if numero_manche < nb_manches:
            from rummikub.moteur.partie import nouvelle_manche
            etat = nouvelle_manche(etat)
            backup_debut_tour(etat)

    return captures


def _classer_phase(tour_index: int, total: int) -> str:
    if total <= 1:
        return "milieu"
    fraction = tour_index / (total - 1)
    if fraction < 1 / 3:
        return "debut"
    if fraction < 2 / 3:
        return "milieu"
    return "fin"


def generer(cible: int, plafond_par_partie: int, budget_ia: float,
           verbose: bool = False) -> list[dict]:
    corpus: list[dict] = []
    ancien_budget = _ia.BUDGET_TEMPS_EXPERT
    _ia.BUDGET_TEMPS_EXPERT = budget_ia
    try:
        plan_idx = 0
        graine = 0
        while len(corpus) < cible:
            nb_joueurs, decalage, nb_manches, max_tours = \
                _PLANS[plan_idx % len(_PLANS)]
            plan_idx += 1
            t0 = time.monotonic()
            captures = _jouer_une_partie(
                graine, nb_joueurs, decalage, nb_manches, max_tours,
                plafond_par_partie)
            graine += 1
            total = len(captures)
            positions_partie = []
            for c in captures:
                phase = _classer_phase(c["tour_index"], total)
                pos = position_depuis_etat(c["etat"], c["idx"], {
                    "seed": graine - 1,
                    "nb_joueurs": nb_joueurs,
                    "niveau_joueur_actif": c["niveau"],
                    "tour_index_partie": c["tour_index"],
                    "nb_tours_partie": total,
                    "phase": phase,
                })
                pos["meta"]["charge"] = nb_tuiles_plateau(pos) >= SEUIL_CHARGE
                positions_partie.append(pos)
            corpus.extend(positions_partie)
            if verbose:
                dt = time.monotonic() - t0
                print(f"  graine={graine - 1:<3} joueurs={nb_joueurs} "
                      f"décalage={decalage} tours_captures={total:<4} "
                      f"total_corpus={len(corpus):<4} ({dt:.1f}s)")
    finally:
        _ia.BUDGET_TEMPS_EXPERT = ancien_budget
    return corpus


def _repartition(corpus: list[dict]) -> str:
    phases = {}
    charges = 0
    joueurs = {}
    for p in corpus:
        m = p["meta"]
        phases[m["phase"]] = phases.get(m["phase"], 0) + 1
        joueurs[m["nb_joueurs"]] = joueurs.get(m["nb_joueurs"], 0) + 1
        if m["charge"]:
            charges += 1
    return (f"phases={phases}  joueurs={joueurs}  "
            f"chargees={charges}/{len(corpus)}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cible", type=int, default=320,
                        help="Nombre minimal de positions à capturer "
                             "(défaut 320, marge sur les 300 demandées).")
    parser.add_argument("--plafond-partie", type=int, default=90,
                        help="Nombre maximal de tours capturés par partie "
                             "(défaut 90).")
    parser.add_argument("--budget-ia", type=float, default=0.3,
                        help="Budget du solveur Expert PENDANT LA GÉNÉRATION "
                             "seulement, en secondes (défaut 0.3 — accélère "
                             "la génération, ne change rien au jeu réel).")
    parser.add_argument("--sortie", default=str(
        RACINE / "tests" / "donnees" / "corpus_positions_222.json"),
        help="Fichier JSON de sortie.")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv[1:])

    # Échec franc sans solveur exact (issue #224, suite de #223) : les
    # parties génératrices font jouer tous les niveaux d'IA (dont Avancé/
    # Expert/Champion du Monde, selon le décalage de ``_PLANS``), sans option
    # ``--sans-exact``. Voir l'incident documenté dans
    # ``_verif_solveur_exact.py``.
    exiger_solveur_exact_ou_quitter()

    print(f"Génération du corpus (cible={args.cible} positions)...")
    debut = time.monotonic()
    corpus = generer(args.cible, args.plafond_partie, args.budget_ia,
                     verbose=args.verbose)
    duree = time.monotonic() - debut

    sortie = Path(args.sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    donnees = {
        "issue": 222,
        "description": "Corpus de positions réelles de tour d'IA pour la "
                       "mesure de limites de volume de calcul du solveur.",
        "dependances_generation": entete_dependances(),
        "nb_positions": len(corpus),
        "positions": corpus,
    }
    texte = json.dumps(donnees, ensure_ascii=False, separators=(",", ":"))
    sortie.write_text(texte, encoding="utf-8")

    taille_ko = sortie.stat().st_size / 1024
    print(f"{len(corpus)} position(s) écrites dans {sortie} "
          f"({taille_ko:.0f} Ko) en {duree:.1f}s.")
    print(_repartition(corpus))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
