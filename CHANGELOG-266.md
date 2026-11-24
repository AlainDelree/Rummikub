# Issue #266 — Audit sécurité : corriger le libellé SEC-003 et protéger les deux tests d'existence restants

## Contexte

Suite de l'issue #265 (dont les corrections n'étaient pas encore présentes
dans cette worktree au moment du traitement, car sa branche n'a pas encore
été fusionnée — voir point de vigilance ci-dessous). Deux défauts relevés :
un amalgame entre `valider_chemin_actualise` (la mesure de validation,
issue #234) et SEC-003 (la règle d'audit qu'elle justifie), et deux tests
d'existence (`Path.exists()`) non protégés contre une `PermissionError`
dans `main.py`.

## 1. Libellé corrigé (`docs/contexte/linter_securite.md`)

Le paragraphe sur les `subprocess` validés par un fichier externe écrivait
« `valider_chemin_actualise`/SEC-003 », comme si c'était la même chose.
Reformulé : `valider_chemin_actualise` (issue #234) est la mesure qui
justifie l'appel ; SEC-003 est la règle d'audit qui exige cette
justification en ligne. Aucune autre occurrence du même amalgame (slash
entre le nom de fonction et le code de règle) trouvée dans les
commentaires en ligne, docstrings ou docs — les mentions restantes de
SEC-003 (`main.py`, `src/rummikub/ui/application.py`,
`src/rummikub/actualise.py`, `tests/test_actualise_securite.py`) la citent
déjà séparément de la fonction de validation. `CHANGELOG.md` (historique)
non modifié.

## 2. Protection des deux tests d'existence dans `main.py`

- `_lancer_actualise_ui_si_flag` (test d'existence du flag) et
  `_lancer_actualise_au_demarrage` (test d'existence du chemin fixe
  d'Actualise) : le `if not <chemin>.exists(): return` est désormais
  entouré d'un `try/except OSError: return` (`PermissionError` est une
  sous-classe d'`OSError`, non capturée par `Path.exists()` lui-même).
  Docstrings mises à jour en conséquence.

## 3. Tests ajoutés (`tests/test_actualise_flag_lancement.py`)

- `test_main_drapeau_permission_denied_ne_plante_pas_et_ne_lance_rien` :
  simule une `PermissionError` sur `Path.exists()` restreinte au nom du
  fichier flag (`monkeypatch.setattr(Path, "exists", ...)`), vérifie
  qu'aucune exception n'est levée et qu'aucun `subprocess.Popen` n'est
  appelé.
- `test_main_actualise_au_demarrage_permission_denied_ne_plante_pas` :
  même principe pour le chemin fixe `C:\Actualise\Actualise.exe`.

Les deux simulations sont indépendantes des droits réels du système
(patch ciblé sur `Path.exists`), donc valables sous Linux comme sous
Windows.

## Vérifications

- `pytest tests/test_actualise_flag_lancement.py` : 13 passés (11 existants
  + 2 nouveaux).
- `pytest` (suite complète) : 545 passés, 13 sautés, 0 échec — aucune
  régression.
- `ruff check --select S main.py src/rummikub/ui/application.py
  src/rummikub/actualise.py` : 2 avertissements `S603` préexistants
  (lancements `subprocess.Popen` dans `main.py`/`ui/application.py`),
  inchangés par cette tâche — non touchés car la justification en ligne de
  ces appels relève de #265 (voir point de vigilance).

## Point de vigilance — décalage avec l'issue #265

Cette tâche est décrite comme la suite de #265, qui aurait déjà : justifié
en ligne les deux `subprocess.Popen` validés par `valider_chemin_actualise`
(suppression des 2 avertissements `S603`), et protégé `Path.exists()` du
flag dans le gestionnaire de fermeture (`_handler_fermeture_actualise`,
`src/rummikub/ui/application.py`) contre une `PermissionError`. Au moment
du traitement de #266, le commit de #265 (`f7f36f7`) existe dans une
worktree séparée (`worktree-issue-265`) mais n'est **pas** un ancêtre de la
branche `worktree-issue-266` (créée depuis `master` avant la fusion de
#265) : ni la justification en ligne des deux `subprocess`, ni la
protection du gestionnaire de fermeture ne sont présentes ici.

Pour rester strictement dans le périmètre de #266 (« protéger ces deux
tests d'existence dans `main.py` »), `src/rummikub/ui/application.py` n'a
donc **pas** été modifié par cette tâche : son `_flag.exists()` reste non
protégé dans cette worktree précise. Le paragraphe de
`docs/contexte/linter_securite.md` a été corrigé directement sur sa version
actuelle (celle d'avant #265, qui ne contient pas encore la clause
« traité comme faux positif acquis »), et non sur le texte réécrit par
#265 qui n'existe pas ici — la formulation produite reste correcte par
rapport à l'état réel du code de cette worktree (les deux `subprocess`
restent « à juger au cas par cas », ce qui est toujours vrai ici).

**À surveiller lors de la fusion** : les deux worktrees (#265 et #266)
modifient des lignes voisines de `main.py` et du même paragraphe de
`docs/contexte/linter_securite.md` — un conflit de fusion est probable et
devra être résolu par Alain en gardant les deux apports (justification en
ligne de #265 + libellé et protection `main.py` de #266). Non traité ici
(hors périmètre d'un agent CCL : pas de fusion inter-worktrees).
