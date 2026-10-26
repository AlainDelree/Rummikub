#!/usr/bin/env python3
"""Vérification croisée du solveur de réarrangement global (issue #193,
suite de #188, point 5) contre une recherche exhaustive indépendante.

Génère ``--nb`` petites positions aléatoires (graine ``--seed`` fixe, donc
reproductible à l'identique), suffisamment petites pour qu'une recherche
exhaustive simple (volontairement lente, ``moteur/verif_solveur.py``) donne
le maximum RÉEL de tuiles du chevalet posables en conservant le plateau.
Compare ce maximum à celui du solveur de production
(``moteur/solveur.py::resoudre_coup``) avec un budget généreux. Si le
solveur trouve moins, la position est signalée comme un écart — jamais
corrigée automatiquement (voir l'avertissement de ``verif_solveur.py``).

Ne modifie jamais le solveur ni l'IA : lecture pure + comparaison.

Usage :

    python scripts/verifier_solveur_exhaustif.py
    python scripts/verifier_solveur_exhaustif.py --nb 500 --seed 7
    python scripts/verifier_solveur_exhaustif.py --budget-solveur 5 > rapport.txt
"""

import argparse
import random
import sys
import time
from pathlib import Path

_RACINE = Path(__file__).resolve().parent.parent
_SRC = _RACINE / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from rummikub.moteur.partie import _plateau_vers_dict  # noqa: E402
from rummikub.moteur.solveur import resoudre_coup, BudgetDepasse  # noqa: E402
from rummikub.moteur.verif_solveur import (  # noqa: E402
    generer_position_aleatoire, max_tuiles_posables_exhaustif,
)


def _decrire_position(pos: dict) -> str:
    def _tuile(t):
        return "joker" if t.est_joker else f"{t.couleur} {t.valeur}"
    plateau = " / ".join(", ".join(_tuile(t) for t in combo) for combo in pos["plateau"]) or "(vide)"
    main = ", ".join(_tuile(t) for t in pos["chevalet"])
    return f"plateau=[{plateau}] main=[{main}]"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nb", type=int, default=300,
                        help="Nombre de positions aléatoires à tester (défaut 300).")
    parser.add_argument("--seed", type=int, default=193,
                        help="Graine du générateur aléatoire (défaut 193, reproductible).")
    parser.add_argument("--budget-solveur", type=float, default=5.0,
                        help="Budget de temps du solveur par position, en secondes "
                             "(défaut 5 — les positions sont volontairement petites).")
    parser.add_argument("--max-tuiles-main", type=int, default=6,
                        help="Taille maximale de la main générée (défaut 6 — garde la "
                             "recherche exhaustive praticable).")
    args = parser.parse_args(argv)

    rng = random.Random(args.seed)
    ecarts, inconclusifs = [], 0
    t0 = time.monotonic()

    for i in range(args.nb):
        pos = generer_position_aleatoire(rng, max_tuiles_main=args.max_tuiles_main)
        exhaustif = max_tuiles_posables_exhaustif(pos["plateau"], pos["chevalet"])

        etat = {
            "joueurs": [{"chevalet": [t.as_dict() for t in pos["chevalet"]],
                         "mise_initiale_faite": True}],
            "plateau": _plateau_vers_dict(pos["plateau"]),
            "config": {"mise_initiale_min": 30},
        }
        try:
            coup = resoudre_coup(etat, 0, budget_temps=args.budget_solveur)
            nb_solveur = len(coup["ids_tuiles"]) if coup else 0
        except BudgetDepasse:
            inconclusifs += 1
            continue

        if nb_solveur < exhaustif:
            ecarts.append((i, pos, exhaustif, nb_solveur))

    duree = time.monotonic() - t0
    print(f"Positions testées     : {args.nb} (graine {args.seed}, {duree:.1f} s)")
    print(f"Inconclusives (budget) : {inconclusifs}")
    print(f"Écarts détectés        : {len(ecarts)}")
    if ecarts:
        print("\nATTENTION — le solveur trouve moins que le maximum réel sur "
              f"{len(ecarts)} position(s) (voir moteur/solveur.py) :")
        for i, pos, exhaustif, nb_solveur in ecarts[:10]:
            print(f"  - position #{i} : exhaustif={exhaustif}, solveur={nb_solveur} "
                  f"— {_decrire_position(pos)}")
        if len(ecarts) > 10:
            print(f"  ... et {len(ecarts) - 10} de plus.")
    else:
        print("\nAucun écart : le solveur retrouve le maximum réel sur toutes les "
              "positions testées.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
