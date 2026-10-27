# Issue #195 — Documenter dans CONTEXTE.md les pistes d'amélioration de l'IA à tester (idées d'Alain)

Documentation uniquement, aucun changement de code. Ajout de la section
« 13. Pistes d'amélioration de l'IA à tester (issue #195) » à `CONTEXTE.md`,
en fin de fichier, pour ne pas perdre les idées formulées par Alain au fil
des parties de calibrage contre Expert :

1. Réserve d'un coup (garder un coup pour le tour suivant) — risque :
   l'adversaire peut occuper la place entre-temps ; test : nécessite une
   évaluation sur deux tours, l'analyse des coups ratés (§11) donnera de
   premières statistiques.
2. Éliminer en priorité les doublons de la main (exemple d'Alain : main
   1/2/2/3 rouges + 3 bleu/noir → jouer la suite plutôt que le groupe) ;
   hypothèse d'un critère de « main restante la plus facile à placer » à
   ajouter au départage actuel (points puis jokers, §8bis) ; test via
   `scripts/comparer_niveaux_ia.py` (§9).
3. Plus de temps de réflexion pour Expert, ou un niveau au-dessus (lien
   avec les mesures #187/#190).
4. Procédure commune d'évaluation d'une piste (comparaison en miroir,
   marge d'erreur, gain significatif + temps par tour raisonnable).
5. Rôle des points dans le départage — ne devraient primer que si la
   partie se termine bloquée, ou en cas de score cumulé sur plusieurs
   manches ; sinon laisser la place à la piste 2.
6. Constat (non corrigé ici) sur le réglage « Nombre de manches » : la
   règle `est_fin_partie` (`moteur/partie.py`) ne comptait pas de vraies
   manches ; décision d'Alain (#192, §3bis) de jouer en une seule manche ;
   le taux de parties bloquées en simulation (29 % au départ, 5-10 % avec
   le solveur d'Expert) est un signe de faiblesse de l'IA à suivre comme
   indicateur de qualité, pas un phénomène normal entre joueurs humains.

Chaque piste porte une case à cocher, pour que de futures issues puissent
la reprendre et la clore au fur et à mesure.

## Fichiers touchés

- `CONTEXTE.md` : + section 13 (texte seul, aucun code).
