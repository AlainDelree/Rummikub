# -*- mode: python ; coding: utf-8 -*-
# Stub minimal PyInstaller — sera complété à l'issue 4.
# Build attendu (ultérieurement) :
#   pyinstaller rummikub.spec

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("src/rummikub/ui/web", "rummikub/ui/web"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Rummikub",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
