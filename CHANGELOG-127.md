# Issue #127 — Réorganisation des tuiles dans une zone de pose, comme sur le tapis

## Contexte
Le mécanisme d'insertion d'une tuile entre deux tuiles déjà placées existait
déjà dans le code des zones de pose (ajouté aux issues #27 et #31, zones
`.zone-ext-interne` + `insererTuileRangee`), au même titre que sur le tapis.
Mais `selectionnerTuile()` — appelée au clic sur une tuile du chevalet —
rafraîchissait le chevalet et le tapis, sans jamais rafraîchir la zone de
travail. Les zones d'insertion internes des rangées de pose (et les
gestionnaires de clic associés) restaient donc figés dans l'état « aucune
tuile sélectionnée », rendant l'insertion interne invisible et inopérante :
seul un clic sur le fond de la rangée (= ajout systématique en fin) restait
disponible.

## Correction
`src/rummikub/ui/web/jeu.js` — `selectionnerTuile()` appelle désormais aussi
`rafraichirZoneTravail()`, au même titre que `rafraichirChevalet()` et
`rafraichirPlateau()`. Les zones d'insertion (avant la première tuile, entre
deux tuiles, après la dernière) apparaissent donc correctement dès qu'une
tuile du chevalet est sélectionnée, avec le même comportement que sur le
tapis.

## Validation
- `node --check src/rummikub/ui/web/jeu.js` : OK.
- `python3 -m pytest` : 25 tests, tous au vert (aucune régression).
- Relecture manuelle du flux : sélection d'une tuile du chevalet → zones
  `.zone-ext-interne` recréées dans chaque rangée de travail non vide, avec
  les bons gestionnaires de clic (`insererTuileRangee` au lieu de l'ancien
  `reprendreTuileRangee` figé).
