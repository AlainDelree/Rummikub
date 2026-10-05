#!/usr/bin/env python3
"""Simulation headless de parties Rummikub IA vs IA (sans pywebview/UI).

Fait s'affronter 2 à 4 IA (niveaux configurables) sur une ou plusieurs manches
en pilotant directement le moteur de jeu (``rummikub.moteur``), exactement
comme le fait ``Api.jeu_ia_jouer`` côté UI (mêmes appels, même traitement du
cas « coup IA invalide » : annulation + pioche de secours). Toute exception,
coup invalide ou blocage (trop de tours sans fin de manche) est journalisé et
compté comme anomalie ; le code de sortie reflète le résultat (0 = partie
saine, 1 = au moins une anomalie détectée).

Usage :

    python scripts/simulation_ia.py
    python scripts/simulation_ia.py --joueurs 3 --manches 5 --seed 42
    python scripts/simulation_ia.py --niveaux Débutant,Expert,Expert -v

Options :
    --joueurs N      Nombre d'IA (2-4, défaut 4).
    --niveaux LISTE  Niveaux séparés par des virgules, un par joueur
                     (ex. "Débutant,Avancé"). Par défaut, les niveaux sont
                     répartis cycliquement sur les 5 niveaux disponibles.
    --manches N      Nombre de manches à jouer (défaut 1).
    --max-tours N    Garde-fou anti-blocage : nombre max de tours dans une
                     même manche avant abandon (défaut 500).
    --seed N         Graine aléatoire, pour une simulation reproductible.
    -v, --verbose    Journalise chaque tour (sinon, seules les anomalies et
                     les fins de manche sont journalisées).
"""

import argparse
import logging
import random
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rummikub.config import NIVEAUX  # noqa: E402
from rummikub.moteur.ia import jouer_ia  # noqa: E402
from rummikub.moteur.partie import (  # noqa: E402
    annuler_tour,
    backup_debut_tour,
    creer_partie,
    jouer_tour,
    nouvelle_manche,
    passer_tour,
    piocher,
)

logger = logging.getLogger("simulation_ia")


# --------------------------------------------------------------------------- #
# Construction de la partie
# --------------------------------------------------------------------------- #

def construire_joueurs(nb_joueurs: int, niveaux: list[str] | None) -> list[dict]:
    """Construit la config_joueurs attendue par ``creer_partie`` : nb_joueurs
    IA, avec les niveaux donnés (ou, à défaut, répartis cycliquement sur les
    5 niveaux connus)."""
    if niveaux is None:
        niveaux = [NIVEAUX[i % len(NIVEAUX)] for i in range(nb_joueurs)]
    return [
        {"nom": f"IA-{i + 1} ({niveaux[i]})", "est_ia": True, "niveau": niveaux[i]}
        for i in range(nb_joueurs)
    ]


# --------------------------------------------------------------------------- #
# Un tour d'IA (réplique la logique de Api.jeu_ia_jouer, sans pywebview)
# --------------------------------------------------------------------------- #

def jouer_un_tour(etat: dict, idx: int) -> tuple[list[str], dict]:
    """Joue le tour de l'IA à l'index ``idx``.

    Retourne ``(anomalies, etat)``. En cas d'exception de l'IA ou de coup
    invalide, se replie sur une pioche de secours (comme côté UI) pour que la
    simulation puisse continuer et journalise l'anomalie.
    """
    anomalies: list[str] = []
    nom = etat["joueurs"][idx]["nom"]
    backup_debut_tour(etat)

    try:
        res_ia = jouer_ia(etat, idx)
    except Exception:
        logger.exception(
            "Exception de l'IA %s au tour %d", nom, etat["tour_numero"])
        anomalies.append(f"tour {etat['tour_numero']} : exception IA ({nom})")
        annuler_tour(etat)
        return anomalies, piocher(etat)["etat"]

    action = res_ia.get("action")
    if action == "jouer":
        res = jouer_tour(etat, res_ia["ids_tuiles"], res_ia["nouveau_plateau"])
        if not res["ok"]:
            logger.warning(
                "Coup invalide proposé par %s au tour %d : %s",
                nom, etat["tour_numero"], res["erreur"])
            anomalies.append(
                f"tour {etat['tour_numero']} : coup invalide ({nom}) "
                f"— {res['erreur']}")
            annuler_tour(etat)
            res = piocher(etat)
    elif action == "piocher":
        res = piocher(etat)
    elif action == "passer":
        res = passer_tour(etat)
    else:
        logger.warning(
            "Action IA inconnue %r proposée par %s au tour %d",
            action, nom, etat["tour_numero"])
        anomalies.append(
            f"tour {etat['tour_numero']} : action inconnue ({action!r}) "
            f"de {nom}")
        annuler_tour(etat)
        res = piocher(etat)

    return anomalies, res["etat"]


# --------------------------------------------------------------------------- #
# Simulation complète
# --------------------------------------------------------------------------- #

