# Issue #166 — Tri automatique : appliquer dès le début de partie et à la reprise

Le réglage « Tri automatique » (#126/#130) ne triait la main qu'au moment
d'une pioche. Si la case est cochée, la main est maintenant déjà triée :

- dès la toute première distribution de tuiles d'une nouvelle partie ;
- immédiatement après la reprise d'une partie sauvegardée.

`naviguer_vers_jeu` et `reprendre_jeu` (`application.py`) chargent tous deux
`jeu.html`, qui exécute `init()` à son ouverture : c'est ce point de passage
commun qui restaure déjà l'état de la case `tri_auto` depuis `etat.config`.
Il suffit d'y trier `chevaletLocal` (même ordre que le bouton « Trier » et
l'insertion à la pioche) quand le réglage est actif, avant le premier rendu —
sans toucher au comportement existant à la pioche.
