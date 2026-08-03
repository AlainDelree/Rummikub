# Issue #75 — Mode `--publier` dans `rebuild_rummikub.bat` (SHA-256 + version.json automatiques)

## Contexte
Automatiser la publication d'une nouvelle version pour éviter les erreurs
manuelles (numéro de build, calcul du SHA-256, rédaction de `version.json`).
La référence mentionnée (`build/rebuild_actualise.bat` du dépôt
`AlainDelree/Bridge_Agent`, issue #365) n'était pas accessible au moment du
traitement (HTTP 404 : chemin absent de l'arbre `master`) ; l'implémentation
s'appuie donc sur la spécification détaillée de l'issue.

## Modifications
- `build/rebuild_rummikub.bat` :
  - **Analyse d'arguments** (nouveau bloc après `setlocal`) : `--publier`
    (active la publication) et `--build N` (force le numéro de build). Sans
    argument, le comportement historique est strictement inchangé.
  - **Étape 8bis (`--publier` uniquement)**, insérée après l'étape 8 (une fois
    `rummikub.zip` généré) :
    - lecture du build courant depuis `%ORIGDIR%\version.json` via PowerShell
      (`ConvertFrom-Json`), puis `build + 1` ; surchargé par `--build N` ;
    - réécriture de `manifest.json` avec le nouveau numéro et régénération de
      `rummikub.zip` (`Compress-Archive` de `dist\Rummikub\*` + `manifest.json`),
      recopié vers le partage ;
    - calcul du **SHA-256** du zip via `Get-FileHash` (PowerShell), en
      minuscules ;
    - écriture de `version.json` à la racine du clone partagé (`%ORIGDIR%`,
      soit `Z:\CCW\rummikub`) au format `{"build": N, "sha256": "..."}` ;
    - **commit local** de `version.json` (`git -C "%ORIGDIR%" commit -- version.json`).
  - **Étape 9** : en mode `--publier`, le `git reset --hard origin/master` du
    clone partagé est **désactivé** afin de préserver le commit `version.json`
    fraîchement créé (il serait sinon effacé). Comportement normal inchangé
    hors `--publier`.
  - **Fin de script** : en mode `--publier`, rappel explicite des étapes
    restées **manuelles** — `git push` puis création de la Release GitHub (tag
    `vN`) avec `Rummikub-Setup.exe` et `rummikub.zip` en pièces jointes.

## Points d'attention
- **Jamais de `git push` ni de `gh release create`** dans le script,
  conformément à l'issue et aux consignes du bridge : seul un commit local est
  réalisé.
- Le `reset --hard` de l'étape 9 aurait supprimé le commit `version.json` en
  mode publication : il est donc explicitement contourné dans ce mode. En mode
  normal (sans `--publier`), aucun commit n'est fait et le reset garde son
  rôle de nettoyage habituel.
- `--build N` fixe le build à **N** exactement (pas `N+1`) ; sans lui, le build
  vaut `version.json.build + 1`.
- Script Windows (`.bat`) : non exécutable/validable sous Linux ; revue
  statique de la syntaxe batch effectuée (labels, blocs `if`/parenthèses,
  échappements `^( ^)`, expansion différée `!VAR!`).
