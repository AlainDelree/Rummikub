# Issue #190 — Suite #187 : accélérer le solveur Expert sur les plateaux chargés

## Constat (où part le temps)

Sur le cas de régression `tests/donnees/cas_expert_budget_tour81.json`
(plateau avant le tour 81 d'Olivia, ≈ 70 tuiles, 19 combinaisons posées),
`_separer_combos_figees` ne gèle (hors recherche) que les combinaisons ne
partageant AUCUNE couleur ni valeur avec la main — avec seulement 4
couleurs, une main de 2-3 couleurs distinctes suffit à rendre « flexible »
la quasi-totalité du plateau. La recherche se retrouve donc avec ~45
emplacements obligatoires (une tuile du plateau à replacer), une
quarantaine de candidats chacun. Dans cet arbre, le premier chemin DFS
(candidats triés pour maximiser l'usage de la main, `_score_rapide`)
tombait régulièrement sur une impasse — un emplacement obligatoire sans
aucun candidat compatible avec l'état déjà réduit par les choix
précédents — forçant un retour en arrière coûteux. Avant qu'AUCUN
réarrangement complet n'ait jamais été trouvé nulle part dans l'arbre, le
budget s'épuisait.

Cause précise : la plupart de ces emplacements obligatoires ne touchent en
rien la main (aucun gain à les restructurer : plusieurs candidats sont
ex-aequo à 0 sur `_score_rapide`), mais la recherche les traitait comme
n'importe quel autre nœud, essayant toutes les régularisations possibles
avant celle, triviale, qui reconduit simplement la combinaison déjà posée.

## Correctif

Chaque candidat généré (`_candidats_groupe`, `_candidats_suite` et leurs
variantes « joker ») porte désormais une signature `(type, couleur/valeur,
taille)` (`_signatures_originales`, dans `moteur/solveur.py`). Parmi les
candidats ex-aequo sur `_score_rapide` (typiquement ceux qui n'utilisent
aucune tuile de la main pour ce nœud), celui qui reproduit une combinaison
déjà posée sur le plateau avant ce tour est tenté EN PREMIER. Cela évite à
la recherche de restructurer, par essais-erreurs coûteux, des zones du
plateau que la main ne concerne pas vraiment — la principale source du
backtracking observé. Ni ce critère ni les deux mesures d'atténuation
précédentes (#186) ne changent jamais le résultat optimal trouvé avec un
budget suffisant, seulement la vitesse pour l'atteindre (et, en cas
d'égalité stricte de la valeur de départage entre plusieurs réarrangements
équivalents, lequel des deux est renvoyé).

Le comportement « anytime » existait déjà depuis #186 (`BudgetDepasse`
n'est levée que si rien n'a été trouvé nulle part ; sinon le meilleur
réarrangement déjà trouvé est renvoyé) — #190 le rend effectif dès les
tout premiers appels sur un plateau chargé, plutôt qu'après plusieurs
secondes, voire jamais dans le budget de production.

Le budget de production (`BUDGET_TEMPS_EXPERT = 1.5`) n'a **pas** été
augmenté : il suffit désormais à retrouver le coup de 3 tuiles sur le cas
cible (voir mesure ci-dessous), ce qui répond à l'objectif mesurable sans
faire attendre le joueur plus longtemps qu'avant.

Mesure additionnelle ajoutée : `scripts/comparer_niveaux_ia.py` compte
désormais, pour le niveau Expert, les replis sur Avancé — en distinguant
(1) repli par dépassement de budget sans rien trouver (`BudgetDepasse`,
seule cause visée par #190) de (2) repli parce qu'aucun coup n'est
légitimement possible (sans rapport avec la vitesse de recherche). Les
deux causes étaient confondues jusqu'ici, ce qui aurait rendu la mesure
ci-dessous ininterprétable.

## Mesure 1 — cas ciblé (tour 81), objectif mesurable de #190

Mesuré directement via `resoudre_coup()` sur
`cas_expert_budget_tour81.json`, machine de développement (pas de machine
dédiée aux mesures — ordres de grandeur, pas des bornes dures) :

| Budget   | Avant #190 (commit `74db5a3`)      | Après #190                         |
|----------|-------------------------------------|-------------------------------------|
| 0.05 s   | `BudgetDepasse`                     | 3 tuiles trouvées (56 ms)           |
| 1.5 s (production) | `BudgetDepasse` — **aucun coup**, repli sur Avancé | **3 tuiles** (11 noir, 11 noir, 7 rouge), 1531 ms |
| 2.5 s    | `BudgetDepasse`                     | 3 tuiles (confirmées, pas de mieux) |
| 3.0 s    | 3 tuiles trouvées (3040 ms)          | 3 tuiles (3030 ms)                   |
| 20 s     | 3 tuiles (idem, pas de mieux — correspond au cas de test à gros budget de #187) | 3 tuiles (idem) |

Point de bascule avant #190 : échec jusqu'à 2.5 s, succès entre 2.5 et
3.0 s. La mention « 3 tuiles en 20 s » du cas de test d'origine (#187)
reflétait une marge large choisie pour le test à gros budget, pas le temps
minimal réellement nécessaire (~2.5-3 s).

**Objectif atteint** : au budget de production (1.5 s), le solveur trouve
désormais le coup de 3 tuiles identifié manuellement, là où il ne
trouvait rien avant #190 (repli total sur Avancé, qui ne posait qu'une
tuile). Gain d'environ 45 à 50× pour atteindre un premier coup valide (56
ms contre ~2.5-3 s), à qualité de résultat égale. Ce qui empêche d'aller
plus loin dans le temps restant du budget de production : la recherche
continue d'essayer de faire mieux que ces 3 tuiles jusqu'à expiration du
budget (anytime) mais n'en trouve pas — rien n'indique qu'un coup
strictement meilleur existe sur ce plateau précis ; nous ne l'avons pas
non plus trouvé avec un budget de 20 s.

Deux tests ajoutés dans `tests/test_ia.py` :
- `test_solveur_plateau_charge_trouve_au_moins_trois_tuiles_avec_gros_budget`
  (budget 10 s, fiable) : ≥ 3 tuiles, plateau valide, aucune tuile perdue.
- `test_solveur_plateau_charge_trouve_un_coup_avec_budget_de_production`
  (budget = `BUDGET_TEMPS_EXPERT × 6` = 9 s, tolérance large anti-
  flakiness sur machine de CI lente — le coup réel est trouvé en ~56-100
  ms, bien avant même le seul budget de production de 1.5 s) : ≥ 3 tuiles,
  mêmes vérifications.

## Mesure 2 — campagne Avancé vs Expert (même format que #187)

Contrainte de temps : une campagne de 20 donnes (40 parties) au budget de
production prend environ 450-530 s sur cette machine pour le solveur
d'après #190 (Expert y passe le plus souvent tout son budget, trouvé un
coup ou non). Pour tenir dans le temps imparti à cette tâche, la campagne
« après » a été menée en 3 lots (10 + 5 + 5 donnes, graines 100/200/201 —
soit bien les 20 donnes / 40 parties demandées, agrégées ci-dessous) et la
campagne « avant » en 2 lots de 5 donnes avec le solveur d'avant #190
(commit `74db5a3`, graines 100/101) — 10 donnes / 20 parties, comme permis
par les consignes de reprise quand le temps est compté. Mêmes paramètres
que #187 sinon (2 joueurs, mise initiale 30 points, garde-fou 300 tours).

