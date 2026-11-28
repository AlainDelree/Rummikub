# Linter — sécurité (règles `S`/bandit, issue #248)

> À lire avant de traiter un avertissement de sécurité du linter (famille
> `ruff --select S`, codes bandit `Bxxx` correspondants).

## Principe

**Corriger plutôt que supprimer** quand c'est possible sans changement de
comportement :
- `try/except/pass` → `with contextlib.suppress(<exception>): ...` (mêmes
  exceptions captées, juste la forme).
- `urlopen` : vérifier que l'adresse commence par `https://` avant l'appel,
  plutôt que suppression aveugle.

## Suppression en ligne (faux positif restant)

Toujours DEUX lignes, jamais un `noqa` ou `nosec` seul :

```python
# raison en clair, par exemple URL constante en https, jamais saisie par l'utilisateur
x = urllib.request.urlopen(URL, timeout=15)  # noqa: S310  # nosec B310
```

Codes bandit/ruff déjà traités comme faux positifs jugés dans Rummikub :
- `S603`/`S607` (↔ `B603`/`B607`) : `subprocess` à arguments fixes ou
  contrôlés par le script appelant (scripts de mesure, `taskkill` par PID).
- `S311` (↔ `B311`) : aléa de jeu (mélange du sac, tirage de l'oubli des
  niveaux, nom aléatoire d'IA, graines de simulation) — sans enjeu crypto.

Un `subprocess` dont un argument provient d'un fichier externe validé par
`valider_chemin_actualise` (issue #234 : existence, extension `.bat`/`.exe`,
racine Actualise autorisée) est traité comme faux positif acquis et justifié
en ligne (`main.py`, `ui/application.py`, les trois lancements d'Actualise) :
cas jugé, pas laissé signalé. La validation des chemins est la mesure qui
justifie l'appel ; SEC-003 est la règle d'audit qui exige cette justification
en ligne.

`S101` (assert) dans `tests/` : convention pytest standard, ignoré par
configuration (voir ci-dessous) — pas une suppression en ligne au cas par
cas.

## État actuel de la configuration ruff (issue #281)

Le dépôt a désormais un `ruff.toml` à la racine :

```toml
[lint]
extend-select = ["S"]

[lint.per-file-ignores]
"tests/*" = ["S101"]
```

`ruff check` (sans option) tourne donc avec les règles `S` (sécurité)
activées en plus de la sélection par défaut, et ignore `S101` (assert) dans
`tests/`. Le crochet pre-push (`ruff --select S main.py src`) reste valide
avec cette configuration (il écrasait déjà la sélection par défaut, donc le
comportement ne change pas pour lui).

Avec cette configuration, les 17 anciens `noqa` `S311`/`S603`/`S607` ne sont
plus signalés `RUF100` : les deux restés nécessaires (`S311`, `S607`) sont
désormais réellement couverts par la sélection par défaut, et le `noqa:
S603` mort de `scripts/tournoi_niveaux.py` ligne 592 a été retiré (le
`S607` du même appel, lui, reste utile et est conservé).

Les 3 remarques `S` qui apparaissaient sous cette configuration ont été
traitées :
- `scripts/construire_deb.py` lignes 59/160 (deux appels `subprocess`,
  `S603`) : même traitement que les cas déjà jugés ci-dessus (arguments
  fixes du script ou fournis par lui-même, aucune saisie utilisateur) —
  raison en clair en commentaire + `noqa: S603  # nosec B603`.
- `tests/test_coups_rates_filtre_date.py` ligne 16 (`S108`, chemin `/tmp`
  en dur) : corrigé plutôt que supprimé — remplacé par la fixture pytest
  `tmp_path`, sans changer les vérifications ni ce que les tests testent
  (ils ne lisent que les noms de fichiers).

`ruff check .` : 0 `RUF100`, 0 remarque `S`. Les autres familles
(`BLE001`, `PLW1510`, `F841`, `RUF013`, `EXE001`, etc., inventaire #280)
sont hors périmètre de cette issue et inchangées.
