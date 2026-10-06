# Issue #141 — Fin de partie : message de fin de manche redondant supprimé + animation de victoire

## Contexte
À la fin d'une partie, deux fenêtres s'affichaient l'une après l'autre : l'overlay de fin de
manche (« Dernière manche — X remporte la manche », tableau manche/total) suivi immédiatement
de l'overlay de classement final (« X remporte la partie ! », tableau de classement). Les deux
montraient la même information quand la partie ne comptait qu'une seule manche.

## Correctif (`jeu.js`, `jeu.html`, `jeu.css`)
- `afficherFinDeManche()` (nouveau dispatcher) remplace les deux appels directs à
  `afficherFinManche()` : si `etat.terminee` (la manche qui se termine est la dernière de la
  partie), on affiche directement le classement final (`afficherClassementFinal()`) sans
  passer par l'overlay de fin de manche intermédiaire. Sinon, comportement inchangé.
- `afficherFinManche()` simplifiée : elle n'est plus jamais appelée avec `etat.terminee` vrai,
  donc la logique de titre/boutons conditionnelle à la fin de partie (bouton « Fin de partie »,
  titre « Dernière manche — ») a été retirée, ainsi que `onFinPartie()` et son écouteur,
  devenus inatteignables.
- Ajout d'une animation de feu d'artifice (CSS, particules générées par
  `lancerFeuArtifice()`) affichée derrière la carte du classement final lors de l'annonce du
  gagnant de la partie. Plusieurs bouquets de particules colorées jaillissent en cercle puis
  s'évanouissent (`@keyframes eclat-feu`), positions/couleurs/délais randomisés en JS, le
  mouvement restant purement CSS (`transform: rotate() translateX()`).

## Non régression
Le comportement pour une manche intermédiaire (partie à plusieurs manches) est inchangé :
l'overlay de fin de manche avec bouton « Manche suivante » / « Retour au menu » continue de
s'afficher normalement quand `etat.terminee` est faux.
