## Issue #134 — Mesure de la fréquence réelle de `_coup_scission` via le script de simulation

Suite à l'investigation en lecture seule de l'issue #133 (qui n'avait pas pu exécuter
`python3` sous le système de permissions en mode lecture), relance en écriture : un
script d'observation externe temporaire (non committé) a monkey-patché en mémoire
`rummikub.moteur.ia._coup_scission` pour compter ses déclenchements, sans modifier
`ia.py`, puis a exécuté 500 parties via `scripts/simulation_ia.simuler` (1 manche
chacune) :

- 150 parties « 4× Avancé » : 626 déclenchements, 98,0 % des parties avec ≥ 1
  déclenchement, moyenne 4,17/partie.
- 150 parties « 4× Expert » : 664 déclenchements, 97,3 % des parties, moyenne
  4,43/partie.
- 100 parties « 2× Avancé + 2× Expert » : 445 déclenchements, 98,0 % des parties,
  moyenne 4,45/partie.
- 60 parties multi-niveaux (Débutant/Facile/Intermédiaire/Avancé) : 58
  déclenchements, 63,3 % des parties, moyenne 0,97/partie (un seul joueur sur 4
  invoque le mécanisme).
- 40 parties multi-niveaux (Débutant/Facile/Intermédiaire/Expert) : 42
  déclenchements, 62,5 % des parties, moyenne 1,05/partie.

**Total global : 1835 déclenchements sur 500 parties, 90,8 % des parties avec au
moins un déclenchement, moyenne 3,67/partie.** Aucune anomalie détectée dans les 500
parties. Conclusion : `_coup_scission` n'est pas un cas théorique rarement atteint —
dès qu'un niveau Avancé ou Expert est présent, il se déclenche en pratique dans la
quasi-totalité des parties, plusieurs fois par partie en moyenne.

Aucune modification de `ia.py` ni d'aucun fichier du moteur. Le script d'observation
temporaire n'a pas été committé (conformément à la consigne de l'issue).
