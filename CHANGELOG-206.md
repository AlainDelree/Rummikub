# Issue #206 — Expert : la recherche du solveur remplacée par une résolution exacte légère (programmation linéaire en nombres entiers, HiGHS) (suite de #204)

La vérification de #204 (bibliothèque libre `rummikub-solver` comme oracle
exact) avait montré que la recherche arborescente d'Expert
(`moteur/solveur.py`) restait **sous l'optimum sur 5 cas réels sur 10** au
budget de jeu (1,5 s), dont **2 cas même à 30 s** (faiblesse d'algorithme, pas
de temps) : Bruno tour 57 (3 tuiles au lieu de 4) et Ines tour 85 (une
**victoire immédiate manquée**, 1 au lieu de 2). #206 remplace cette recherche
par un **modèle exact maison** qui trouve TOUJOURS le coup posant le plus de
tuiles, en une fraction de seconde, sans aucune bibliothèque lourde. Les
niveaux inférieurs (Débutant à Avancé) ne changent pas.

## Changements

- **Nouveau module `src/rummikub/moteur/solveur_exact.py`** : formule le coup
  d'un tour comme une **programmation linéaire en nombres entiers** (den Hertog
  & Hulshof, *The Computer Journal*, 2006), résolue par **HiGHS** via `highspy`
  (MIT) + `numpy` (BSD) — **sans** `cvxpy` ni `scipy` (la « voie (b) » du
  rapport de #204, ≈3× plus légère). Une variable entière `x_s ∈ {0,1,2}` par
  ensemble valide possible (suites de longueur 3 à 5, groupes de 3-4, jokers en
  remplacement ; ~1170 ensembles énumérés une seule fois), contrainte de
  conservation `t_i ≤ Σ a_{s,i} x_s ≤ t_i + r_i` par type de tuile (toutes les
  tuiles du plateau restent posées, jamais plus de tuiles qu'on n'en a). Toute
  solution est **remise dans l'ordre** (suites, jokers aux bons endroits) puis
  **revalidée par `valider_combinaison`**, et la **conservation du plateau** est
  contrôlée avant d'être renvoyée — un résultat qui échouerait n'est jamais
  joué.
- **Critères de départage** (lexicographiques, par passes successives figeant
  l'optimum entier de la précédente ; le nombre de tuiles posées reste TOUJOURS
  le premier critère) : (1) tuiles posées, (2) **perturbation minimale** du
  plateau (#199 : tuiles déplacées puis combinaisons modifiées, via des
  variables d'affectation `cover` — totalement unimodulaires, donc exactes),
  (3) points posés, (4) économie de jokers de la main. Le cas de David tour 31
  reste joué **en un seul geste** (extension d'un groupe, 0 tuile déplacée).
- **Mise initiale** : tant qu'elle n'est pas faite, le plateau est GELÉ
  (reconduit à l'identique), les ensembles ne sont formés que depuis la main,
  avec `Σ points_s x_s ≥ mise_initiale_min`. Contrairement à la bibliothèque de
  #204 (qui réarrangeait le plateau), le modèle maison respecte la règle (test
  dédié).
- **Reproductibilité & budget** : HiGHS en `threads=1`, `random_seed=0`, sortie
  muette, limite de temps ferme = `BUDGET_TEMPS_EXPERT` (1,5 s). Résultats
  reproductibles.
- **Branchement dans Expert** (`moteur/ia.py`) : `jouer_niveau_expert` utilise
  le modèle exact. **Repli, sans jamais lever ni bloquer le jeu** : absence de
  `highspy`/`numpy` (`SolveurExactIndisponible`), budget dépassé sans solution
  (`BudgetExactDepasse`) ou erreur → repli sur la recherche arborescente
  conservée telle quelle (`solveur.py`), puis sur Avancé. Nouveau drapeau
  `UTILISER_SOLVEUR_EXACT` / paramètre `utiliser_exact` pour comparer les deux
  versions. **Avancé et les niveaux inférieurs sont inchangés.**
- **Dépendances & distribution** : `highspy>=1.7,<2` et `numpy>=1.26,<3`
  ajoutés à `requirements.txt` (roues Python 3.12 / Windows) ; fichier
  **`THIRD_PARTY_LICENSES.txt`** créé (textes MIT de HiGHS et BSD de numpy) ;
  `rummikub.spec` embarque explicitement `highspy` (sous-modules + bibliothèques
  natives) et distribue le fichier de licences à la racine de `dist/Rummikub/`.
  Le build (`build/rebuild_rummikub.bat`) installe déjà `requirements.txt` et
  l'installeur (`installeur/rummikub.iss`) copie tout `dist\Rummikub\*` — rien
  d'autre à changer côté pipeline ; voir le rapport pour la checklist CCW.

## Tests

- **`tests/test_solveur_exact_maison.py`** (nouveau) : optimum exact sur
  **tous** les `cas_expert_*.json` / `reference_*.json` (atteint
  `attendu_exact_tuiles`, au budget de production mis à l'échelle de la vitesse
  machine) ; accord avec la recherche exhaustive indépendante
  (`verif_solveur`, positions aléatoires graine fixe : jamais sous l'optimum,
  toujours valide/conservé) ; accord **exact** avec la bibliothèque
  `rummikub-solver` quand elle est installée (sauté sinon) ; replis (highspy
  absent, budget nul) ; mise initiale (ne touche pas le plateau, échec si
  minimum inatteignable) ; critères de départage (David tour 31 en un geste,
  économie de jokers).
- **`tests/conftest.py`** (nouveau) : calibration de la vitesse machine
  (`facteur_machine`), appliquée aux budgets des tests de la **recherche de
  repli** dont le résultat dépend de la vitesse (point 8 de #204 enfin traité —
  aucun de ces tests n'est supprimé ni allégé, seuls leurs budgets sont mis à
  l'échelle). Tests concernés listés dans le rapport.
- Toute la suite existante passe (257 tests hors Playwright).

## Mesure

Voir **`RAPPORT_SOLVEUR_EXACT_MAISON_206.md`** : optimum atteint sur 10/10 cas
(écart nul), temps par cas, campagne Avancé vs Expert avant/après, démarrage et
poids ajoutés, et la checklist de vérification sous Windows (CCW).
