# Issue #218 — Harmonisation de `rebuild_rummikub.bat` (zéro initial, rappel de fin, arrêt de processus)

Revue de `build\rebuild_rummikub.bat` par rapport au guide `BUILD_WINDOWS_CCW.md`
et aux scripts de Scrabble/Actualise. Trois écarts corrigés, sans toucher au
reste du script.

## 1. Contrôle du numéro de build — zéro initial

Le contrôle acceptait un numéro comme `014`, qui aurait ensuite été écrit tel
quel dans `version.json` et aurait rendu ce JSON invalide. Le motif
`findstr /r "^[0-9][0-9]*$"` est remplacé par `^[1-9][0-9]*$` (comme Scrabble) :
exige désormais un entier strictement positif, sans zéro initial. Le reste de
la garde (strictement supérieur au build de `version.json`, refus de `--build`
sans valeur, refus des arguments inconnus) ne change pas.

## 2. Rappel de fin de script

Le rappel affiché à la fin avec `--publier` indiquait « git push depuis le
worktree, puis Release », à l'inverse de l'ordre du guide. Remplacé (en ASCII
pur, avec échappement des parenthèses dans le bloc `if`) par l'ordre attendu :
1) fusionner la branche du worktree dans master (relecture_web, entrée
rummikub_ccw), SANS pousser ; 2) créer la Release v<N> (numéro de build réel)
avec les deux fichiers attachés (installeur + archive) ; 3) pousser master.

## 3. Étape 3 : arrêt de processus → détection sans fermeture

`taskkill /im Rummikub.exe /f` arrêtait de force toute instance de
`Rummikub.exe` de la machine, y compris une partie en cours, alors que le
build se fait entièrement dans `%BUILDDIR%` (copie locale) qui ne verrouille
aucun fichier réellement lu ou écrit par une instance en cours (l'exécutable
installé tourne depuis un tout autre emplacement). **Cette étape n'avait donc
pas de raison d'être réelle.** Remplacée par une détection via
`tasklist /fi "imagename eq Rummikub.exe"` qui signale une éventuelle instance
en cours sans jamais la fermer et sans arrêter le build (sur le modèle
d'Actualise).

## Essais (commit construit : d7611d2, solveur exact depuis la v14)

- **Build complet `--build 99` (test, sans `--publier`)** : réussi, code de
  sortie 0, aucun avertissement de taille.
  - `dist\Rummikub` non compressé : 62 571 296 octets (fourchette attendue
    20–125 Mo, OK).
  - `Rummikub-Setup-v99.exe` (installeur compressé) : 21 077 072 octets
    (fourchette attendue 5–50 Mo, OK).
  - `rummikub-v99.zip` (archive) : 25 962 601 octets (même fourchette, OK).
  - Copie vers `C:\CCW_Share\_derniers_builds\rummikub\` : mêmes tailles pour
    les deux fichiers.
  - Détection d'instance (point 3) : « Aucune instance de Rummikub.exe en
    cours » — aucune fermeture tentée.
  - Solveur exact : `highspy` et `numpy` bien présents dans le commit construit
    (installés via `requirements.txt`, DLL `highspy`/`numpy.libs` embarquées
    par PyInstaller) ; autotest `--autotest` réussi : backend HIGHS, 6 tuiles
    posées en 0 ms (optimum prouvé). Aucun avertissement affiché par le script.
  - `version.json` inchangé (`--publier` non utilisé).
- **Trois refus attendus**, chacun code de sortie 1, rien écrit, `git diff --
  version.json` vide :
  - `--build 0` → refusé.
  - `--build 014` → refusé.
  - `--build 05` → refusé.
