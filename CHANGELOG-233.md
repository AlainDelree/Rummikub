# Issue #233 — Suite #232 : l'exposition d'un joker en bout de suite doit compter la libération par prolongement puis détachement

Correction de la stratégie `placement_joker` (#232, Champion du Monde SEUL,
désactivée par défaut). #232 affirmait que ce moteur ne distingue pas un
joker « au milieu » d'une suite d'un joker « au bout » (une seule valeur de
remplacement par échange direct dans les deux cas), et en déduisait que les
deux placements avaient la MÊME exposition. Cette conclusion est
incomplète : elle ignorait une seconde voie, propre au bout — prolonger
l'extrémité OPPOSÉE (même couleur, valeur voisine) transforme la suite de 3
en suite de 4, où le joker, désormais en bout d'une combinaison de 4, se
détache SANS remplacement (mécanisme déjà implémenté pour l'IA elle-même,
#150). Un joker en bout de suite est donc PLUS exposé qu'un joker au
milieu, et la stratégie doit préférer le milieu à exposition égale des
tuiles posées.

**Vérification demandée (tâche 1) sur le MOTEUR RÉEL**, pas seulement en
lisant le code : `partie.jouer_tour` accepte bien le coup « pose du
prolongement devant 4-5-joker, détachement du joker, rejeu du joker ailleurs,
même tour » et le plateau final reste valide — confirmé dans les deux sens
de symétrie (joker en bout haut, joker en bout bas). Voir
`tests/test_ia_placement_joker.py::
test_moteur_reel_detachement_par_prolongement_joker_en_haut_de_suite` et
`..._en_bas_de_suite`.

**Voies de libération d'un joker, désormais comptées par l'exposition** :
échange direct (milieu ET bout) ; prolongement d'une extrémité suivi d'un
détachement sans remplacement (bout seulement, nouveau). **Voies NON
comptées** (approximation assumée, documentée dans CONTEXTE.md §13, point
9) : tout réarrangement plus large du plateau que seul le solveur complet
(Expert) peut trouver — démantèlement complet d'une suite (#175, non
implémenté pour Avancé), scission combinée à d'autres combinaisons,
recombinaison globale à plusieurs coups d'avance. Cette stratégie départage
entre coups déjà proposés par le solveur, jamais n'en invente un nouveau :
elle mesure le risque le plus direct, pas le risque total.

## `src/rummikub/moteur/ia.py`

- `_types_remplacement_joker(combo, position_index)` : pour une suite de 3
  avec le joker à une EXTRÉMITÉ (`position_index` 0 ou 2), ajoute désormais
  le type `(couleur, valeur_prolongement)` — même couleur, valeur de
  l'extrémité opposée ± 3 selon le sens — si cette valeur reste dans 1..13
  (sinon le joker est en bout CONTRE UNE BORNE du jeu, ex. suite 1,2,joker :
  pas de seconde voie, même exposition qu'au milieu, aucune régression).
  Pour le milieu (`position_index == 1`) et pour un groupe de 3, aucun
  changement. `_exposition_coup_joker` (non modifiée) somme automatiquement
  les exemplaires inconnus de ces types, sans compter deux fois un même
  type ; la nuance d'exclusion (point 4 de #232, tuile déjà en main) et la
  variante d'asymétrie désactivée par défaut (point 5 de #232) héritent
  automatiquement de la correction, puisqu'elles ne font que parcourir les
  types retournés par `_types_remplacement_joker`.
- `_detecter_reprises_joker` (`scripts/comparer_niveaux_ia.py`) : ne dépend
  PAS de `_types_remplacement_joker` (détection par signature de
  compagnes de combinaison, indépendante des types de remplacement) —
  vérifié, aucun changement nécessaire.

## `tests/test_ia_placement_joker.py`

- Nouvelle section « tâche 1 » : deux tests sur le moteur réel
  (`partie.jouer_tour`), symétriques, qui vérifient la légalité du coup
  prolongement + détachement + rejeu du joker.
- `test_types_remplacement_suite_bout_une_seule_valeur_aussi` (affirmait à
  tort l'équivalence milieu/bout) remplacé par
  `test_types_remplacement_suite_bout_deux_valeurs` et
  `test_types_remplacement_suite_bout_bas_deux_valeurs` (deux types, les
  deux sens de symétrie) ; ajout de
  `test_types_remplacement_suite_bout_contre_une_borne_une_seule_valeur`
  (cas limite, une seule voie).
- Ajout de `test_exposition_suite_bout_quatre_exemplaires_inconnus`,
  `test_exposition_suite_bout_contre_une_borne_meme_exposition_qu_au_milieu`,
  `test_exposition_exclue_si_je_detiens_deja_la_tuile_de_prolongement`.
- Ajout du dilemme bout-en-bout `test_sans_la_strategie_le_solveur_prefere_
  le_bout_plus_rentable` /
  `test_placement_joker_prefere_le_milieu_au_bout_a_tuiles_egales` : à
  tuiles égales, la stratégie choisit désormais le milieu (exposition 2)
  plutôt que le bout (exposition 4), même quand le bout rapporte plus de
  points. Tous les tests existants de la stratégie restent verts.

## `CONTEXTE.md`

- §13, point 9 (`placement_joker`, #232) : corrige l'affirmation « milieu
  et bout sont équivalents », décrit la voie par prolongement puis
  détachement vérifiée sur le moteur réel, liste les voies comptées et non
  comptées, et précise explicitement que l'exposition reste une
  APPROXIMATION (le solveur complet peut libérer un joker par des
  réarrangements plus larges, non comptés ici).

## Vérifications

- `pytest -q` : 544 passés, 14 ignorés (dépendances du modèle exact
  absentes dans cet environnement) — aucune régression.
- `python3 -m py_compile src/rummikub/moteur/ia.py
  tests/test_ia_placement_joker.py` : OK.
- Aucune modification d'Expert, des niveaux inférieurs, des règles du jeu,
  de l'interface ou du solveur lui-même. `placement_joker` reste désactivée
  par défaut et réservée à Champion du Monde.
