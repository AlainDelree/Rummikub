# Issue #247 — Tests : un dernier échec propre à Windows (cas de référence Bruno à budget trop court), correction du test seulement

## Contexte

Après #244, la suite complète sous Windows (commit `e9d8c9b`, Python 3.12.7)
donnait 433 réussis, 16 ignorés et **un** échec restant, non listé par #244 :
`tests/test_coups_rates_extensions.py::test_cas_reference_bruno_budget_trop_court_signale_inconclusif`
(ligne 364 à l'époque) — `assert r["inconclusif"] is True` recevait `False`.

## Analyse (hypothèse confirmée)

Lecture de `test_coups_rates_extensions.py` puis de
`persistance/coups_rates.py::analyser_decision_complete` et du solveur de
repli `moteur/solveur.py` : le test appelle
`CR.analyser_decision_complete(decision, budget_genereux=0.0)`, qui descend
jusqu'à `resoudre_coup` → `_meilleur_rearrangement` → `_Contexte`. Comme pour
#244, `_Contexte.verifier_budget` compare `time.monotonic() > self.limite`
(stricte), vérifiée dès le 1er appel. Avec un budget nul, cette comparaison
n'est fiable que si l'horloge a réellement avancé entre la pose de `limite`
(dans `_meilleur_rearrangement`, puis recopiée dans `_Contexte.__init__`) et
sa première vérification quelques appels plus tard. Sous Linux, l'horloge est
de haute résolution et avance toujours. Sous Windows, `time.monotonic()` réel
n'avance que par paliers d'environ 15 ms : si tous ces appels tombent dans le
même palier, `time.monotonic()` renvoie exactement la même valeur partout, la
comparaison stricte reste fausse, `BudgetDepasse` n'est jamais levée, et —
comme ce cas de référence se résout désormais en ~0,1 s depuis #194 — la
recherche a largement le temps d'aboutir avant que l'horloge bouge. Le
résultat obtenu est alors un vrai coup (`pose_sous_optimale=True`), pas
« inconclusif ». Confirmé : défaut du TEST (dépendance à la finesse de
l'horloge réelle), pas du jeu — le budget réel en production est de 1,5 s
(`BUDGET_TEMPS_EXPERT`), bien au-dessus de ce cas limite.

## Modification

- **`tests/test_coups_rates_extensions.py`**
  (`test_cas_reference_bruno_budget_trop_court_signale_inconclusif`) : ajout
  du paramètre `horloge_solveur_deterministe` (fixture de #244,
  `tests/conftest.py`), qui substitue à `moteur.solveur.time` une horloge
  factice avançant d'un pas fixe à CHAQUE appel — jamais l'horloge réelle,
  jamais `time.sleep`. La fixture ne patche que le nom `time` du module
  `solveur.py` ; comme `resoudre_coup` (importé par `coups_rates.py`) lit
  `time.monotonic()` dans les globales de CE module au moment de l'appel,
  elle s'applique aussi bien à travers `analyser_decision_complete` qu'à un
  appel direct à `resoudre_coup`. La fixture n'a pas eu besoin d'être
  étendue : elle s'appliquait déjà au bon point d'entrée. Le reste du test
  (`pose_sous_optimale is False`, `coup_rate is False`) reste vérifié et
  continue de passer — seule l'assertion `inconclusif is True` était en
  cause. `test_cas_reference_bruno_detecte_avec_budget_suffisant` (budget
  généreux de 15 s, chemin « détecté ») n'est pas concerné et reste
  inchangé : il a besoin du temps de calcul RÉEL de la machine, pas d'une
  horloge factice.
- **`CONTEXTE.md`** (§6 Tests) : une ligne ajoutée à l'entrée de #244 citant
  ce troisième cas et confirmant qu'aucun nouveau mécanisme n'a été
  nécessaire (même fixture).

## Recherche d'autres tests sensibles à la finesse de l'horloge

Recherche dans tout `tests/` des budgets nuls ou minuscules
(`budget_temps`/`budget_genereux` à `0.0`, motifs `trop_court`/`budget_nul`,
appels directs à `resoudre_coup`/`jouer_niveau_expert`/`resoudre_exact`) :

- `tests/test_ia.py::test_expert_se_replie_sur_avance_si_budget_depasse` et
  `tests/test_solveur_exact_maison.py::test_expert_se_replie_si_budget_nul` :
  déjà corrigés par #244, utilisent déjà `horloge_solveur_deterministe`.
  Toujours corrects.
- `tests/test_solveur_exact_maison.py` ligne 106
  (`se.resoudre_exact(etat, idx, budget_temps=0.0)`) : passe par
  `moteur/solveur_exact.py::resoudre_exact`, qui contrôle `budget_temps <= 0`
  explicitement, SANS passer par l'horloge (voir point ci-dessous) — non
  concerné par ce défaut.
- Aucun autre test du dépôt n'appelle la recherche de repli
  (`moteur/solveur.py`) avec un budget nul ou assez petit pour dépendre de la
  granularité de l'horloge sans déjà utiliser la fixture. Les autres usages
  de petits budgets dans `test_ia.py`/`test_verif_solveur.py` utilisent des
  budgets réels de l'ordre de la seconde (mis à l'échelle par
  `facteur_machine`), où un éventuel dépassement est une issue normale et
  tolérée (`except BudgetDepasse`), pas une condition testée à la limite de
  l'horloge.

## Point de code de production à décider (signalé, non modifié)

Identique à #244, reconfirmé ici : `moteur/solveur.py` (recherche de repli)
n'a aucun contrôle explicite `if budget_temps <= 0: ...` indépendant de
l'horloge — contrairement à `moteur/solveur_exact.py::resoudre_exact`, qui en
a un. En jeu réel le budget est de 1,5 s (`BUDGET_TEMPS_EXPERT`), donc cette
finesse n'a aucun effet pratique constaté. Non modifié ici (hors périmètre :
« corriger les tests seulement, jamais le code de production »).

## Vérification

- `pytest tests/` (Linux, Python 3.12.x) : **459 passed, 13 skipped**, aucun
  échec — suite exécutée en totalité, pas seulement le fichier modifié.
- `python -m py_compile tests/test_coups_rates_extensions.py` : OK.
- **Non exécuté sous Windows** (agent Linux, aucun accès à une machine
  Windows) : le raisonnement ci-dessus garantit cependant le résultat
  indépendamment de la résolution de l'horloge de l'OS, puisque
  `horloge_solveur_deterministe` remplace entièrement `time.monotonic()` par
  une horloge logicielle strictement croissante à chaque appel — le test ne
  lit plus jamais l'horloge réelle du système, qu'elle soit fine (Linux) ou à
  paliers de 15 ms (Windows). Alain relancera la suite complète sur le PC fixe
  pour confirmer zéro échec.
