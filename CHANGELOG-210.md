# Issue #210 — Fiabiliser les tests dépendant de la vitesse machine ou de la source du scénario, sans en supprimer aucun (suite de #209)

Certains tests échouaient par intermittence selon la charge de la machine ou
selon le solveur ayant construit leur scénario, sans aucune régression réelle
du jeu. L'issue #210 supprime cette sensibilité **sans affaiblir la moindre
exigence sur le RÉSULTAT** (nombre de tuiles, validité du coup, conservation
du plateau, nombre d'étapes réel) et **sans toucher** au moteur, à l'IA, au
solveur ni au pas-à-pas : uniquement les tests et `pytest.ini`.

## Changements

### 1. Pas-à-pas condensé du coup de Bruno — jugé sur le solveur MAISON

`tests/test_condense_solveur.py::test_condense_bruno_tour57_moins_de_onze_etapes`
construisait le coup avec la **bibliothèque externe** `rummikub-solver`, qui
propose un arrangement un peu différent de celui du jeu (même nombre de tuiles
posées, une combinaison de plus déplacée → 12 étapes condensées) ; le seuil
« < 11 » avait été calibré sur le solveur MAISON et échouait donc à tort.

- Le test repose désormais sur le solveur **MAISON** (`moteur/solveur_exact.py`,
  HiGHS), celui que le jeu utilise réellement au niveau Expert — il juge ainsi
  l'affichage du coup **réellement joué**.
- Nombre d'étapes mesuré avec cette source : **exactement 13** (solveur
  déterministe, `threads=1`/`random_seed=0` ; stable quel que soit le budget,
  atteint en ~0,3 s). Détaillé : 27 étapes.
- Nouveau seuil : **« au plus 13 »** — juste au-dessus du nombre réellement
  obtenu, une vraie borne nettement sous le détaillé (objectif de #207), sans
  chiffre magique ni dépendance à la source. Choix documenté dans le test.
- Les propriétés GÉNÉRALES du condensé (`test_condense_coup_exact_proprietes`,
  tous les cas) restent testées via la bibliothèque externe : elles sont
  insensibles à la source (bornes lâches). Le fichier ne saute donc plus tout
  en bloc : le test de Bruno dépend de `highspy`, les propriétés générales de
  `rummikub-solver`.

### 2. Tests au budget de temps en secondes — indépendants de la charge

Budget multiplié par le `facteur_machine` mesuré une fois par session dans
`tests/conftest.py` (micro-benchmark CPU existant, #206 ; ≈ 1 sur la machine
de dev, ≥ 1 sur une machine lente, plafonné à 30). Recensement des tests
concernés, temps sur machine calme et marge retenue :

| Test | Temps calme | Ancien budget | Nouveau budget |
|------|------------|---------------|----------------|
| `test_solveur_cascade_joker_61_trouve_attendu_avec_gros_budget` (tour61) | ~5–7 s | 12 s **codé en dur** | `12 s × facteur_machine` |
| `test_solveur_cas_reference_200_atteint_attendu_avec_gros_budget` (tour59) | ~2–4 s | 10 s **codé en dur** | `10 s × facteur_machine` |
| `test_solveur_cas_reference_200_atteint_attendu_avec_budget_de_production` (tour59) | ~2–4 s | `×6` (9 s) | `×6 × facteur_machine` |
| `test_expert_se_replie_si_modele_exact_indisponible` (tour37, arborescent) | ~0,5 s | 10 s **codé en dur** | `10 s × facteur_machine` |

Les autres tests de solveur à gros budget étaient **déjà** mis à l'échelle par
`facteur_machine` (#206) : plateau chargé #190, cascade #194, départage
#199/#200. Les tests à très large marge (bruno arborescent 0,12 s / 15 s ;
autotest 6 tuiles / 5 s ; cas « sans coup possible » à 1 s) n'ont pas été
touchés (marge > 100×, insensibles à la charge). **Aucune exigence de résultat
modifiée** : seul le temps alloué s'adapte à la vitesse de la machine.

### 3. Marqueur `@pytest.mark.lent`

Déclaré dans `pytest.ini` et posé sur les tests de solveur à gros budget
(plusieurs secondes chacun). Ils restent **exécutés par défaut** avec toute la
suite ; le marqueur permet seulement de les lancer/isoler à part (`pytest -m
lent`, `pytest -m "not lent"`) sans jamais les exclure. Documenté dans
`CONTEXTE.md` §6.

## Vérification

- Suite complète (`/usr/bin/python3 -m pytest tests/ -q`, environnement avec
  `highspy`/`numpy`/`rummikub_solver`) : **282 passed, 3 skipped** (Playwright
  absent), deux exécutions consécutives identiques (~1 min 47 chacune) — aucune
  intermittence.
- Robustesse sous charge démontrée : avec 8 cœurs saturés, `facteur_machine`
  monte à ≈ 2,7 et **tous** les tests sensibles passent (l'ancien budget 12 s
  codé en dur aurait été dépassé).
- Fichiers touchés : `tests/test_condense_solveur.py`, `tests/test_ia.py`,
  `tests/test_solveur_exact_maison.py`, `pytest.ini`, `CONTEXTE.md`.
  **Aucun** changement au moteur, à l'IA, au solveur ni au pas-à-pas.
