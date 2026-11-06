# Issue #244 — Tests : deux échecs propres à Windows (comparaison de chemins et budget de temps), correction des tests seulement

## Contexte

La suite complète passe sous Linux mais donnait deux échecs sous Windows
(432 réussis, 16 ignorés, 2 échecs). Les deux sont des défauts de TEST, pas
du code de production : une comparaison de chemins écrite en texte avec des
barres obliques dures, et une recherche de dépassement de budget qui
suppose que l'horloge réelle avance entre deux appels très rapprochés — vrai
sous Linux, pas garanti sous Windows (`time.monotonic()` y avance par
paliers d'environ 15 ms).

## Modifications

- **`tests/test_actualise_flag_lancement.py`**
  (`test_main_chemins_valides_lancent_sans_shell`) : la comparaison de chemin
  `bat.resolve().as_posix() in [str(a) for a in args]` comparait un `Path`
  écrit avec des barres obliques à des arguments écrits avec les barres
  inverses natives de Windows — mêmes fichiers, textes différents, donc
  échec de pure forme sous Windows. Remplacée par une comparaison de `Path`
  résolus (`Path(a).resolve()`), indépendante du séparateur du système.
  Les assertions de sécurité (liste en premier argument de `Popen`,
  `shell` jamais vrai) sont désormais placées AVANT la comparaison de
  chemin, pour qu'un défaut de comparaison ne les masque plus jamais — ce
  qui était le cas avant cette correction : sous Windows, l'assertion de
  chemin échouait la première et les deux assertions de sécurité qui la
  suivaient n'étaient donc jamais exécutées. Recherche des mêmes motifs
  (`as_posix()` contre un `str(...)` de chemin, barres obliques écrites en
  dur) dans le reste de `tests/` : aucune autre occurrence trouvée (une
  seule au total dans tout le dépôt).
- **`tests/test_ia.py`** (`test_expert_se_replie_sur_avance_si_budget_depasse`)
  et **`tests/test_solveur_exact_maison.py`**
  (`test_expert_se_replie_si_budget_nul`) : les deux tests appellent la
  recherche de repli (`moteur/solveur.py::resoudre_coup`) avec
  `budget_temps=0.0` et s'attendent à un dépassement de budget immédiat.
  Lecture de `moteur/solveur.py` (confirmée) : `_Contexte.verifier_budget`
  compare `time.monotonic() > self.limite` (strict), vérifié au 1er appel
  puis tous les 50. Avec un budget nul, cette comparaison n'est fiable que
  si l'horloge a réellement avancé entre la pose de `limite` et sa
  vérification — vrai sous Linux (horloge haute résolution), pas garanti
  sous Windows (paliers d'environ 15 ms) : une recherche assez courte peut
  alors ne jamais déclencher `BudgetDepasse`. Correction : nouvelle fixture
  `horloge_solveur_deterministe` (`tests/conftest.py`) qui substitue à
  `moteur.solveur.time` une horloge factice strictement croissante à chaque
  appel (jamais l'horloge réelle de l'OS, jamais `time.sleep`) — ne touche
  que le nom `time` du module `solveur.py`, aucun autre module. Les deux
  tests l'utilisent désormais ; la seconde moitié de chacun (repli sur
  exactement le coup d'Avancé) reste vérifiée avec ce réglage et continue de
  passer. Recherche d'autres tests à budget nul ou très petit dans
  `tests/` : seuls ces deux-là utilisent `budget_temps=0.0` (ou équivalent)
  en s'attendant à un dépassement immédiat ; les autres usages de
  `BudgetDepasse`/`budget_temps` à petit budget (`test_verif_solveur.py`,
  `test_ia.py::test_preferer_simple_*`) utilisent des budgets réels
  (secondes) où un dépassement est une issue normale et déjà tolérée
  (`except BudgetDepasse: ...`), pas une condition testée à la limite de
  l'horloge — non concernés.
- **`CONTEXTE.md`** (§6 Tests) : une ligne rappelant que les tests de
  dépassement de budget n'utilisent pas l'horloge réelle (celle de Windows
  avance par paliers d'environ 15 ms) et que les tests de chemins se
  comparent avec `Path`.

## Point de code de production à décider (signalé, non modifié)

`moteur/solveur_exact.py::resoudre_exact` traite déjà un budget nul comme
« déjà dépassé » par un contrôle explicite (`if budget_temps <= 0: raise
BudgetExactDepasse(...)`, indépendant de l'horloge) — robuste par
construction. `moteur/solveur.py` (recherche de repli) n'a PAS ce
contrôle explicite : un budget nul y est traité uniquement via la
comparaison d'horloge décrite ci-dessus. En jeu réel le budget est de 1,5 s
(`BUDGET_TEMPS_EXPERT`), donc cette finesse n'a aucun effet pratique — mais
si Alain souhaite un jour un comportement garanti pour un budget nul/négatif
indépendamment de l'horloge (comme dans `solveur_exact.py`), un contrôle
explicite équivalent dans `moteur/solveur.py` serait à ajouter. Non fait ici
(hors périmètre : « corriger les tests seulement, jamais le code de
production »).

## Vérification

- `pytest tests/` (Linux, Python 3.12.3) : **459 passed, 13 skipped** (dont
  les deux tests visés par cette issue).
- `python3 -m py_compile` sur les quatre fichiers modifiés : OK.
- Les deux tests sont écrits pour être indépendants du système (comparaison
  par `Path` résolus ; horloge factice déterministe au lieu de l'horloge
  réelle de l'OS) mais n'ont pas pu être exécutés sous Windows par cet
  agent (environnement Linux uniquement) — Alain relancera la suite
  complète sur le PC fixe Windows pour confirmer zéro échec.
