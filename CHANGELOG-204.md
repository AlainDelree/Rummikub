# Issue #204 — Vérification du solveur d'Expert par un solveur exact indépendant (suite de #201)

Mesure **indépendante et exacte** de ce que le solveur d'Expert
(`moteur/solveur.py`) rate, à l'aide de la bibliothèque libre `rummikub-solver`
(PyPI, licence MIT, programmation linéaire en nombres entiers de den Hertog &
Hulshof 2006). **Aucune modification du solveur d'Expert, du jeu livré ni des
niveaux d'IA.** La bibliothèque est une **dépendance de développement
seulement** (absente de `requirements.txt` et du build Windows).

## Ajouts

- **`scripts/solveur_exact.py`** — adaptateur vers la bibliothèque : conversion
  de nos états (plateau, main, drapeau de mise initiale) vers la bibliothèque
  (couleurs noir=BLACK, bleu=BLUE, jaune=ORANGE, rouge=RED ; jokers), résolution
  exacte, et reconstruction dans notre domaine — nombre de tuiles posées,
  combinaisons **remises dans l'ordre** (suites, place des jokers), durée du
  calcul. Chaque solution est **vérifiée par `valider_combinaison`** et la
  **conservation des tuiles du plateau** contrôlée. S'importe sans la
  bibliothèque (`DISPONIBLE=False`, message d'installation).
- **`scripts/comparer_solveur_exact.py`** — comparaison sur tous les
  `tests/donnees/cas_expert_*.json` et `reference_*.json` : nombre de tuiles de
  notre solveur à 1,5 s (production) et 10 s (généreux), nombre et durée du
  solveur exact, écart ; synthèse finale (cas ratés à 1,5 s, écart moyen/maximal,
  temps total exact, contrôles). Option `--journaux [--tous] [--dossier]` pour
  comparer sur de vrais journaux de parties.
- **`scripts/analyser_coups_rates.py --juge-exact`** — option (désactivée par
  défaut) qui utilise le solveur exact comme **juge** à la place du solveur
  maison : plus aucune décision « inconclusive » ni coup manqué par gel de
  combinaisons. Signale clairement l'absence de la bibliothèque.
- **`tests/test_solveur_exact.py`** — tests de l'adaptateur (correspondances,
  remise dans l'ordre, validité + conservation + maximum exact sur les 10 cas,
  non-régression Ines, interface drop-in), **sautés proprement** si la
  bibliothèque est absente (comme Playwright).
- **`RAPPORT_SOLVEUR_EXACT_204.md`** — rapport : répartition des écarts, durées,
  taille d'installation et démarrage, deux voies d'embarquement éventuel
  (a : la bibliothèque telle quelle via cvxpy/scipy ; b : modèle maison direct
  sur `highspy`+`numpy`, ~3× plus léger), liste des licences et obligations
  (avis de copyright ; éviter l'extra GPL `glpk_mi`).

## Modifications

- **`tests/donnees/*.json`** — clé **`attendu_exact_tuiles`** (maximum exact)
  ajoutée à chaque cas de référence, `attendu_min_tuiles` conservée.
- **`src/rummikub/persistance/coups_rates.py`** — `analyser_decision_complete`
  (et `analyser_decisions_completes`) acceptent un paramètre `solveur`
  optionnel (callable, défaut = solveur maison inchangé) permettant d'injecter
  le juge exact. Le module **n'importe jamais** la bibliothèque. Comportement
  par défaut strictement identique.
- **`CONTEXTE.md`** — nouvelle **§14** (installation, usage, résultats).
- **`.gitignore`** — ignore `.venv-solveur-exact/` (venv de dev, ~316 Mo,
  jamais versionné).

## Résultats mesurés (10 cas de référence, backend HiGHS)

- Notre solveur rate des tuiles sur **5/10 cas à 1,5 s** (budget de production).
- Le solveur exact calcule l'optimum prouvé en **~84 ms/cas** (max ~145 ms).
- Deux cas restent sous l'optimum **même à 10 s** (faiblesse d'algorithme, pas
  de budget) : **Bruno tour 57** (3 vs 4 — tuile manquante `rouge_12`, obtenue
  en scindant la suite rouge 6–10) et **Ines tour 85** (1 vs 2, victoire
  immédiate manquée → test de non-régression de la suite).
- Toutes les combinaisons proposées sont valides et conservent le plateau.

**Réponse à la question de l'issue** : le solveur exact trouve le maximum du
tour **nettement plus vite** que le nôtre. Reste à trancher l'embarquabilité
(voie b recommandée : `highspy` direct, MIT) — hors périmètre de cette issue,
qui ne modifie pas le build.
