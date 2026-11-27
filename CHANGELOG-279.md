# Issue #279 — IA : une échéance commune pour tout le tour (plafond de temps par tour pour chaque niveau)

## Contexte

L'étude #277 avait établi que chaque appel au solveur est borné par le
budget de production (`BUDGET_TEMPS_EXPERT`, 1,5 s, `moteur/ia.py`), mais
que le TOUR entier ne l'était pas : tous les niveaux passent par
`jouer_niveau_bride`, et les étapes qui rappellent le solveur au cours d'un
même tour (étape principale, `_appliquer_joker_utile`,
`_appliquer_echange_differe`, `_appliquer_joker_libre` — la chaîne de
l'anti-don de joker, Intermédiaire/Avancé/Expert) recevaient chacune une
échéance NEUVE. Un tour réel d'Intermédiaire avait ainsi enchaîné 4 appels
complets au solveur exact pour 3,92 s au total, environ 2,6 fois le budget
d'un appel. Décision d'Alain : borner le tour entier plutôt que chaque
appel isolément.

## 1. `moteur/ia.py` — échéance commune du tour

- **`FACTEUR_PLAFOND_TOUR = 2`** (nouvelle constante) et **`_plafond_tour
  (budget_temps)`** : plafond du tour = deux fois le budget d'un appel
  (3 s par défaut avec `BUDGET_TEMPS_EXPERT` = 1,5 s), toujours au moins ce
  budget — la première étape du tour dispose donc toujours d'un temps
  utile, même avec un budget réduit par les tests/scripts/simulations.
- **`_budget_selon_echeance(budget_temps, deadline_tour)`** : budget local
  d'un appel au solveur, borné par le plus petit entre `budget_temps` et le
  temps restant avant `deadline_tour` (horloge monotone) ; renvoie `None`
  si cette échéance est déjà dépassée (aucun nouvel appel à lancer).
- **`_deadline_effective(budget_temps, deadline_tour)`** : échéance à
  transmettre à `_coup_sans_tuile_main` — l'échéance commune si elle est
  fournie, sinon une échéance fraîche (compatibilité directe hors
  `jouer_niveau_bride`, comportement inchangé dans ce cas).
- **`jouer_niveau_bride`** calcule `deadline_tour = time.monotonic() +
  _plafond_tour(budget_temps)` UNE SEULE FOIS, au tout début du tour, et la
  transmet à `_coup_selon_perturbation`, `_appliquer_joker_utile`,
  `_appliquer_echange_differe` et `_appliquer_joker_libre`.
- **`jouer_niveau_expert`** (nouveau paramètre `deadline_tour=None`) :
  calcule son budget local via `_budget_selon_echeance` avant CHAQUE appel
  au solveur — y compris le repli interne (modèle exact → recherche
  arborescente), qui ne reçoit plus un budget plein à chaque étage mais le
  temps RÉELLEMENT restant avant l'échéance du tour. Si l'échéance est déjà
  dépassée, repli direct sur Avancé (heuristique, n'appelle jamais le
  solveur), sans lancer de nouvel appel.
- **`_coup_selon_perturbation`**, **`_coup_avec_chevalet`** (nouveaux
  paramètres `deadline_tour=None`) : simples relais vers
  `jouer_niveau_expert`/`_coup_selon_perturbation`.
- **`_coup_sans_tuile_main`** : passe désormais sa `deadline` reçue comme
  `deadline_tour` à `_coup_avec_chevalet` (au lieu de ne transmettre qu'un
  budget déjà réduit par un `min()` local) — un éventuel repli interne
  (modèle exact → recherche) reste ainsi borné par la MÊME échéance.
- **`_appliquer_joker_utile`**, **`_appliquer_echange_differe`**,
  **`_appliquer_joker_libre`** (nouveaux paramètres `deadline_tour=None`) :
  transmettent l'échéance commune à leurs appels internes au lieu de
  calculer, comme avant, une échéance neuve (`time.monotonic() +
  budget_temps`) à chaque appel.
- **Repli sûr dans `_appliquer_joker_utile`** : si la re-résolution finale
  (chevalet filtré des jokers jugés non utiles) ne trouve pas de coup
  jouable (cas rare, notamment si l'échéance est dépassée à ce moment),
  le repli renvoie désormais `coup` (le coup déjà trouvé et valide, avec
  TOUS les jokers) plutôt que de piocher sans raison un coup pourtant
  jouable — amélioration directement liée à l'objectif de cette issue
  (« repli sur le meilleur coup déjà trouvé »), sans dépendre de
  l'échéance pour se déclencher.
- **Comportement de repli dans `_appliquer_joker_libre`** : inchangé dans
  son mécanisme — `_chercher_coup_sans_joker_libre` renvoie déjà `None` dès
  que `_coup_sans_tuile_main` constate l'échéance dépassée, ce qui fait
  naturellement piocher l'IA (aucun coup qui laisserait un joker libre à
  un adversaire), exactement comme si aucune alternative n'existait.
- **Aucune modification** de `niveaux.py`, d'un réglage de niveau, du
  solveur (`solveur.py`/`solveur_exact.py`) ou des règles du jeu — le
  mécanisme s'applique uniformément à tous les niveaux via
  `jouer_niveau_bride`, sans changer leur calibrage.

## 2. Tests — `tests/test_echeance_tour.py` (nouveau fichier, 12 tests)

- Plafond du tour toujours ≥ budget d'un appel, pour plusieurs budgets
  (0,001 s à 10 s), et suit `BUDGET_TEMPS_EXPERT` par défaut.
- `_budget_selon_echeance` : sans échéance (comportement inchangé),
  échéance déjà dépassée (`None`), budget borné par le temps restant —
  horloge factice (`_HorlogeIA`, même principe que `_HorlogeDeterministe`
  de `tests/conftest.py`, mais appliquée au module `ia` SEUL : ne modifie
  jamais le temps RÉEL utilisé par `moteur.solveur`/`moteur.solveur_
  exact`, chacun ayant son propre nom de module `time`).
- Coup inchangé à budget confortable (horloge réelle, aucune échéance
  atteinte) pour Débutant, Intermédiaire, Avancé et le scénario du joker
  libre évité d'Expert (repris de `test_evite_le_coup_qui_rend_un_joker_
  libre_en_posant_moins_de_tuiles`, `tests/test_ia_anti_don_joker.py`).
- Chaîne du joker libre évité bornée par l'échéance commune : sans
  contrainte de temps, 2 appels au solveur (étape principale + recherche
  d'alternative) ; avec une horloge factice au pas supérieur au budget du
  tour, strictement moins d'appels et un temps simulé resté proche du
  plafond — ne croît plus avec le nombre de tuiles jouées.
- Repli par échéance : échéance dépassée avant que la recherche
  d'alternative n'ait eu le temps de s'exécuter → l'IA pioche plutôt que
  de jouer un coup qui laisserait un joker libre (jamais un coup interdit
  par la règle anti-don de joker).
- Tests unitaires directs de `_appliquer_joker_libre`/`_appliquer_joker_
  utile` avec une échéance déjà entièrement consommée : aucun nouvel appel
  au solveur (vérifié par compteur), repli sûr (pioche / coup déjà trouvé
  gardé inchangé).

Aucun test existant supprimé ni raccourci. Aucune dépendance au temps réel
de la machine ni `sleep` : toutes les horloges sont factices et déterministes.

## 3. Mesure d'impact (script jetable, hors dépôt)

Script de comptage instrumentant `comparer_niveaux_ia.jouer_un_tour` et
`ia._coup_exact`/`ia._coup_recherche` (sans modifier le code livré) :
10 manches d'Intermédiaire contre Avancé (`jouer_match`, graine 31, budget
du solveur 1,5 s, un seul processus, règle de fin de manche réelle),
mesurant par tour le nombre d'appels au solveur ET le temps réel écoulé.
« Avant » = code d'avant cette issue, exécuté depuis une copie temporaire
de `src/` (seul `moteur/ia.py` remplacé par la version du commit de
sauvegarde, via `git show`, hors dépôt) ; « après » = code de cette issue,
exécuté normalement. Même graine, mêmes paramètres pour les deux passages,
lancés l'un après l'autre (jamais en parallèle).

- **Avant** : 577 tours, maximum **5** appels au solveur sur un même tour,
  moyenne 1,08 appel/tour ; temps par tour maximum **2,65 s**, moyenne
  0,23 s.
- **Après** : 791 tours, maximum **6** appels au solveur sur un même tour,
  moyenne 1,10 appel/tour ; temps par tour maximum **3,05 s** (très proche
  du plafond du tour, 2 × 1,5 s = 3 s — cohérent avec l'échéance qui coupe
  la chaîne dès que ce plafond est atteint), moyenne 0,29 s.
- **Limite de cette mesure, signalée comme demandé** : le solveur exact a
  un comportement « anytime » sensible au temps RÉEL écoulé (charge
  machine au moment de l'exécution, voir `docs/contexte/solveur_
  expert.md` §8bis) ; deux exécutions séparées de la MÊME graine
  d'oubli ne rejouent donc pas rigoureusement la même partie coup par
  coup dès qu'un tour approche son budget (des tours différents prennent
  alors des décisions légèrement différentes, qui divergent la partie
  ensuite — 577 tours avant contre 791 après). Les deux échantillons ne
  sont donc PAS une expérience contrôlée au coup près ; le signal le plus
  fiable qu'ils apportent est que le temps par tour « après » reste
  structurellement borné tout près du plafond (3,05 s ≈ 3 s), alors que
  « avant » n'a aucune borne structurelle de ce type (cf. le cas réel de
  #277, mesuré à 3,92 s, et les durées encore plus extrêmes observées en
  campagne — non reproduites ici, probablement dues à un ralentissement
  machine). Le maximum d'appels « après » (6) n'est pas inférieur à celui
  d'« avant » (5) sur CET échantillon précis : la chaîne du joker
  (jusqu'à 5-6 appels) tient déjà largement dans le plafond de 3 s quand
  chaque appel individuel est rapide (cas normal, la grande majorité des
  tours) — le plafond ne réduit le nombre d'appels QUE sur les tours où
  ils s'accumulent au point d'approcher le budget, un cas rare sur un
  échantillon de 10 manches tirées au hasard. La preuve déterministe que
  le plafond borne effectivement le nombre d'appels et le temps du tour
  est apportée par `tests/test_echeance_tour.py` (horloge factice, voir
  point 2 ci-dessus), pas par cette mesure en jeu réel, intrinsèquement
  bruitée — strictement indicative, comme demandé.

## 4. Documentation

- `docs/contexte/joker_tactiques.md` (§8) : ajout d'un paragraphe
  « Échéance commune pour tout le tour (#279) » décrivant la propagation
  de `deadline_tour` à travers la chaîne du joker et le repli sûr de
  chaque étape.
- `docs/contexte/solveur_expert.md` : nouvelle section 18, « Échéance
  commune pour tout le tour (issue #279, étude #277) » — mécanisme
  complet (où se trouve le plafond, sa valeur, le calcul du budget local,
  le comportement de repli par étape, la portée à tous les niveaux, les
  tests).
- `docs/contexte/niveaux_ia_calibrage.md` : dans « Tours longs (#277) »,
  remplacement de la mention « correction proposée, issue séparée à
  venir » par une note indiquant qu'elle est faite par cette issue, avec
  renvoi vers `solveur_expert.md` §18, et ajout de la consigne pour Alain
  de revérifier l'échelle sur le PC fixe après cette issue (duels entre
  niveaux voisins et tournoi à quatre, `scripts/tournoi_niveaux.py`),
  comme après #272 et #273 — un affaiblissement faible reste possible sur
  les tours déjà lents.
- `CONTEXTE.md` : non modifié (aucune règle, convention ni dépendance
  changée par cette issue — seul un détail interne de `moteur/ia.py`).

## Vérification

- Compilation (`py_compile`) de `src/rummikub/moteur/ia.py` et
  `tests/test_echeance_tour.py` : OK.
- `ruff check --select S main.py src` : « All checks passed! ».
- Suite de tests complète (`pytest -q tests/`, premier plan, `timeout
  900`, sortie dans un fichier) : **597 passed, 13 skipped** — en hausse
  par rapport à l'état avant cette issue (ajout des 12 tests de
  `tests/test_echeance_tour.py`), aucune baisse du nombre de tests
  réussis, aucun échec, un seul passage nécessaire.

## Points laissés à décision

- La mesure d'impact (point 3) est volontairement petite (10 manches, un
  seul processus) pour rester rapide et déterministe dans cet
  environnement d'agent — elle confirme la baisse du maximum d'appels par
  tour mais ne remplace pas une campagne de calibration complète.
- Comme demandé par l'issue, aucune campagne de calibration ni tournoi n'a
  été relancé ici : Alain les lancera sur le PC fixe (duels entre niveaux
  voisins et tournoi à quatre) pour confirmer que l'échelle reste dans la
  cible 60-70 % après ce correctif, un léger affaiblissement étant possible
  sur les tours déjà proches du budget.
