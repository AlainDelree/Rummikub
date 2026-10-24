# Issue #176 — build\rebuild_rummikub.bat : chercher Inno Setup dans C:\CCW\tools\InnoSetup6 avant .tools\InnoSetup6

- `build\rebuild_rummikub.bat` (étape 0) : recherche désormais `ISCC.exe`
  d'abord dans `C:\CCW\tools\InnoSetup6\ISCC.exe` (installé hors des dépôts,
  accessible depuis n'importe quel worktree CCW frais), puis seulement en
  repli dans l'ancien chemin `%ORIGDIR%\.tools\InnoSetup6\ISCC.exe` (utile
  pour un build lancé hors d'un worktree CCW, ex. en local par Alain).
- Si aucun des deux chemins n'existe, le script échoue toujours
  immédiatement et proprement, avec un message mentionnant les deux chemins
  recherchés.
