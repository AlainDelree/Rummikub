# Issue #228 — Infrastructure des stratégies de Champion du Monde : registre, option unique, analyse par niveau, outil de matrice reprenable

Issue d'**INFRASTRUCTURE uniquement** : aucune nouvelle stratégie, aucun
changement de comportement du jeu, d'Expert (témoin), des niveaux inférieurs,
du solveur ni de l'interface. `STRATEGIES_CHAMPION_PAR_DEFAUT` reproduit à
l'identique l'état actuel de Champion du Monde (vérifié par une assertion à
l'import de `moteur/niveaux.py`).

## `src/rummikub/moteur/niveaux.py`

- Registre unique des stratégies multi-tours : `Strategie` (dataclass :
  `id`, `description`, `niveaux` applicables, `active_par_defaut`,
  `compteurs`), `STRATEGIES` (`verif_finition` #221, `garde_joker` #225,
  branchées sans changer leur comportement), `STRATEGIES_CHAMPION_PAR_
  DEFAUT`, `strategies_champion_valides()`, `valider_noms_strategies()`,
  `bridage_champion_personnalise()`.

## `scripts/comparer_niveaux_ia.py`

- `--strategies-champion LISTE|aucune|defaut|toutes` et `--sans-strategie
  NOM` (répétable) : remplacent, DURANT la campagne seulement, la liste de
  stratégies actives de Champion du Monde — nom inconnu = arrêt avec la
  liste des noms valides. `--sans-garde-joker`/`--sans-verif-finition`
  conservés tels quels (compatibilité, portées inchangées).
- `--budget-solveur-expert SECONDES` : budget du solveur par coup, appliqué
  à TOUS les niveaux joués (défaut : celui du jeu, 1,5 s, inchangé sans
  l'option).
- Compteurs génériques par stratégie (« déclenchée »/« a changé le coup »),
  affichés dans le rapport et exportés par match (`strategies_changees`
  dans `--export-resultats`) sans code spécifique par stratégie dans la
  boucle de rapport/export.
- `comparer()` accepte désormais `donnes_debut`/`donnes_fin`/`mode_fichier`
  (reprise par tranches, utilisé par `matrice_strategies.py`) ; les écritures
  JSON Lines (`--export-resultats`/`--export-trace`) sont `flush()`ées ligne
  par ligne (tolérance à une coupure brutale).

## `scripts/analyser_phases.py`

- `--par-niveau` : regroupe l'analyse par niveau d'IA (durée de phase,
  tuiles posées par tour, fréquence de pioche).
- `--comparer AUTRE_TRACE` : affiche les écarts par phase entre deux traces
  (p. ex. témoin vs stratégies, même graine).

## `scripts/matrice_strategies.py` (nouveau)

- Outil qui enchaîne une série de comparaisons sans surveillance (plans
  `ablation`/`complet`/personnalisé JSON), reprenable après interruption
  (checkpoint atomique après chaque donne, refuse de reprendre si le commit
  a changé sauf `--forcer-reprise-commit-different`), `--statut`, résumé
  final mis à jour après chaque configuration (réutilise
  `comparer_campagnes_appariees.py`), `--controle-rapide`, `--processus 1|2`,
  `--limite-temps` (garde-fou externe de #220, comme `echelle_niveaux.py`).

## `scripts/lancer_matrice_windows.ps1` (nouveau)

- Lanceur minimal pour reprendre une série après une coupure de courant sous
  Windows ; documentation de la tâche planifiée (`schtasks`) dans
  `CONTEXTE.md` §13, non créée par cet agent.

## `CONTEXTE.md`

- Nouvelle sous-section en fin de §13 : registre, option unique, méthode
  d'ablation, outil de matrice (plans/reprise/statut/résumé), règle « même
  machine pour tous les bras », consigne veille/redémarrage Windows.

## Tests

- `tests/test_registre_strategies.py`, `tests/test_option_strategies_
  champion.py`, `tests/test_matrice_strategies.py` (nouveaux) ; extension de
  `tests/test_analyser_phases.py` (`--par-niveau`/`--comparer`) et mise à
  jour de l'inventaire figé de `tests/test_garde_fou_scripts_tous.py`.
- Vérifié par les tests (489 passent, aucune régression) et par un essai
  réel de deux configurations de deux donnes (`--plan ablation --strategies
  garde_joker --donnes 2`) : série complète, reprise après interruption
  (process tué en plein milieu, aucune partie rejouée), `--statut`,
  `--controle-rapide`. Aucune campagne longue lancée par l'agent
  (CONTEXTE.md §7).
