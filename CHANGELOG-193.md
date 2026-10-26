# Issue #193 — Fiabiliser l'analyse des coups ratés : poses sous-optimales, budget nécessaire, vérification croisée du solveur

## Contexte
Suite de #188 : l'analyse des coups ratés de l'IA (`scripts/analyser_coups_rates.py`)
ne regardait que les pioches/passes, avec un budget pouvant être trop court
(cas réel : tour 57 de Bruno, 1 tuile posée alors que le solveur en trouve 3
avec 10 s), et ne vérifiait jamais le solveur lui-même (juge et joueur à la
fois). Objectif : rendre cette analyse fiable — poses sous-optimales
comprises, budget nécessaire mesuré, validée sur des cas connus et contre une
recherche exhaustive indépendante — et l'étendre à un joueur humain.

## Modifications
- `src/rummikub/persistance/coups_rates.py` (fonctions de #188 inchangées,
  nouvelles fonctions ajoutées) :
  - `extraire_toutes_decisions`/`extraire_decisions_ia_toutes`/
    `extraire_decisions_joueur` : extraction généralisée aux POSES (pas
    seulement pioche/passe) et à n'importe quel joueur (IA ou humain nommé) ;
    dédoublonnage après une pose annulée puis rejouée (même tour réutilisé,
    comme `bilan.py`), reconstruction de l'état même à travers une entrée
    `"annulation"` du journal.
  - `analyser_decision_complete` : classe une décision en `coup_rate`
    (pioche/passe), `pose_sous_optimale` (pose inférieure au maximum du
    solveur) ou `joueur_bat_solveur` (pose supérieure — humain uniquement),
    ou `inconclusif` (budget épuisé — JAMAIS confondu avec « pas de coup
    raté »).
  - `calculer_resume_complet`/`top_coups_rates_complet` : résumé étendu par
    niveau/phase, distinguant les deux catégories de coup raté.
  - `budget_necessaire`/`repartition_budget_necessaire` : plus petit budget
    (série 1,5/3/6/10/20/30 s) qui retrouve un coup déjà identifié comme raté,
    et répartition pour décider « laisser réfléchir plus longtemps » vs
    « changer la recherche ».
  - `detecter_reserves_joueur`/`resume_joueur_humain` : technique de la
    « réserve » d'un joueur humain (tuile gardée volontairement un tour,
    posée au tour suivant) jamais comptée comme coup raté ni comme cas où le
    solveur est battu ; deux listes séparées (coups peut-être ratés / solveur
    battu) + statistiques de style purement descriptives (jokers gardés,
    pioches avec coup possible, écart au maximum du solveur).
- `src/rummikub/moteur/verif_solveur.py` (nouveau module pur) :
  `max_tuiles_posables_exhaustif` (recherche exhaustive volontairement lente,
  sans aucune optimisation du solveur) + `generer_position_aleatoire` (petite
  position reproductible, graine fixe) — vérification croisée indépendante du
  solveur.
- `scripts/verifier_solveur_exhaustif.py` (nouveau) : compare solveur et
  recherche exhaustive sur `--nb` positions aléatoires (graine `--seed`),
  signale tout écart sans jamais corriger le solveur. **300 positions,
  graine 193 : 0 écart, 0 inconclusive.**
- `scripts/analyser_coups_rates.py` (réécrit) : analyse poses comprises,
  avertissement si `--budget` < 10 s, `--budget-mesure` (budget nécessaire),
  `--retenter-inconclusifs` (seconde passe à budget plus grand sous une
  limite de durée totale ferme), `--enregistrer-cas-reference` (écrit de
  nouveaux `tests/donnees/cas_expert_*.json`, n'écrase jamais l'existant),
  `--joueur "Nom"` (même analyse pour un joueur humain).
- Tests : `tests/test_coups_rates_extensions.py` (poses sous-optimales,
  joueur bat le solveur, résumé étendu, budget nécessaire, détection de
  réserve réussie/perdue, validation sur le cas réel de Bruno avec budget
  suffisant ET avec budget délibérément trop court — robuste au temps de
  calcul de la machine) ; `tests/test_verif_solveur.py` (recherche exhaustive
  sur cas unitaires + campagne aléatoire à graine fixe, 60 positions, contre
  le solveur de production). Suite complète : **141 tests passent**
  (122 avant #193 + 19 nouveaux).
- `CONTEXTE.md` §11bis : nouvelles capacités et limites restantes documentées.

## Points d'attention
- **Non exécuté sur les vrais journaux de parties** : cette issue a été
  traitée dans un worktree isolé (périmètre strict) dont `data/logs_parties`
  est vide — les vrais journaux vivent hors de ce périmètre
  (`/home/alain/Rummikub/data/logs_parties` notamment), auquel je n'ai pas
  accès depuis ce worktree. Le point 6 de l'issue (« lancer l'outil sur tous
  les journaux de `RACINE_DATA/logs_parties` ... inclure les chiffres dans le
  rapport ») n'a donc **pas pu être exécuté avec des données réelles** : le
  script a été vérifié de bout en bout (tous les modes) sur des journaux
  fabriqués à la main, mais les vrais chiffres restent à produire par Alain,
  en relançant `python scripts/analyser_coups_rates.py --tous --budget 10`
  (et `--joueur "Alain"`) depuis une installation courante du projet (pas ce
  worktree). Le point 6 bis (« 13/54 décisions inconclusives sur une
  première analyse réelle ») fait référence à une analyse déjà réalisée par
  Alain avant cette issue, pas reproductible ici pour la même raison.
- **Technique de la réserve, limite assumée** : la détection ne regarde que
  le tour immédiatement suivant du même joueur dans la même partie ; une
  vraie réserve stratégique reste a posteriori indiscernable d'un simple
  oubli qui se résout par hasard au tour suivant (déjà noté dans l'issue).
- **`budget_necessaire`/`--budget-mesure` sont coûteux** (relancent le
  solveur une fois par palier de budget) : volontairement réservés aux coups
  déjà identifiés comme ratés, jamais appliqués en routine à toute une
  campagne.
- Le `joueur_bat_solveur` n'est, par construction, jamais déclenché pour une
  IA en usage normal (le budget généreux du contrôle est toujours ≥ celui de
  production, donc le solveur ne peut pas faire moins bien que lui-même) —
  catégorie pensée pour `--joueur` (humain).
- Vérification croisée du solveur limitée aux petites positions (plateau
  ≤ 4 tuiles, main ≤ 6) : ne prouve rien sur un plateau de taille réelle,
  hors de portée d'une recherche exhaustive.
