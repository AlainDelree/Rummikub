# Issue #177 — Build Windows Rummikub v13

- Build de publication Rummikub effectué via `build\rebuild_rummikub.bat
  --publier --build 13` : `version.json` mis à jour (build 13, SHA-256
  recalculé et vérifié identique à l'archive produite).
- Vérifications effectuées : `manifest.json` sans BOM (premiers octets
  `7B 22 62`), tailles conformes aux garde-fous (dossier non compressé
  ~25 Mo, installeur compressé ~12,8 Mo), structure de l'archive (racine :
  `Rummikub.exe` + `manifest.json` ; `_internal\` : ~87 entrées).
- Fichiers produits dans `installeur\output\` : `Rummikub-Setup-v13.exe`
  et `rummikub-v13.zip` (non poussés, non publiés — à récupérer avant
  suppression du worktree).
