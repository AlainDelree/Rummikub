# CONTEXTE — Projet Rummikub

> Fichier injecté automatiquement (4000 premiers caractères) dans le prompt
> de chaque issue CCL. Tenir l'état actuel et les règles, jamais l'historique
> (détail et récits : fichiers de domaine ci-dessous, CHANGELOG.md).

## Règles impératives

- **Jamais de `git push`** : CCL committe en local, Alain vérifie et pousse.
- **Commit de sauvegarde `--allow-empty` AVANT** toute modification.
- **Vérification front-end** (`jeu.js/html/css`, `accueil.js/html/css`...) :
  **ne jamais lancer l'application pywebview réelle** ni un navigateur piloté
  sur l'app réelle (bloque en headless, dépassement de TIMEOUT). Toujours
  **Playwright** sur le fichier HTML concerné + **mock de
  `window.pywebview.api`** (état réaliste construit via le moteur réel si
  besoin) — détail : `tests_frontend.md`.

## Architecture résumée

Python 3.12, pywebview (fenêtre native, navigation par `load_url`, API JS via
`js_api`), PyInstaller onedir (`rummikub.spec`), SQLite (`sqlite3`), portable
Linux/Windows (`pathlib.Path`). `src/rummikub/moteur/` = logique pure (tuiles,
validation, partie, score, ia, niveaux, solveur, solveur_exact,
description_coup) ; `persistance/` = SQLite + journal/bilan/coups_rates ;
`ui/` = application pywebview + API + front `ui/web/`.

## Conventions clés

- État de partie = **dict JSON-sérialisable**, jamais d'objets Python stockés.
- **Le plateau ne perd jamais de tuile** (#187) — contrôlé dans `jouer_tour`.
- Chemins toujours via `pathlib.Path`.
- Suppressions de sécurité du linter (`ruff --select S`) : corriger plutôt que
  supprimer, sinon `noqa`/`nosec` précis + raison en clair sur deux lignes —
  voir `linter_securite.md`.

## Index des fichiers de domaine (`docs/contexte/`)

- `architecture.md` — stack + structure détaillée : avant une modif touchant
  plusieurs modules.
- `moteur_regles.md` — moteur de jeu, manches multiples, conventions d'état :
  avant de toucher `moteur/partie.py`, `score.py`, l'état de partie.
- `tests_frontend.md` — suite de tests + méthode Playwright/mock : avant tout
  test ou vérification front-end.
- `joker_tactiques.md` — tactiques de récupération de joker (niveau Avancé) :
  avant de modifier `ia.py` côté Avancé.
- `solveur_expert.md` — solveur de réarrangement global (niveau Expert) :
  avant de toucher `solveur.py` ou le comportement d'Expert.
- `solveur_verification_exacte.md` — solveur exact, vérif croisée bibliothèque,
  limites de volume de calcul : avant de toucher `solveur_exact.py` ou son
  budget/ses limites.
- `ia_anti_don_joker.md` — règle anti-don de joker (Intermédiaire/Avancé/
  Expert) : avant de toucher cette règle ou de lancer une campagne de mesure.
- `coups_rates_bilan.md` — journal, bilan par niveau, détection des coups
  ratés de l'IA : avant de toucher `journal.py`, `bilan.py`, `coups_rates.py`.
- `description_coup.md` — résumé écrit + pas-à-pas d'un coup de l'IA : avant
  de toucher `description_coup.py` ou l'écran pas-à-pas.
- `scripts_simulation.md` — scripts de simulation IA vs IA : avant de lancer
  ou modifier `scripts/simulation_ia.py`/`comparer_niveaux_ia.py`.
- `niveaux_ia_calibrage.md` — échelle des 5 niveaux d'IA et calibrage : avant
  de toucher `niveaux.py` ou de relancer une campagne de calibrage.
- `pistes_amelioration_ia.md` — pistes d'amélioration de l'IA à tester (dont
  recherche multi-tours) : avant de proposer une nouvelle piste IA.
- `paquet_linux.md` — paquet `.deb` Ubuntu LTS, chemins de données en mode
  gelé Linux : avant de toucher `scripts/construire_deb.py` ou `config.py`
  côté Linux.
- `linter_securite.md` — traitement des avertissements `ruff --select S` :
  avant de supprimer un avertissement de sécurité du linter.
