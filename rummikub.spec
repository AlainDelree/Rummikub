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

datas = collect_tree("src/rummikub/ui/web", "rummikub/ui/web")


a = Analysis(
    ["main.py"],
    pathex=[os.path.join(RACINE, "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
