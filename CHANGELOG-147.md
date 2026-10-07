# Issue #147 — Suite #144 : reformuler et habiller la modale de confirmation du rejeu du dernier coup IA

## Contexte
La confirmation avant rejeu du dernier coup IA (#144) utilisait le mot « annulé », qui pouvait
faire craindre à Alain de perdre un tour de jeu complet, alors qu'il s'agit seulement de remettre
en main les tuiles pas encore validées du tour en cours. C'était par ailleurs une `confirm()`
JavaScript native, sans style ni titre spécifique.

## Modification
- `jeu.html` : nouvel overlay `#overlay-confirm-rejeu` (`.carte.carte-confirm`), avec titre
  `#titre-confirm-rejeu` rempli dynamiquement et deux boutons (`btn-confirm-rejeu-non` /
  `btn-confirm-rejeu-oui`).
- `jeu.css` : styles `.carte-confirm` (carte compacte, titre coloré comme les fiches IA via
  `--couleur-ordinateur`) et `.btn-secondaire` (nouveau bouton générique pour les annulations).
- `jeu.js` :
  - Nouvelle fonction `confirmerRejeuIA(nomIA)`, qui affiche l'overlay stylé avec pour titre
    « Dernier coup de `<nomIA>` » et résout une Promise `true`/`false` selon le bouton cliqué.
  - `rejouerDernierCoupIA()` utilise désormais cette modale (au lieu de `confirm()` natif), avec
    pour titre le prénom de l'IA dont on rejoue le coup (`coup.nom`, déjà présent dans
    `dernier_coup_ia`).
  - Texte reformulé : « Vos tuiles pas encore validées pour ce tour seront remises en main pour
    laisser la place au rejeu — continuer ? » (plus de mention d'annulation de tour).

## Tests
- `python3 -m pytest` : 25 passed (aucune régression, modification purement front-end).
- `node --check jeu.js` : syntaxe JS valide.
