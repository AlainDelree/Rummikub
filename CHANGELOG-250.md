## Issue #250 — Build Windows d'essai (n°99, non publié) avec les dépendances épinglées

Build d'essai local (`build\rebuild_rummikub.bat --build 99`, sans `--publier`) sur une
machine sans le runtime Visual C++ installé dans `System32` (`vcruntime140.dll`,
`vcruntime140_1.dll`, `msvcp140.dll` absentes), pour vérifier les six dépendances
épinglées depuis l'issue #241 et confirmer que le jeu embarque lui-même son runtime C.

- Les six versions installées (`versions_build.txt`) correspondent exactement à
  `requirements.txt` : pywebview 6.2.1, pyinstaller 6.22.3, pytest 9.2.0,
  highspy 1.15.1, numpy 2.5.4, pythonnet 3.2.1.
- L'archive `rummikub-v99.zip` embarque son propre runtime C (`_internal\VCRUNTIME140.dll`,
  `_internal\VCRUNTIME140_1.dll`, et deux `msvcp140-*.dll` vendues par highspy/numpy) :
  pas de dépendance sur le runtime VC++ système.
- Autotest de l'exécutable gelé (exécuté par le script de build, étape 5bis) :
  code de sortie 0, solveur exact backend HiGHS, optimum prouvé.
- Build 99 jamais publié, laissé dans `C:\CCW_Share\_derniers_builds\rummikub\`
  pour qu'Alain installe/lance/teste à la main, puis à supprimer après usage.
