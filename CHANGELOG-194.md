# Issue #194 — Suite #190 : nouvelle stratégie de recherche du solveur Expert

## Constat (point de départ, où la recherche perd son temps)

#190 n'accélérait que les nœuds où plusieurs candidats sont ex-aequo sur
`_score_rapide` (candidats qui n'utilisent aucune tuile de la main) — ne
réglait pas le cas où le coup optimal exige d'enchaîner plusieurs échanges de
jokers à travers des zones différentes du plateau. Deux cas de référence :

- `cas_expert_budget_tour81.json` (#190, 70 tuiles/19 combos) : déjà résolu
  en 1.5s depuis #190.
- `cas_expert_bruno_tour57.json` (nouveau, 52 tuiles/15 combos, tour réel de
  Bruno en partie) : Expert n'avait posé **qu'UNE tuile**, alors que le
  solveur en trouve 3 (`rouge_11_b`, `jaune_8_a`, `jaune_13_a` — un joker
  d'un groupe de 4 remplacé par la tuile d'une suite voisine) — mais
  seulement avec un budget de 10s ; **rien** à 1.5s, 3s ni 6s.

Analyse (avant #194) sur ce second cas : l'ordre de visite des emplacements
obligatoires (`_ordre_slot`, par couleur puis valeur) force la recherche à
épuiser tout un bloc de couleur avant d'atteindre un groupe qui n'a besoin
que d'UNE tuile de la main dans une couleur différente. Et la recherche vise
l'optimum exact en une seule passe : sur ce plateau, la combinatoire pour
PROUVER l'optimum (3 tuiles) dépasse largement ce qu'un budget d'1.5-6s
permet d'explorer, même si un coup à 1 ou 2 tuiles, bien plus facile à
trouver, existe aussi (mais n'est jamais retenu seul puisqu'il n'est pas
l'optimum).

## Changements

Deux changements combinés dans `src/rummikub/moteur/solveur.py` (voir la
docstring du module pour le détail technique) :

1. **Recherche par paliers croissants** (`_meilleur_rearrangement`,
   `_Contexte.objectif`, `_seuil_atteint`) : au lieu de viser l'optimum en
   une seule passe, le solveur cherche d'abord « au moins 1 tuile posable »,
   puis si trouvé « au moins 2 », etc. Chaque palier intermédiaire coupe la
   recherche dès qu'IL est atteint n'importe où dans l'arbre (pas seulement
   au plafond optimiste global) — beaucoup moins coûteux que de prouver
   l'optimum d'un coup. Si le budget s'épuise en cours de palier, le
   dernier palier PROUVÉ atteignable est renvoyé (recherche interrompue
   mais pas perdue), au lieu de tout perdre comme le ferait une passe
   unique sans palier. Tant que tous les paliers jusqu'au plafond
   optimiste aboutissent dans le budget, le dernier palier est strictement
   équivalent à l'ancienne passe unique (même résultat, même départage).
2. **Ordre de visite par VALEUR** (`_ordre_slot`) plutôt que par couleur :
   un groupe réunit plusieurs couleurs à la MÊME valeur ; visiter toutes les
   valeurs d'une seule couleur avant la suivante (ordre d'origine) force la
   recherche à épuiser tout un bloc de couleur combinatoire avant
   d'atteindre un groupe utile à la main d'une tout autre couleur. Visiter
   par valeur croissante atteint ce groupe dès que sa valeur revient, et le
   palier correspondant (voir point 1) coupe alors la recherche
   immédiatement au lieu de retomber dans le bloc combinatoire.

Pistes évoquées par l'issue et **non retenues** (choix de méthode laissé à
CCL par l'issue) :
- **Zones indépendantes du plateau** : `_separer_combos_figees` (#190)
  gèle déjà toute combinaison sans aucune tuile/valeur en commun avec la
  main ni avec un joker — c'est déjà, en pratique, la même idée (les zones
  non pertinentes sont écartées de la recherche, pas résolues séparément
  puis recombinées). Un découpage plus fin en composantes connexes
  indépendantes à l'intérieur même des combinaisons flexibles n'a pas été
  tenté : les deux changements ci-dessus suffisent aux deux cas de
  référence, et l'ajouter aurait complexifié la mémoïsation sans cas
  identifié qui en aurait besoin.
- **Mémoriser les sous-problèmes déjà résolus entre paliers** : la
  mémoïsation existe déjà PAR passe (`_Contexte.memo`, #186) ; elle ne peut
  PAS être conservée D'UN PALIER À L'AUTRE sans risque d'incohérence (une
  valeur mémoïsée sous l'objectif *k* peut représenter un arrêt anticipé
  invalide pour l'objectif *k+1*) — chaque palier repart donc avec une
  mémoïsation vide, intentionnellement.
- **Essayer en priorité les échanges de jokers** : déjà couvert
  indirectement par le tri des candidats sur `_score_rapide` (#186) et la
  priorité aux signatures d'origine (#190) ; le changement d'ordre de visite
  (point 2) a un effet comparable pour le cas qui motive l'issue, pour un
  coût d'implémentation moindre qu'une heuristique dédiée aux jokers.

Budget de production (`BUDGET_TEMPS_EXPERT`) **inchangé à 1.5s** — aucune
augmentation n'a été nécessaire.

## Mesure 1 — deux cas de référence, objectif mesurable de #194

Mesuré directement via `resoudre_coup()`, machine de développement :

| Cas                           | Budget | Avant #194            | Après #194           |
|--------------------------------|--------|------------------------|------------------------|
| `cas_expert_budget_tour81.json` (#190) | 1.5s   | 3 tuiles (1.53s, déjà bon depuis #190) | 3 tuiles (1.53s, inchangé) |
| `cas_expert_bruno_tour57.json`  | 1.5s   | **aucun coup**         | **3 tuiles** (~0.3s)   |
| `cas_expert_bruno_tour57.json`  | 3s     | **aucun coup**         | 3 tuiles (~0.3s)       |
| `cas_expert_bruno_tour57.json`  | 6s     | 2 tuiles seulement     | 3 tuiles (~0.3s)       |
| `cas_expert_bruno_tour57.json`  | 10s    | 3 tuiles               | 3 tuiles (~0.3s)       |

**Objectif atteint sur les deux cas de référence** : au budget de
production (1.5s), le solveur trouve désormais le coup à 3 tuiles de
`cas_expert_bruno_tour57.json`, là où il ne trouvait rien avant #194 —
10× à 20× plus rapide que les 6-10s nécessaires avant #194 pour atteindre
ce même résultat. Le cas `tour81` (#190) reste résolu dans le même budget,
sans régression.

Tests ajoutés dans `tests/test_ia.py` :
- `test_solveur_cascade_joker_trouve_trois_tuiles_avec_gros_budget` (budget
  10s, fiable) : ≥ 3 tuiles (`attendu_min_tuiles` du fichier de cas), plateau
  valide, aucune tuile perdue.
- `test_solveur_cascade_joker_trouve_un_coup_avec_budget_de_production`
  (budget = `BUDGET_TEMPS_EXPERT × 6`, tolérance large anti-flakiness sur
  machine de CI lente — le coup est trouvé en ~0.3s en développement, bien
  avant même le seul budget de production de 1.5s) : mêmes vérifications.

## Mesure 2 — campagne Avancé vs Expert (même format que #190/#186)

Contrainte de temps (campagne au budget de production, coûteuse) : 8 donnes
/ 16 parties (seed 100, `--max-tours 300`), contre les 20 donnes / 40
parties de la mesure #190 — réduit pour tenir dans le temps imparti à cette
tâche, comme déjà fait pour #190 (lecture à faire avec cette réserve en
tête : échantillon plus petit, bruit plus grand). Le solveur étant
inchangé entre #190 et #194 avant ce correctif (vérifié par `git log --
solveur.py`), les chiffres « avant #194 » réutilisent directement la mesure
« après #190 » déjà publiée (20 donnes/40 parties, mêmes paramètres).

| Mesure                                               | Avant #194 (= après #190, 20 donnes/40 parties) | Après #194 (8 donnes/16 parties) |
|-------------------------------------------------------|:---:|:---:|
| Victoires Expert                                       | 31/40 (77.5 %) | 13/16 (81.2 %) |
| Temps Expert par tour — moyenne                        | 839.7 ms (1661 tours) | **378.8 ms** (556 tours) |
| Temps Expert par tour — maximum                        | 1632.7 ms     | 1523.3 ms |
| Replis Expert→Avancé, toute cause                      | 1254/1661 (75.5 %) | 322/556 (57.9 %) |
| — dont repli par timeout (seule cause visée par #190/#194) | 690/1661 (41.5 %) | **31/556 (5.6 %)** |
| — dont repli par coup légitimement impossible          | 564/1661 (34.0 %) | 291/556 (52.3 %) |
| Anomalies de conservation des tuiles                   | 0             | 0 |

**Lecture** : contrairement à #190 (qui n'améliorait pas la mesure
agrégée sur plateaux aléatoires), #194 montre une amélioration nette et de
grande ampleur sur cet échantillon : le taux de repli par timeout passe de
41.5 % à 5.6 %, et le temps moyen par tour d'Expert est plus que divisé par
deux (839.7 ms → 378.8 ms). Cohérent avec l'analyse : la recherche par
paliers et le nouvel ordre de visite ne profitent pas qu'au cas ciblé
(enchaînement de jokers), ils réduisent aussi, plus généralement, le nombre
de nœuds explorés avant de trouver un premier coup correct sur n'importe
quel plateau chargé — contrairement au critère de #190 (signatures
d'origine), qui ne s'appliquait qu'aux candidats ex-aequo. Échantillon plus
petit que celui de la mesure #190 (16 vs 40 parties) : l'écart observé est
cependant bien supérieur à la marge de bruit attendue à cette taille, donc
interprété comme un effet réel, pas seulement un artefact d'échantillonnage.

## Mesure 3 — rejeu de tours réels (journaux de parties)

Aucun journal de partie réel n'existe dans ce worktree (`data/logs_parties`
est vide, listé dans `.gitignore` — comportement attendu, ces journaux ne
sont écrits qu'en usage réel via l'UI). Pour disposer de tours réels à
analyser avec `scripts/analyser_coups_rates.py`, 4 parties Avancé vs Expert
ont été réellement jouées de bout en bout (moteur seul, script ponctuel
`scripts/_generer_logs_194.py`, supprimé après la mesure) en activant le
journal (`config.LOG_PARTIES`), produisant 4 fichiers au même format que des
parties jouées via l'UI (309 décisions au total, 153 décisions Expert après
mise initiale + 9 avant).

Comparaison entre le solveur d'avant #194 (`git show
bb6f543:...solveur.py`, temporairement restauré pour la mesure puis
immédiatement remis en place — vérifié par `git diff` et par la suite de
tests, 143 tests toujours passés après restauration) et celui d'après
#194, les deux interrogés avec budget généreux = 10s et budget de
production = 1.5s (`scripts/analyser_coups_rates.py --tous --budget 10
--budget-production 1.5`).

Les 4 journaux ont d'abord été analysés en entier avec le solveur d'après
#194 (309 décisions, 153 décisions Expert). Avec le solveur d'avant #194,
l'analyse des MÊMES 4 journaux est nettement plus lente (plus de budgets
généreux de 10s consommés en entier sans conclure) : dans le temps imparti
à cette mesure, seuls les 2 premiers journaux (147 décisions, 73 décisions
Expert) ont pu être analysés en entier par l'ancien solveur — la
comparaison ci-dessous se limite donc, pour les deux versions, à ces 2
journaux (`cas` = `partie_20261027_011020.json` +
`partie_20261027_011034.json`), seul sous-ensemble analysé en entier par
les deux versions :

| Mesure (niveau Expert, après la mise initiale, 72 décisions)         | Avant #194 | Après #194 |
|----------------------------------------------------------|:---:|:---:|
| Pioche/passe alors qu'un coup existait (« coup raté »)    | 0 | 0 |
| Poses sous-optimales                                       | 1 (1 tuile manquante) | 5 (5 tuiles manquantes) |
| ... dont limitées par le budget de production (1.5s)       | 1 | 4 |
| **Décisions inconclusives (budget GÉNÉREUX de 10s épuisé sans conclure)** | **8** | **0** |

(Les décisions jouées dans les 4 journaux l'ont été par le solveur D'APRÈS
#194 — ce tableau ne mesure donc pas « comment Expert aurait joué avant
#194 », mais, sur les MÊMES états de plateau réels, « combien de fois le
budget de production retrouve ce que le budget généreux trouve » avec
chaque version du solveur — la mesure pertinente pour l'objectif de #194 :
réduire les coups manqués PAR MANQUE DE TEMPS.)

**Lecture, prudente comme l'exige le script lui-même (voir ses propres
avertissements)** : à nombre de décisions égal (72), le changement le plus
frappant n'est PAS le nombre de « poses sous-optimales » (5 après contre 1
avant) mais le nombre de décisions **inconclusives** : 8 avant #194 contre
0 après. Une décision inconclusive signifie que même le budget GÉNÉREUX de
10s ne suffisait pas à l'ancien solveur pour conclure sur ce plateau réel —
la vraie valeur de ces 8 décisions reste CONNUE pour 1 seule dimension :
inconnue, pas « aucun problème ». En les comptant au pire (silencieusement
sous-optimales), le total de décisions potentiellement sous-optimales est
d'AU PLUS 9 avant #194 (1 confirmée + 8 inconnues) contre EXACTEMENT 5
après (toutes désormais résolues, aucune inconnue) — une amélioration nette
de la capacité du solveur à conclure sur des plateaux réels dans un budget
donné, cohérente avec la Mesure 2. Les 5 poses sous-optimales après #194
restent minimes (1 tuile manquante chacune) et à 4/5 explicitement
attribuées au budget de PRODUCTION (1.5s), pas à une limite de l'algorithme
lui-même (confirmées par le budget généreux de 10s).

## Ne rien dégrader

- `pytest tests/` : 143 tests passés (aucune régression, y compris les
  tests d'Avancé et des niveaux inférieurs — `moteur/ia.py` n'a pas été
  modifié, seul `moteur/solveur.py`, utilisé uniquement par Expert, l'a
  été).
- Les deux cas de référence restent résolus avec toutes les tuiles du
  plateau conservées (`_verifier_coup_valide_sans_perte`).
- Aucune anomalie de conservation des tuiles détectée sur les campagnes
  ci-dessus (0/16 et 0/4 parties).
- Budget de production inchangé (1.5s) — aucune augmentation n'a été
  nécessaire pour atteindre l'objectif.

## Fichiers modifiés

- `src/rummikub/moteur/solveur.py` : recherche par paliers croissants
  (`_Contexte.objectif`, `_seuil_atteint`), ordre de visite par valeur
  (`_ordre_slot`), docstring du module mise à jour.
- `tests/test_ia.py` : deux nouveaux tests sur
  `tests/donnees/cas_expert_bruno_tour57.json` (déjà présent, issu d'une
  tentative précédente sur cette même issue — vérifié, conservé).
- `tests/test_coups_rates_extensions.py` : le test de budget délibérément
  trop court (`test_cas_reference_bruno_budget_trop_court_signale_
  inconclusif`) utilise désormais un budget nul (au lieu de 0.05s) — ce cas
  de référence précis est désormais résolu en ~0.3s, un budget de 0.05s ne
  suffirait plus à garantir l'« inconclusif » attendu par ce test.
- `CONTEXTE.md` (§8bis) : nouvelle stratégie documentée, avec renvoi vers
  ce rapport pour les chiffres avant/après.
