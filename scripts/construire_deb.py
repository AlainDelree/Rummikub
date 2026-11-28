"""Construit le paquet .deb « clé en main » de Rummikub pour Ubuntu LTS
(amd64) — issue #258.

Usage (depuis la racine du dépôt) :
    python3 scripts/construire_deb.py [--force-pyinstaller] [--garder-etape]

- Compile avec PyInstaller (``rummikub.spec``) si ``dist/Rummikub`` n'existe
  pas encore, ou toujours si ``--force-pyinstaller`` est passé.
- Assemble l'arborescence du paquet (``/opt/rummikub``, lien ``/usr/bin/
  rummikub``, lanceur ``.desktop``, icônes) dans un dossier de travail sous
  ``build/deb_staging/``, supprimé en fin d'exécution sauf si
  ``--garder-etape`` est passé.
- Produit ``dist/rummikub_<version>_amd64.deb``. La version vient de
  ``version.json`` (champ ``build``), combinée au numéro majeur.mineur fixe
  utilisé par l'installeur Windows (``installeur/rummikub.iss``,
  ``MyAppVersion``) : ``1.0.<build>``.

Ce script ne modifie ni ne lance le jeu : il se contente d'empaqueter le
résultat de ``pyinstaller rummikub.spec`` (voir CONTEXTE.md pour le détail du
build). Aucune connexion réseau n'est nécessaire : les seules dépendances
exécutées sont celles déjà installées localement (PyInstaller, dpkg-deb).
"""
from __future__ import annotations

import argparse
import json
import shutil
import stat
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# Dépendance système unique déclarée : le moteur web WebKitGTK (liaison
# GObject-introspection 4.1). PyInstaller embarque déjà GTK3, GLib, PyGObject
# (module « gi » compilé) et leurs .typelib — vérifié par essai réel sur
# Ubuntu 24.04.5 LTS (voir docs/contexte/paquet_linux.md) : seuls
# libwebkit2gtk-4.1 et libsoup-3.0 manquent au binaire gelé. apt résout seul
# la fermeture transitive (gir1.2-webkit2-4.1 dépend déjà de
# libwebkit2gtk-4.1-0, gir1.2-gtk-3.0, gir1.2-soup-3.0,
# gir1.2-javascriptcoregtk-4.1) : inutile de les lister un par un.
DEPENDANCES_SYSTEME = ["gir1.2-webkit2-4.1"]


def lire_version() -> str:
    donnees = json.loads((RACINE / "version.json").read_text("utf-8"))
    return f"1.0.{donnees['build']}"


def construire_pyinstaller(forcer: bool) -> None:
    dist_dir = RACINE / "dist" / "Rummikub"
    if dist_dir.exists() and not forcer:
        print(f"[construire_deb] {dist_dir} existe déjà : build PyInstaller sauté "
              "(--force-pyinstaller pour forcer).")
        return
    print("[construire_deb] Construction avec PyInstaller (rummikub.spec)...")
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "rummikub.spec"]
    # aucun shell ; arguments fixes du script, aucune saisie utilisateur
    subprocess.run(cmd, cwd=RACINE, check=True)  # noqa: S603  # nosec B603
    if not (dist_dir / "Rummikub").exists():
        raise SystemExit(f"[construire_deb] ERREUR : {dist_dir}/Rummikub introuvable après le build.")


