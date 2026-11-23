# Paquet .deb Linux (Ubuntu LTS) — issue #258

> Lire avant toute modification du paquet .deb, de `rummikub.desktop`, des
> icônes `assets/icons_deb/`, ou des chemins de données en mode gelé Linux
> (`src/rummikub/config.py`).

## Construction

`python3 scripts/construire_deb.py` (depuis la racine du dépôt, sous
Linux) :

1. Compile avec PyInstaller (`pyinstaller rummikub.spec`, mode onedir) si
   `dist/Rummikub` n'existe pas déjà (`--force-pyinstaller` pour forcer).
2. Assemble l'arborescence du paquet dans `build/deb_staging/` (supprimé en
   fin de build, sauf `--garder-etape`).
3. Produit `dist/rummikub_<version>_amd64.deb` avec `dpkg-deb --build
   --root-owner-group` (pas besoin de root ni de `fakeroot` pour construire).

La version du paquet est `1.0.<build>`, `<build>` venant de `version.json`
(même source que l'installeur Windows — `1.0` est la version majeure fixe
d'`installeur/rummikub.iss`, `MyAppVersion`).

## Arborescence installée

- `/opt/rummikub/` — dossier onedir PyInstaller complet (exécutable
  `Rummikub` + `_internal/`). Jamais de données utilisateur dedans.
- `/usr/bin/rummikub` — lien symbolique vers `/opt/rummikub/Rummikub`.
- `/usr/share/applications/rummikub.desktop` — lanceur (catégories
  `Game;BoardGame;`), validé avec `desktop-file-validate`.
- `/usr/share/icons/hicolor/<N>x<N>/apps/rummikub.png` — icône carrée
  générée depuis `Rummikub.png` (racine du dépôt) aux tailles 16 à 512 px,
  pré-rendues dans `assets/icons_deb/` (pas de dépendance Pillow au
  moment du build : les PNG sont déjà dans le dépôt).
- `postinst`/`postrm` rafraîchissent `update-desktop-database` et
  `gtk-update-icon-cache` s'ils sont présents (jamais fatal sinon).

## Dépendances système déclarées

```
Depends: gir1.2-webkit2-4.1
```

C'est la SEULE dépendance système explicite. Établie par essai réel (pas de
mémoire), sur Ubuntu 24.04.5 LTS, en deux temps :

1. **Build PyInstaller inspecté** : `dist/Rummikub/_internal/gi_typelibs/`
   contient déjà Gtk-3.0, Gdk-3.0, GLib-2.0, GObject-2.0, Atk-1.0,
   GdkPixbuf-2.0, Pango-1.0, cairo-1.0, HarfBuzz-0.0 — PyInstaller les
   embarque via son hook `gi`. **WebKit2-4.1 et Soup-3.0 manquent** : le hook
   PyInstaller ne les collecte jamais (ce sont des bibliothèques système
   volumineuses, pywebview s'appuie sciemment sur celles d'Ubuntu — voir
   `webview/platforms/gtk.py`, `gi.require_version('WebKit2', '4.1')` /
   `gi.require_version('Soup', '3.0')`, avec repli `4.0`/`2.4`).
2. **Exécution réelle du binaire gelé**, sans serveur d'affichage
   (`DISPLAY` et `WAYLAND_DISPLAY` retirés) : le process charge `gi`, `Gtk`,
   `WebKit2`, `Soup` avec succès (aucune `ImportError`), lance son serveur
   HTTP interne, et échoue seulement à l'étape suivante
   (`Gtk-WARNING: cannot open display`) — preuve directe que la résolution
   des `.typelib` WebKit2/Soup retombe sur le chemin système
   (`/usr/lib/x86_64-linux-gnu/girepository-1.0/`) même si le *runtime hook*
   PyInstaller (`pyi_rth_gi.py`) réduit `GI_TYPELIB_PATH` au seul dossier
   embarqué (confirmé en rejouant ce réglage dans un `python3` non gelé).

`gir1.2-webkit2-4.1` dépend lui-même, via apt, de `libwebkit2gtk-4.1-0`,
`gir1.2-gtk-3.0`, `gir1.2-soup-3.0` et `gir1.2-javascriptcoregtk-4.1`
(vérifié avec `apt-cache depends`) : apt résout donc seul toute la
fermeture transitive, pas besoin de lister chaque paquet. `python3-gi` n'est
**pas** déclaré : le module `gi` compilé (`_gi*.so`) et `libgirepository`
sont déjà embarqués par PyInstaller — confirmé par la même exécution réelle
(pas d'erreur d'import malgré l'absence du module `gi` du dépôt dans le
`sys.path` d'un exécutable gelé).

**Limite connue** : pas de conteneur/VM Ubuntu 24.04 strictement vierge
disponible dans cet environnement (ni `docker`, ni `podman`, ni `lintian`,
ni `xvfb-run`) — la machine de test a déjà `gir1.2-webkit2-4.1` et ses
dépendances installées (utilisées par d'autres projets locaux). La preuve
ci-dessus (absence du `.typelib` WebKit2/Soup dans le binaire gelé +
chargement réussi au runtime) est solide mais n'a pas été recoupée par une
installation `apt install ./rummikub_*.deb` sur un Ubuntu fraîchement
installé. **Ubuntu plus récent qu'24.04** : `gir1.2-webkit2-4.1` existe
encore en 24.04 aux côtés de `gir1.2-webkit-6.0` (migration WebKitGTK 6.0 en
cours dans l'écosystème GNOME) ; rien ne garantit que `gir1.2-webkit2-4.1`
reste disponible indéfiniment sur de futures LTS — à revérifier si le
paquet est un jour construit/installé sur une version post-24.04.

## Emplacement des données utilisateur

Mode gelé (paquet installé) **sous Linux uniquement** (`src/rummikub/
config.py`, `_calculer_racine_data_gelee`) :
`$XDG_DATA_HOME/rummikub` si la variable est définie (et non vide), sinon
`~/.local/share/rummikub`. Contient `config.json`, `parties.db`,
`logs_parties/`. Créé au premier lancement (pas à l'installation). Windows
gelé (`%APPDATA%\Rummikub`) et mode développement (`data/`, `config.json` à
la racine du dépôt) restent inchangés.

## Désinstallation

`sudo apt remove rummikub` retire `/opt/rummikub`, `/usr/bin/rummikub`, le
lanceur et les icônes. Les données utilisateur (`~/.local/share/rummikub`)
ne sont jamais touchées : elles sont hors de l'arborescence du paquet, dpkg
ne les connaît pas.

## Limites connues / non vérifié

- Pas de lancement avec une vraie fenêtre (serveur graphique) dans cet
  environnement : seule l'absence d'erreur avant `cannot open display` a pu
  être vérifiée (voir ci-dessus).
- Pas d'installation réelle via `sudo apt install ./rummikub_*.deb` ni de
  double-clic dans le centre de logiciels d'Ubuntu (à faire par Alain sur
  une machine graphique).
- `lintian` indisponible dans cet environnement : seules les vérifications
  `dpkg-deb --info/--contents` et `desktop-file-validate` ont pu tourner.
