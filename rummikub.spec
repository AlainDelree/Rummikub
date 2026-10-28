# -*- mode: python ; coding: utf-8 -*-
# Spécification PyInstaller pour Rummikub (adaptée de scrabble.spec).
#
# Build (depuis la racine du dépôt, Linux ou Windows) :
#     pyinstaller rummikub.spec
#
# Produit un dossier dist/Rummikub/ contenant l'exécutable « Rummikub »
# et ses ressources web. Portable Linux/Windows : aucun séparateur de
# chemin codé en dur, tout passe par os.path.

import os

RACINE = SPECPATH  # répertoire contenant ce fichier .spec (injecté par PyInstaller)

# Modèle exact d'Expert (issue #206) : highspy (HiGHS, extension native pybind11)
# + numpy. PyInstaller détecte en général numpy via ses hooks ; highspy, étant
# une extension compilée, est plus sûr à collecter explicitement (sous-modules
# + bibliothèques dynamiques _core*.pyd/.so). Si les paquets ne sont PAS
# installés dans l'environnement de build, on n'embarque rien : le jeu se
# replie alors au runtime sur la recherche arborescente (solveur.py), sans
# planter — voir ``moteur/solveur_exact.py`` et ``moteur/ia.py``.
_hidden_exact = []
_binaries_exact = []
try:
    from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules
    _hidden_exact = ["numpy"] + collect_submodules("highspy")
    _binaries_exact = collect_dynamic_libs("highspy")
except Exception:
    _hidden_exact = []
    _binaries_exact = []


def collect_tree(src_dir, dest_dir):
    """Liste [(chemin_source, dossier_destination), ...] pour tout un arbre.

    Équivalent portable de la copie récursive d'un dossier de ressources ;
    ``src_dir`` est relatif à la racine du dépôt (séparateurs « / »).
    """
    resultats = []
    base = os.path.join(RACINE, *src_dir.split("/"))
    for racine, _dirs, fichiers in os.walk(base):
        for fichier in fichiers:
            chemin = os.path.join(racine, fichier)
            rel = os.path.relpath(os.path.dirname(chemin), base)
            cible = dest_dir if rel == os.curdir \
                else os.path.join(dest_dir, rel)
            resultats.append((chemin, cible))
    return resultats


# Icône personnalisée facultative (assets/rummikub.ico).
_icone = os.path.join(RACINE, "assets", "rummikub.ico")
_icone = _icone if os.path.exists(_icone) else None

# Métadonnées de version Windows (clic droit -> Propriétés -> Détails ->
# « Version du fichier »). Le fichier version_info.txt (racine du dépôt) contient
# le jeton « BUILD » que le script de build (build/rebuild_rummikub.bat) remplace
# par le numéro de build réel avant PyInstaller. On n'active la ressource que si
# ce jeton a bien été substitué : ainsi un « pyinstaller rummikub.spec » lancé
# directement (sans substitution, jeton encore présent) ne casse pas l'analyse
# du fichier de version par PyInstaller. Sous Linux, ce paramètre est ignoré.
_fichier_version = os.path.join(RACINE, "version_info.txt")
_version = None
if os.path.exists(_fichier_version):
    with open(_fichier_version, "r", encoding="utf-8") as _f:
        if "BUILD" not in _f.read():
            _version = _fichier_version

datas = collect_tree("src/rummikub/ui/web", "rummikub/ui/web")

# Fichier de licences tierces (highspy MIT, numpy BSD — issue #206), distribué
# à la racine de dist/Rummikub/ comme l'exigent ces licences permissives.
_licences = os.path.join(RACINE, "THIRD_PARTY_LICENSES.txt")
if os.path.exists(_licences):
    datas.append((_licences, "."))


a = Analysis(
    ["main.py"],
    pathex=[os.path.join(RACINE, "src")],
    binaries=_binaries_exact,
    datas=datas,
    hiddenimports=_hidden_exact,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Exclusions (issue #208) : le jeu n'utilise de numpy/highspy QUE le strict
    # nécessaire au solveur exact (moteur/solveur_exact.py = import numpy +
    # highspy). On retire donc :
    #   - les gros paquets scientifiques jamais utilisés, au cas où un hook les
    #     entraînerait (scipy, matplotlib, pandas) ;
    #   - les toolkits d'interface inutiles (le jeu utilise pywebview, pas Tk/Qt) ;
    #   - les sous-paquets de développement/compilation/tests de numpy (f2py,
    #     distutils, tests), inutiles au runtime et volumineux.
    # Aucune de ces exclusions ne touche l'import du solveur (vérifié par
    # l'essai de build Linux + l'autotest, issue #208).
    excludes=[
        "scipy",
        "matplotlib",
        "pandas",
        "tkinter",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "numpy.f2py",
        "numpy.distutils",
        "numpy.testing",
        "numpy.tests",
        "numpy.array_api",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Rummikub",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icone,  # None => aucune icône personnalisée
    version=_version,  # None => ressource VERSIONINFO non injectée (jeton non substitué)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Rummikub",
    contents_directory=".",
)
