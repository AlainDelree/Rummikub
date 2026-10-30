#!/usr/bin/env python3
"""Recherche de réglages (perturbation permise × taux d'oubli) pour un niveau
d'IA bridé, mesurés sur le BON critère de force : les **tuiles restantes en
main quand le niveau PERD** (issue #216, suite #213).

Rappel du critère (voir ``scripts/profil_joueur.py`` et CONTEXTE.md §16) : plus
ce nombre est BAS, plus le niveau finit près de la sortie, donc plus il est
FORT. L'échelle de #213 est ordonnée mais mal étalée ; #216 recalibre Débutant,
Facile et Intermédiaire pour des écarts réguliers, Alain (≈ 3,5 tuiles) visé
ENTRE Intermédiaire et Avancé.

Principe : pour chaque réglage candidat ``(perturbation_max, taux_oubli)``, on
remplace TEMPORAIREMENT l'entrée du niveau dans ``moteur/niveaux.BRIDAGES``,
puis on simule des donnes EN MIROIR du niveau contre lui-même (``comparer`` de
``scripts/comparer_niveaux_ia.py``, reproductible sous graine fixe) et on relève
la moyenne des tuiles restantes du perdant. On balaie ainsi toute une grille de
candidats et on affiche, pour chacun, la mesure obtenue — de quoi choisir le
réglage qui atteint une cible (option ``--cible``, qui marque le plus proche).

Deux garde-fous de temps, car un niveau FAIBLE peut jouer des parties
interminables (défaut connu de #213 : > 300 tours) :

* ``--max-tours`` (défaut 150) borne chaque manche en nombre de tours ;
* ``--limite-temps`` fixe une limite FERME pour TOUTE la campagne : on ne lance
  plus de nouveau candidat (ni de nouvelle donne) une fois la limite atteinte,
  et on affiche les résultats PARTIELS déjà obtenus.

Le solveur exact (chemin ``perturbation_max > 0`` ou ``None``) est coûteux : son
budget par tour est réglable par ``--budget-solveur`` (défaut 0,5 s, contre
1,5 s en production) pour garder une campagne de calibrage dans un temps
raisonnable. Le réglage FINAL retenu doit être revérifié par le tournoi complet
(``scripts/echelle_niveaux.py``), qui, lui, joue au budget de production.

Usage :

    # Balaye une grille pour Intermédiaire et vise 4,5 tuiles restantes.
    python scripts/calibrer_niveaux.py --niveau Intermédiaire \
        --perturbations "2,3,4,inf" --oublis "0.0,0.05,0.1" \
        --donnes 20 --cible 4.5 --limite-temps 1200

    # Balaye le taux d'oubli de Facile (perturbation nulle, chemin rapide).
    python scripts/calibrer_niveaux.py --niveau Facile \
        --perturbations "0" --oublis "0.05,0.10,0.15" --donnes 20 --cible 7
"""

import argparse
import logging
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "src"
SCRIPTS = RACINE / "scripts"
for _p in (SRC, SCRIPTS):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rummikub.config import NIVEAUX  # noqa: E402
from rummikub.moteur import ia as _ia  # noqa: E402
from rummikub.moteur import niveaux as _niveaux  # noqa: E402

# Réutilisation directe de la logique de match miroir, reproductible (#213).
from comparer_niveaux_ia import comparer, moyenne  # noqa: E402

logger = logging.getLogger("calibrer_niveaux")


def _parse_perturbations(valeur: str) -> list[int | None]:
    """Liste de perturbations candidates. ``inf``/``none``/``illimite`` → None
    (solveur complet) ; sinon un entier >= 0."""
    candidats: list[int | None] = []
    for brut in valeur.split(","):
        brut = brut.strip().lower()
        if not brut:
            continue
        if brut in ("inf", "none", "illimite", "illimité", "∞"):
            candidats.append(None)
        else:
            n = int(brut)
            if n < 0:
                raise argparse.ArgumentTypeError(
                    f"perturbation négative interdite : {n}")
            candidats.append(n)
    if not candidats:
        raise argparse.ArgumentTypeError("aucune perturbation fournie")
    return candidats


def _parse_oublis(valeur: str) -> list[float]:
    oublis: list[float] = []
    for brut in valeur.split(","):
        brut = brut.strip()
        if not brut:
            continue
        o = float(brut)
        if not 0.0 <= o <= 1.0:
            raise argparse.ArgumentTypeError(
                f"taux d'oubli hors de [0, 1] : {o}")
        oublis.append(o)
    if not oublis:
        raise argparse.ArgumentTypeError("aucun taux d'oubli fourni")
    return oublis


