#!/usr/bin/env python3
"""Tournoi de validation CIBLÉ du BAS de l'échelle (issue #217, suite #216).

Ne joue que les deux paires du bas de l'échelle — **Débutant vs Facile** et
**Facile vs Intermédiaire** — plus la mesure des **tuiles restantes en défaite**
(miroir) de Débutant, Facile et Intermédiaire. Objectif : vérifier, après le
recalibrage de Facile (#217), que

  * Facile bat désormais Débutant dans une fourchette nette (visé 60–75 %) et
    qu'il lui reste MOINS de tuiles que Débutant (Débutant redevient le plus
    faible) ;
  * Facile vs Intermédiaire est redescendu SOUS 80 %.

Pensé pour tenir dans un temps imparti serré : limite de temps FERME
(``--limite-temps``), **résultats partiels écrits en continu** dans
``--sortie`` (après CHAQUE donne), budget du solveur exact réglable
(``--budget-solveur``, défaut production 1,5 s). Réutilise ``comparer`` de
``scripts/comparer_niveaux_ia.py`` (match miroir reproductible de #213), comme
``scripts/echelle_niveaux.py``.

Usage (commande à relancer par Alain hors contrainte de temps) :

    python scripts/valider_bas_echelle.py --donnes 40 --seed 0 \
        --budget-solveur 1.5 --max-tours 300 --limite-temps 5400 \
        --sortie resultats_bas_echelle_217.txt
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
from comparer_niveaux_ia import (  # noqa: E402
    comparer, intervalle_confiance_95, moyenne,
)

logger = logging.getLogger("valider_bas_echelle")

PAIRES = [("Débutant", "Facile"), ("Facile", "Intermédiaire")]
NIVEAUX_PROFIL = ["Débutant", "Facile", "Intermédiaire"]


def _ecrire(sortie, lignes: list[str]) -> None:
    """Réécrit INTÉGRALEMENT le fichier de sortie (résultats partiels) et vide
    le tampon, pour qu'Alain puisse suivre l'avancement en continu."""
    if sortie is None:
        return
    Path(sortie).write_text("\n".join(lignes) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Tournoi de validation ciblé du bas de l'échelle "
                    "(Débutant/Facile/Intermédiaire, issue #217).")
    parser.add_argument("--donnes", type=int, default=40)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-tours", type=int, default=300)
    parser.add_argument("--donnes-profil", type=int, default=20,
                        help="Donnes par niveau pour les tuiles restantes en "
                             "défaite (miroir ; 0 pour ne pas mesurer).")
    parser.add_argument("--budget-solveur", type=float, default=None,
                        help="Budget du solveur exact par tour (défaut "
                             "production = 1.5 s). À signaler si réduit.")
    parser.add_argument("--limite-temps", type=float, default=None,
                        help="Limite de temps FERME (s) pour tout le tournoi.")
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
    args = parser.parse_args(argv[1:])

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
        if args.budget_solveur <= 0:
            parser.error("--budget-solveur doit être > 0")
        _ia.BUDGET_TEMPS_EXPERT = args.budget_solveur

    debut = time.monotonic()
    deadline = (debut + args.limite_temps) if args.limite_temps else None

    lignes: list[str] = []
    budget_txt = (f"{args.budget_solveur:.2f} s/tour"
                  if args.budget_solveur is not None else "production (1.50 s)")
    lignes.append("=" * 72)
    lignes.append("VALIDATION DU BAS DE L'ÉCHELLE (issue #217)")
    _bf = _niveaux.BRIDAGES["Facile"]
    _pf = "∞" if _bf.perturbation_max is None else str(_bf.perturbation_max)
    lignes.append(f"donnes={args.donnes} seed={args.seed} "
                  f"max_tours={args.max_tours} budget_solveur={budget_txt}")
    lignes.append(f"Réglage Facile testé : perturbation={_pf} "
                  f"oubli={_bf.taux_oubli:.2f}")
    lignes.append("Critère force : tuiles restantes en défaite (plus bas = "
                  "plus fort).")
    lignes.append("=" * 72)
    _ecrire(args.sortie, lignes)

    # (0) Profil tuiles restantes par niveau (fait en premier pour figurer au
    # rapport même si le tournoi est écourté).
    lignes.append("")
    lignes.append("TUILES RESTANTES EN DÉFAITE PAR NIVEAU (miroir) :")
    _ecrire(args.sortie, lignes)
    if args.donnes_profil > 0:
        for niveau in NIVEAUX_PROFIL:
            tuiles: list[int] = []
            gf = 0
            lignes.append(f"    {niveau:<14s} (en cours...)")
            idx_ligne = len(lignes) - 1
            for i in range(args.donnes_profil):
                if deadline is not None and time.monotonic() >= deadline:
                    break
                r = comparer(niveau, niveau, 1, args.seed + i, args.max_tours,
                             nb_manches=1, preferer_simple=True)
                tuiles.extend(r["tuiles_perdant"])
                gf += r["fins"]["garde_fou"]
                moy = moyenne(tuiles) if tuiles else float("nan")
                lignes[idx_ligne] = (
                    f"    {niveau:<14s} ~{moy:.2f} tuile(s) "
                    f"[{len(tuiles)} manche(s), {i + 1} donne(s)"
                    f"{f', garde-fou×{gf}' if gf else ''}]")
                _ecrire(args.sortie, lignes)

    # (1) Les deux paires du bas.
    lignes.append("PAIRES DU BAS (taux de victoire du niveau le PLUS FORT) :")
    _ecrire(args.sortie, lignes)
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
            if decides:
                taux, marge = intervalle_confiance_95(victoires, decides)
                lignes[idx_ligne] = (
                    f"    {faible} vs {fort}: {fort} "
                    f"{victoires}/{decides} = {taux * 100:.1f} % "
                    f"± {marge * 100:.1f} pt "
                    f"[{donnes_jouees}/{args.donnes} donnes]")
            else:
                lignes[idx_ligne] = (
                    f"    {faible} vs {fort}: aucun match décidé "
                    f"[{donnes_jouees}/{args.donnes} donnes]")
            _ecrire(args.sortie, lignes)
        lignes.append("")
        _ecrire(args.sortie, lignes)

    lignes.append(f"Temps total : {time.monotonic() - debut:.1f} s.")
    lignes.append("=" * 72)
    _ecrire(args.sortie, lignes)
    print("\n".join(lignes))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
