# CHANGELOG — Issue #113

## Correction rebuild_rummikub.bat : chemin Z:\CCW\rummikub à l'étape 8

- `build/rebuild_rummikub.bat` (étape 8, hors mode `--publier`) : la commande
  `git -C Z:\CCW\rummikub reset --hard origin/master` référençait le lecteur
  réseau `Z:` qui n'existe plus sur le PC fixe physique (échec silencieux).
  Remplacement du chemin par `C:\CCW_Share\CCW\rummikub` (même correctif que
  `rebuild_scrabble.bat`, issue #410).
- Correction également du commentaire stale ligne 349
  (`%ORIGDIR% = Z:\CCW\rummikub` → `%ORIGDIR% = C:\CCW_Share\CCW\rummikub`)
  afin qu'il ne subsiste plus aucune référence à `Z:\CCW` dans le fichier.
