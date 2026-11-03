# Issue #232 — Champion du Monde : stratégie « placement du joker »

Nouvelle stratégie **indépendante**, réservée à Champion du Monde et
**désactivée par défaut dans le jeu** (ABSENTE de
`STRATEGIES_CHAMPION_PAR_DEFAUT` — Expert et les niveaux inférieurs restent
strictement inchangés), activable en campagne par `--strategies-champion
placement_joker`. Aucune lecture de la main d'un adversaire (seule la
brique « Inconnues », #219, est utilisée). Valeurs de départ INDICATIVES
(`ASYMETRIE_JOKER_ACTIVE=False`, `POIDS_ASYMETRIE_JOKER=1.0`), réglables au
seul endroit `moteur/niveaux.py`.

Règles de libération d'un joker VÉRIFIÉES dans le code (jamais affirmées
sans l'avoir lu) — voir CONTEXTE.md §13, point 9 : l'échange direct
(`_jokers_recuperables`) est le SEUL mécanisme avec une tuile de
remplacement précise ; pour une suite, UNE seule valeur convient QUE le
joker soit au milieu OU au bout — contrairement à l'intuition de l'énoncé
initial (« deux valeurs voisines » pour le cas bout) ; pour un groupe de 3,
les deux couleurs manquantes conviennent. Les combinaisons de 4 tuiles ou
plus (libération sans remplacement) restent hors de portée, déjà évitées
par le solveur de base.

## `src/rummikub/moteur/niveaux.py`

- `Bridage.placement_joker` (`False` par défaut) ; constantes
  `ASYMETRIE_JOKER_ACTIVE=False` et `POIDS_ASYMETRIE_JOKER=1.0` (variante
  d'asymétrie, point 5 de l'issue, désactivée par défaut).
- Registre : entrée `placement_joker`, `niveaux=("Champion du Monde",)`,
  `active_par_defaut=False`. `bridage_champion_personnalise()` la câble.

## `src/rummikub/moteur/ia.py`

- `_types_remplacement_joker(combo, position_index)` : types de tuile
  (couleur, valeur) qui remplaceraient directement le joker à cette
  position — `None` si la combinaison ne compte pas exactement 3 tuiles
  (hors scope).
- `_exposition_coup_joker(etat, idx, coup)` : exposition d'un coup qui pose
  un ou plusieurs jokers depuis le chevalet — somme des exemplaires encore
  INCONNUS (brique « Inconnues ») des types de remplacement, pour chaque
  joker posé dans une combinaison de 3 tuiles. Exclut (`info["exclu"]`) les
  placements où la main (après le coup) contient encore la tuile de
  remplacement (nuance d'Alain, point 4 de l'issue).
- `_candidats_placement_joker`/`_appliquer_placement_joker` : même
  mécanisme que `_candidats_sorties` (#231, écart STRICTEMENT nul, pas de
  variante tolérante) — retire, tour à tour, chacune des tuiles posées par
  le coup normal, résout à nouveau, et garde le coup équivalent (NON exclu)
  à l'exposition la plus faible.
- Appliqué dans `jouer_niveau_bride` JUSTE APRÈS `chances_prochain_tour` et
  AVANT `reserve_tuile`/`retenue_debut`/les variantes tolérantes (qui
  peuvent réduire le nombre de tuiles posées).
- Nouveau code solveur `SOLVEUR_PLACEMENT_JOKER` (journalisation).

## `scripts/comparer_niveaux_ia.py`

- Compteurs génériques (`stats_placement_joker`,
  `_compteurs_placement_joker`) + `nb_jokers_poses`/`exposition_liste`
  (exposition moyenne) et le mécanisme VISÉ par la stratégie,
  `joker_repris_par_adversaire` : détecté à CHAQUE tour (pas seulement au
  tour suivant du même joueur) via `_detecter_reprises_joker`, une
  signature d'échange direct (approximation documentée — un réarrangement
  du plateau sans rapport avec ce joker précis pourrait, en théorie,
  produire le même signal, jugé négligeable en pratique).
- Section dédiée dans `afficher_rapport`.

## Tests

- `tests/test_ia_placement_joker.py` (nouveau), deux niveaux :
  - brique directe (`_types_remplacement_joker`/`_exposition_coup_joker`) :
    suite au milieu et au bout donnent la MÊME forme (une seule valeur) ;
    groupe (deux couleurs manquantes) ; combinaison de 4 (hors scope) ;
    exposition nulle ; exclusion (tuile de remplacement encore en main) ;
    aucun joker posé ;
  - stratégie bout-en-bout (`jouer_niveau_bride`), SANS tapis (évite la
    reformulation globale du solveur complet) : dilemme à nombre de tuiles
    posées égal (série très rentable mais très exposée vs suite peu
    rentable mais peu exposée) — la stratégie choisit la suite ;
    désactivée (décision identique) ; Expert inchangé ; coup sans joker
    (aucun effet) ; coup qui vide la main (joué tel quel).
- `tests/test_registre_strategies.py`/`tests/test_option_strategies_
  champion.py` : mis à jour pour la septième entrée du registre (inventaire
  attendu, pas une régression).

## Essai manuel (2 donnes, premier plan)

`comparer_niveaux_ia.py --niveau-a Expert --niveau-b "Champion du Monde"
--donnes 2 --strategies-champion placement_joker` : stratégie déclenchée 3
fois, coup changé 0 fois, exposition moyenne 2,33, 2/3 jokers posés repris
par l'adversaire d'après `_detecter_reprises_joker` — chiffres PUREMENT
indicatifs (échantillon de 3 événements), qui montrent seulement que la
mesure fonctionne de bout en bout. Surcoût de calcul négligeable sur cet
essai (dans le bruit de mesure).

## Documentation

- `CONTEXTE.md` §13, point 9 : règles de libération vérifiées (et l'écart
  avec l'énoncé initial sur le cas « bout de suite »), définition de
  l'exposition, variante d'asymétrie, compteurs, expérience prévue.
