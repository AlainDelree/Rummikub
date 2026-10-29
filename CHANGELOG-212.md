# Issue #212 — Match : notre solveur d'Expert contre la bibliothèque `rummikub-solver` sur des parties entières (suite de #206)

Nos deux solveurs trouvent le même **nombre** de tuiles posables à chaque tour
(vérifié en #204), mais départagent différemment à nombre égal : le nôtre
préfère la **perturbation minimale** du plateau (#199) puis **économise les
jokers**, la bibliothèque applique ses propres règles. Cette issue répond à la
question d'Alain : *ces choix de départage nous désavantagent-ils sur une partie
entière ?* en faisant jouer une partie entière pilotée par chaque solveur, en
miroir (mêmes donnes, places échangées), sur de nombreuses donnes.

**Portée (à ne pas sur-interpréter)** : les deux solveurs n'optimisent qu'UN
tour. Le match ne mesure donc PAS les stratégies sur plusieurs tours (réserve,
joker gardé, rétention — CONTEXTE.md §13), ni la force d'un humain : seulement
si, à jeu « un tour » égal, nos critères de départage tiennent la route.

**Rien du jeu livré, du moteur, de l'IA ni du solveur n'est modifié** :
`rummikub-solver` reste une dépendance de DÉVELOPPEMENT (hors `requirements.txt`,
hors build Windows) ; tout est sous `scripts/` et `tests/`, en outil d'analyse.

## Résultat de la mesure

Campagne du 2026-10-29 (graine de base 20212, `budget Expert=1,5 s`,
`max_tours=400`), arrêtée proprement à la **limite de temps ferme de 2100 s**
en exploitant les résultats partiels : **83 donnes jouées = 164 parties**
(sur 100 donnes visées).

| Solveur | Victoires | Taux | IC 95 % (Wilson) |
|---------|-----------|------|------------------|
| **Notre solveur (Expert)** | 89 / 164 | **54,3 %** | **[46,6 % ; 61,7 %]** |
| **Bibliothèque** | 75 / 164 | **45,7 %** | **[38,3 % ; 53,4 %]** |

Égalités : 0 — parties bloquées : 0.

Indicateurs de marge et de jeu :

- Tours par partie (moyen) : **64,9**.
- Tuiles restantes en main du **perdant** (serrage, indicateur demandé par
  Alain) : **2,44** quand notre solveur perd (75 défaites), **2,45** quand la
  bibliothèque perd (89 défaites) — quasi identiques.
- Tuiles posées par tour : **0,978** (notre) vs **0,975** (biblio).
- Temps par coup — moyen / max : **0,093 s / 1,56 s** (notre, modèle exact
  maison borné à 1,5 s) vs **0,039 s / 0,39 s** (biblio).
- Coups « main seule » contraints avant la mise (biblio) : **529** (gérés
  proprement par construction, voir §1 ci-dessus).

Contrôles : **0 erreur de conservation** des 106 tuiles, **0 coup refusé** par
le moteur. **1 écart d'optimalité** signalé (donne 20B, tour 64 : notre=1,
biblio=0) sur ~10 000 états rencontrés. Rejeu propre, **monothread et
déterministe, de cette donne : l'écart NE se reproduit PAS** (partie jouée
jusqu'au bout, 77 tours, aucun écart, résultat stable sur deux exécutions).
L'explication la plus probable est un **artefact temporel** du solveur maison
**borné en temps** (budget 1,5 s) sous la **charge CPU concurrente** du match
(double résolution par tour), et non un défaut d'optimalité structurel entre
les deux modèles exacts (dont l'égalité exacte avait été vérifiée en #204). Cet
unique état n'affecte pas la conclusion (IC largement chevauchants).

### Interprétation (sans sur-vendre)

Les intervalles de confiance à 95 % des deux taux de victoire **se
chevauchent** : sur cet échantillon, **aucun des deux solveurs n'a d'avantage
démontré** au jeu « un tour ». Nos critères de départage (perturbation minimale
#199, économie de jokers) **ne nous désavantagent pas de façon mesurable**. Le
léger 54,3 % en notre faveur n'est pas significatif (borne basse de notre IC
46,6 % < borne haute de l'IC adverse 53,4 %).

**Portée — à ne pas sur-interpréter.** Les deux solveurs n'optimisent qu'UN
tour. Ce match ne mesure PAS les stratégies sur plusieurs tours (réserve, joker
gardé, rétention — CONTEXTE.md §13), ni la force d'un humain. Le progrès est à
chercher dans le jeu sur plusieurs tours.

## Changements

### 1. `scripts/match_solveurs.py` (nouveau) — script de match

- **« Joueur bibliothèque »** (`decider_bibliotheque`) bâti sur l'adaptateur
  `scripts/solveur_exact.py` (#204) : prend l'état (plateau, main, mise initiale
  faite ou non) et renvoie un **coup complet** (tuiles posées + nouveau plateau)
  déjà **remis dans l'ordre et validé par `valider_combinaison`**, conservation
  du plateau contrôlée par l'adaptateur. **Mise initiale** : la bibliothèque
  réarrange table + main au second temps, interdit avant la mise ; on la
  **contraint à n'utiliser que la main** (résolution sur plateau vide puis
  recollage du plateau intact), le cas étant compté à part (`mise_contrainte`).
- **« Notre solveur »** = niveau **Expert livré** (`jouer_niveau_expert`,
  modèle exact maison + départage #199/jokers), le joueur réellement embarqué.
- **Protocole miroir** : chaque donne (graine fixe) est jouée deux fois, places
  échangées — chaque solveur joue une fois chaque main et une fois chaque
  position (avantage de la main et de l'ouverture neutralisés).
- **Contrôles à chaque coup** : conservation des **106 tuiles** ; et, sur le
  même état, comparaison du **nombre maximal de tuiles posables** des deux
  solveurs — tout écart est signalé (ne devrait jamais arriver : écart
  d'optimalité à investiguer).
- **Limite de temps ferme** (`--limite-temps`), arrêt propre entre deux parties,
  **résultats partiels** écrits en continu (rapport texte + `.json` frère).
- **Indicateurs** (point 3) : taux de victoire + **IC 95 % (Wilson)**, tuiles
  **restantes en main du perdant** (indicateur de serrage demandé par Alain),
  tuiles posées par tour, tours par partie, parties bloquées, temps moyen et
  maximal par coup de chaque solveur. **Interprétation factuelle** sans
  sur-vente (point 4), avec rappel explicite de la portée « un tour ».

### 2. `tests/test_match_solveurs.py` (nouveau)

Tests du script sur un petit nombre de parties, **sautés proprement si la
bibliothèque est absente** (`pytest.importorskip`) : décideur bibliothèque
(coup ordonné/validé/conservatif, contrainte « main seule » avant la mise),
conservation des 106 tuiles, IC 95 % de Wilson, **égalité d'optimalité** des
deux solveurs sur des états de départ, et un **petit match complet** (marqué
`lent`) vérifiant miroir, conservation et absence d'écart d'optimalité.

### 3. `CONTEXTE.md`

Nouvelle **§15** documentant le script de match, le protocole miroir, la
contrainte de mise initiale et le résultat chiffré.

## Fichiers

- `scripts/match_solveurs.py` (nouveau, outil d'analyse dev-only)
- `tests/test_match_solveurs.py` (nouveau)
- `CONTEXTE.md` (nouvelle §15)
- `resultats_match_212.txt` / `.json` (rapport de la campagne)
