# Issue #139 — Suite #136 : pourtour des tuiles déplacées depuis le tapis indiscernable

## Contexte
#136 avait introduit `.deplacee-tapis` (pourtour bleu `#3b82f6`) pour distinguer les tuiles déjà
sur le tapis mais déplacées ce tour-ci, des tuiles neuves de la main (`.ce-tour`, vert). En test
réel, ce bleu se fondait avec le contour pointillé bleu que `.tapis-manipulable` (jeu.css) applique
à toutes les tuiles manipulables du tapis une fois la mise initiale faite — la même collision
visuelle déjà corrigée pour le vert en #129.

## Correctif (`commun.css`, `jeu.css`)
- `.deplacee-tapis` passe du bleu `#3b82f6` à l'orange `#f59e0b` (border-color + box-shadow),
  désormais distinct à la fois du vert de `.ce-tour` et du bleu de `.tapis-manipulable`.
- Ajout de `.tuile-jeu.deplacee-tapis.tapis-manipulable` (et son `:hover`) sur le même modèle que
  `.tuile-jeu.ce-tour.tapis-manipulable` déjà présent : le contour pointillé de
  `.tapis-manipulable` reprend la couleur orange plutôt que de l'écraser.
- `.ce-tour` et `.deplacee-tapis` restent mutuellement exclusifs côté JS (`jeu.js`, `else if`),
  aucune règle de combinaison des deux classes n'était donc nécessaire.
