# Rapport — Vérification du solveur d'Expert par un solveur exact indépendant (issue #204, suite de #201)

> Mesure **indépendante** et **exacte** de ce que le solveur d'Expert
> (`moteur/solveur.py`) rate, à l'aide de la bibliothèque libre
> `rummikub-solver` (PyPI, licence MIT), qui implémente la programmation
> linéaire en nombres entiers de den Hertog & Hulshof (*The Computer
> Journal*, 2006). **Aucune modification du solveur d'Expert, du jeu livré ni
> des niveaux d'IA.** La bibliothèque est une dépendance de **développement
> seulement** (voir CONTEXTE.md §14).

Tous les chiffres ci-dessous sont reproductibles :

```
python -m venv .venv-solveur-exact
.venv-solveur-exact/bin/pip install 'rummikub-solver[highs]' pytest
.venv-solveur-exact/bin/python scripts/comparer_solveur_exact.py
.venv-solveur-exact/bin/python -m pytest tests/test_solveur_exact.py
```

---

## 1. Réponse chiffrée : « peut-on remplacer le solveur d'Expert par un solveur exact rapide et embarquable ? »

**Oui pour « rapide et exact », à qualifier pour « embarquable ».**

- **Exactitude et vitesse — sans ambiguïté : le solveur exact trouve le
  maximum du tour nettement plus vite que le nôtre.** Sur les 10 cas de
  référence, il calcule l'**optimum prouvé** en **≈ 84 ms/cas en moyenne**
  (max ≈ 145 ms), là où notre solveur, même avec un budget généreux de 10 s,
  **reste strictement en dessous sur 2 cas** (Bruno tour 57 : 3 vs 4 ; Ines
  tour 85 : 1 vs 2) et met **~2 à 5 s** pour atteindre certains maxima qu'il
  finit par trouver (tours 59/61). Au budget de **production (1,5 s)**, notre
  solveur rate des tuiles sur **5 des 10 cas**.
- **Embarquable — c'est la seule vraie question.** La bibliothèque telle
  quelle tire `cvxpy-base` → `scipy` (+ `sparsediffpy`, `qdldl`), soit un
  poids et un temps de démarrage importants (§4–5). Une **voie (b)** —
  réimplémenter la même méthode ILP en appelant **directement `highspy`**,
  sans `cvxpy` ni `scipy` — est nettement plus légère et reste MIT (§5).

Décision à prendre par Alain (hors périmètre de cette issue, qui ne modifie
pas le build) : si Expert doit un jour viser l'optimum exact, la voie (b) est
recommandée ; la voie (a) sert déjà, dès aujourd'hui, d'**oracle de
vérification** hors production.

---

## 2. Répartition des écarts et durées sur les cas de référence

Sortie de `scripts/comparer_solveur_exact.py` (backend HiGHS) :

| cas | `attendu_min` | **exact** | notre 1,5 s | notre 10 s | écart (exact − 1,5 s) | durée exact |
|-----|:---:|:---:|:---:|:---:|:---:|---:|
| cas_expert_bruno_tour57 | 3 | **4** | 3 | 3 | **+1** | 55 ms |
| cas_expert_budget_tour81 (Olivia) | — | 3 | 3 | 3 | +0 | 144 ms |
| cas_expert_coup_simple_david_tour31 | 1 | 1 | 1 | 1 | +0 | 19 ms |
| cas_expert_humain_…172338_tour66 | 7 | 7 | 6 | 7 | +1 | 130 ms |
| cas_expert_humain_…174101_tour81 | 3 | 3 | 3 | 3 | +0 | 146 ms |
| cas_expert_humain_…213723_tour65 | 3 | 3 | 3 | 3 | +0 | 125 ms |
| cas_expert_ia_…172338_tour37 (Gaëlle) | 6 | 6 | 6 | 6 | +0 | 23 ms |
| cas_expert_ia_…172338_tour59 | 7 | 7 | 6 | 7 | +1 | 66 ms |
| cas_expert_ia_…172338_tour61 | 4 | 4 | 1 | 4 | **+3** | 55 ms |
| **reference_victoire_manquee_ines_tour85** | 2 | **2** | 1 | 1 | **+1** | 79 ms |

**Synthèse :**
- Cas où notre solveur rate des tuiles à **1,5 s** : **5 / 10**.
- Écart (exact − notre solveur à 1,5 s) : **moyen 0,70**, **maximal 3**.
- Temps **total** du solveur exact : **~842 ms** pour les 10 cas (~84 ms/cas).
- **Les deux contrôles indépendants de l'adaptateur passent sur tous les
  cas** : chaque combinaison proposée est valide selon `valider_combinaison`,
  et aucune tuile du plateau n'est perdue (conservation vérifiée).

