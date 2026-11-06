# Issue #241 — Épinglage des dépendances directes de requirements.txt aux versions du build Windows (EXP-001)

## Contexte
L'audit de Diagnostique_Programme (règle EXP-001) relevait qu'aucune
dépendance de `requirements.txt` n'était épinglée avec `==` : `highspy` et
`numpy` n'avaient que des bornes, les autres aucune version. Pour un solveur
exact distribué, un build reproductible compte : sans épinglage, le script de
build installe la dernière version autorisée par les bornes, donc deux builds
à des dates différentes peuvent embarquer des versions différentes. Les
versions retenues sont celles réellement installées par le build Windows
d'essai de l'issue #238 (5 novembre 2026, numéro fictif 99, non publié,
Python 3.12.7).

## Modifications

- **`requirements.txt`** — les six dépendances directes sont épinglées à
  `==` aux versions du build Windows d'essai : `pywebview==6.2.1`,
  `pyinstaller==6.22.3`, `pytest==9.2.0`, `highspy==1.15.1`, `numpy==2.5.4`,
  `pythonnet==3.2.1` (marqueur `sys_platform == "win32"` conservé). Chaque
  ligne garde en commentaire l'ancienne contrainte et la source de la
  version. Les seize dépendances indirectes relevées par l'issue #238 sont
  listées en commentaire en fin de fichier, sous le titre « Versions
  indirectes observées au build du 5 novembre 2026 (information, non
  contraignant) » — non épinglées dans le fichier actif car plusieurs sont
  propres à Windows (`pythonnet`, `clr_loader`, `pefile`,
  `pywin32-ctypes`) et casseraient l'installation ailleurs.
- **`tests/test_requirements_epinglees.py`** (nouveau) — vérifie que chaque
  ligne de dépendance de `requirements.txt` (hors commentaires, lignes vides
  et options pip) contient `==` ; échoue en nommant la ou les dépendances non
  épinglées sinon.