def simuler(nb_joueurs: int, niveaux: list[str] | None, nb_manches: int,
            max_tours: int, seed: int | None = None) -> dict:
    """Joue ``nb_manches`` manches complètes IA vs IA.

    Retourne un résumé : nombre de manches/tours joués, anomalies
    rencontrées, durée et scores cumulés finaux.
    """
    if seed is not None:
        random.seed(seed)

    config_joueurs = construire_joueurs(nb_joueurs, niveaux)
    etat = creer_partie(config_joueurs, {"nb_manches": 1})
    backup_debut_tour(etat)

    noms = [j["nom"] for j in etat["joueurs"]]
    logger.info("Partie créée : %s", ", ".join(noms))

    debut = time.monotonic()
    anomalies_total: list[str] = []
    nb_tours_total = 0
    manches_jouees = 0
    bloquee = False

    for numero_manche in range(1, nb_manches + 1):
        tours_manche = 0
        while not etat["manche_terminee"]:
            tours_manche += 1
            nb_tours_total += 1
            if tours_manche > max_tours:
                logger.error(
                    "Blocage détecté en manche %d : %d tours joués sans "
                    "fin de manche (seuil=%d).",
                    numero_manche, tours_manche, max_tours)
                anomalies_total.append(
                    f"manche {numero_manche} : blocage après {tours_manche} "
                    f"tours sans fin de manche")
                bloquee = True
                break

            idx = etat["index_joueur_actuel"]
            if verbose_actif():
                logger.debug(
                    "Manche %d, tour %d : au tour de %s (%d tuile(s))",
                    numero_manche, etat["tour_numero"], etat["joueurs"][idx]["nom"],
                    len(etat["joueurs"][idx]["chevalet"]))
            anomalies, etat = jouer_un_tour(etat, idx)
            anomalies_total.extend(anomalies)
            backup_debut_tour(etat)

        if bloquee:
            break

        manches_jouees += 1
        scores = {j["nom"]: j["score_manche"] for j in etat["joueurs"]}
        logger.info(
            "Manche %d terminée en %d tour(s). Scores de la manche : %s",
            numero_manche, tours_manche, scores)

        if numero_manche < nb_manches:
            etat = nouvelle_manche(etat)
            backup_debut_tour(etat)

    duree = time.monotonic() - debut
    scores_finaux = {j["nom"]: j["score_cumul"] for j in etat["joueurs"]}

    return {
        "manches_jouees": manches_jouees,
        "manches_demandees": nb_manches,
        "tours_total": nb_tours_total,
        "anomalies": anomalies_total,
        "duree_s": duree,
        "scores_finaux": scores_finaux,
        "bloquee": bloquee,
    }


def verbose_actif() -> bool:
    return logger.isEnabledFor(logging.DEBUG)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def parse_niveaux(valeur: str | None, nb_joueurs: int) -> list[str] | None:
    if valeur is None:
        return None
    niveaux = [n.strip() for n in valeur.split(",")]
    if len(niveaux) != nb_joueurs:
        raise argparse.ArgumentTypeError(
            f"--niveaux doit contenir exactement {nb_joueurs} niveau(x) "
            f"séparés par des virgules (reçu : {len(niveaux)})")
    for n in niveaux:
        if n not in NIVEAUX:
            raise argparse.ArgumentTypeError(
                f"niveau inconnu : {n!r} (valides : {', '.join(NIVEAUX)})")
    return niveaux


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Simulation headless de parties Rummikub IA vs IA.")
    parser.add_argument("--joueurs", type=int, default=4, choices=(2, 3, 4),
                        help="Nombre d'IA (2-4, défaut 4).")
    parser.add_argument("--niveaux", type=str, default=None,
                        help="Niveaux séparés par des virgules, un par "
                             "joueur (défaut : répartition cyclique).")
    parser.add_argument("--manches", type=int, default=1,
                        help="Nombre de manches à jouer (défaut 1).")
    parser.add_argument("--max-tours", type=int, default=500,
                        help="Garde-fou anti-blocage par manche (défaut 500).")
    parser.add_argument("--seed", type=int, default=None,
                        help="Graine aléatoire (reproductibilité).")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Journalise chaque tour.")
    args = parser.parse_args(argv[1:])

    try:
        niveaux = parse_niveaux(args.niveaux, args.joueurs)
    except argparse.ArgumentTypeError as e:
        parser.error(str(e))
        return 2

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    resume = simuler(args.joueurs, niveaux, args.manches, args.max_tours,
                     args.seed)

    print("-" * 60)
    print(f"RÉSUMÉ : {resume['manches_jouees']}/{resume['manches_demandees']} "
          f"manche(s) jouée(s), {resume['tours_total']} tour(s) au total, "
          f"{resume['duree_s']:.2f}s.")
    print(f"Scores cumulés finaux : {resume['scores_finaux']}")
    if resume["anomalies"]:
        print(f"ANOMALIES ({len(resume['anomalies'])}) :")
        for a in resume["anomalies"]:
            print(f"  - {a}")
        return 1
    print("Aucune anomalie détectée.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
