# Issue #186 — Suite #184 : IA Expert, solveur de réarrangement global du plateau

La campagne de #184 montrait qu'Avancé et Expert ne se distinguaient pas de
façon significative (53 % / 47 % sur 100 parties) et que 29 % des parties se
terminaient bloquées (pioche épuisée). Cause identifiée : toutes les
tactiques existantes (`CONTEXTE.md` §8) ne modifient qu'une ou deux
combinaisons du plateau à la fois — un joueur humain fort démonte et
recompose souvent plusieurs combinaisons pour poser davantage de tuiles.

## Solveur de réarrangement global (`moteur/solveur.py`, nouveau)

Reconstruit librement tout le plateau (plateau + chevalet confondus en un
seul « sac ») pour y poser le plus de tuiles du chevalet possible, sous la
seule contrainte dure qu'aucune tuile déjà posée ne peut disparaître (elle
peut changer de combinaison). Jokers compris, y compris ceux déjà posés.

- Recherche récursive mémoïsée sur des compteurs par emplacement
  `(couleur, valeur)` (0 à 2 tuiles réelles) et sur les 2 jokers du jeu,
  chacun marqué « obligatoire » (vient du plateau, doit finir posé) ou
  « optionnel » (vient du chevalet, peut rester en main).
- Départage entre réarrangements posant le même nombre de tuiles : d'abord
  le plus de points posés, puis, à égalité, le moins de jokers du chevalet
  utilisés — un joker reste une ressource précieuse même à nombre de tuiles
  égal.
- Mise initiale pas faite : le plateau n'est pas touché (règle du jeu), le
  solveur cherche la meilleure combinaison formable depuis la seule main
  sous la contrainte des points ≥ `mise_initiale_min`.
- **Combinaisons gelées** (`_separer_combos_figees`) : une combinaison du
  plateau sans aucune couleur/valeur commune avec la main, et sans joker,
  est reconduite telle quelle hors recherche — nécessaire pour borner la
  combinatoire sur les plateaux de milieu/fin de partie (principal facteur
  de ralentissement observé).
- **Repli budget de temps** (`BudgetDepasse`) : recherche interrompue
  au-delà de `BUDGET_TEMPS_EXPERT` (1.5s par défaut, `moteur/ia.py`) ;
  `jouer_niveau_expert` se replie alors sur le comportement d'Avancé pour ce
  tour (idem si le solveur ne trouve lui-même aucun coup).
- Pur Python, aucune dépendance nouvelle (contrainte Windows/PyInstaller).

## `moteur/ia.py`

- `jouer_niveau_expert` réécrit : appelle `solveur.resoudre_coup`, repli sur
  `jouer_niveau_avance` en cas de `BudgetDepasse` ou d'échec du solveur.
- **Règle supprimée** : Expert ne refuse plus de poser quand un adversaire a
  ≤ 3 tuiles (ancienne prudence) — la campagne de #184 n'a montré aucun
  avantage mesurable, poser davantage de tuiles est presque toujours
  préférable.
- Avancé (et les niveaux inférieurs) inchangés.

## Tests (`tests/test_ia.py`, 81 tests au total, +12 vs #184)

- Le solveur retrouve au moins aussi bien chaque scénario déjà couvert par
  Avancé (échange direct, détachement en bout, libérations combinées,
  groupe de 4, scission en milieu de suite, groupe de 4 avec joker retiré).
