# Issue #205 — Nombre de manches : déplacé sur l'écran d'accueil, près de « Lancer la partie » (suite de #203)

#203 avait réactivé le choix du nombre de manches, mais le champ se trouvait
dans les Réglages (onglet « Règles du jeu »). Le nombre de manches étant un
choix propre à chaque match (comme la liste des adversaires) et non un réglage
permanent, il est désormais sur la **carte principale de l'écran d'accueil**,
juste au-dessus du bouton « Lancer la partie ». **Aucun changement du moteur,
des IA ni des écrans de jeu.**

## Changements

- **Contrôle compact sur l'accueil** (`accueil.html`) : libellé « Nombre de
  manches : » + liste déroulante de 1 à 9 (défaut 1), dans le même style que
  « Ajouter un adversaire : », placé juste avant « Lancer la partie »
  (`#choix-manches` / `#acc-manches`).
- **Retrait de l'onglet « Règles du jeu »** : plus aucun champ « Nombre de
  manches » dans les Réglages — un seul endroit pour ce choix.
- **Mémorisation** (`accueil.js`) : le choix est persisté dès qu'il change,
  sous la **même clé `nb_manches`** et via la même API que les autres réglages
  (`sauvegarder_reglages`, sans toast), puis présélectionné à l'ouverture
  suivante (`remplirChampManches`). Une valeur absente ou hors de [1, 9]
  retombe sur 1, sans erreur JavaScript même si un ancien `config.json` porte
  encore la clé.
- **Lancement inchangé** : la valeur (bornée 1 à 9) est transmise à
  `lancer_nouvelle_partie` dans `regles.nb_manches`, exactement comme avant.
  Avec 1 manche, rien d'autre ne change (pas d'indicateur « Manche N / M »,
  écran de fin habituel).
- **Mise en page** (`accueil.css`) : contrôle sur une seule ligne, compact,
  lisible à la taille minimale de la fenêtre, avec ou sans parties
  sauvegardées, sans débordement.

## Tests

- `tests/test_playwright_accueil_reglages.py` mis à jour (Playwright sur
  `accueil.html` chargé en direct, jamais la vraie app pywebview, voir
  CONTEXTE.md §7) : choix présent sur l'accueil juste avant « Lancer » et
  **absent des Réglages**, valeur rechargée depuis `nb_manches`, enregistrée au
  changement, transmise au lancement, et valeur invalide/absente ramenée à 1.
- `CONTEXTE.md` §3bis mis à jour.
