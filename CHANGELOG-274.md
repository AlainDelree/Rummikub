# Issue #274 — Documenter la vérification de l'échelle des niveaux après #272 et #273

## Contexte

Après #272 (contrôles du moteur sur l'origine des tuiles d'ouverture) et
#273 (plus aucune modification de la table pendant le tour d'ouverture,
pour l'IA comme pour le moteur), #273 avait laissé une note : l'échelle
calibrée de #267 devait être revérifiée, à faire par Alain sur le PC fixe.
Alain a rejoué les quatre duels de l'échelle (commit `1136c8c` de master,
`scripts/calibrer_echelle.py`, graine 31, budget solveur 1,5 s — budget de
jeu réel, contre 4,0 s en calibration d'origine —, règle de fin de manche
réelle #255, cible 60-70 %, miroir). Issue purement documentaire : aucun
code, aucun réglage touché.

Résultats : Expert contre Avancé 63,5 % ± 6,7 (identique, au match près, à
la mesure d'avant #273) ; Avancé contre Intermédiaire 61,0 % ± 9,6 ;
Intermédiaire contre Facile 63,0 % ± 9,5 (65,0 % avant #273) ; Facile
contre Débutant 68,0 % ± 9,1 (67,0 % avant #273). Les quatre duels restent
dans la cible : l'échelle est validée, aucun réglage ne change.

## 1. `docs/contexte/niveaux_ia_calibrage.md`, section « Échelle calibrée »

- Ajouté le sous-paragraphe « Vérification après #272 et #273 » : les
  quatre duels avec leurs chiffres complets (taux de victoire, IC 95 %,
  Elo, durée moyenne des manches, répartition des fins de manche, temps
  par tour moyen/maximum par niveau), la comparaison avec la mesure
  d'avant #273 quand elle existait, et la conclusion que l'échelle reste
  validée sans aucun changement de réglage. Conditions de mesure précisées
  (commit `1136c8c`, budget solveur 1,5 s, graine 31).
- Consigné les deux points de vigilance sur les temps par tour maximaux,
  sans cause affirmée : (a) les maximums relevés ici (Intermédiaire 116 s
  et 96 s, Avancé 19 s) dépassent très largement le budget de 1,5 s du
  solveur, cas rares, moyennes sous la seconde, étude séparée prévue ;
  (b) rappel de l'ancienne mesure d'avant #267 à ~1 h pour un seul tour
  d'Intermédiaire, probablement une mise en veille du PC, non reproduit
  depuis.
- Mis à jour la note laissée par #273 (« l'échelle de #267 doit être
  revérifiée ») pour indiquer que la vérification a été faite par #274,
  avec renvoi vers le nouveau sous-paragraphe.

Aucun autre fichier modifié (ni `niveaux.py`, ni code, ni `CONTEXTE.md`,
ni tests, ni anciens CHANGELOG).
