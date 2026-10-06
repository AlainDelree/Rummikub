# Issue #137 — Échanger une tuile de la main contre un joker équivalent du tapis

## Contexte
Un joker posé dans une combinaison du tapis représente une tuile précise (même valeur, et
même couleur dans le cas d'une suite). Quand le joueur a en main cette tuile exacte, il
pouvait déjà la sélectionner puis cliquer sur le joker pour l'échanger (`tenterRecupererJoker`,
issue #12) — mais le joker libéré était simplement désélectionné et renvoyé en zone de
travail, sans pouvoir être immédiatement replacé ailleurs d'un seul geste.

## Correctif (`jeu.js`)
- `tenterRecupererJoker` : le joker libéré par l'échange devient désormais la tuile
  sélectionnée (`tuileSelectionnee = dictJoker.id`) au lieu d'être désélectionné, et
  `majFantome()` remplace `detruireFantome()` pour qu'il suive le curseur — exactement le
  même traitement qu'une tuile fraîchement prise sur le tapis (`prendreTuileTapis`).
- Le joker libéré est ajouté à `tuilesOrigineTapis` (comme toute tuile provenant du tapis),
  afin que les mécanismes existants de replacement (`etendreTapis`, `insererTuileTapis`,
  `reprendreTuileRangee`, …) le traitent correctement.

## Résultat
Un joueur peut déposer une tuile de sa main sur un joker du tapis qu'elle remplace
exactement ; le joker libéré reste attaché au curseur, prêt à être reposé ailleurs dans le
même tour, sans étape intermédiaire.
