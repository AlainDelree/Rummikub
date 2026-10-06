# Issue #145 — Animation quand l'ordinateur pioche une tuile

## Contexte
Le joueur humain disposait déjà d'une animation à la pioche (`animerPiochee` dans jeu.js :
tuile montrée en grand au centre de l'écran, puis glissée/rétrécie vers le chevalet). Rien
d'équivalent n'existait côté IA : quand un joueur IA pioche, le tour se terminait directement
par un simple toast ("X pioche"), sans aucun geste visuel.

## Modification
- `commun.js` : nouvelle fonction `creerTuileDos()`, qui construit une tuile au même gabarit
  que `creerTuileJeu()` mais avec un disque central vide — aucune couleur ni valeur n'est donc
  révélée.
- `jeu.js` : nouvelle fonction `animerPiocheeIA(idxIA, apres)`, variante de `animerPiochee()`.
  La tuile dos visible part du centre de l'écran (comme pour l'humain) puis glisse vers la
  fiche du joueur IA concerné — position calculée dynamiquement via `getBoundingClientRect()`
  sur `.fiche-joueur` (nécessaire car la disposition des fiches varie selon le nombre de
  joueurs). Repli vers le haut de l'écran si la fiche n'est pas trouvée.
  Dans `jouerIA()`, la branche « aucune tuile ajoutée » distingue désormais pioche et passe :
  en cas de pioche, `animerPiocheeIA()` est jouée avant de rafraîchir l'affichage ; en cas de
  passe, le délai fixe de 800 ms est conservé inchangé.
- `jeu.css` : nouvelle règle `.vers-ia` (variables `--dx`/`--dy` posées en JS) qui réutilise la
  transition déjà définie sur `.tuile-piochee-grande`, en parallèle de `.vers-chevalet`
  (animation existante côté humain, inchangée).

## Test
`python -m pytest` : 25 passés (aucun fichier Python modifié, animation purement front-end).
