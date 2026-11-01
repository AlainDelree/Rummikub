#!/usr/bin/env python3
"""Mesure, sur le corpus de positions réelles (issue #222, tâche 3), la
qualité du coup d'Expert selon la limite imposée au solveur exact
(``highspy``/HiGHS, ``moteur/solveur_exact.py``) — AUCUNE autre partie du jeu
n'est modifiée (voir CONTEXTE.md, nouvelle section « mesure du solveur »).

Pour chaque position du corpus, résout trois façons :
  1. RÉFÉRENCE : budget de temps large (``--ref-temps``, défaut 60 s) — nombre
     de tuiles posées à l'optimum (prouvé ou non) et volume de travail
     effectué (nœuds MIP + itérations simplex cumulés sur les passes
     lexicographiques, voir ``scripts/_mesure_volume_222.py``).
  2. BUDGET ACTUEL : le budget de production (``--budget-actuel``, défaut
     1.5 s, secondes) — tel qu'utilisé réellement en jeu.
  3. CANDIDATS : plusieurs limites de VOLUME (nombre de nœuds MIP,
     ``--candidats``, défaut "1,5,50,500"), avec un plafond de temps large en
     sécurité (``--securite-temps``, défaut 20 s) qui ne doit normalement
     jamais mordre (sinon le volume n'est pas la seule limite active).

Le fichier de résultats (``--sortie``) est RÉÉCRIT en continu après chaque
position (comme ``scripts/echelle_niveaux.py``, issue #220) : toujours
lisible, y compris partiel, avec le nom de la machine en en-tête
(``scripts/_rapport_duels.py``). Il permet de lire, à la fin : la part de
coups sous-optimaux dus au budget de 1.5 s (par moment de partie), et la plus
petite limite candidate qui égale au moins cette qualité.

Limite de temps FERME (``--limite-temps``) : garde-fou externe identique à
``scripts/echelle_niveaux.py`` (issue #220) — ``scripts/_limite_temps_ferme.py``.

Usage (essai rapide, 20 positions) :

    python scripts/mesurer_volume_solveur_222.py --n 20 --sortie /tmp/mesure_test.txt -v

Usage (mesure complète — commande fournie dans le rapport de clôture, à
lancer par Alain, PAS par cet agent) :

    python scripts/mesurer_volume_solveur_222.py --sortie <hors-dépôt>.txt --limite-temps 3600
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "src"
SCRIPTS = Path(__file__).resolve().parent
for p in (SRC, SCRIPTS):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from _corpus_positions_222 import etat_depuis_position  # noqa: E402
from _limite_temps_ferme import (  # noqa: E402
    CODE_LIMITE_TEMPS, CODE_TERMINE, lancer_avec_limite_ferme,
)
from _mesure_volume_222 import resoudre_avec_limite  # noqa: E402
from _rapport_duels import entete_machine  # noqa: E402

logger = logging.getLogger("mesurer_volume_solveur_222")


# --------------------------------------------------------------------------- #
# Chargement du corpus
# --------------------------------------------------------------------------- #

def charger_corpus(chemin: str, n: int | None) -> list[dict]:
    donnees = json.loads(Path(chemin).read_text(encoding="utf-8"))
    positions = donnees["positions"]
    if n is not None:
        positions = positions[:n]
    return positions


# --------------------------------------------------------------------------- #
# Mesure d'une position
# --------------------------------------------------------------------------- #

def mesurer_position(position: dict, ref_temps: float, budget_actuel: float,
                     candidats: list[int], securite_temps: float) -> dict:
    etat, idx = etat_depuis_position(position)

    reference = resoudre_avec_limite(etat, idx, None, ref_temps)
    actuel = resoudre_avec_limite(etat, idx, None, budget_actuel)

    nb_ref = reference["nb_tuiles"]
    resultats_candidats = {}
    for n in candidats:
        resultats_candidats[n] = resoudre_avec_limite(
            etat, idx, n, securite_temps)

    def _perte(res):
        if nb_ref is None or res["nb_tuiles"] is None:
            return None
        return nb_ref - res["nb_tuiles"]

    return {
        "meta": position["meta"],
        "reference": reference,
        "actuel": {**actuel, "perte": _perte(actuel)},
        "candidats": {n: {**r, "perte": _perte(r)}
                     for n, r in resultats_candidats.items()},
    }


# --------------------------------------------------------------------------- #
# Rapport texte, réécrit en continu (comme echelle_niveaux.py, issue #220)
# --------------------------------------------------------------------------- #

def _ecrire(sortie, lignes: list[str]) -> None:
    if sortie is None:
        return
    Path(sortie).write_text("\n".join(lignes) + "\n", encoding="utf-8")


def _entete(nb_positions_total: int, ref_temps: float, budget_actuel: float,
           candidats: list[int], securite_temps: float,
           limite_temps: float | None) -> list[str]:
    lignes = ["=" * 78,
              "MESURE DE VOLUME DE CALCUL DU SOLVEUR EXACT (issue #222)"]
    lignes.extend(entete_machine())
    lignes.append(f"positions={nb_positions_total} ref_temps={ref_temps:.0f}s "
                  f"budget_actuel={budget_actuel:.2f}s "
                  f"candidats_noeuds={candidats} securite_temps="
                  f"{securite_temps:.0f}s"
                  + (f" limite_temps={limite_temps:.0f}s"
                     if limite_temps is not None else ""))
    lignes.append("=" * 78)
    return lignes


def _ligne_position(i: int, r: dict) -> str:
    m = r["meta"]
    ref, act = r["reference"], r["actuel"]
    cand_txt = "  ".join(
        f"n={n}:{c['nb_tuiles']}({c['perte'] if c['perte'] is not None else '?'})"
        for n, c in r["candidats"].items())
    return (f"  #{i:<4} phase={m['phase']:<6} charge={str(m['charge']):<5} "
            f"joueurs={m['nb_joueurs']} "
            f"ref={ref['nb_tuiles']}/{ref['statut']}({ref['duree_s']:.2f}s) "
            f"actuel={act['nb_tuiles']}/{act['statut']} perte={act['perte']} "
            f"| candidats: {cand_txt}")


def _agreger(resultats: list[dict], candidats: list[int]) -> list[str]:
    """Résumé recalculé à partir des résultats déjà accumulés (valable même
    partiel) : taux de coups à l'optimum et perte moyenne, par moment de
    partie, pour le budget actuel et chaque candidat, et la plus petite
    limite candidate qui égale au moins la qualité du budget actuel."""
    lignes = ["", "RÉSUMÉ (sur les positions traitées jusqu'ici) :"]
    phases = ["debut", "milieu", "fin"]

    def _stats(cle_extraction, sous_ensemble):
        pertes = [cle_extraction(r) for r in sous_ensemble]
        pertes = [p for p in pertes if p is not None]
        n = len(sous_ensemble)
        n_optimaux = sum(1 for p in pertes if p == 0)
        moyenne = sum(pertes) / len(pertes) if pertes else None
        return n, n_optimaux, moyenne

    lignes.append(f"  Positions traitées : {len(resultats)}")
    for phase in phases:
        sous = [r for r in resultats if r["meta"]["phase"] == phase]
        if not sous:
            continue
        n, n_opt, moyenne = _stats(lambda r: r["actuel"]["perte"], sous)
        moyenne_txt = f"{moyenne:.2f}" if moyenne is not None else "?"
        lignes.append(f"  Budget actuel (1.5s), phase={phase:<6} : "
                      f"{n_opt}/{n} à l'optimum, perte moyenne={moyenne_txt}")

    lignes.append("")
    n_tot, n_opt_tot, moyenne_tot = _stats(
        lambda r: r["actuel"]["perte"], resultats)
    moyenne_txt = f"{moyenne_tot:.2f}" if moyenne_tot is not None else "?"
    lignes.append(f"  Budget actuel (1.5s), TOUTES PHASES : "
                  f"{n_opt_tot}/{n_tot} à l'optimum, perte moyenne="
                  f"{moyenne_txt}")

    plus_petit_suffisant = None
    for n in candidats:
        nn, n_opt_n, moyenne_n = _stats(
            lambda r, n=n: r["candidats"][n]["perte"], resultats)
        moyenne_n_txt = f"{moyenne_n:.2f}" if moyenne_n is not None else "?"
        duree_max = max((r["candidats"][n]["duree_s"] for r in resultats),
                        default=0.0)
        lignes.append(f"  Candidat mip_max_nodes={n:<6} : "
                      f"{n_opt_n}/{nn} à l'optimum, perte moyenne="
                      f"{moyenne_n_txt}, durée max (indicatif)="
                      f"{duree_max:.2f}s")
        if (moyenne_n is not None and moyenne_tot is not None
                and moyenne_n <= moyenne_tot and plus_petit_suffisant is None):
            plus_petit_suffisant = n

    lignes.append("")
    if plus_petit_suffisant is not None:
        lignes.append(f"  Plus petite limite candidate >= qualité du budget "
                      f"actuel : mip_max_nodes={plus_petit_suffisant}")
    else:
        lignes.append("  Plus petite limite candidate >= qualité du budget "
                      "actuel : Non établi (aucun candidat testé ne l'atteint, "
                      "ou pas assez de positions traitées).")
    return lignes


# --------------------------------------------------------------------------- #
# Boucle principale
# --------------------------------------------------------------------------- #

def mesurer(positions: list[dict], ref_temps: float, budget_actuel: float,
           candidats: list[int], securite_temps: float,
           limite_temps: float | None = None, sortie=None) -> dict:
    debut = time.monotonic()
    deadline = (debut + limite_temps) if limite_temps is not None else None
    lignes = _entete(len(positions), ref_temps, budget_actuel, candidats,
                     securite_temps, limite_temps)
    _ecrire(sortie, lignes)

    resultats = []
    interrompu = False
    for i, position in enumerate(positions):
        if deadline is not None and time.monotonic() >= deadline:
            interrompu = True
            lignes.append(f"  (arrêté sur la limite de temps après "
                          f"{i}/{len(positions)} position(s)) [partiel]")
            _ecrire(sortie, lignes)
            break
        r = mesurer_position(position, ref_temps, budget_actuel, candidats,
                             securite_temps)
        resultats.append(r)
        lignes.append(_ligne_position(i, r))
        _ecrire(sortie, lignes + _agreger(resultats, candidats)
                + ["", f"  ({len(resultats)}/{len(positions)} position(s) "
                      "traitées jusqu'ici) [partiel]" if interrompu or
                      len(resultats) < len(positions) else ""])
        logger.info("Position %d/%d traitée.", i + 1, len(positions))

    duree = time.monotonic() - debut
    lignes_finales = (lignes + _agreger(resultats, candidats) + [""])
    lignes_finales.append(f"Temps total : {duree:.1f} s.")
    if interrompu:
        lignes_finales.append("(!) ARRÊTÉ SUR LA LIMITE DE TEMPS : MESURE "
                              "INCOMPLÈTE.")
    else:
        lignes_finales.append("TERMINÉ NORMALEMENT (toutes les positions "
                              "traitées).")
    lignes_finales.append("=" * 78)
    _ecrire(sortie, lignes_finales)

    return {
        "resultats": resultats,
        "interrompu": interrompu,
        "duree_s": duree,
        "nb_positions": len(positions),
        "nb_traitees": len(resultats),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _parse_candidats(valeur: str) -> list[int]:
    return [int(x.strip()) for x in valeur.split(",") if x.strip()]


def _construire_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mesure du volume de calcul du solveur exact d'Expert "
                    "sur le corpus de positions réelles (issue #222).")
    parser.add_argument("--corpus", default=str(
        RACINE / "tests" / "donnees" / "corpus_positions_222.json"),
        help="Fichier JSON du corpus (défaut : corpus du dépôt).")
    parser.add_argument("--n", type=int, default=None,
                        help="Limite le nombre de positions utilisées "
                             "(défaut : toutes). Utiliser 20 pour l'essai.")
    parser.add_argument("--ref-temps", type=float, default=60.0,
                        help="Budget de temps de la RÉFÉRENCE, en secondes "
                             "(défaut 60).")
    parser.add_argument("--budget-actuel", type=float, default=1.5,
                        help="Budget de temps de production à comparer, en "
                             "secondes (défaut 1.5).")
    parser.add_argument("--candidats", type=_parse_candidats,
                        default=[1, 5, 50, 500],
                        help="Limites de volume candidates (mip_max_nodes), "
                             "séparées par des virgules (défaut 1,5,50,500).")
    parser.add_argument("--securite-temps", type=float, default=20.0,
                        help="Plafond de temps en SÉCURITÉ pour les candidats "
                             "de volume, en secondes (défaut 20 ; ne doit "
                             "normalement jamais mordre).")
    parser.add_argument("--limite-temps", type=float, default=None,
                        help="Limite de temps FERME, en secondes, pour toute "
                             "la mesure (garde-fou externe, voir "
                             "scripts/_limite_temps_ferme.py).")
    parser.add_argument("--sortie", default=None,
                        help="Fichier où écrire les résultats PARTIELS en "
                             "continu (après chaque position).")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    return parser


def _executer(args) -> int:
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )
    positions = charger_corpus(args.corpus, args.n)
    rapport = mesurer(positions, args.ref_temps, args.budget_actuel,
                      args.candidats, args.securite_temps,
                      args.limite_temps, sortie=args.sortie)
    print(f"{rapport['nb_traitees']}/{rapport['nb_positions']} position(s) "
          f"traitée(s) en {rapport['duree_s']:.1f}s"
          + (" [INTERROMPU]" if rapport["interrompu"] else " [TERMINÉ]"))
    if args.sortie:
        print(f"Résultats écrits dans {args.sortie}")
    return CODE_LIMITE_TEMPS if rapport["interrompu"] else CODE_TERMINE


def main(argv: list[str]) -> int:
    parser = _construire_parser()
    args = parser.parse_args(argv[1:])

    if args.n is not None and args.n < 1:
        parser.error("--n doit être au moins 1")
    if not Path(args.corpus).is_file():
        parser.error(f"corpus introuvable : {args.corpus}")

    if args._worker or args.limite_temps is None:
        return _executer(args)

    return lancer_avec_limite_ferme(Path(__file__), list(argv[1:]),
                                    args.limite_temps)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
