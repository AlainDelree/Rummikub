# Issue #238 — Build Windows : écrire la liste exacte des versions installées avant la suppression de l'environnement de build

## Contexte
`build\rebuild_rummikub.bat` installe les dépendances dans un `.venv_build`
local (`C:\Temp\RummikubBuild`), puis supprime entièrement ce dossier en fin
de build (étape 9) : après un build, aucune version réellement installée
n'est plus consultable. L'audit de Diagnostique_Programme (règle EXP-001)
demande pourtant d'épingler `requirements.txt` avec `==`, à partir des
versions réellement résolues par pip — pas des bornes `>=`/`<` actuelles.

## Modifications
- **`build\rebuild_rummikub.bat`** : nouvelle étape **2bis**, exécutée juste
  après l'installation des dépendances (y compris `pyinstaller`, étape 2) et
  avant la suppression de `%BUILDDIR%` (étape 9). Elle écrit
  `versions_build.txt` (ASCII pur) avec une en-tête (date, numéro de build,
  commit construit via `git rev-parse HEAD`, version de Python et de `pip`
  de l'environnement de build) suivie de la sortie complète de
  `pip list --format=freeze`. Le fichier est copié dans `build\` du worktree
  (non versionné, comme les autres sorties de build) puis, à l'étape 8, dans
  `C:\CCW_Share\_derniers_builds\rummikub\`, à côté de l'installeur et de
  l'archive, dans tous les modes (`--publier` ou non). Le script affiche en
  fin de build l'emplacement des deux copies et les versions des six
  dépendances directes de `requirements.txt` (`highspy`, `numpy`,
  `pywebview`, `pyinstaller`, `pytest`, `pythonnet`).
- Aucune autre étape du script n'est modifiée.

## Vérification (build d'essai non publié, build 99)
`build\rebuild_rummikub.bat --build 99` (sans `--publier`), commit construit
`9d85c0f` (descendant de `392469c`, ancêtre de `HEAD` au moment de la
rédaction de l'issue) :
- Code de sortie 0 ; `version.json` inchangé.
- Autotest (`dist\Rummikub\Rummikub.exe --autotest <rapport>`) réussi :
  backend HIGHS, 6 tuiles posées en 0 ms (optimum prouvé).
- Tailles dans les fourchettes attendues (aucun `[ATTENTION]`) : dossier
  `dist\Rummikub` ≈ 62,6 Mo, installeur ≈ 21,1 Mo, archive ≈ 26,0 Mo.
- `versions_build.txt` écrit et identique dans `build\` (worktree) et dans
  `C:\CCW_Share\_derniers_builds\rummikub\`.
- Un bug de génération de `versions_build.txt` (guillemets imbriqués dans un
  `for /f` + backticks appelant `python.exe -c "..."`, provoquant
  `'...python.exe" -c "import' is not recognized...`, champ Python vide)
  a été détecté lors d'un premier build d'essai puis corrigé (suppression
  des guillemets superflus autour du chemin de l'exécutable, sans espace
  dans `%BUILDDIR%`) ; corrigé et revérifié par un second build d'essai
  complet, qui produit l'en-tête correctement remplie.
