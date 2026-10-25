# Issue #179 — Build Windows Rummikub v14

- Build de publication Rummikub effectué via `build\rebuild_rummikub.bat
  --publier --build 14` (commit construit : `b4dc23a`) : `version.json` mis
  à jour (build 14, SHA-256 recalculé et vérifié identique à l'archive
  produite : `526084f1735e93ac1d9684ee3f2c22e295e09b6208077b1eeed66779ae04aec5`).
- Vérifications effectuées : `manifest.json` sans BOM (premiers octets
  `7B 22 62`), tailles conformes aux garde-fous (dossier non compressé
  ~25,0 Mo / 26 251 767 octets, installeur compressé ~12,8 Mo /
  12 801 538 octets, archive ~12,9 Mo / 12 895 604 octets), structure de
  l'archive (racine : `Rummikub.exe` + `manifest.json` ; `_internal\` :
  73 fichiers). Seuls avertissements PyInstaller : hidden imports
  `pycparser.lextab`/`pycparser.yacctab` (connus, sans impact) ; aucun
  avertissement Inno Setup.
- Copie hors worktree (issue #178) confirmée vers
  `C:\CCW_Share\_derniers_builds\rummikub\` : `Rummikub-Setup-v14.exe`
  (12 801 538 octets) et `rummikub-v14.zip` (12 895 604 octets).
- Fichiers produits dans `installeur\output\` : `Rummikub-Setup-v14.exe`
  et `rummikub-v14.zip` (non poussés, non publiés — à récupérer avant
  suppression du worktree, même si la copie externe de #178 réduit
  désormais ce risque).
