# Issue #199 — Suite #194 : Expert, à nombre de tuiles posées égal, préférer le coup le plus simple

Cas réel (David, tour 31) : l'IA avait une seule tuile à poser (1 noir), que
le plateau permettait d'ajouter directement au groupe de 1 (rouge, bleu,
jaune) déjà posé pour en faire un groupe de 4 couleurs en un seul geste.
Expert avait pourtant joué ce coup en 12 étapes de pas-à-pas : plusieurs
combinaisons défaites et recréées, pour poser au final la même seule tuile.
Cause : le solveur (`moteur/solveur.py`) cherchait le plus grand nombre de
tuiles posées puis départageait par points/jokers, sans jamais regarder
combien de tuiles du plateau étaient déplacées — parmi toutes les solutions
posant une tuile, il pouvait renvoyer n'importe laquelle.

0. **Mesure de perturbation** `(tuiles_déplacées, combinaisons_modifiées)`,
   calculée directement sur les compteurs par emplacement de la recherche
   (`_perturbation_candidat`), sans reconstruire le plateau concret : nulle
   si un candidat n'utilise aucune tuile du plateau, ou si les tuiles du
   plateau qu'il utilise reproduisent EXACTEMENT une combinaison déjà posée
   avant ce tour (il ne fait qu'ajouter des tuiles de la main à cette
   combinaison, ou la reconduire à l'identique) ; non nulle sinon
   (fragmente ou fusionne des combinaisons existantes). Deux tuiles de même
   aspect (même valeur, même couleur, ou deux jokers quelconques) sont
   interchangeables, comme pour le pas-à-pas (#197). `mesurer_perturbation`
   (API publique de `solveur.py`) calcule la même mesure sur un plateau
   avant/après concret — utilisée par les tests et par
   `scripts/comparer_niveaux_ia.py`, jamais par la recherche elle-même.
1. **Nouveau critère de départage** : nombre de tuiles posées, puis
   perturbation minimale, puis points posés, puis économie de jokers
   (`_meilleur_rearrangement`). Réglage `preferer_simple`
   (`solveur.PREFERER_SIMPLICITE`, activé par défaut), exposé en paramètre
   de `resoudre_coup` et `jouer_niveau_expert` pour comparer les deux
   versions par simulation.
2. **Recherche des coups simples d'abord** : dans le tri des candidats
   (`_resoudre`), la perturbation REMPLACE — plutôt que de s'ajouter à —
   le critère de signature d'origine (#190) parmi les ex-aequo sur
   `_score_rapide`. La signature (forme + taille seulement, pas la
   composition exacte) aurait sinon fait gagner, par coïncidence de forme,
   un candidat qui FRAGMENTE une combinaison d'origine (même signature que
   l'original) sur celui qui l'ÉTEND proprement — exactement le bug
   observé (un groupe de 1 à 3 couleurs, signature identique qu'il soit
   fragmenté en 2 + une tuile de la main ou étendu à 4 couleurs). Mesuré
   sur un cas déjà difficile pour la recherche
   (`cas_expert_ia_261026172338_tour61.json`, cascade de jokers à travers
   tout le plateau, #194) : AJOUTER la perturbation en plus de la
   signature (sans même réordonner), même optimisée pour un coût minimal
   par candidat (frozenset plutôt qu'un tri, calcul unique partagé entre
   le tri et l'application), suffisait déjà à faire manquer, à budget
   identique, le palier que l'ancien comportement trouvait de justesse —
   ce cas est nativement sans la moindre marge pour un coût supplémentaire
   par nœud de recherche. REMPLACER la signature (plutôt que l'additionner)
   évite ce coût tout en corrigeant le cas de David.
3. **Limite documentée** : un candidat qui ne reconstitue qu'une FRACTION
   d'une combinaison d'origine (celle-ci ayant été fragmentée entre
   plusieurs candidats) compte sa propre perturbation indépendamment de
   l'autre fragment — peut compter deux combinaisons modifiées là où un
   œil humain n'en verrait qu'une scindée en deux, sans jamais fausser la
   distinction nulle/non-nulle qui est l'essentiel de ce critère pour le
   départage et la recherche.

## Cas de test (`tests/test_ia.py`)

- `test_solveur_coup_simple_trouve_et_retient_le_coup_sans_perturbation` :
  cas réel de David (`tests/donnees/cas_expert_coup_simple_david_
  tour31.json`) — le solveur trouve au moins la tuile attendue ET une
  solution qui ne touche qu'une seule combinaison, sans déplacer aucune
  tuile du plateau.
- `test_solveur_departage_petit_plateau_fabrique_prefere_la_solution_simple` :
  plateau minimal fabriqué (réduit du cas réel par dichotomie — un groupe
  de 1 et une suite jaune 2-4, main = 1 noir + 12 jaune sans rapport, qui
  rend la suite jaune « flexible » pour la recherche et crée ainsi une
  vraie égalité entre une solution simple et une solution qui fragmente le
  groupe) où le critère doit retenir la solution simple ; vérifie aussi que
  désactiver le critère retrouve l'ancienne solution plus compliquée, pour
  prouver que l'égalité construite est réelle.
- `test_preferer_simple_ne_pose_jamais_moins_de_tuiles_au_budget_de_
  production` (paramétré sur `cas_expert_budget_tour81.json`,
  `cas_expert_bruno_tour57.json`, `cas_expert_humain_*`,
  `cas_expert_ia_261026172338_tour37/59.json`) et
  `test_preferer_simple_atteint_le_meme_plafond_sur_le_cas_le_plus_dur`
  (`cas_expert_ia_261026172338_tour61.json`, à budget large) : non-
  régression — le nouveau critère ne pose jamais moins de tuiles que
  l'ancien comportement. Le cas `tour61` est testé séparément à budget
  large (12s) plutôt qu'au budget de production : il est structurellement
  instable à ce budget (le solveur n'y trouve souvent rien en 1.5s, avec
  ou sans le nouveau critère, déjà avant #199), une comparaison stricte à
  budget de production y serait un test intrinsèquement flaky, pas une
  mesure de régression.

Tous les cas de référence déjà existants continuent de passer sans
changement de temps notable. 164 tests passent au total (`pytest -q`).

## Mesure (campagne Avancé vs Expert, `scripts/comparer_niveaux_ia.py`)

10 donnes x 2 (miroir) = 20 parties, seed 42, budget de production (1.5s) :

| | AVEC le critère (défaut) | SANS le critère |
|---|---|---|
| Victoires Expert | 19/20 — 95.0 % ± 9.6 pt (IC 95 %) | 16/20 — 80.0 % ± 17.5 pt (IC 95 %) |
| Perturbation moyenne / coup Expert | 2.43 tuile(s) déplacée(s), 2.19 combo(s) modifiée(s) | 3.00 tuile(s) déplacée(s), 2.63 combo(s) modifiée(s) |
| Temps moyen / tour Expert | 204.0 ms (max 1559.7 ms) | 221.3 ms (max 1535.1 ms) |
| Replis sur Avancé (faute de budget) | 0.6 % des tours Expert | 1.5 % des tours Expert |

Les deux intervalles de confiance se recoupent largement (échantillon
réduit, comme pour #190/#194) : l'écart de taux de victoire n'est pas
démontrable à ce niveau, mais il n'y a AUCUNE baisse — le but affiché par
la tâche (ne pas perdre de force, pas forcément en gagner) est atteint. La
perturbation moyenne baisse nettement, conformément à l'objectif. Le temps
de calcul et le taux de repli restent comparables (légèrement meilleurs
avec le critère). Le critère reste donc activé par défaut
(`PREFERER_SIMPLICITE = True`).

## Documentation

`CONTEXTE.md` §8bis (nouvelle puce sur le critère de simplicité, avec le
détail technique et les chiffres de la campagne) et §13 (piste cochée :
« complexifier le plateau n'a pas de bénéfice stratégique démontré, la
simplicité est désormais un critère mesuré »).

## Fichiers modifiés

- `src/rummikub/moteur/solveur.py` : mesure de perturbation
  (`_perturbation_candidat`, `_aspects_plateau_candidat`,
  `_multisets_originaux`, `_cle_multiset`), nouveau critère de départage
  (`_meilleur_rearrangement`, `_Contexte`), tri des candidats modifié
  (`_resoudre`), API publique `mesurer_perturbation`, constante
  `PREFERER_SIMPLICITE`, paramètre `preferer_simple` sur `resoudre_coup`.
- `src/rummikub/moteur/ia.py` : paramètre `preferer_simple` sur
  `jouer_niveau_expert` (lu depuis `solveur.PREFERER_SIMPLICITE` par
  défaut, comme `budget_temps`).
- `scripts/comparer_niveaux_ia.py` : drapeau `--sans-preferer-simple`,
  mesure et affichage de la perturbation moyenne par coup d'Expert.
- `tests/test_ia.py` : 5 nouveaux tests (voir ci-dessus).
- `CONTEXTE.md` : §8bis et §13.
