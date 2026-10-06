# Issue #130 — Tri automatique : correction du dysfonctionnement et mémorisation du choix

## Contexte
La case « Tri automatique » (issue #126) était censée insérer chaque tuile
piochée directement à sa place triée dans le chevalet. En test réel, l'effet
ne se produisait pas correctement, et l'état de la case n'était jamais
persisté : il repartait toujours décoché à chaque relance.

## Diagnostic
`insererTrie()` (jeu.js) recherchait la position d'insertion par un simple
balayage linéaire supposant le chevalet **déjà trié**. Or un chevalet n'est
trié que si le joueur a cliqué sur « Trier » : la distribution initiale (et
toute réorg manuelle ultérieure) le laisse dans un ordre quelconque. Sur un
chevalet non trié, le balayage s'arrête dès le premier élément « plus grand »
rencontré en partant du début — une position qui n'a souvent aucun rapport
avec la vraie place triée globale (ex. un 13 rouge pioché atterrissait avant
une tuile bleue placée tôt dans la main, au lieu de rejoindre les autres
tuiles rouges). D'où l'impression que la case n'avait aucun effet.
Par ailleurs, la case n'était reliée à aucun réglage persisté : `reglages.py`
ne connaissait pas de clé `tri_auto`, et `jeu.js` ne faisait que maintenir
une variable JS locale (`triAutoActif`), réinitialisée à `false` à chaque
chargement de l'écran de jeu.

## Corrections
- **Tri** (`jeu.js`, `insererTrie()`) : au lieu d'une recherche de position
  par balayage linéaire, la fonction ajoute la tuile piochée au chevalet
  local puis retrie l'ensemble via `comparerTuiles` (même comparateur que le
  bouton « Trier »). Résultat garanti correct quel que soit l'ordre courant
  du chevalet.
- **Persistance** :
  - `reglages.py` : nouvelle clé `tri_auto` (défaut `False`) dans `DEFAUTS`.
  - `ui/application.py` : `naviguer_vers_jeu()` et `reprendre_jeu()`
    reportent désormais `cfg.get("tri_auto", False)` dans
    `etat_jeu["config"]["tri_auto"]`, selon le même schéma déjà utilisé pour
    `mode_reorg`/`ia_auto`.
  - `jeu.js` :
    - `init()` restaure `triAutoActif` et l'état de la case `#chk-tri-auto`
      depuis `etat.config.tri_auto` au chargement de l'écran de jeu.
    - le gestionnaire `change` de la case appelle désormais
      `window.pywebview.api.sauvegarder_reglages({ tri_auto: ... })` pour
      persister le choix immédiatement dans `config.json`.

## Fichiers touchés
`src/rummikub/reglages.py`, `src/rummikub/ui/application.py`,
`src/rummikub/ui/web/jeu.js`.

## Tests
- `python3 -m pytest` : 25 tests, tous au vert (aucune régression).
- `node --check src/rummikub/ui/web/jeu.js` : OK.
- Script Node ad hoc reproduisant un chevalet non trié + pioche d'un 13
  rouge : confirme que l'ancienne logique plaçait mal la tuile, et que la
  nouvelle la place correctement (regroupée avec les autres tuiles rouges).