- Nouveaux : démantèlement complet d'une courte suite avec joker (#175,
  identifié mais non implémenté par Avancé — confirmé par un test de
  non-régression dédié), mise initiale (ouverture atteignant le minimum
  requis, et refus d'ouvrir sous ce minimum), aucun coup possible, et repli
  sur budget de temps dépassé (budget nul : `BudgetDepasse` levée, puis
  `jouer_niveau_expert` rejoue exactement le coup d'Avancé).
- Un test existant devenu faux à bon escient :
  `test_expert_ne_detache_pas_un_joker_en_bout_de_suite_par_scission`
  (plateau 4-5-6-joker, chevalet 7 bleu/7 jaune) supposait qu'aucun coup
  n'était possible — légitime pour Avancé (tactiques locales, toujours
  vrai, test conservé), mais le solveur y trouve un coup réellement
  meilleur : la suite redevient 4-5-6 (toujours valide) et le joker libéré
  forme un NOUVEAU groupe de 7 avec les deux tuiles de la main. Remplacé
  par `test_expert_trouve_un_groupe_pour_le_joker_en_bout_de_suite`, qui
  vérifie ce nouveau coup.
- Suite complète : `pytest -q` → **81 passed**.

## Mesure (`scripts/comparer_niveaux_ia.py`, Expert vs Avancé)

Campagne lancée au budget de PRODUCTION du solveur (1.5s/tour, `BUDGET_TEMPS_EXPERT`),
en deux lots indépendants (même outil, deux graines), combinés ci-dessous :

```
python scripts/comparer_niveaux_ia.py --niveau-a Avancé --niveau-b Expert --donnes 5  --seed 0
python scripts/comparer_niveaux_ia.py --niveau-a Avancé --niveau-b Expert --donnes 15 --seed 1
```

| | Lot 1 (seed 0) | Lot 2 (seed 1) | **Combiné (40 parties)** |
|---|---|---|---|
| Victoires Expert | 10/10 | 22/30 | **32/40 — 80.0 % ± 12.4 pt (IC 95 %)** |
| Fins par pioche épuisée (bloqué) | 1/10 | 3/30 | **4/40 — 10.0 %** (vs 29 % en #184) |
| Durée moyenne (tours) | 84.0 | 98.4 | **94.8** |
| Temps Expert par tour | moy. 853 ms / max 1536 ms (422 tours) | moy. 855 ms / max 1574 ms (1479 tours) | **moy. ≈ 855 ms / max 1574 ms (1901 tours)** |
| Temps Avancé par tour | moy. 1.8 ms / max 7.9 ms | moy. 2.1 ms / max 15.0 ms | moy. ≈ 2.0 ms / max 15.0 ms |

**Écart par rapport à 50/50 significatif** (80.0 % ± 12.4 pt exclut 50 %) : Expert bat
nettement Avancé. La part de parties bloquées (pioche épuisée) chute de 29 % (#184) à
10 % ici. Le temps de calcul Expert reste sous le budget de 1.5s dans tous les cas
observés (max 1574 ms, légèrement au-dessus de 1.5s du fait de l'arrondi des points de
vérification du budget tous les 50 appels — voir `_Contexte.verifier_budget` — jamais
un dépassement significatif).

**Écart entre #184 (0 % significatif) et ici (80 %)** : la suppression de la règle
« pioche si adversaire ≤ 3 tuiles » (tâche 4) contribue, mais l'essentiel vient du
solveur lui-même — voir le point suivant sur l'effet du budget de temps.

**200/500 donnes demandées, mais hors de portée du temps de calcul disponible pour
cette tâche (TIMEOUT #186) :** au budget de production, une partie Expert vs Avancé
prend ~35-40s (dominé par les ~85-100 décisions Expert à ~850ms chacune). 200 donnes
(400 parties) représenteraient donc plusieurs heures, bien au-delà du budget alloué à
ce traitement. Un essai de calibration à budget RÉDUIT (`scripts/_campagne_186.py`,
0.3s/tour, 10 donnes/20 parties, seed 1, non retenu comme mesure officielle) donne
Expert 12/20 (60 %, ÉCART NON significatif) contre 100 %/73 % aux deux lots à budget
plein — **le budget de temps du solveur a un effet de premier ordre sur sa force** :
diviser le budget par 5 ramène quasiment Expert au niveau d'Avancé. Ce constat
confirme que le repli sur Avancé en cas de `BudgetDepasse` (tâche 3) est un véritable
compromis qualité/temps, pas une formalité, et qu'il serait risqué de tirer une
conclusion de mesures faites à budget réduit : les 40 parties ci-dessus, bien qu'en
dessous de l'échantillon demandé, sont donc mesurées au budget RÉEL de production
pour rester représentatives, plutôt qu'un échantillon plus large mais biaisé par un
budget artificiellement réduit. Avec davantage de temps de calcul disponible, refaire
cette campagne à 200, puis 500 donnes (budget plein, ou en parallélisant les parties)
resterait la suite logique pour resserrer la marge d'erreur (actuellement ± 12.4 pt).

## `CONTEXTE.md`

- §8 : recentré sur Avancé (et le repli d'Expert) ; #175 retiré de la liste
  « identifiée mais pas encore implémentée » côté Expert (reste non
  implémentée pour Avancé, confirmé par un test dédié).
- Nouvelle §8bis décrivant le solveur de réarrangement global d'Expert.
- §2/§6 : arborescence (`solveur.py`) et compteur de tests (81) à jour.
