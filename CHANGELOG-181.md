# Issue #181 — Suite #180 : IA : scinder une longue suite en son milieu pour libérer une tuile ou un joker

Suite #180 : dans `CONTEXTE.md` §8, la « scission en milieu de suite »
était identifiée mais jamais formalisée. `_coup_scission` ne détachait
jusqu'ici qu'une tuile réelle en BOUT d'une suite de 4 tuiles ou plus — la
suite restante restait d'un seul tenant. Une suite assez longue (7 tuiles
ou plus) peut pourtant être coupée en DEUX suites valides en retirant une
tuile ou un joker intérieur (ni en tête ni en queue), libérant cette
tuile/ce joker pour un usage ailleurs sur le plateau.

Deux cas couverts, qui découlent du même principe :

- **Tuile réelle intérieure** : suite rouge 1-2-3-4-5-6-7 + un 4 bleu et un
  4 jaune en main → retirer le 4 rouge laisse deux suites valides (1-2-3 et
  5-6-7) et le 4 rouge libéré forme avec la main le groupe 4
  rouge/bleu/jaune.
- **Joker intérieur** : suite bleue 3-4-5-(joker)-7-8-9 → retirer le joker
  laisse deux suites valides (3-4-5 et 7-8-9) et le joker libéré est rejoué
  avec la main dans un groupe de 12 (rouge/jaune/joker).

## Ajout

`src/rummikub/moteur/ia.py` :

- `_coup_scission` généralisée : la boucle sur les positions d'une suite
  parcourt désormais TOUTES les positions (plus seulement les deux bouts)
  et calcule les deux parties de part et d'autre de la tuile retirée
  (`combo[:pi]` / `combo[pi+1:]`). Si une seule partie est non vide (cas
  bout, inchangé) ou si les deux sont non vides et valides (≥ 3 tuiles
  chacune, cas milieu, nouveau), la suite d'origine est remplacée par ces
  parties et la tuile retirée tente de former un nouveau groupe avec des
  tuiles de la main, exactement comme pour le cas bout existant. Le
  comportement en bout de suite n'est pas modifié (même séquence
  d'essais, mêmes résultats).
- `_jokers_liberables_par_scission_milieu(plateau, chevalet)` (nouvelle
  fonction) : détecte, pour toute suite d'au moins 7 tuiles, un joker en
  position strictement intérieure dont le retrait laisse deux suites
  valides (chacune ≥ 3 tuiles) de part et d'autre. Ne consomme aucune
  tuile de la main pour la scission elle-même (contrairement à
  `_jokers_detachables_par_extension`, qui nécessite une tuile
  d'extension au bout opposé).
- `_liberations_possibles` intègre cette quatrième tactique au format
  unifié de #169/#180 : `appliquer(plateau)` remplace ici la combinaison
  d'origine par sa moitié gauche et AJOUTE la moitié droite comme nouvelle
  combinaison du plateau (une combinaison devient deux — cas qui ne se
  présentait pas pour les tactiques précédentes, qui modifiaient une ou
  deux combinaisons déjà existantes en place). Le champ `combis` ne
  référence que l'index d'origine, ce qui suffit à la détection de
  conflit : une libération qui toucherait la même combinaison du plateau
  est rejetée par `_meilleur_coup_liberations` comme pour les autres
  tactiques. `tuiles_consommees` est vide ici (aucune tuile de main n'est
  nécessaire pour la scission), ce que le format supportait déjà (cf.
  #180). Le joker libéré doit être rejoué dans le même tour avec des
  tuiles de la main — s'il ne peut être replacé, `_coup_depuis_liberations`
  renvoie `None` et le coup n'est pas retenu, comme pour les autres
  tactiques.
- Limité à Avancé/Expert via les points d'entrée déjà en place
  (`_coup_scission` et `_meilleur_coup_avec_joker`) — aucun changement
  dans `jouer_niveau_avance`/`jouer_niveau_expert`. Facile et
  Intermédiaire restent inchangés.

`CONTEXTE.md` §8 mis à jour :

- La « scission en milieu de suite » déplacée des tactiques « Identifiées
  mais pas encore implémentées » vers les « Implémentées », avec le
  numéro de cette issue (#181) et une description courte des deux cas
  (tuile réelle / joker).
- Note finale sur `_coup_scission` réécrite : elle ne se limite plus aux
  seuls bouts de suite (couvre désormais aussi le milieu), mais reste
  étrangère aux jokers, dont la libération (bout ou milieu) passe
  entièrement par `_liberations_possibles`.

## Tests

`tests/test_ia.py` : six nouveaux tests.

- `test_avance_scinde_une_suite_pour_liberer_une_tuile_interieure` et
  `test_expert_scinde_une_suite_pour_liberer_une_tuile_interieure` :
  reprennent l'exemple « tuile réelle intérieure » (suite rouge 1-7,
  main 4 bleu + 4 jaune) ; vérifient le coup joué, la validité du plateau
  résultant (3 combinaisons : 2 suites + 1 groupe) et la composition du
  nouveau groupe de 4.
- `test_avance_scinde_une_suite_pour_liberer_un_joker_interieur` et
  `test_expert_scinde_une_suite_pour_liberer_un_joker_interieur` :
  reprennent l'exemple « joker intérieur » (suite bleue 3-9 avec joker en
  position 4, main 12 rouge + 12 jaune) ; vérifient le coup joué, la
  validité du plateau résultant et que le joker se retrouve bien dans le
  nouveau groupe de 12 (et nulle part ailleurs).
- `test_facile_ne_scinde_pas_une_suite_en_son_milieu` : non-régression —
  Facile ne tente pas la scission (reprend le scénario « tuile réelle
  intérieure », où Facile ne peut rien jouer avec seulement 2 tuiles de
  même valeur).
- `test_avance_ne_scinde_pas_une_suite_trop_courte` : suite rouge de
  longueur 5 (3-4-5-6-7) avec en main un 5 bleu et un 5 jaune — retirer la
  tuile centrale laisserait deux parties de longueur 2, invalides ; le
  coup de scission ne doit pas être proposé.

Tous les tests existants (#148, #150, #169, #180) passent sans
modification de leurs assertions. Suite complète : 44 tests, tous au vert
(`pytest -q`).
