# Issue #208 — Préparer le build Windows avec le solveur exact : autotest `--autotest`, garde-fous de taille adaptés, exclusions inutiles (suite de #206)

#206 a fait entrer `highspy` (HiGHS, extension native) et `numpy` dans le
paquet livré (modèle exact d'Expert). Deux risques pour le prochain build
Windows, pas encore essayé : (1) si PyInstaller collecte mal ces paquets
natifs, Expert retombe **silencieusement** sur l'ancienne recherche
arborescente, sans que rien ne le signale ; (2) les garde-fous de taille du
script de build (dossier 20-45 Mo, installeur 5-25 Mo) refuseraient
probablement un paquet pourtant légitime devenu plus gros (~+55 Mo). #208
outille la détection et élargit les garde-fous, sans lancer aucun build
Windows.

## Changements

- **Option `--autotest` (nouveau module `src/rummikub/autotest.py`)** : vérifie,
  **sans ouvrir de fenêtre** et **sans importer `pywebview`/l'interface**, que
  le solveur exact fonctionne dans le binaire. Affiche en quelques lignes
  lisibles : version de Python, mode (sources / exécutable gelé), versions de
  `numpy` et `highspy`, présence des ressources web, puis **résout une petite
  position intégrée** (plateau vide + suite 5-6-7 + groupe de 10 → 6 tuiles
  attendues) avec `moteur/solveur_exact.py` et affiche le nombre de tuiles
  posées et la durée. **Code de sortie 0** si tout fonctionne, **1** sinon avec
  la cause. Fonctionne depuis les sources ET depuis l'exécutable gelé par
  PyInstaller. **Ne lit/écrit aucune donnée utilisateur** (ni SQLite ni
  `config.json`).
- **`main.py`** : détecte `--autotest` **avant** tout import de
  `rummikub.ui.application` (l'import de la fenêtre devient paresseux) → aucune
  fenêtre, aucun chargement de `pywebview` en mode autotest.
- **Rapport fichier** : l'exe Windows étant fenêtré (`console=False`), sa sortie
  standard est perdue ; `--autotest <chemin>` écrit donc aussi le compte rendu
  complet dans le fichier indiqué, que le script de build récupère.
- **Script de build `build/rebuild_rummikub.bat`** :
  - nouvelle **sous-étape 5bis** (sans renuméroter l'existant, comme `3bis`/
    `8bis`) : lance `dist\Rummikub\Rummikub.exe --autotest <log>` après
    PyInstaller, **reprend le log** dans le compte rendu (`type`), et **refuse
    le build** (`exit /b 1`, message clair) si le code de sortie n'est pas 0 ;
  - **garde-fous de taille élargis** (valeurs **provisoires** à confirmer au
    1ᵉʳ build Windows) : dossier non compressé **20-120 Mo** (étape 5),
    installeur compressé **5-50 Mo** (étape 6), zip compressé **5-50 Mo**
    (étape 7, même famille que l'installeur) ;
  - les autres garde-fous (numéro de build, arguments) sont **inchangés**.
- **`rummikub.spec`** : `excludes` ajoutés pour ne pas embarquer d'inutile —
  `scipy`, `matplotlib`, `pandas`, `tkinter`, `PyQt5/6`, `PySide2/6`, et les
  sous-paquets de dev/compilation/tests de numpy (`f2py`, `distutils`,
  `testing`, `tests`, `array_api`). Vérifié : l'import du solveur n'est pas
  cassé. ⚠️ `numpy.libs/libscipy_openblas64_*.so` (~27 Mo) est l'**OpenBLAS
  vendu par numpy** (requis), PAS le paquet `scipy` — jamais exclu.
- **Tests `tests/test_autotest.py`** : cas réussi (solveur présent), dépendances
  absentes simulées (`numpy`/`highspy`), ressources web manquantes, écriture du
  rapport, et garantie que `--autotest` n'importe **jamais** `pywebview`/l'UI
  (exécution réelle de `main.py --autotest` en sous-processus).

## Essai Linux (détection précoce — ne remplace pas le build Windows)

PyInstaller, `highspy`, `numpy` et `pywebview` installés dans un venv de dev
hors dépôt (`.venv-exact`, gitignoré ; `requirements.txt` **non modifié**).
Build onedir `pyinstaller rummikub.spec` → OK.

- `--autotest` sur l'exe gelé : **code 0**, backend HIGHS, **6 tuiles** posées,
  ressources web trouvées dans le bundle, rapport fichier écrit.
- **Poids du dossier produit : ~74 Mo** (numpy.libs/OpenBLAS 27 Mo + numpy
  14 Mo + libpython 8,7 Mo + highspy 6 Mo + libcrypto 5,1 Mo + reste runtime).
- **Modules manquants** : seulement des faux positifs habituels de numpy
  (`numpy._core.*`, accès d'attributs, pas de vrais modules) et les backends
  Windows de pywebview (`winreg`, `webview.platforms.winforms`…), normaux sous
  Linux. **Aucun** paquet exclu (scipy/matplotlib/tkinter/Qt, numpy
  f2py/distutils/tests) n'est entraîné.

## Estimation du poids final (Windows, à confirmer)

Dossier non compressé **~75-85 Mo** (build 13 : 26 Mo + ~+55 Mo numpy/highspy),
installeur et zip compressés **~25-35 Mo** (build 13 : 12,8 Mo). Tous dans les
nouvelles fourchettes.

## Tests

- `tests/test_autotest.py` : **8 passés** avec `highspy`/`numpy` présents (dans
  le venv de dev) ; les cas « deps présentes » sont sautés à défaut, comme
  `test_solveur_exact_maison.py`.
- Suite complète (venv avec deps) : **244 passés, 5 sautés**, 1 échec
  **préexistant et sans rapport avec #208** :
  `test_ia.py::test_solveur_cascade_joker_61_trouve_attendu_avec_gros_budget`
  — test machine-dépendant de l'ANCIENNE recherche arborescente
  (`solveur.py`, budget 12 s codé en dur) : échoue à l'identique sur le HEAD
  pristine (3 tuiles au lieu de 4 ; la machine d'essai est plus lente que la
  machine de référence du test). Aucun fichier de `src/rummikub/moteur/` n'est
  touché par #208.

## À mettre à jour dans le guide de build avant le prochain essai Windows

Fiche Rummikub de `BUILD_WINDOWS_CCW.md` (dépôt Bridge_Agent, **hors périmètre,
non modifié ici**) — voir le rapport de clôture pour les lignes exactes et la
checklist du poste Windows.
