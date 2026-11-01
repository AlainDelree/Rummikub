#!/usr/bin/env python3
"""Tournoi de validation CIBLÉ du BAS de l'échelle, par DUELS uniquement
(issue #220, suite de #216/#217).

Ne joue que les deux paires du bas de l'échelle — **Débutant vs Facile** et
**Facile vs Intermédiaire** — chaque donne jouée DEUX fois en miroir (mains
des deux IA échangées). Objectif : vérifier que

  * Facile bat Débutant dans une fourchette nette (visée 60–75 %) ;
  * Facile vs Intermédiaire reste dans une fourchette nette (60–75 %).

**#220 retire le relevé des tuiles restantes en défaite** (miroir d'un niveau
contre lui-même, option ``--donnes-profil``) : ce critère mesurait surtout la
longueur des parties (dépend de la vitesse de l'adversaire, pas comparable à
un joueur humain), les manches ne finissent plus naturellement dès que
``perturbation_max >= 1`` (les deux joueurs réarrangent le plateau sans
avancer), et il consommait TOUT le temps imparti des tournois de #216/#217
sans que les duels ci-dessus ne soient jamais joués. Voir CONTEXTE.md §16.
``scripts/calibrer_niveaux.py`` et le relevé de ``scripts/profil_joueur.py``
reposent ENCORE sur ce critère (hors périmètre de #220).

Limite de temps FERME (``--limite-temps``) : en plus de l'arrêt propre interne
(aucune nouvelle donne lancée au-delà de la limite), un garde-fou EXTERNE
(sous-processus surveillé, voir ``scripts/_limite_temps_ferme.py``) termine le
tournoi — et tout sous-processus qu'il aurait créé — si la limite est
dépassée d'une marge bornée, quoi qu'il arrive à l'intérieur (donne bloquée
ou non). Code de sortie : ``0`` terminé normalement, ``3`` arrêté sur la
limite de temps, ``1`` erreur.

Résultats PARTIELS écrits en continu dans ``--sortie`` (après CHAQUE donne) :
chaque paire affiche victoires/parties jouées, taux ± marge, et donnes
terminées/prévues — marquée « partiel » tant qu'elle n'est pas finie. La fin
du fichier indique si le tournoi est allé au bout ou s'est arrêté sur la
limite de temps, et liste les paires incomplètes.

Usage (commande à relancer par Alain hors contrainte de temps) :

    python scripts/valider_bas_echelle.py --donnes 40 --seed 0 \
        --budget-solveur 1.5 --max-tours 300 --limite-temps 5400 \
        --sortie resultats_bas_echelle_220.txt
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

from rummikub.moteur import ia as _ia  # noqa: E402
from rummikub.moteur import niveaux as _niveaux  # noqa: E402
from comparer_niveaux_ia import comparer, intervalle_confiance_95  # noqa: E402
from _limite_temps_ferme import (  # noqa: E402
    CODE_LIMITE_TEMPS, CODE_TERMINE, lancer_avec_limite_ferme,
)
from _rapport_duels import entete_machine, verdict_ecart  # noqa: E402
from _verif_solveur_exact import exiger_solveur_exact_ou_quitter  # noqa: E402

logger = logging.getLogger("valider_bas_echelle")

PAIRES = [("Débutant", "Facile"), ("Facile", "Intermédiaire")]


def _ecrire(sortie, lignes: list[str]) -> None:
    """Réécrit INTÉGRALEMENT le fichier de sortie (résultats partiels) et vide
    le tampon, pour qu'Alain puisse suivre l'avancement en continu."""
    if sortie is None:
        return
    Path(sortie).write_text("\n".join(lignes) + "\n", encoding="utf-8")


def _executer(args) -> int:
    """Logique réelle du tournoi — appelée en sous-processus (``--_worker``)
    quand ``--limite-temps`` est fourni, ou en direct sinon (voir ``main``)."""
    paires = {"deb-fac": [PAIRES[0]], "fac-int": [PAIRES[1]]}.get(
        args.paire, PAIRES)

    # Override candidat de Facile (comparaison de réglages avant de figer
    # niveaux.py) : ne modifie que l'entrée en mémoire de ce processus.
    if args.facile_perturbation is not None or args.facile_oubli is not None:
        actuel = _niveaux.BRIDAGES["Facile"]
        if args.facile_perturbation is None:
            pert = actuel.perturbation_max
        elif str(args.facile_perturbation).strip().lower() in (
                "inf", "none", "illimite", "illimité", "∞"):
            pert = None
        else:
            pert = int(args.facile_perturbation)
        oubli = actuel.taux_oubli if args.facile_oubli is None else args.facile_oubli
        _niveaux.BRIDAGES["Facile"] = _niveaux.Bridage(
            perturbation_max=pert, taux_oubli=oubli)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
    logger.setLevel(logging.INFO)

    if args.budget_solveur is not None:
        _ia.BUDGET_TEMPS_EXPERT = args.budget_solveur

    debut = time.monotonic()
    deadline = (debut + args.limite_temps) if args.limite_temps else None

    lignes: list[str] = []
    budget_txt = (f"{args.budget_solveur:.2f} s/tour"
                  if args.budget_solveur is not None else "production (1.50 s)")
    lignes.append("=" * 72)
    lignes.append("VALIDATION DU BAS DE L'ÉCHELLE PAR DUELS (issue #220, "
                  "suite #216/#217)")
    lignes.extend(entete_machine())
    _bf = _niveaux.BRIDAGES["Facile"]
    _pf = "∞" if _bf.perturbation_max is None else str(_bf.perturbation_max)
    lignes.append(f"donnes={args.donnes} seed={args.seed} "
                  f"max_tours={args.max_tours} budget_solveur={budget_txt}")
    lignes.append(f"Réglage Facile testé : perturbation={_pf} "
                  f"oubli={_bf.taux_oubli:.2f}")
    lignes.append("Critère force : duel entre niveaux voisins (même donne "
                  "jouée 2x, mains échangées) ; visé 60-75 % pour le niveau "
                  "le plus fort.")
    lignes.append("=" * 72)
    _ecrire(args.sortie, lignes)

    lignes.append("")
    lignes.append("PAIRES DU BAS (taux de victoire du niveau le PLUS FORT) :")
    _ecrire(args.sortie, lignes)

    paires_incompletes: list[tuple[str, str, int, int]] = []
    for faible, fort in paires:
        victoires = decides = 0
        donnes_jouees = 0
        lignes.append("")  # ligne vivante de cette paire, remplacée à chaque donne
        idx_ligne = len(lignes) - 1
        for i in range(args.donnes):
            if deadline is not None and time.monotonic() >= deadline:
                break
            r = comparer(faible, fort, 1, args.seed + i, args.max_tours,
                         nb_manches=1, preferer_simple=True)
            victoires += r["victoires"]["B"]
            decides += r["matchs_decides"]
            donnes_jouees += 1
            partiel = " [partiel]" if donnes_jouees < args.donnes else ""
            if decides:
                taux, marge = intervalle_confiance_95(victoires, decides)
                verdict = verdict_ecart(taux, marge)
                lignes[idx_ligne] = (
                    f"    {faible} vs {fort}: {fort} "
                    f"{victoires}/{decides} = {taux * 100:.1f} % "
                    f"± {marge * 100:.1f} pt "
                    f"[{donnes_jouees}/{args.donnes} donnes]{partiel} {verdict}")
            else:
                lignes[idx_ligne] = (
                    f"    {faible} vs {fort}: aucun match décidé "
                    f"[{donnes_jouees}/{args.donnes} donnes]{partiel}")
            _ecrire(args.sortie, lignes)
        if donnes_jouees < args.donnes:
            paires_incompletes.append((faible, fort, donnes_jouees, args.donnes))
        lignes.append("")
        _ecrire(args.sortie, lignes)

    interrompu = bool(paires_incompletes)
    duree = time.monotonic() - debut
    lignes.append(f"Temps total : {duree:.1f} s.")
    if interrompu:
        lignes.append("(!) ARRÊTÉ SUR LA LIMITE DE TEMPS : tournoi INCOMPLET.")
        for faible, fort, jouees, demandees in paires_incompletes:
            lignes.append(f"    Paire incomplète : {faible} vs {fort} "
                          f"({jouees}/{demandees} donnes).")
    else:
        lignes.append("TERMINÉ NORMALEMENT (toutes les donnes demandées jouées).")
    lignes.append("=" * 72)
    _ecrire(args.sortie, lignes)
    print("\n".join(lignes))
    return CODE_LIMITE_TEMPS if interrompu else CODE_TERMINE


def _construire_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tournoi de validation ciblé du bas de l'échelle par "
                    "DUELS (Débutant/Facile/Intermédiaire, issue #220).")
    parser.add_argument("--donnes", type=int, default=40)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-tours", type=int, default=300)
    parser.add_argument("--budget-solveur", type=float, default=None,
                        help="Budget du solveur exact par tour (défaut "
                             "production = 1.5 s). À signaler si réduit.")
    parser.add_argument("--limite-temps", type=float, default=None,
                        help="Limite de temps FERME (s) pour tout le "
                             "tournoi : aucune nouvelle donne lancée au-delà, "
                             "et un garde-fou externe termine le processus "
                             "(et tout sous-processus) si elle est quand "
                             "même dépassée.")
    parser.add_argument("--sortie", default=None,
                        help="Fichier où écrire les résultats PARTIELS en "
                             "continu (après chaque donne).")
    parser.add_argument("--facile-perturbation", default=None,
                        help="Override TEMPORAIRE de la perturbation de Facile "
                             "(entier >= 0, ou inf) pour tester un réglage "
                             "candidat sans toucher niveaux.py.")
    parser.add_argument("--facile-oubli", type=float, default=None,
                        help="Override TEMPORAIRE du taux d'oubli de Facile.")
    parser.add_argument("--paire", choices=("toutes", "deb-fac", "fac-int"),
                        default="toutes",
                        help="Restreindre aux paires jouées (défaut : les deux).")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str]) -> int:
    parser = _construire_parser()
    args = parser.parse_args(argv[1:])

    if args.budget_solveur is not None and args.budget_solveur <= 0:
        parser.error("--budget-solveur doit être > 0")
    if args.donnes < 1:
        parser.error("--donnes doit être au moins 1")

    # Échec franc sans solveur exact (issue #223, point 1) : Facile et
    # Intermédiaire consultent aussi le modèle exact (voir
    # ia._coup_selon_perturbation) — pas de ``--sans-exact`` ici, donc
    # toujours requis. AVANT la relance surveillée ci-dessous.
    exiger_solveur_exact_ou_quitter()

    if args._worker or args.limite_temps is None:
        return _executer(args)

    # Relance surveillée (garde-fou externe, #220) : plus de limite de temps
    # qui ne soit pas ferme — voir scripts/_limite_temps_ferme.py.
    return lancer_avec_limite_ferme(Path(__file__), list(argv[1:]),
                                    args.limite_temps)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
