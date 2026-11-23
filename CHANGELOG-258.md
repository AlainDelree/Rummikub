# Issue #258 — Paquet .deb « clé en main » pour Ubuntu LTS (installation par double-clic, lanceur dans le menu, données hors du dossier d'installation)

## Contexte

Le jeu doit être installé sur le PC d'une personne âgée sous Ubuntu LTS :
double-clic sur un fichier, bouton « Installer », puis une icône Rummikub
dans le menu des applications, sans terminal. Le dépôt n'avait jusqu'ici que
l'installeur Windows (`installeur/`) ; sous Linux, seul le lancement depuis
les sources était documenté.

## 1. Données utilisateur hors du dossier d'installation (Linux, mode gelé uniquement)

`src/rummikub/config.py` : nouvelle fonction `_calculer_racine_data_gelee`.
En mode gelé (PyInstaller) :
- **Windows** : `%APPDATA%\Rummikub` — **inchangé**.
- **Linux** (nouveau, issue #258) : `$XDG_DATA_HOME/rummikub` si la
  variable est définie et non vide, sinon `~/.local/share/rummikub`. Le
  dossier est créé au premier lancement (par `reglages.sauvegarder` ou
  `persistance.stockage._conn`), jamais à l'installation.

Mode développement (lancement depuis les sources) : **inchangé**
(`data/`, `config.json` à la racine du dépôt).

Testé de bout en bout (hors tests unitaires ci-dessous) : simulation d'un
mode gelé Linux avec `HOME` temporaire — `config.json` et `parties.db`
apparaissent bien sous `~/.local/share/rummikub`, avec les réglages par
défaut.

## 2. Script de construction du paquet

`scripts/construire_deb.py` (nouveau) :
- Compile avec PyInstaller (`rummikub.spec`) si `dist/Rummikub` n'existe
  pas déjà (`--force-pyinstaller` pour forcer).
- Assemble l'arborescence du paquet (`/opt/rummikub`, lien `/usr/bin/
  rummikub`, lanceur `.desktop`, icônes hicolor) dans `build/deb_staging/`.
- Construit `dist/rummikub_<version>_amd64.deb` avec `dpkg-deb --build
  --root-owner-group` (pas besoin de root pour construire). Version lue
  dans `version.json` (`1.0.<build>`, même convention que l'installeur
  Windows).

## 3. Lanceur et icône

- `assets/rummikub.desktop` (nouveau) : nom « Rummikub », commentaire en
  français, catégories `Game;BoardGame;`. Validé avec
  `desktop-file-validate` (code de sortie 0).
- `assets/icons_deb/<N>x<N>/rummikub.png` (nouveau, N = 16/32/48/64/128/
  256/512) : icône carrée générée une fois depuis `Rummikub.png` (racine du
  dépôt), pré-rendue dans le dépôt pour ne pas ajouter de dépendance Pillow
  au script de build.

## 4. Dépendances système

Une seule dépendance déclarée dans le paquet : `gir1.2-webkit2-4.1`.
Établie par essai réel sur Ubuntu 24.04.5 LTS (machine de développement) :
inspection du build PyInstaller (WebKit2-4.1/Soup-3.0 absents des
`.typelib` embarqués, contrairement à Gtk-3.0/GLib/GObject/etc.) +
exécution réelle du binaire gelé sans serveur d'affichage (chargement de
`gi`/`Gtk`/`WebKit2`/`Soup` réussi, échec seulement à l'ouverture d'un
affichage). `gir1.2-webkit2-4.1` entraîne par apt toute sa fermeture
transitive (`libwebkit2gtk-4.1-0`, `gir1.2-gtk-3.0`, `gir1.2-soup-3.0`,
`gir1.2-javascriptcoregtk-4.1`) — vérifié avec `apt-cache depends`.
`python3-gi` n'est **pas** déclaré : le module `gi` compilé et
`libgirepository` sont déjà embarqués par PyInstaller. Détail complet,
limites (pas de conteneur Ubuntu vierge disponible ici) dans
`docs/contexte/paquet_linux.md`.

## 5. Installation / mise à jour / désinstallation

`sudo apt install ./rummikub_<version>_amd64.deb` installe le jeu et ses
dépendances ; une nouvelle version s'installe par-dessus (rien dans
`/opt/rummikub` n'est une donnée utilisateur). `sudo apt remove rummikub`
retire `/opt/rummikub`, `/usr/bin/rummikub`, le lanceur et les icônes, sans
jamais toucher à `~/.local/share/rummikub` (hors de l'arborescence du
paquet).

## 6. Vérification

Faite : `dpkg-deb --info`/`--contents` (métadonnées, arborescence,
root/root, permissions), `desktop-file-validate` sur le `.desktop`,
exécution réelle du binaire gelé sans serveur d'affichage (voir §4), test
de bout en bout des chemins de données (§1), suite de tests complète.
**Non faite** (outils absents de cet environnement : `docker`, `podman`,
`lintian`, `xvfb-run`) : `lintian`, installation dans un conteneur Ubuntu
24.04 propre, lancement avec une vraie fenêtre graphique — à faire par
Alain sur une machine Ubuntu avec serveur graphique.

## 7. Documentation

- `README.md` : nouvelle section Linux (installation du `.deb`, double-clic,
  désinstallation, reconstruction du paquet), mise à jour de « Données
  personnelles » (trois emplacements selon la plateforme/le mode) et de
  l'arborescence du dépôt.
- `docs/contexte/paquet_linux.md` (nouveau) : construction, dépendances,
  emplacements, limites connues.
- `CONTEXTE.md` : ligne d'index ajoutée (section 1, Stack technique) +
  description de `config.py` mise à jour (section 2, arborescence) pour
  pointer vers `docs/contexte/paquet_linux.md`.

## Tests

- `tests/test_config_chemins_donnees.py` (nouveau) : mode développement
  (inchangé), Windows gelé simulé (avec/sans `APPDATA`), Linux gelé simulé
  (avec/sans/vide `XDG_DATA_HOME`).
- Suite complète (`pytest tests/ -q`, hors tests Playwright nécessitant un
  navigateur) : verte avant et après les changements.

## Fichiers touchés

- `src/rummikub/config.py` (modifié)
- `scripts/construire_deb.py` (nouveau)
- `assets/rummikub.desktop` (nouveau)
- `assets/icons_deb/` (nouveau, 7 tailles)
- `tests/test_config_chemins_donnees.py` (nouveau)
- `README.md`, `CONTEXTE.md`, `docs/contexte/paquet_linux.md` (documentation)

## Le .deb produit localement

`dist/rummikub_1.0.14_amd64.deb` (non commité, non publié — produit en
local comme demandé). Taille : voir rapport de clôture de l'issue.