def mesurer_reglage(niveau: str, perturbation: int | None, oubli: float,
                    nb_donnes: int, seed: int, max_tours: int,
                    deadline: float | None) -> dict:
    """Mesure un réglage candidat pour ``niveau`` : remplace TEMPORAIREMENT son
    bridage par ``(perturbation, oubli)`` et simule ``nb_donnes`` donnes EN
    MIROIR du niveau contre lui-même (chacune jouée 2 fois, places échangées),
    DONNE PAR DONNE pour respecter ``deadline`` (instant monotone, vérifié avant
    chaque donne). Renvoie la moyenne des tuiles restantes du perdant et le
    nombre de manches décidées.

    Chaque donne ``i`` utilise ``seed + i`` : la campagne est reproductible et
    tous les réglages jouent la MÊME suite de donnes (comparables entre eux)."""
    ancien = _niveaux.BRIDAGES.get(niveau)
    _niveaux.BRIDAGES[niveau] = _niveaux.Bridage(
        perturbation_max=perturbation, taux_oubli=oubli)
    tuiles_perdant: list[int] = []
    manches_decidees = 0
    garde_fou = 0
    donnes_jouees = 0
    try:
        for i in range(nb_donnes):
            if deadline is not None and time.monotonic() >= deadline:
                break
            resume = comparer(niveau, niveau, 1, seed + i, max_tours,
                              nb_manches=1, preferer_simple=True)
            tuiles_perdant.extend(resume["tuiles_perdant"])
            manches_decidees += len(resume["tuiles_perdant"])
            garde_fou += resume["fins"]["garde_fou"]
            donnes_jouees += 1
    finally:
        if ancien is not None:
            _niveaux.BRIDAGES[niveau] = ancien
        else:  # pragma: no cover - niveau hors table (ne devrait pas arriver)
            _niveaux.BRIDAGES.pop(niveau, None)

    return {
        "perturbation": perturbation,
        "oubli": oubli,
        "tuiles_restantes": moyenne(tuiles_perdant) if tuiles_perdant else None,
        "manches_decidees": manches_decidees,
        "donnes_jouees": donnes_jouees,
        "donnes_demandees": nb_donnes,
        "garde_fou": garde_fou,
    }


def balayer(niveau: str, perturbations: list[int | None], oublis: list[float],
            nb_donnes: int, seed: int, max_tours: int,
            limite_temps: float | None) -> list[dict]:
    """Balaie la grille ``perturbations × oublis`` sous la limite de temps
    FERME ``limite_temps`` (secondes). On arrête de lancer de nouveaux réglages
    dès la limite dépassée (résultats partiels exploités)."""
    debut = time.monotonic()
    deadline = (debut + limite_temps) if limite_temps is not None else None
    resultats: list[dict] = []
    for perturbation in perturbations:
        for oubli in oublis:
            if deadline is not None and time.monotonic() >= deadline:
                logger.warning("Limite de temps atteinte : arrêt du balayage.")
                return resultats
            p_txt = "∞" if perturbation is None else str(perturbation)
            logger.info("Réglage perturbation=%s oubli=%.2f ...", p_txt, oubli)
            res = mesurer_reglage(niveau, perturbation, oubli, nb_donnes, seed,
                                  max_tours, deadline)
            resultats.append(res)
            if res["tuiles_restantes"] is not None:
                logger.info("  → %.2f tuile(s) restante(s) (%d manche(s))",
                            res["tuiles_restantes"], res["manches_decidees"])
    return resultats


# --------------------------------------------------------------------------- #
# Affichage
# --------------------------------------------------------------------------- #

