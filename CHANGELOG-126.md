# Issue #126 — Ergonomie : jeu automatique de l'IA, tri automatique au pioché, suppression d'un texte inutile

## Contexte
Trois petites améliorations d'ergonomie identifiées en jouant, indépendantes
les unes des autres.

## Ajouts / changements
- **Jeu automatique de l'IA** : nouveau réglage « Jouer automatiquement le
  tour de l'ordinateur » (onglet Général des réglages, clé `ia_auto` dans
  `config.json`). Quand il est actif, dès que c'est le tour d'une IA, son
  coup se déclenche seul après une latence d'environ 1 seconde (pour ne pas
  paraître brusque), sans qu'il faille cliquer sur le bouton « Jouer » de sa
  fiche. Ce bouton manuel reste affiché et fonctionnel (clic possible pendant
  la latence, ou si le réglage est désactivé).
- **Tri automatique à la pioche** : nouvelle case à cocher « Tri automatique »
  à côté du bouton « Trier » du chevalet. Quand elle est active, chaque tuile
  piochée est insérée directement à sa place triée (couleur puis valeur,
  jokers en fin) plutôt qu'ajoutée en fin de chevalet. Le bouton « Trier »
  existant est inchangé et reste utilisable indépendamment de la case.
- **Suppression du texte « Mes tuiles — cliquez, réarrangez »** affiché
  au-dessus du chevalet du joueur : n'apportait rien à l'utilisateur.

## Fichiers touchés
`src/rummikub/reglages.py`, `src/rummikub/ui/application.py`,
`src/rummikub/ui/web/{accueil.html,accueil.js,jeu.html,jeu.css,jeu.js}`.
