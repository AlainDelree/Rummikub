#!/usr/bin/env python3
"""Lance la campagne de comparaison Expert vs Avancé pour le rapport de
clôture #186, avec un budget de temps réduit pour le solveur d'Expert
(justifié dans le rapport : budget de production 1.5s, réduit ici pour que
la campagne tienne dans le temps de calcul disponible pour cette tâche)."""
import argparse
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
sys.path.insert(0, str(RACINE / "scripts"))

from rummikub.moteur import ia as ia_mod  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--donnes", type=int, default=60)
parser.add_argument("--seed", type=int, default=0)
parser.add_argument("--budget-expert", type=float, default=0.15)
parser.add_argument("--max-tours", type=int, default=300)
args = parser.parse_args()

ia_mod.BUDGET_TEMPS_EXPERT = args.budget_expert

import comparer_niveaux_ia as cmp  # noqa: E402

print(f"Budget de temps Expert pour cette campagne : {args.budget_expert}s "
      f"(défaut production : 1.5s)")
debut = time.monotonic()
resume = cmp.comparer("Avancé", "Expert", args.donnes, args.seed, args.max_tours)
duree = time.monotonic() - debut
cmp.afficher_rapport(resume)
print(f"Temps total de la campagne : {duree:.1f}s.")