**Les deux cas où notre solveur reste battu même à 10 s** (donc une faiblesse
d'**algorithme**, pas de budget) : **Bruno tour 57** (3 vs 4, voir §3) et
**Ines tour 85** (1 vs 2). Ce dernier est désormais le **test de
non-régression** de la suite (`tests/test_solveur_exact.py::
test_non_regression_victoire_manquee_ines`) : une IA Expert avec 2 tuiles en
main n'en a posé qu'une — **victoire immédiate manquée** que le solveur exact
voit.

Les tours 59/61 illustrent l'autre limite (budget) : notre solveur **trouve**
l'optimum, mais seulement avec 10 s (tour 61 : 1 tuile à 1,5 s, 4 à 10 s),
quand l'exact le prouve en ~55–66 ms.

---

## 3. Cas de Bruno tour 57 — quelle tuile supplémentaire, et pourquoi notre solveur la rate

- **Main de Bruno** : rouge 1, jaune 13, rouge 12, jaune 8, rouge 11.
- **Notre solveur (3 tuiles, même à 20/30 s)** : pose jaune 8, jaune 13, rouge 11.
- **Solveur exact (4 tuiles)** : pose **jaune 8, jaune 13, rouge 11 ET
  rouge 12**. La **tuile supplémentaire est `rouge_12`**.

**Comment l'exact atteint 4 :** il **scinde la suite rouge 6–7–8–9–10** du
plateau en **rouge 6–7–8** (toujours valide) + **rouge 9–10–11–12**, en
ajoutant rouge 11 **et** rouge 12 de la main sur la partie haute fraîchement
détachée — tout en plaçant jaune 8 (extension de la suite jaune 6–9) et
jaune 13 (groupe des 13) dans deux autres zones du plateau.

**Pourquoi notre solveur ne la trouve pas :** la 4ᵉ tuile n'exige pas plus de
temps (il reste à 3 même à **30 s**), mais une **recombinaison multi-zones**
que sa recherche **bornée** ne parvient pas à prouver : poser rouge 12
suppose de prouver simultanément la scission de la suite rouge **et** les deux
placements jaune, alors que la recherche procède par paliers et renvoie le
dernier palier **prouvé** (3). C'est exactement la limite de « borne basse »
que l'issue cherchait à quantifier : le solveur maison est juge et partie, et
ce coup lui échappe. Le solveur exact, lui, le trouve en **55 ms**.

---

## 4. Taille d'installation et démarrage

**Tailles de roues Windows (téléchargement, chiffres de l'issue + PyPI) :**

| paquet | licence | roue Windows (≈) |
|--------|---------|-----:|
| `rummikub-solver` | MIT | ~20 Ko |
| `scipy` | BSD-3 | ~37 Mo |
| `numpy` | BSD-3 | ~13 Mo |
| `highspy` | MIT | ~3 Mo |
| `cvxpy-base` | Apache-2.0 | ~1 Mo (+ `sparsediffpy` ~12 Mo, `qdldl` ~1,5 Mo en 1.9.x) |

**Empreinte réellement installée mesurée (Linux, décompressée, ce worktree) :**

| paquet | installé |
|--------|-----:|
| `scipy` | **109 Mo** |
| `numpy` | 43 Mo |
| `cvxpy` (base) | 13 Mo |
| `highspy` | 12 Mo |
| `qdldl` | ~5,4 Mo |
| `sparsediffpy` | ~0,6 Mo |
| `rummikub_solver` | ~0,14 Mo |
| **Total site-packages** | **~316 Mo** |

> La taille **décompressée** (ce qui compte pour un bundle PyInstaller onedir)
> est bien supérieure aux roues : `scipy` seul pèse ~109 Mo installé. Les
> chiffres de roue de l'issue sous-estiment donc le poids final dans
> `dist/Rummikub/`. Une passe d'`--exclude`/strip PyInstaller réduirait une
> partie de `scipy`/`numpy` (tests, en-têtes), mais l'ordre de grandeur reste
> de plusieurs dizaines de Mo.

**Démarrage (temps d'import, ce worktree) :**

| import | durée |
|--------|-----:|
| `highspy` | ~98 ms |
| `rummikub_solver` | ~121 ms (sans forcer cvxpy) |
| **`cvxpy`** | **~826 ms** |

Le poste dominant est **`cvxpy` (~0,8 s au premier import)**, qui s'ajoute au
démarrage de l'application à chaque lancement si on embarque la voie (a).

---

## 5. Deux voies pour un éventuel embarquement (comparaison)

### Voie (a) — la bibliothèque `rummikub-solver` telle quelle

- **Dépendances tirées** : `cvxpy-base` → `scipy` + `numpy` (+ `sparsediffpy`,
  `qdldl`). `highspy` en extra `highs`.
- **Poids estimé dans le bundle** : **~+150 à 200 Mo** décompressés
  (scipy+numpy dominent), avant tout strip.
- **Démarrage** : **+~0,8 s** (import `cvxpy`).
- **Difficulté de mise en œuvre** : **faible** (déjà fait, API propre,
  `RuleSet(numbers=13, repeats=2, colours=4, jokers=2, min_len=3,
  min_initial_value=30)` correspond exactement à notre jeu).
- **Verdict** : parfait comme **oracle de vérification hors production** (ce
  que fait cette issue). Trop lourd pour le bundle sans justification forte.

### Voie (b) — modèle maison de la même méthode, appelant directement `highspy`

- **Principe** : réécrire le modèle ILP de den Hertog & Hulshof 2006
  (variables binaires « quelles tuiles poser » × « quels ensembles former »,
  contraintes de conservation) en construisant directement le problème pour
  **`highspy`** (solveur HiGHS, MIT), avec **`numpy`** seul — **sans `cvxpy`
  ni `scipy`**.
- **Poids estimé dans le bundle** : **~+55 Mo** décompressés
  (`highspy` ~12 Mo + `numpy` ~43 Mo), soit **~3× plus léger** que la voie (a),
  et **sans** le démarrage `cvxpy`.
- **Bonus** : on peut y **ajouter nos critères de départage** (simplicité du
  coup #199, économie de jokers, évaluation de la main) comme **objectifs
  secondaires** lexicographiques — chose que la bibliothèque n'expose pas.
- **Difficulté de mise en œuvre** : **moyenne** (il faut porter le modèle et
  la génération des ensembles valides ; la logique de `_ruleset.py` de la
  bibliothèque sert de référence, licence MIT compatible avec une
  réécriture). Un adaptateur de reconstruction/validation (remise dans
  l'ordre des suites, place des jokers) existe déjà :
  `scripts/solveur_exact.py` est directement réutilisable.
- **Verdict** : la voie à privilégier **si** on décide un jour de remplacer le
  solveur d'Expert par un solveur exact embarqué.

> Dans les deux cas, **le build Windows n'est pas modifié par cette issue** :
> ces estimations sont indicatives, à valider par un build réel avant toute
> décision.

---

## 6. Licences des dépendances et obligations

| paquet | licence | note |
|--------|---------|------|
| `rummikub-solver` | **MIT** | bibliothèque elle-même |
| `highspy` (HiGHS) | **MIT** | solveur recommandé (extra `highs`) |
| `numpy` | **BSD-3-Clause** | |
| `scipy` | **BSD-3-Clause** | tiré par `cvxpy-base` (voie a) |
| `cvxpy-base` | **Apache-2.0** | voie (a) uniquement |
| `qdldl`, `sparsediffpy` | BSD / permissive | tirés par `cvxpy-base` 1.9.x |

**Obligations si l'une de ces dépendances est distribuée** (voies a ou b) :
MIT/BSD/Apache-2.0 sont toutes permissives mais **exigent de conserver leurs
avis de copyright et de licence** dans ce qui est distribué — concrètement,
**un fichier « licences tierces »** (p. ex. `THIRD_PARTY_LICENSES.txt`) à
inclure dans l'installateur Windows, listant chaque paquet embarqué et son
texte de licence. Apache-2.0 demande en plus de signaler les modifications
éventuelles des fichiers concernés.

**⚠️ À éviter — extra GPL :** la bibliothèque propose un backend
**`glpk_mi` (GLPK, licence GPL-3.0)** via `cvxopt`. **Ne jamais l'installer
ni l'embarquer** : la GPL est incompatible avec une distribution propriétaire
du jeu. Nous utilisons exclusivement **`highs`** (MIT) ; `SCIPY` (BSD, bâti
sur HiGHS) est le repli automatique. L'adaptateur sélectionne HiGHS puis SciPy
et **n'active jamais** GLPK.

---

## 7. Livrables de cette issue (aucune modification du jeu livré)

- `scripts/solveur_exact.py` — **adaptateur** : conversion de nos états vers la
  bibliothèque (couleurs noir/bleu/jaune=orange/rouge, jokers), résolution
  exacte, reconstruction dans notre domaine (nombre de tuiles, combinaisons
  **remises dans l'ordre** avec place des jokers, durée), **vérifiées par
  `valider_combinaison` + conservation du plateau**. S'importe sans la
  bibliothèque (`DISPONIBLE=False`).
- `scripts/comparer_solveur_exact.py` — **script de comparaison** (cas de
  référence + option `--journaux` sur de vrais journaux).
- `scripts/analyser_coups_rates.py --juge-exact` — **juge exact** optionnel :
  plus aucune décision « inconclusive » ni coup manqué par gel de
  combinaisons (désactivé par défaut, signale clairement l'absence de la
  bibliothèque).
- `tests/donnees/*.json` — clé **`attendu_exact_tuiles`** ajoutée (maximum
  exact), `attendu_min_tuiles` conservée.
- `tests/test_solveur_exact.py` — tests, **sautés proprement** si la
  bibliothèque est absente (comme Playwright).
- `CONTEXTE.md` §13 — installation et usage documentés.