def assembler_arborescence(staging: Path, version: str) -> None:
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    # /opt/rummikub — copie du dossier onedir produit par PyInstaller, sans
    # jamais inclure d'éventuelles données utilisateur (config.json, data/,
    # logs_parties/) qui auraient pu être créées là par erreur pendant un
    # lancement manuel de test : le paquet doit rester sans état, comme
    # l'installeur Windows (voir installeur/rummikub.iss, section [Files]).
    opt_dir = staging / "opt" / "rummikub"
    shutil.copytree(
        RACINE / "dist" / "Rummikub", opt_dir,
        ignore=shutil.ignore_patterns("config.json", "data", "logs_parties", "*.db"),
    )
    exe = opt_dir / "Rummikub"
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    # /usr/bin/rummikub — lien symbolique vers l'exécutable.
    bin_dir = staging / "usr" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "rummikub").symlink_to("/opt/rummikub/Rummikub")

    # Lanceur .desktop (menu des applications).
    apps_dir = staging / "usr" / "share" / "applications"
    apps_dir.mkdir(parents=True)
    shutil.copy2(RACINE / "assets" / "rummikub.desktop", apps_dir / "rummikub.desktop")

    # Icônes (thème hicolor), plusieurs tailles — assets/icons_deb/<N>x<N>/rummikub.png.
    icones_source = RACINE / "assets" / "icons_deb"
    for dossier_taille in sorted(icones_source.iterdir()):
        if not dossier_taille.is_dir():
            continue
        cible = staging / "usr" / "share" / "icons" / "hicolor" / dossier_taille.name / "apps"
        cible.mkdir(parents=True)
        shutil.copy2(dossier_taille / "rummikub.png", cible / "rummikub.png")

    ecrire_control(staging, version)
    ecrire_scripts_maintainer(staging)


def taille_installee_ko(staging: Path) -> int:
    total = 0
    for chemin in staging.rglob("*"):
        if chemin.is_symlink() or chemin.is_file():
            total += chemin.lstat().st_size
    return max(1, total // 1024)


def ecrire_control(staging: Path, version: str) -> None:
    debian_dir = staging / "DEBIAN"
    debian_dir.mkdir(parents=True)
    taille_ko = taille_installee_ko(staging)
    control = f"""\
Package: rummikub
Version: {version}
Section: games
Priority: optional
Architecture: amd64
Maintainer: Alain Delree <rummikub@localhost>
Installed-Size: {taille_ko}
Depends: {", ".join(DEPENDANCES_SYSTEME)}
Homepage: https://github.com/AlainDelree/Rummikub
Description: Rummikub à jouer seul contre l'ordinateur
 Jeu de Rummikub avec cinq niveaux d'intelligence artificielle, interface
 graphique native (pywebview + WebKitGTK). Les parties et réglages sont
 sauvegardés dans le dossier personnel de l'utilisateur.
"""
    (debian_dir / "control").write_text(control, "utf-8")


def ecrire_scripts_maintainer(staging: Path) -> None:
    """postinst/postrm : rafraîchissent le cache d'icônes et la base des
    lanceurs .desktop après installation/suppression, pour que l'icône et
    l'entrée de menu apparaissent sans ouverture de session. Ne doivent
    jamais faire échouer l'installation si ces outils sont absents (``|| true``)."""
    debian_dir = staging / "DEBIAN"
    corps = """#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
exit 0
"""
    for nom in ("postinst", "postrm"):
        fichier = debian_dir / nom
        fichier.write_text(corps, "utf-8")
        fichier.chmod(0o755)


def construire_deb(staging: Path, version: str) -> Path:
    sortie = RACINE / "dist" / f"rummikub_{version}_amd64.deb"
    cmd = ["dpkg-deb", "--build", "--root-owner-group", str(staging), str(sortie)]
    # aucun shell ; arguments fournis par le script lui-même, aucune saisie utilisateur
    subprocess.run(cmd, check=True)  # noqa: S603  # nosec B603
    return sortie


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force-pyinstaller", action="store_true",
                         help="Reconstruit avec PyInstaller même si dist/Rummikub existe déjà.")
    parser.add_argument("--garder-etape", action="store_true",
                         help="Ne supprime pas le dossier de travail build/deb_staging/ après le build.")
    args = parser.parse_args()

    version = lire_version()
    print(f"[construire_deb] Version du paquet : {version}")

    construire_pyinstaller(args.force_pyinstaller)

    staging = RACINE / "build" / "deb_staging" / f"rummikub_{version}_amd64"
    print(f"[construire_deb] Assemblage de l'arborescence dans {staging}...")
    assembler_arborescence(staging, version)

    print("[construire_deb] Construction du .deb avec dpkg-deb...")
    sortie = construire_deb(staging, version)

    if not args.garder_etape:
        shutil.rmtree(staging)

    taille_mo = sortie.stat().st_size / (1024 * 1024)
    print(f"[construire_deb] Terminé : {sortie} ({taille_mo:.1f} Mo)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