def afficher(niveau: str, resultats: list[dict], cible: float | None,
             budget_solveur: float, duree: float) -> None:
    print("=" * 72)
    print(f"CALIBRAGE DU NIVEAU « {niveau} » (issue #216)")
    print("Critère : tuiles restantes en main quand le niveau PERD "
          "(plus bas = plus fort).")
    print(f"Budget du solveur exact par tour : {budget_solveur:.2f} s "
          "(production : 1,50 s — revérifier au tournoi complet).")
    if cible is not None:
        print(f"Cible visée : {cible:.2f} tuile(s) restante(s).")
    print("-" * 72)
    print(f"  {'Perturbation':>12s}  {'Oubli':>6s}  "
          f"{'Tuiles déf.':>11s}  {'Manches':>7s}  "
          f"{'Écart cible' if cible is not None else '':>11s}")
    print("-" * 72)

    meilleur = None
    for res in resultats:
        p_txt = "∞" if res["perturbation"] is None else str(res["perturbation"])
        if res["tuiles_restantes"] is None:
            mesure = "n/a"
            ecart_txt = ""
        else:
            mesure = f"{res['tuiles_restantes']:.2f}"
            if cible is not None:
                ecart = abs(res["tuiles_restantes"] - cible)
                ecart_txt = f"{ecart:.2f}"
                if meilleur is None or ecart < meilleur[0]:
                    meilleur = (ecart, res)
            else:
                ecart_txt = ""
        marque = ""
        gf = f" (garde-fou×{res['garde_fou']})" if res["garde_fou"] else ""
        print(f"  {p_txt:>12s}  {res['oubli']:>6.2f}  {mesure:>11s}  "
              f"{res['manches_decidees']:>7d}  {ecart_txt:>11s}{marque}{gf}")

    print("-" * 72)
    if cible is not None and meilleur is not None:
        _ecart, res = meilleur
        p_txt = "∞" if res["perturbation"] is None else str(res["perturbation"])
        print(f"  RÉGLAGE LE PLUS PROCHE DE LA CIBLE ({cible:.2f}) : "
              f"perturbation={p_txt}, oubli={res['oubli']:.2f} "
              f"→ {res['tuiles_restantes']:.2f} tuile(s) "
              f"(écart {_ecart:.2f}).")
        if _ecart > 1.0:
            print("  (!) Écart > 1 tuile : cible possiblement NON atteignable "
                  "avec ces deux paramètres — élargir la grille ou retenir "
                  "ce plus proche en le signalant (issue #216 §2).")
    print(f"  Temps total du balayage : {duree:.1f}s.")
    print("=" * 72)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Recherche de réglages (perturbation × oubli) d'un niveau "
                    "d'IA par la mesure des tuiles restantes en défaite "
                    "(issue #216).")
    parser.add_argument("--niveau", required=True, choices=NIVEAUX,
                        help="Niveau à calibrer.")
    parser.add_argument("--perturbations", default="0,1,2,3",
                        help="Perturbations candidates, séparées par des "
                             "virgules (entiers >= 0, ou inf/none pour le "
                             "solveur complet). Défaut « 0,1,2,3 ».")
    parser.add_argument("--oublis", default="0.0,0.1,0.2,0.3",
                        help="Taux d'oubli candidats dans [0, 1], séparés par "
                             "des virgules. Défaut « 0.0,0.1,0.2,0.3 ».")
    parser.add_argument("--donnes", type=int, default=20,
                        help="Donnes distinctes par réglage (défaut 20 ; "
                             "chacune jouée 2 fois en miroir).")
    parser.add_argument("--seed", type=int, default=0,
                        help="Graine aléatoire (défaut 0, reproductible).")
    parser.add_argument("--max-tours", type=int, default=150,
                        help="Garde-fou anti-blocage par manche (défaut 150 ; "
                             "borne les parties interminables des niveaux "
                             "faibles, défaut connu > 300 tours de #213).")
    parser.add_argument("--budget-solveur", type=float, default=0.5,
                        help="Budget du solveur exact par tour, en secondes "
                             "(défaut 0.5 ; production 1.5). Baisser accélère "
                             "le balayage ; revérifier au tournoi complet.")
    parser.add_argument("--cible", type=float, default=None,
                        help="Cible en tuiles restantes en défaite : marque le "
                             "réglage le plus proche.")
    parser.add_argument("--limite-temps", type=float, default=None,
                        help="Limite de temps FERME, en secondes, pour tout le "
                             "balayage (résultats partiels exploités).")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Journalise le détail du balayage.")
    args = parser.parse_args(argv[1:])

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )
    logger.setLevel(logging.INFO)

    try:
        perturbations = _parse_perturbations(args.perturbations)
        oublis = _parse_oublis(args.oublis)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
        return 2

    if args.donnes < 1:
        parser.error("--donnes doit être au moins 1")

    # Budget du solveur exact pour TOUTE la campagne (accélère le balayage).
    _ia.BUDGET_TEMPS_EXPERT = args.budget_solveur

    debut = time.monotonic()
    resultats = balayer(args.niveau, perturbations, oublis, args.donnes,
                        args.seed, args.max_tours, args.limite_temps)
    duree = time.monotonic() - debut
    afficher(args.niveau, resultats, args.cible, args.budget_solveur, duree)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
