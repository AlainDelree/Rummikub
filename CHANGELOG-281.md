## Issue #281 — Ruff : activer les règles S par une configuration, retirer le noqa S603 mort, traiter les 3 remarques S restantes

Suite directe de #280 : création de `ruff.toml` (`extend-select = ["S"]` +
`per-file-ignores` `tests/* = ["S101"]`, rien d'autre), ce qui fait passer
les 17 `RUF100` restants de #280 à 0 (le `noqa: S603` mort de
`scripts/tournoi_niveaux.py` ligne 592 a été retiré, `S607` conservé).

Les 3 remarques `S` révélées par l'activation ont été traitées :
- `scripts/construire_deb.py` lignes 59 et ~160 : deux appels `subprocess`
  justifiés en ligne (`noqa: S603  # nosec B603` + raison en clair),
  arguments fixes ou fournis par le script lui-même.
- `tests/test_coups_rates_filtre_date.py` ligne 16 : chemin `/tmp` en dur
  remplacé par la fixture pytest `tmp_path` (seule l'origine du dossier
  change, pas les vérifications).

`docs/contexte/linter_securite.md` mis à jour pour décrire cet état
(configuration créée, S101 ignoré par config dans les tests, les 3
remarques traitées, noqa mort retiré). Aucun changement de comportement
du jeu, du moteur ou de l'IA. `CONTEXTE.md` inchangé (aucune règle qui y
figure n'est devenue fausse).

`ruff check .` : 188 → 171 (exactement les 17 `RUF100` résorbés, aucune
autre famille touchée) ; `RUF100` et `S` à 0. Crochet pre-push
(`ruff check --select S main.py src`) toujours « All checks passed! ».
Tests : 597 passés avant comme après (un test sensible à la charge,
`test_coup_inchange_avec_budget_confortable_intermediaire`, a échoué une
première fois sous charge puis passé en isolation — flakiness déjà
documentée, pas de régression).
