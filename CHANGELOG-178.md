# Issue #178 — Durcir build\rebuild_rummikub.bat (copie hors worktree, garde-fou, nettoyage, rappels)

- `build\rebuild_rummikub.bat` copie désormais l'installeur et l'archive
  vers `C:\CCW_Share\_derniers_builds\rummikub\` dans TOUS les modes (même
  sans `--publier`), avec le numéro de build réel dans les deux noms de
  fichiers (`rummikub-vN.zip` remplace l'ancien nom fixe `rummikub.zip`
  des builds de test). Le script affiche lui-même, en fin d'exécution, les
  noms et tailles en octets des deux fichiers copiés ainsi que
  l'emplacement d'Inno Setup utilisé.
- Garde-fou du numéro de build : le build demandé (`--build N` ou build
  courant + 1 par défaut) est désormais lu et validé dès l'analyse des
  arguments (nouvelle étape `0bis`, avant toute copie robocopy), et non
  plus seulement vers l'ancienne étape 7. Refusé avant toute
  construction/écriture si non entier, non strictement supérieur au
  build courant de `version.json`, ou si `--build` est fourni sans valeur
  (ou suivi d'un autre argument). Tout argument inconnu est également
  refusé (liste des arguments acceptés affichée), au lieu d'être ignoré
  avec un simple avertissement.
- Nettoyage : suppression du `git -C C:\CCW_Share\CCW\rummikub reset
  --hard origin/master` de l'ancienne étape 8 (modèle de clone partagé
  obsolète) et des commentaires associés. Le script est maintenant décrit
  tel qu'il est réellement : il construit dans un dossier local
  (`C:\Temp\RummikubBuild`) et n'écrit que dans le worktree courant et
  dans le dossier fixe hors worktree ci-dessus.
- Rappel de fin de script (`--publier`) : confirmé qu'il mentionne bien
  les DEUX fichiers (installeur + archive) à attacher à la Release
  GitHub.
- Essais effectués (PowerShell, `call` + `%errorlevel%` pour la mesure
  fiable du code de sortie) : un essai complet sans `--publier` avec
  `--build 99` (numéro fictif, ~100 s, installeur ~12,8 Mo, archive
  ~12,9 Mo, copiés dans le worktree et dans le dossier fixe — à
  nettoyer à la main par Alain dans `C:\CCW_Share\_derniers_builds\rummikub\`)
  ; et les six refus attendus (numéro égal, numéro inférieur, numéro non
  numérique, `--build` sans valeur, `--publier --build` non supérieur,
  argument inconnu), tous avec code de sortie 1, message clair, et aucune
  écriture (`version.json` inchangé, aucun nouveau fichier dans
  `installeur\output` pour ces six cas).
- `version.json` n'a pas été modifié par cette issue (aucun essai n'a
  utilisé `--publier` avec un numéro réel).
