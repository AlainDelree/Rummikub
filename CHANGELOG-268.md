# Issue #268 — Tests : ne plus dépendre des réglages calibrés d'un niveau, et borner la durée de chaque test

## Contexte

Depuis #267, Débutant vaut `perturbation_max=1` (plus `0`) : il appelle donc
le solveur exact à CHAQUE tour (≈ 1 s/tour), alors qu'avant il ne le faisait
jamais. Plusieurs tests jouaient « Débutant contre Débutant » comme
adversaire FAIBLE et RAPIDE sur des campagnes à `max_tours=300` sans budget
réduit : la suite complète ne se terminait plus (82 min sans finir, coincée
sur `tests/test_export_trace.py`).

## 1. Mesure (étape 1, voir rapport de clôture pour le détail)

Les 42 fichiers de tests ont été lancés un par un sous `timeout 300`,
`--durations`. Un seul fichier est réellement cassé par #267 :
`tests/test_export_trace.py` (184 s au lieu de ≈ 1 s, ses 3 tests entre
31 s et 119 s chacun). Les autres fichiers cités par l'issue
(`test_ia.py`, `test_ia_anti_don_joker.py`, `test_echelle_niveaux.py`,
`test_coups_rates.py`, `test_verif_solveur_exact.py`,
`test_calibrer_echelle.py`) restent rapides : soit ils n'exercent jamais
une vraie partie (dicts fabriqués, sortie anticipée sans solveur exact),
soit ils bornent déjà `--max-tours`/`--budget-solveur` à des valeurs
minuscules, indépendantes de la calibration réelle d'un niveau.
`tests/test_ia.py` reste à 71 s, mais c'est PRÉEXISTANT et déjà marqué
`lent` (tests de solveur à gros budget, sans rapport avec Débutant).

## 2. Fixture de test indépendante de la calibration (`tests/conftest.py`)

- `niveau_debutant_rapide` (fixture, PAS autouse) : installe pour la durée
  du test, via `monkeypatch.setitem`, l'ancien réglage rapide de Débutant
  (`perturbation_max=0, taux_oubli=0.42, eviter_don_joker=False` — #216/
  #217, avant la calibration par duels de #267) dans `niveaux.BRIDAGES`.
  Appliquée aux 3 tests de `tests/test_export_trace.py`, qui n'ont besoin
  que d'un joueur faible et rapide, pas du réglage calibré réel.
  `niveaux.py` n'est pas touché.
- `_bridages_restaures` (fixture AUTOUSE) : sauvegarde/restaure
  `niveaux.BRIDAGES` autour de CHAQUE test. Découverte en cours de route :
  `scripts/calibrer_echelle.py` (`_jouer_tache`) installe un `--reglage`
  candidat directement dans ce dict global SANS jamais le restaurer
  (voulu hors tests) ; un test de `test_calibrer_echelle.py` (réglage
  `Facile=1/0.30`) laissait ce réglage actif pour toute la session, faisant
  ensuite échouer `test_niveaux.py::test_reglages_calibres_267` une fois
  la suite complète capable d'atteindre ce test (invisible avant #268,
  puisque la suite se bloquait plus tôt sur `test_export_trace.py`).

## 3. Garde-fou de durée par test (`tests/conftest.py`)

Fixture autouse `_limite_temps_par_test` : arme
`faulthandler.dump_traceback_later` au début de chaque test (60 s par
défaut, 240 s pour un test marqué `lent`), désarmée à la fin. Bibliothèque
standard, aucune dépendance ajoutée, fonctionne sous Linux comme sous
Windows (contrairement à `signal.alarm`). La trace est écrite dans un
fichier dédié sous `tempfile.gettempdir()` (pas sur `sys.stderr` : la
capture de sortie de pytest redirige le descripteur de fichier avant que
`os._exit` ne saute le rapport final — la trace y serait invisible).
Vérifié avec un test de démonstration qui boucle : arrêt net après 60 s,
trace de piles lisible, code de sortie 1.

## 4. Règle de travail (`docs/contexte/niveaux_ia_calibrage.md`)

Quelques lignes ajoutées : les tests ne doivent jamais dépendre des
réglages calibrés d'un niveau ; pour un joueur rapide, utiliser
`niveau_debutant_rapide` ; modifier `niveaux.BRIDAGES` ne doit jamais
allonger la suite.

## 5. Mesure finale

Suite complète (`pytest tests -q`) : **547 passed, 13 skipped en 117 s
(1 min 57)**, contre 82 min sans se terminer avant correction. Pic mémoire
(RSS, `/usr/bin/time -v`) sur la suite complète : ≈ 292 MiB — aucune
anomalie. 15 tests les plus longs après correction : tous préexistants et
sans rapport avec #267/#268 (solveur à gros budget, déjà marqués `lent`
pour la plupart), le plus long à 20,5 s
(`test_evaluation_main.py::test_eval_ne_change_pas_nb_tuiles_cas_reference`,
non marqué `lent`, signalé mais non modifié — hors périmètre de #268,
qui ne porte que sur la dépendance à la calibration d'un niveau).

Aucun test supprimé ni raccourci ; aucune modification de `niveaux.py`,
des réglages des niveaux, ou du moteur.
