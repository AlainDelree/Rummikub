# Issue #257 — Diagnostic de lenteur : duel Intermédiaire contre Avancé 6/0.04 (une partie sur deux dix fois plus lente que sa miroir)

## Contexte

La calibration de l'échelle des niveaux (`scripts/calibrer_echelle.py`)
était devenue beaucoup trop lente pour le duel Intermédiaire contre Avancé
6/0.04 (environ 250 s par donne sur le PC fixe) : le journal détaillé
montrait qu'une des deux parties en miroir d'une même donne (l'ordre où
Intermédiaire joue en premier) pouvait prendre dix fois plus de temps que
l'autre. Cette issue reproduit la lenteur sur Linux, la profile, en
explique la cause, applique le seul correctif sûr identifié (sans changer
aucun coup joué par l'IA), et rend le phénomène visible dans le rapport de
calibration pour la prochaine fois.

## 1. Reproduction (Linux, limites de temps fermes)

- Commande de référence de l'issue (seed 31) reproduite : 162,7 s à
  197,8 s à 216,8 s selon l'essai (forte variance run-à-run, voir §3).
- Essayé sur 6 graines supplémentaires (1, 2, 3, 7, 31, 42), une donne
  chacune : environ 1 graine sur 3 produit une partie très lente dans un
  des deux ordres miroir (seeds 3 et 31 ici) — cohérent avec le « une
  partie sur deux » de l'issue, sans être exactement une sur deux sur cet
  échantillon.

## 2. Profil (cProfile + chronométrage direct, partie la plus lente : seed 3, ordre Intermédiaire d'abord, 139 tours, Linux)

- 139 tours, manche terminée par **blocage** (vraie règle #255), pas par
  chevalet vidé.
- 141 appels à `solveur_exact.resoudre_exact` (~1 par tour) ; chacun
  effectue, en interne, jusqu'à **3 résolutions HiGHS successives**
  (modèle lexicographique : tuiles posées, puis simplicité du plateau,
  puis points/jokers) — **407 appels réels** à `highspy.Highs.run()`
  mesurés (~2,93/tour), confirmant qu'il s'agit bien d'un facteur ~3, pas
  d'un bug qui multiplierait les résolutions sans raison.
- 84,2 s des 93,9 s totaux de cette manche (89,6 %) passés directement
  dans `Highs.run()` ; aucun dépassement du budget de 4 s (0/141).
- 10 tours les plus coûteux : tous dans la seconde moitié de la manche
  (tours 73 à 136), de 1,55 s à 2,53 s chacun, corrélés à la taille du
  plateau (60 à 97 tuiles, 16 à 19 combinaisons) — pas à la taille du
  chevalet (2 à 7 tuiles seulement) ni à la présence d'un joker.
- `cProfile` seul est TROMPEUR sur cette mesure (attribution incohérente
  d'une partie du temps à des fonctions triviales de `highspy`, due à son
  mécanisme de callback interne) : le chronométrage direct (wall-clock,
  autour de chaque appel) est la source retenue pour les chiffres
  ci-dessus.

## 3. Cause

Même phénomène que celui déjà documenté pour Intermédiaire contre
Intermédiaire (`docs/contexte/ia_anti_don_joker.md` §10, issue #256), mais
qui touche aussi le duel Intermédiaire/Avancé sur certaines donnes : une
des deux parties en miroir finit par un **blocage** (pioche vide, tous les
joueurs ont passé) plutôt que par un chevalet vidé, ce qui la fait durer
beaucoup plus de tours (139 contre ~55-70) avec un plateau qui grossit
tour après tour (jusqu'à une centaine de tuiles). Chaque décision d'IA,
même bridée, résout TOUJOURS le modèle exact complet (HiGHS) au moins une
fois pour mesurer la perturbation du coup — et ce modèle résout le
plateau en 3 passes successives. Sur un gros plateau, UNE seule de ces
résolutions peut coûter 1 à 2,5 s ; répété sur ~140 tours au lieu de ~60,
cela suffit à expliquer le facteur 10 avec la partie miroir. Observation
annexe : la décision du solveur exact dépend du temps réel écoulé quand
son budget (4 s) est consommé en cours de résolution — ce qui peut faire
diverger deux parties par ailleurs identiques (même graine) d'un essai à
l'autre, et explique une partie de la variance observée au §1/§4 (non
corrigé : changerait la force de l'IA).

## 4. Correction appliquée : accélération pure, vérifiée à coups identiques (`moteur/ia.py`)

- `_coup_selon_perturbation` calculait SYSTÉMATIQUEMENT le coup sans
  réarrangement (`_coup_sans_rearrangement`, une résolution complète de
  plus) AVANT même de savoir si le coup complet tiendrait dans la borne de
  perturbation du niveau — gaspillé dans le cas (le plus fréquent) où le
  coup complet convient déjà tel quel. Rendu LAZY (calculé seulement dans
  les deux branches de repli qui s'en servent réellement) : pure
  réorganisation de l'ordre des appels, aucune des deux fonctions ne mute
  l'état ni ne consomme le module `random` global (vérifié : seul
  `random.shuffle` du niveau Débutant, hors de ce chemin, et les tirages
  d'oubli utilisent un `random.Random` isolé par tour).
- **Preuve d'identité des parties avant/après** : 40 matchs (20 donnes x 2
  miroir, `comparer_niveaux_ia.py --niveau-a Intermédiaire --niveau-b
  Avancé --donnes 20 --seed 0`, niveaux du jeu) rejoués avant et après —
  fichiers de résultats **identiques ligne à ligne** (`diff` sans aucune
  différence), mêmes victoires (14/40 contre 26/40), mêmes nombres de
  tours (1348/1354), mêmes compteurs de gestion du joker.
- Gain mesuré : marginal (< 1 % du temps total de la partie la plus
  lente), `_coup_sans_rearrangement` ne coûtant qu'environ 1 ms contre
  ~700 ms pour une résolution HiGHS complète — ne corrige PAS le facteur
  10 lui-même (voir §3, intrinsèque au solveur sur un gros plateau).
- **Pistes NON appliquées** (changeraient potentiellement les décisions
  de l'IA, décrites pour qu'Alain décide) : multi-thread HiGHS
  (`threads`/`parallel`, actuellement forcés à 1/`"off"`) pourrait
  accélérer la preuve d'optimalité sans changer le résultat SI l'objectif
  lexicographique élimine déjà toute égalité résiduelle — non vérifié
  avec certitude, donc non appliqué ; autoriser un écart d'optimalité
  (`mip_rel_gap`/`mip_abs_gap`) accélérerait nettement mais changerait
  potentiellement le coup choisi — explicitement exclu par les
  contraintes de l'issue.

## 5. Rapport de calibration plus parlant (`scripts/calibrer_echelle.py`)

- Nouveau fichier par tâche `stats_<label>.jsonl` (une ligne par donne
  jouée, en phase avec `resultats_<label>.jsonl` — même troncature de
  reprise en cas de coupure brutale) : cumule les statistiques que
  `comparer()` calcule déjà (`fins`, `tours_decidees`,
  `temps_par_niveau`) mais que la calibration jetait jusqu'ici.
- Le rapport affiche désormais, sous chaque ligne de résultat, une ligne
  « manches : » avec la durée moyenne des manches (en tours), la
  répartition des fins de manche (chevalet vidé / blocage / pioche vide
  test / garde-fou) et le temps de calcul par tour (moyenne/maximum) de
  chaque niveau — absente (sans erreur) si aucune statistique n'est
  encore disponible (dossier créé avant #257, ou aucune donne jouée).
- Format inchangé pour le reste du rapport (en-tête, lignes de résultat,
  distance Elo, pied de page).

## 6. Mesure finale (Linux, commande de référence de l'issue, seed 31)

- **Avant** : 162,7 s (manches identiques, mêmes coups). D'autres essais
  sur la même graine, avant toute correction, avaient donné 197,8 s et
  216,8 s (voir §3 : variance due au budget de temps du solveur, pas au
  code).
- **Après** (point 4 + point 5 appliqués) : 162,7 s — écart non mesurable
  sur cette partie précise, cohérent avec le gain marginal (< 1 %)
  attendu du seul correctif sûr identifié. Le rapport affiche maintenant
  (nouveauté du point 5) : « manches : 102,5 tour(s) en moyenne ; fins :
  chevalet_vide 50 %, manche_bloquee 50 % ; temps/tour : Avancé moy 651 ms
  max 6017 ms, Intermédiaire moy 936 ms max 4081 ms » — rendant la
  lenteur visible sans nouvelle mesure, comme demandé.

## 7. Tests ajoutés

- `tests/test_niveaux.py::test_coup_sans_rearrangement_calcule_seulement_si_necessaire` :
  vérifie (par un espion sur `_coup_sans_rearrangement`) qu'il n'est PAS
  appelé quand le coup complet tient déjà dans la borne, et qu'il L'EST
  (exactement une fois) en repli — confirmé en échec sur le code d'avant
  la correction, en succès après.
- `tests/test_calibrer_echelle.py` : 5 nouveaux tests — écriture d'une
  ligne de stats par donne jouée (`jouer_tache`), cumul correct sur
  plusieurs donnes (`_agreger_stats_jeu`), troncature en phase avec le
  fichier principal en cas de reprise après coupure brutale
  (`_tronquer_stats_si_necessaire`), absence propre de la ligne « manches
  : » quand aucune statistique n'est disponible, et présence de cette
  ligne dans un rapport complet.

## Fichiers touchés

- `src/rummikub/moteur/ia.py` — `_coup_selon_perturbation` : calcul lazy
  de `_coup_sans_rearrangement` (accélération pure, point 4).
- `scripts/calibrer_echelle.py` — nouveau fichier `stats_<label>.jsonl`
  par tâche, nouvelle ligne « manches : » dans le rapport (point 5).
- `tests/test_niveaux.py`, `tests/test_calibrer_echelle.py` — tests
  ajoutés (point 7).
- `CONTEXTE.md`, `docs/contexte/ia_anti_don_joker.md` (§11) — documentation.
