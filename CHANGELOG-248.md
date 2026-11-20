# Issue #248 — Sécurité du linter : corriger ce qui peut l'être et justifier en ligne les faux positifs déjà jugés

## Contexte

`ruff check . --select S` depuis la racine (pas de config ruff dédiée dans le
dépôt, defaults purs) recensait 1258 avertissements de sécurité : 1231 `S101`
(`assert`) et 1 `S108` (`/tmp`), tous dans `tests/` — convention pytest
standard, hors périmètre de cette issue (limitée aux lignes de sécurité
« déjà jugées » : `subprocess`, aléa de jeu, `urlopen`) — 9 `S110`
(`try/except/pass`), 6 `S603`/1 `S607` (`subprocess`), 10 `S311` (`random`).
Aucun `S310` (`urlopen`) trouvé.

## Corrections (comportement inchangé)

`try/except/pass` → `with contextlib.suppress(Exception): ...` (9
occurrences, même exception capturée, juste la forme) :
- `main.py:50` (lancement d'ActualiseUI depuis un flag)
- `scripts/_mesure_volume_222.py:59` (compteurs HiGHS best-effort)
- `src/rummikub/autotest.py:164` et `:178` (affichage best-effort sans console)
- `src/rummikub/moteur/solveur_exact.py:437` et `:548` (attribut HiGHS absent / warm start best-effort)
- `src/rummikub/persistance/journal.py:232` (écriture du journal best-effort)
- `src/rummikub/ui/api.py:260` (dump de diagnostic best-effort)
- `src/rummikub/ui/application.py:34` (lancement du bat de mise à jour à la fermeture)

## Suppressions en ligne ajoutées (faux positifs jugés, raison + `noqa`/`nosec` précis)

`subprocess` à arguments fixes ou contrôlés par le script appelant (`S603`/`S607` ↔ `B603`/`B607`) :
- `main.py:63` — chemin et arguments fixes (`Actualise.exe --config rummikub`)
- `scripts/_limite_temps_ferme.py:60` — sous-processus de mesure, argv du script appelant
- `scripts/_limite_temps_ferme.py:91` — `taskkill /PID <pid>` fixe (S603+S607)
- `tests/test_autotest.py:148` — code Python construit par le test lui-même

Aléa de jeu, sans enjeu de sécurité (`S311` ↔ `B311`) :
- `src/rummikub/moteur/tuiles.py:70` (mélange du sac)
- `src/rummikub/moteur/ia.py:986` et `:990` (tirage de l'oubli des niveaux)
- `src/rummikub/ui/noms_ordinateur.py:43` (nom aléatoire d'un joueur IA)
- `scripts/comparer_niveaux_ia.py:526`, `scripts/profil_joueur.py:230`,
  `scripts/verifier_simplicite_expert.py:357`,
  `scripts/verifier_solveur_exhaustif.py:63` (graines de simulation)
- `tests/test_solveur_exact_maison.py:205`, `tests/test_verif_solveur.py:60`
  (positions de test à graine fixe)

Aucun `urlopen` (`S310`) trouvé dans le dépôt : rien à traiter pour ce code.

## Laissé tel quel, signalé (doute — ni corrigé ni supprimé)

- `main.py:45` (`subprocess.Popen` dans `_lancer_actualise_ui_si_flag`) et
  `src/rummikub/ui/application.py:34` (dans `_handler_fermeture_actualise`) :
  arguments provenant d'un fichier flag externe (`actualise_update.flag`),
  bien que validés par `valider_chemin_actualise` (SEC-003 : existence,
  extension `.bat`/`.exe`, confinement à la racine Actualise autorisée).
  Ce n'est pas un « argument fixe » au sens de cette issue — à juger
  séparément si une suppression formelle est souhaitée. **Non touché**, y
  compris la ligne du chemin littéral `main.py` déjà jugée à ne pas traiter
  (hors sécurité).
- `S101` (1231, `assert` dans `tests/`) et `S108` (1, `/tmp` dans un test) :
  convention pytest/test standard, hors des catégories déjà jugées par cette
  issue ; non traités (ni corrigés, ni suppressions ligne par ligne — le
  volume et la nature rendraient une suppression ligne par ligne absurde).
  Une décision de config ruff dédiée (`per-file-ignores` pour `tests/`)
  resterait à prendre séparément si souhaité.

## Comptes

- Avant : 1258 avertissements `S` (1231 `S101`, 10 `S311`, 9 `S110`, 6
  `S603`, 1 `S607`, 1 `S108`).
- Après : 1234 (1231 `S101`, 1 `S108`, 2 `S603` — les deux cas signalés
  ci-dessus). Tous les `S110`, `S311`, `S607` et 4/6 `S603` ont été traités
  (corrigés ou justifiés en ligne) ; 0 `S310`.

## Documentation

Nouveau fichier `docs/contexte/linter_securite.md` : convention de
suppression en ligne (deux lignes, raison + `noqa`/`nosec` précis, jamais
seuls) et principe « corriger plutôt que supprimer ». Pointeur ajouté dans
`CONTEXTE.md` §4 (Conventions importantes).

## Vérifications

- `python3 -m py_compile` sur tous les fichiers modifiés : OK.
- `python3 -m pytest -q` : 459 réussis, 13 ignorés, 0 échec.
- `ruff check . --select S` : 1234 restants (voir « Comptes » ci-dessus),
  tous soit hors périmètre (tests), soit signalés avec raison dans ce
  changelog.
