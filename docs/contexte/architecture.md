# Architecture — stack technique et structure du projet

## 1. Stack technique

- **Python 3.12** (aucune dépendance web côté serveur JS : pas d'Electron, pas de Node).
- **pywebview** : fenêtre native unique. Navigation entre écrans par
  `window.load_url(...)` (pas de routeur SPA). Le back-end Python expose une
  API à JS via `js_api` → `window.pywebview.api.*`.
- **PyInstaller** (`rummikub.spec`, mode **onedir** via `COLLECT`) : produit
  `dist/Rummikub/`. Build : `pyinstaller rummikub.spec` depuis la racine.
- **SQLite** (module standard `sqlite3`) pour la persistance des parties.
- **Portable Linux ET Windows** : aucun séparateur de chemin codé en dur,
  tout passe par `pathlib.Path` (côté app) ou `os.path` (côté `.spec`).
- Dépendances (`requirements.txt`) : `pywebview`, `pyinstaller`, `pytest`.
- **Paquet .deb Ubuntu LTS** (`scripts/construire_deb.py`, issue #258) : voir
  `docs/contexte/paquet_linux.md` (construction, dépendances système,
  chemins de données utilisateur en mode gelé Linux).

## 2. Architecture générale

```
main.py                     Point d'entrée. Ajoute src/ au sys.path (sauf si frozen),
                            puis appelle rummikub.ui.application.main().
config.json                 Réglages utilisateur persistés (à la racine).
rummikub.spec               Spec PyInstaller onedir (embarque ui/web/).
pytest.ini                  pythonpath=src, testpaths=tests.
data/parties.db             Base SQLite (créée à la volée).

src/rummikub/
  config.py                 Constantes globales + chemins frozen/dev (RACINE_PROJET
                            via sys._MEIPASS si gelé, sinon parents). RACINE_DATA en
                            mode gelé : %APPDATA%\Rummikub (Windows, inchangé) ou
                            $XDG_DATA_HOME/rummikub ~ ~/.local/share/rummikub (Linux,
                            issue #258) — voir docs/contexte/paquet_linux.md. COULEURS,
                            VALEUR_MIN/MAX, NB_JOKERS(2), NB_TUILES_DEPART(14),
                            MISE_INITIALE_MIN(30), NIVEAUX (6 libellés IA, §16), AVATARS.
  reglages.py               charger()/sauvegarder(data) de config.json (fusion DEFAUTS).
  persistance/stockage.py   SQLite : sauvegarder_partie, charger_parties(5 derniers),
                            charger_partie, marquer_terminee, supprimer_partie.
  persistance/journal.py   Journal JSON optionnel par partie (debug + bilan, voir §9).
  persistance/bilan.py      Lecture des journaux + calcul du bilan par niveau d'IA (coups_rates_bilan.md §10).
  persistance/coups_rates.py  Détection des coups ratés de l'IA via le solveur
                            d'Expert, à partir des journaux (§11).
  moteur/                   Logique de jeu pure (voir §3).
    tuiles.py               Dataclass Tuile + création/mélange/distribution.
    validation.py           valider_suite/groupe/combinaison/plateau.
    partie.py               État de partie, tours, pioche, backup, manches.
    score.py                calculer_scores_manche, trouver_gagnant_manche.
    ia.py                   5 niveaux d'IA sur un même moteur exact bridé
                            (voir §16, issue #213) + tactiques de
                            récupération de joker (voir §8, repli).
    niveaux.py              Paramètres d'affaiblissement des niveaux (niveaux_ia_calibrage.md §16).
    solveur.py              Solveur de réarrangement global du plateau,
                            utilisé par Expert (voir §8bis, #186).
    description_coup.py     Résumé écrit + étapes du rejeu pas-à-pas d'un
                            coup de l'IA, à partir du plateau avant/après
                            (voir §12, #189).
  ui/
    application.py          ApplicationRummikub : fenêtre pywebview, etat_jeu (public),
                            naviguer_vers_jeu/accueil, reprendre_jeu, load_url.
    api.py                  Classe Api : méthodes appelables depuis JS (voir §4).
    noms_ordinateur.py      choisir() : nom aléatoire pour un joueur IA.
    web/                    Front : accueil.html/css/js, jeu.html/css/js,
                            commun.css/js, avatars/.

tests/                      pytest : test_moteur.py + test_ia.py + test_description_coup.py.
```

