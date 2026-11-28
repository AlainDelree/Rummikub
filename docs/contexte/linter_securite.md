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

`S101` (assert) et `S108` (chemin `/tmp` en dur) dans `tests/` : convention
pytest standard, hors périmètre de ce nettoyage (laissés tels quels).

## État actuel de la configuration ruff (issue #280)

Le dépôt **n'a aucun fichier de configuration ruff** (pas de `pyproject.toml`,
`ruff.toml` ni `setup.cfg` avec section ruff). `ruff check` (sans option)
tourne donc avec la sélection par défaut de l'installation locale, qui
n'inclut PAS les règles `S` (sécurité) — c'est pourquoi les 17 `noqa`
`S311`/`S603`/`S607` ci-dessus sont signalés `RUF100` (noqa inutile) sous
cette sélection par défaut, alors qu'ils restent nécessaires au crochet
pre-push (`ruff --select S main.py src`, qui écrase la sélection par défaut).

Testé en copie jetable (issue #280) : activer `S` par défaut (`extend-select
= ["S"]`) avec un unique `per-file-ignores` sur `tests/* = ["S101"]` (seule
exception de config autorisée) ferait passer les 17 `noqa` de `RUF100` à
0, SAUF un : `scripts/tournoi_niveaux.py` ligne 592 porte un `# noqa: S603`
réellement inutile (S603 ne s'y déclenche pas) — non retiré ici, décision
laissée à Alain. Coût mesuré sur le reste du dépôt : seulement 3 nouvelles
remarques S (2 `S603` à `scripts/construire_deb.py` lignes 59/160, 1 `S108`
à `tests/test_coups_rates_filtre_date.py` ligne 16), le `per-file-ignores`
éliminant la grosse masse de `S101` dans les tests. Le crochet pre-push
reste valide dans les deux cas ; son périmètre (`main.py src`) ne couvre
de toute façon que 7 des 17 emplacements (les 10 autres sont dans
`scripts/`/`tests/`, hors périmètre du crochet, indépendamment de ce test).
Aucune configuration ruff n'a été créée dans le dépôt (il n'en existait
aucune avant) : la décision de créer un `pyproject.toml`/`ruff.toml` avec ce
contenu reste à prendre par Alain.
