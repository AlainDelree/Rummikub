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
