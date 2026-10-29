# Issue #211 — Expert : évaluer la main restante pour départager les coups à nombre de tuiles posées égal (suite de #199)

À nombre de tuiles posées **égal**, Expert départageait jusqu'ici par
perturbation minimale du plateau (#199), puis points posés, puis économie de
jokers — sans jamais regarder ce qui reste dans sa main. Cette issue ajoute une
**évaluation de la main restante** (doublons, tuiles de bord, points restants
selon le nombre de manches) **intégrée au modèle exact** (`moteur/solveur_exact.py`,
HiGHS, #206) comme objectif secondaire linéaire — jamais avant le nombre de
tuiles posées — puis la **mesure critère par critère** par simulation.

**Résultat de la mesure (30 donnes = 60 matchs en miroir, seed 42) : aucun
critère ne produit de gain significatif** (tous les écarts restent dans la marge
d'erreur ±12,6 pt). Conformément au point 4 de l'issue, **l'évaluation est donc
livrée DÉSACTIVÉE par défaut** ; tout le mécanisme est en place, réglable en un
seul endroit, et réactivable si une campagne plus large démontrait un gain.

## Changements

### 1. Évaluation de la main — `moteur/evaluation_main.py` (nouveau)

Fonction **indépendante du solveur** `evaluer_main(tuiles, config)` renvoyant une
pénalité (plus basse = meilleure main), et **tous les poids réglables réunis en
tête de module** (point 4). Trois critères + deux cas traités à part :

- **Doublons** : pénalité par paire identique restante (deux tuiles de même
  valeur et couleur ne peuvent jamais entrer dans la même combinaison).
- **Tuiles de bord** : pénalité **graduée** `penalite_bord(v) = 3 − nb_suites_trois(v)`
  → 2 pour 1/13, 1 pour 2/12, 0 pour 3–11 (un bord entre dans moins de suites
  de trois).
- **Points restants** : poids **nul en 1 manche** (`POIDS_POINTS_1_MANCHE = 0`),
  **non nul à partir de 2** (`POIDS_POINTS_N_MANCHES = 1`), car les points
  s'accumulent alors au score cumulé (#203).
- **Tuiles isolées** : calculées par `tuiles_isolees()` pour les tests et
  l'affichage, mais **laissées de côté dans le solveur** (`POIDS_ISOLEE = 0`) :
  elles ne se linéarisent pas simplement (dépendent du reste de la main, pas
  seulement des tuiles posées). Approximation documentée (en-tête du module).
- **Jokers** : traités à part (`POIDS_JOKER = 0`) — un joker en main est une
  ressource, et l'économie de jokers **posés** est déjà un critère du solveur.

`ConfigEvaluation` (dataclass gelée) porte les critères actifs, les poids et la
position vs la simplicité ; `depuis_preset(nom, nb_manches)` fabrique les
réglages nommés de la simulation.

### 2. Intégration au modèle exact — `moteur/solveur_exact.py`

L'évaluation n'est **pas** un tri après coup : elle est **linéarisée** sur les
tuiles qui resteraient en main et ajoutée comme **passe d'optimisation
lexicographique**, toujours **après** la passe du nombre de tuiles posées (fixé
par une contrainte d'égalité avant toute passe de départage) :

- bords/points → termes `Σ_s (W_bord·pbord_s + W_points·preal_s) x_s`
  (poser une tuile retire sa pénalité de la main) ;
- doublons → **variable auxiliaire** `d_i ∈ [0,1]` par type présent ≥ 2 fois en
  main, avec `d_i + Σ_s a_{s,i} x_s ≥ t_i + r_i − 1` (vaut 1 ssi les deux
  exemplaires restent), pénalisée dans l'objectif. Coefficients **entiers** →
  départage exact (pas d'arrondi), comme les autres critères.

**Position testée dans les deux ordres** (point 2) : `apres_simplicite` (défaut
— ne complique jamais le plateau pour un gain d'évaluation) et `avant_simplicite`
(suffixe `-avant`). Quand l'évaluation est **inactive** (défaut), le solveur
départage **exactement comme avant #211** (simplicité → points posés → jokers) :
comportement et temps de production strictement inchangés.

### 3. Mesure par simulation — `scripts/comparer_niveaux_ia.py`

Nouvelles options `--eval-a` / `--eval-b` : appliquent un preset d'évaluation à
l'Expert de chaque camp, pour comparer **deux réglages d'Expert en miroir** dans
une même campagne (le reste strictement identique). Presets : `off`, `complet`,
`doublons`, `bords`, `points`, `points-nul|faible|moyen|fort`, suffixe
`-avant`/`-apres`.

**Résultats chiffrés complets dans `CONTEXTE.md` §13.** En résumé (camp A = `off`
de référence, camp B = variante ; 60 matchs ; marge ±12,6 pt) :

| Variante (camp B)     | 1 manche — victoires B | 3 manches — victoires B |
|-----------------------|:----------------------:|:-----------------------:|
| doublons              | 46,7 %                 | —                       |
| bords                 | 48,3 %                 | —                       |
| complet               | 46,7 %                 | 48,3 %                  |
| complet (ordre avant) | 48,3 %                 | —                       |
| points-nul            | —                      | 46,7 %                  |
| points-faible         | 48,3 %                 | 45,0 %                  |
| points-moyen          | —                      | 46,7 %                  |
| points-fort           | —                      | 46,7 %                  |

**Aucun écart significatif** (tous à moins de 12,6 pt de 50/50). **Points
contre-productifs ?** Dans cet échantillon, aucun poids (0 → 8) ne fait bouger le
taux de victoire hors du bruit ; le poids fort ne dégrade pas les victoires
(46,7 % = poids nul) et améliore légèrement la marge de score cumulé (déficit
−2,2 à poids nul → −1,0/−1,1 à poids moyen/fort). **Aucun seuil de bascule n'est
atteint jusqu'au poids 8** : l'effet reste sous le plancher de bruit à 30 donnes.
Cause probable : le modèle exact vide déjà les chevalets très vite (180/180
manches terminées chevalet vidé, **0 bloquée**) — quand personne n'est bloqué, la
qualité de la main restante départage rarement le vainqueur.

**Temps de calcul** : l'évaluation ajoute une passe MIP sur le même petit modèle.
Sur les positions typiques ≈ +10 % ; sur les cas de référence les plus lourds
≈ +30 % (530 → 687 ms/coup), toujours **sous le budget de 1,5 s**. Désactivée par
défaut, elle n'ajoute **aucun** temps en production.

### 4. Adoption

`moteur/ia.EVAL_MAIN_DEFAUT = evaluation_main.DEFAUT` avec `active=False` :
**évaluation désactivée par défaut** (aucun gain démontré). Réactivation et
réglage des poids en un seul endroit (`moteur/evaluation_main.py`).

### 5bis. Journal : mécanisme décideur d'Expert

À chaque coup d'une IA Expert, `jouer_niveau_expert` annote le coup du mécanisme
qui a décidé (`moteur/ia.SOLVEUR_EXACT|RECHERCHE|AVANCE`) et `logger_action` écrit
une **clé facultative `solveur`** dans le journal (omise pour les humains et les
autres niveaux — rétrocompatible). Le repli étant silencieux quand
`highspy`/`numpy` manquent, on peut désormais savoir, en lisant un journal, si
Expert a joué avec le modèle exact ou s'est replié. `scripts/analyser_coups_rates.py`
**affiche la répartition** des mécanismes (modèle exact / recherche de repli /
Avancé en repli / non noté) et signale la présence de coups en repli.

### 6. Tests — `tests/test_evaluation_main.py` (nouveau)

19 tests : évaluation sur mains fabriquées (doublons, bords 1/13 vs 2/12 vs
milieu, isolées, joker), poids des points selon le nombre de manches, **propriété
« l'évaluation ne change jamais le nombre de tuiles posées »** (positions
fabriquées + tous les cas de référence, tous presets), départage effectif
(exemple d'Alice : suite 1-2-3 rouge préférée au groupe pour écouler un doublon
et un bord), et annotation `solveur` du journal (5bis).

## Fichiers touchés

- **Nouveau** : `src/rummikub/moteur/evaluation_main.py`, `tests/test_evaluation_main.py`.
- **Modifiés** : `moteur/solveur_exact.py` (passe d'évaluation + doublons),
  `moteur/ia.py` (réglage par défaut, annotation du solveur, fil `eval_config`),
  `persistance/journal.py` (clé `solveur`), `ui/api.py` (transmet le solveur au
  journal), `persistance/coups_rates.py` (`repartition_solveurs`),
  `scripts/comparer_niveaux_ia.py` (`--eval-a/-b`),
  `scripts/analyser_coups_rates.py` (affichage de la répartition), `CONTEXTE.md`
  (§13).

## Ne dégrade pas

Les 252 tests existants passent, tous les cas de référence (`cas_expert_*.json`)
conservent leur nombre de tuiles pour **tous** les presets d'évaluation, Avancé
et les niveaux inférieurs sont inchangés, le budget de production n'est pas
modifié (évaluation désactivée par défaut).
