# Rapport — Expert : la recherche remplacée par une résolution exacte légère (HiGHS) (issue #206, suite de #204)

> La recherche arborescente d'Expert (`moteur/solveur.py`) est remplacée par un
> **modèle exact maison** (programmation linéaire en nombres entiers, den Hertog
> & Hulshof 2006), appelant **HiGHS** (`highspy`, MIT) + `numpy` (BSD) en
> direct, **sans** `cvxpy` ni `scipy` (la « voie (b) » recommandée par le
> rapport de #204). La recherche de #186 est **conservée telle quelle comme
> repli** ; Avancé et les niveaux inférieurs ne changent pas.

## 1. Ce qui change

- **Nouveau** : `src/rummikub/moteur/solveur_exact.py` (modèle ILP + HiGHS,
  reconstruction + revalidation `valider_combinaison` + contrôle de
  conservation), branché dans `moteur/ia.py::jouer_niveau_expert`.
- **Repli, sans jamais bloquer ni lever** : import `highspy`/`numpy` impossible,
  budget dépassé sans solution, résultat non valide ou erreur → recherche
  `solveur.py` (inchangée) puis Avancé. Quand le modèle exact PROUVE qu'aucune
  tuile n'est posable, Expert passe directement à Avancé (pioche/passe) sans
  relancer la recherche incomplète.
- **Dépendances** : `highspy>=1.7,<2`, `numpy>=1.26,<3` dans `requirements.txt`.
- **Licences** : `THIRD_PARTY_LICENSES.txt` (MIT HiGHS + BSD numpy), distribué.

## 2. Exactitude — optimum atteint sur 10/10 cas (écart nul)

`mesures_206/ecart_zero_exact.txt` (budget de production 1,5 s) :

| cas | attendu_exact | modèle exact | écart | durée |
|-----|:---:|:---:|:---:|---:|
| cas_expert_bruno_tour57 | 4 | 4 | +0 | 324 ms |
| cas_expert_budget_tour81 | 3 | 3 | +0 | 810 ms |
| cas_expert_coup_simple_david_tour31 | 1 | 1 | +0 | 57 ms |
| cas_expert_humain_…172338_tour66 | 7 | 7 | +0 | 916 ms |
| cas_expert_humain_…174101_tour81 | 3 | 3 | +0 | 790 ms |
| cas_expert_humain_…213723_tour65 | 3 | 3 | +0 | 190 ms |
| cas_expert_ia_…172338_tour37 | 6 | 6 | +0 | 22 ms |
| cas_expert_ia_…172338_tour59 | 7 | 7 | +0 | 232 ms |
| cas_expert_ia_…172338_tour61 | 4 | 4 | +0 | 164 ms |
| **reference_victoire_manquee_ines_tour85** | 2 | 2 | +0 | 560 ms |

- **Écarts non nuls avec l'optimum : 0 / 10.** Durée **moyenne 406 ms, maximale
  916 ms** (budget 1 500 ms — marge confortable).
- Les deux cas que l'ancienne recherche ratait même à 10-30 s sont désormais
  résolus : **Bruno tour 57** (4 tuiles, pose `rouge_12` en scindant la suite
  rouge) et **Ines tour 85** (victoire immédiate de 2 tuiles).
- Rappel de l'ancienne recherche (rapport #204) : sous l'optimum sur **5/10**
  cas à 1,5 s. `scripts/comparer_solveur_exact.py` (ancienne recherche vs
  bibliothèque) reste dans `mesures_206/campagne.txt` pour trace.

## 3. Campagne Avancé vs Expert — 20 donnes × 2 (miroir), graine 206

Sorties complètes : `mesures_206/campagne.txt` (avant + `comparer_solveur_exact`)
et `mesures_206/apres_corrige.txt` (après). 40 matchs d'1 manche.

| grandeur | AVANT (recherche `solveur.py`) | APRÈS (modèle exact HiGHS) |
|----------|:---:|:---:|
| Victoires Expert | **38/40 (95,0 % ± 6,8 pt)** | **39/40 (97,5 % ± 4,8 pt)** |
| Score cumulé moyen d'Expert | +29,7 | +30,8 |
| Parties bloquées (pioche épuisée / garde-fou) | 0 / 0 | 0 / 0 |
| Anomalies de conservation (#187, attendu 0) | **0** | **0** |
| Temps / tour d'Expert — moyen | 283,6 ms | **75,4 ms** |
| Temps / tour d'Expert — maximal | 1677 ms | **1522 ms** |
| Replis d'Expert — total | 818/1407 (58,1 %) | **0/1378 (0,0 %)** |
| …dont faute de budget (sans solution) | 6 (0,4 %) | **0** |
| …dont coup légitimement impossible | 812 | 0 *(voir note)* |
| Perturbation moyenne (tuiles déplacées / combos modifiées) | 2,26 / 2,03 | **1,95 / 1,84** |

**Lecture.** Expert domine Avancé dans les deux versions (Avancé est un
adversaire bien plus faible que l'une ou l'autre version d'Expert) : le
taux de victoire sur Avancé ne mesure donc pas finement le gain. Le gain réel
est ailleurs, et net :

- **Coups qui n'étaient plus ratés** : les 5/10 cas de référence sous l'optimum
  à 1,5 s (dont 2 insolubles même à 30 s) sont tous résolus (§2) — dont des
  **victoires immédiates** (Ines tour 85) invisibles dans une campagne contre
  un adversaire aussi faible.
- **Temps par tour divisé par ~3,8 en moyenne** (283 → 75 ms) et maximum
  ramené sous le budget ; **plus aucun repli** (le modèle exact ne dépasse
  jamais son budget sur ces parties ; les anciens 58 % de « replis » étaient en
  quasi-totalité des tours sans coup possible — Expert piochait).
- **Perturbation du plateau moindre** (coups plus simples).

*Note sur les replis :* depuis #206, `on_repli` ne compte que les **échecs** du
modèle exact (dépendance absente, budget dépassé, erreur) — 0 ici. Les tours où
aucune tuile n'est posable ne sont plus des « replis » : Expert passe
directement à Avancé pour décider pioche/passe, sans relancer la recherche
incomplète (c'est ce qui divise aussi le temps moyen).

## 4. Démarrage et poids ajoutés (mesuré ici, Linux)

| grandeur | avant | après | ajout |
|----------|------:|------:|------:|
| import du moteur (`rummikub.moteur.ia`) | 32 ms | 97 ms | **+65 ms** |
| dont `numpy` | — | ~69 ms | |
| dont `highspy` | — | ~10 ms | |
| dont énumération des ensembles (1 fois) | — | ~29 ms | |
| empreinte disque `highspy` | — | 12 Mo | |
| empreinte disque `numpy` | — | 43 Mo | **~+55 Mo** |

Conforme à l'estimation « voie (b) » du rapport de #204 (~+55 Mo, ~3× plus
léger que la voie (a) cvxpy/scipy à ~+150-200 Mo et ~+0,8 s). Les chiffres
Windows (roues, bundle PyInstaller) sont à confirmer par CCW (§6).

## 5. Tests

- **`tests/test_solveur_exact_maison.py`** : optimum exact sur tous les cas
  (6a) ; accord avec la recherche exhaustive indépendante `verif_solveur` sur
  250 positions aléatoires graine fixe — jamais sous l'optimum, toujours
  valide/conservé (6b) ; accord **exact** avec la bibliothèque `rummikub-solver`
  quand installée, sinon sauté (6c) ; replis highspy absent / budget nul (6d) ;
  mise initiale et critères de départage (6e).
- **`tests/conftest.py`** : calibration `facteur_machine` (micro-benchmark CPU)
  appliquée aux budgets des tests de la **recherche conservée comme repli** dont
  le résultat dépend de la vitesse de la machine — point 8 de #204 enfin traité.
  **Aucun de ces tests n'est supprimé ni allégé** ; seuls leurs budgets sont mis
  à l'échelle (facteur ≥ 1 ; sur la machine de référence il vaut ≈ 1, budgets
  inchangés).

  **Tests de la recherche de repli dépendant du temps de calcul** (désormais
  calibrés) :
  - `test_solveur_plateau_charge_trouve_au_moins_trois_tuiles_avec_gros_budget`
  - `test_solveur_plateau_charge_trouve_un_coup_avec_budget_de_production`
  - `test_solveur_cascade_joker_trouve_trois_tuiles_avec_gros_budget`
  - `test_solveur_cascade_joker_trouve_un_coup_avec_budget_de_production`
  - `test_solveur_coup_simple_trouve_et_retient_le_coup_sans_perturbation`
  - `test_preferer_simple_ne_pose_jamais_moins_de_tuiles_au_budget_de_production`
  - `test_preferer_simple_atteint_le_meme_plafond_sur_le_cas_le_plus_dur`

  (`test_expert_se_replie_sur_avance_si_budget_depasse` utilise un budget NUL :
  il teste le repli, pas la vitesse — non calibré.)
- Suite complète : **257 tests passent** hors Playwright (avec highspy/numpy) ;
  sans les dépendances, les tests du modèle exact se sautent proprement et les
  5 tests de repli passent.

## 6. À vérifier sous Windows (CCW) — aucun build lancé ici

Le pipeline existant couvre déjà l'essentiel : `build/rebuild_rummikub.bat`
fait `pip install -r requirements.txt` (donc `highspy`+`numpy`), `rummikub.spec`
collecte explicitement `highspy` (sous-modules + bibliothèques natives) et
distribue `THIRD_PARTY_LICENSES.txt` à la racine de `dist\Rummikub\`, et
`installeur\rummikub.iss` copie tout `dist\Rummikub\*`. **À confirmer par CCW :**

1. `pip install -r requirements.txt` installe bien les roues Windows de
   `highspy` et `numpy` pour Python 3.12 (pas de compilation source).
2. Le bundle PyInstaller embarque la bibliothèque native de `highspy`
   (`highspy\_core*.pyd` et DLL éventuelles) — lancer `dist\Rummikub\Rummikub`
   et vérifier qu'une partie en **Expert** joue des coups (pas de repli
   systématique : si `highspy` manquait, Expert jouerait comme Avancé).
   Au besoin, la ligne `collect_dynamic_libs("highspy")` du `.spec` est le point
   à ajuster (hidden import `highspy._core`).
3. `THIRD_PARTY_LICENSES.txt` présent dans `dist\Rummikub\` et dans l'installeur.
4. Mesurer le **poids réel ajouté** à `dist\Rummikub\` et le **surcroît de
   démarrage** sous Windows (l'estimation Linux est ~+55 Mo / ~+65 ms).
5. Mettre à jour `BUILD_WINDOWS_CCW.md` (dépôt bridge_agent, **hors du
   périmètre de cette issue** — non modifié ici) avec ces points.

## 7. Commandes à lancer par Alain (journaux de parties réelles)

Les journaux ne sont pas dans le dossier de travail de l'agent. Pour juger
Expert sur de vraies parties avec le solveur exact :

```
# Comparaison sur les décisions d'IA de vrais journaux (bibliothèque de #204) :
.venv-solveur-exact/bin/python scripts/comparer_solveur_exact.py --journaux --tous

# Coups ratés jugés par le solveur exact :
python scripts/analyser_coups_rates.py --juge-exact

# Campagne avant / après reproductible :
.venv-exact/bin/python scripts/comparer_niveaux_ia.py --niveau-a "Avancé" --niveau-b Expert --donnes 20 --seed 206            # après
.venv-exact/bin/python scripts/comparer_niveaux_ia.py --niveau-a "Avancé" --niveau-b Expert --donnes 20 --seed 206 --sans-exact  # avant
```
