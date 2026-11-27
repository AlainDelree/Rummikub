# Issue #278 — Documentation du premier tournoi à quatre IA (#276) et des conclusions de l'étude des tours longs (#277)

## Contexte

Le tournoi à quatre IA lancé avec `scripts/tournoi_niveaux.py` (#276) et
l'étude des temps de tour anormalement longs (#277) avaient produit des
résultats chiffrés qui restaient à consigner dans les fichiers de
contexte. Cette issue est purement documentaire : aucun code, aucun
réglage de `niveaux.py`, aucun test ne change.

## 1. `docs/contexte/niveaux_ia_calibrage.md`

Dans la section « Échelle calibrée » :

- Remplacement des deux points de vigilance (laissés sans cause par #274)
  par un paragraphe « Tours longs (#277) » : chaîne d'échéances neuves par
  appel au solveur dans `jouer_niveau_bride` (propre à l'anti-don de
  joker, donc à Intermédiaire/Avancé/Expert), explication du cas mesuré
  (4 appels, 3,92 s), caractère non reproductible des durées extrêmes
  (probablement un ralentissement machine, non prouvé pour les campagnes
  du PC fixe), absence de tout tour long dans le tournoi du 27/11/2026, et
  renvoi vers la correction prévue (échéance commune par tour, issue
  séparée à venir).
- Ajout d'un sous-paragraphe « Tournoi à quatre IA (#276, 27/11/2026) » :
  conditions complètes de la campagne, tableau des résultats par niveau
  (victoires, IC 95 % de Wilson, place moyenne, score moyen), matrice
  « qui bat qui », victoires par siège, fins de manche, temps par tour, et
  la conclusion (ordre net Expert > Avancé > Intermédiaire > Facile,
  tournoi complémentaire sans cible ni modification de réglage).

## 2. `docs/contexte/scripts_simulation.md`

Dans la section 10 (`tournoi_niveaux.py`) : ajout de la commande Windows
réellement utilisée pour cette campagne (interpréteur du dossier de
calibration, 100 donnes, graine 31, budget du solveur 1,5 s, 2 processus),
de la commande `--statut` pour relire le rapport en cours de route, de la
durée observée (1 649 s, environ 27 minutes, bien moins que l'estimation
initiale) et d'un renvoi vers le sous-paragraphe correspondant de
`niveaux_ia_calibrage.md`.

## Vérification

Travail purement documentaire : relecture des deux fichiers modifiés et
comparaison ligne à ligne des chiffres recopiés avec ceux fournis par
l'issue #278 (victoires, IC Wilson, places, scores, matrice, sièges,
temps par tour, durée de campagne). Aucun fichier Python modifié, aucune
suite de tests relancée.