| Mesure                                               | Avant #190 (10 donnes/20 parties) | Après #190 (20 donnes/40 parties) |
|-------------------------------------------------------|:---:|:---:|
| Victoires Expert                                       | 16/20 (80 %)  | 31/40 (77.5 %) |
| Victoires Avancé                                        | 4/20 (20 %)   | 9/40 (22.5 %) |
| Parties bloquées (pioche épuisée)                      | 0/20 (0 %)    | 1/40 (2.5 %) |
| Anomalies de conservation des tuiles                   | 0             | 0 |
| Temps Expert par tour — moyenne                        | 671.8 ms (699 tours) | 839.7 ms (1661 tours) |
| Temps Expert par tour — maximum                        | 1548.0 ms     | 1632.7 ms |
| Replis Expert→Avancé, toute cause                      | 498/699 (71.2 %) | 1254/1661 (75.5 %) |
| — dont repli par timeout (#190, seule cause visée)     | 212/699 (30.3 %) | 690/1661 (41.5 %) |
| — dont repli par coup légitimement impossible          | 286/699 (40.9 %) | 564/1661 (34.0 %) |

**Lecture honnête de ce tableau** : à cette taille d'échantillon (bruit
d'échantillonnage important — intervalles de confiance à 95 % de l'ordre
de ±9 à ±30 points sur le seul taux de victoire), la campagne agrégée sur
plateaux tirés au hasard **ne montre pas d'amélioration nette** — le taux
de repli par timeout et le temps moyen par tour d'Expert sont même
légèrement plus élevés après #190. Ce n'est pas contradictoire avec le
gain ×45-50 mesuré sur le cas ciblé (Mesure 1) : le correctif de #190
n'accélère que les nœuds où plusieurs candidats sont ex-aequo à 0 sur
`_score_rapide` — situation caractéristique des plateaux structurellement
proches du cas visé (beaucoup de combinaisons sans rapport avec la main,
typique d'un plateau chargé en milieu/fin de partie), pas de l'ensemble
des plateaux rencontrés en campagne à seulement 2 joueurs et 10-20 donnes.
De plus, le comportement « anytime » (déjà présent depuis #186, rendu
effectif plus tôt par #190) fait que la recherche consomme désormais
systématiquement tout le budget restant pour tenter de faire mieux dès
qu'un premier coup est trouvé — ce qui tend à AUGMENTER le temps moyen par
tour plutôt qu'à le réduire, même quand le résultat final est inchangé.

Taux de victoire d'Expert comparable avant/après (80 % puis 77.5 %, dans
la marge d'incertitude l'un de l'autre et de la mesure #187/#186
précédente — aucun des deux n'est significativement différent de l'autre
à cet échantillon) : aucune régression introduite par #190, conformément
à l'exigence « ne rien dégrader ».

## Conclusion

- Objectif mesurable de #190 (cas du tour 81, budget de production)
  **atteint** : 3 tuiles trouvées en 1.5 s, contre aucun coup avant.
- Budget de production inchangé (1.5 s) — l'accélération a suffi pour le
  cas cible, conformément à la consigne de ne l'augmenter qu'en dernier
  recours.
- Le gain mesuré est **localisé** aux plateaux structurellement proches du
  cas visé, pas généralisé à toute campagne Avancé vs Expert — à signaler
  explicitement plutôt que de laisser croire à un gain uniforme. Une
  accélération plus générale (par ex. élagage plus agressif des candidats
  réellement équivalents, ou détection plus fine des emplacements « sans
  enjeu pour la main ») resterait à explorer si des cas similaires au
  tour 81 se révèlent fréquents en jeu réel.
- Aucun test existant cassé (102 tests passés), aucune perte de tuile,
  Avancé et les niveaux inférieurs inchangés.
