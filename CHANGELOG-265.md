# Issue #265 — Audit sécurité : justifier les deux lancements d'Actualise et protéger la suppression du drapeau

## Contexte

Le dernier audit de Diagnostique_Programme relevait deux défauts sur le
lancement des mises à jour d'Actualise : deux appels `subprocess.Popen` sans
justification en ligne (règle SEC-003 du linter sécurité) alors qu'ils sont
déjà précédés d'une validation par `valider_chemin_actualise`, et une
suppression du fichier-drapeau non protégée dans le gestionnaire de
fermeture (risque de `PermissionError` si le dossier d'installation,
Program Files, n'est pas modifiable par un compte non administrateur).

## 1. Justification en ligne des deux lancements d'Actualise (SEC-003)

- `main.py` (`_lancer_actualise_ui_si_flag`, ~L45) : `subprocess.Popen([...])`
  → ajout de deux lignes (raison en clair + `# noqa: S603  # nosec B603`) :
  aucun shell, `_actualise_ui`/`_bat` validés par `valider_chemin_actualise`
  (existence, extension `.bat`/`.exe`, racine Actualise autorisée), `_flag`
  et `sys.executable` sont des chemins internes non saisis par l'utilisateur.
- `src/rummikub/ui/application.py` (`_handler_fermeture_actualise`, ~L39) :
  `subprocess.Popen([str(_bat)])` → même traitement, `_bat` validé par
  `valider_chemin_actualise`, seul argument du lancement.
- `ruff check --select S` sur `main.py`, `ui/application.py`,
  `actualise.py` : plus aucun avertissement (2 `S603` résolus).

## 2. Suppression tolérante du drapeau (`_handler_fermeture_actualise`)

`_flag.unlink(missing_ok=True)` était hors de toute protection : un échec de
droits y aurait propagé une exception non rattrapée par l'événement
`closing` de pywebview. Entourée d'un `try/except OSError` : un échec est
journalisé sur stderr (même forme que les autres cas du fichier) et
n'empêche ni la fermeture ni la tentative de lancer le bat de mise à jour
juste après. Docstring de la fonction mise à jour en conséquence.

## 3. Vérification de la protection contre les exceptions (point demandé par l'audit)

Les deux fonctions de `main.py` et `_handler_fermeture_actualise` sont
globalement protégées comme l'affirme le rapport (lecture du flag,
validation des chemins, lancement du sous-processus — tous sous
`try/except`/`contextlib.suppress`), à une exception près trouvée dans les
**trois** fonctions : le `Path.exists()` du drapeau/d'Actualise n'était pas
protégé. `pathlib.Path.exists()` ne capture pas `PermissionError` (`EACCES`
n'est pas dans sa liste d'erreurs ignorées) : un dossier illisible
propagerait l'exception.

- **Corrigé** (cas trivial, dans le gestionnaire de fermeture visé par cette
  issue) : `src/rummikub/ui/application.py`, `_handler_fermeture_actualise`
  — `if not _flag.exists(): return` entouré d'un `try/except OSError:
  return`.
- **Non corrigé, signalé pour une issue séparée** (même nature, hors
  périmètre strict de cette tâche) :
  - `main.py`, `_lancer_actualise_ui_si_flag` — même `_flag.exists()` non
    protégé.
  - `main.py`, `_lancer_actualise_au_demarrage` — `_actualise.exists()`
    (chemin fixe `C:\Actualise\Actualise.exe`) non protégé.

## 4. Tests ajoutés

`tests/test_actualise_flag_lancement.py` :
`test_application_echec_suppression_flag_tolere_et_lance_tout_de_meme` —
simule l'échec de suppression via `monkeypatch.setattr(Path, "unlink", ...)`
levant un `PermissionError` (indépendant des droits réels du système,
fonctionne sous Linux comme sous Windows) ; vérifie que le gestionnaire ne
lève pas, que le bat est tout de même lancé sans shell, que le flag reste en
place, et qu'un message apparaît sur stderr.

`pytest tests/test_actualise_flag_lancement.py` : 12 passés (11 existants +
1 nouveau). `pytest -m "not lent"` (suite complète hors tests lents) :
521 passés, 13 sautés, 0 échec.

## 5. Documentation

`docs/contexte/linter_securite.md` : le paragraphe qui laissait les
lancements validés par `valider_chemin_actualise` « signalés plutôt que
supprimés » est mis à jour — ils sont désormais traités comme faux positif
acquis et justifiés en ligne.

## 6. Risque résiduel (demandé en point de vigilance, non traité ici)

Si la suppression du drapeau échoue à la fermeture, `actualise_update.flag`
reste présent dans le dossier d'installation. Au lancement suivant,
`_lancer_actualise_ui_si_flag` (main.py) le relira et relancera
`ActualiseUI.exe` avec les mêmes chemins — tant que la suppression échoue
(droits toujours refusés), ce relancement peut se répéter à chaque
démarrage. Aucune protection anti-répétition n'existe actuellement contre
ce cas ; à traiter séparément si jugé utile (ex. limite de tentatives,
nouvelle tentative de suppression au prochain succès).
