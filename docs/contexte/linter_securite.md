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

Un `subprocess` dont un argument provient d'un fichier externe (même validé
par `valider_chemin_actualise`, issue #234 — la mesure qui justifie l'appel,
pas la règle elle-même ; SEC-003 est la règle d'audit qui exige que ces
appels soient justifiés en ligne — ex. dans `main.py`/`ui/application.py`)
n'est **pas** traité comme faux positif acquis : à juger au cas par cas,
laissé signalé plutôt que supprimé.

`S101` (assert) et `S108` (chemin `/tmp` en dur) dans `tests/` : convention
pytest standard, hors périmètre de ce nettoyage (laissés tels quels).
