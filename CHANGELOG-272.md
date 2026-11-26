# Issue #272 — Moteur : ne compter à l'ouverture que les tuiles réellement venues du chevalet, et exiger au moins une tuile posée

## Contexte

L'étude #270 (lecture seule) avait confirmé un défaut déjà signalé en
11quinquies de `coups_rates_bilan.md` : `jouer_tour` et
`_points_tuiles_posees` (`moteur/partie.py`) calculaient les points de la
mise initiale en additionnant la valeur de chaque identifiant déclaré comme
« posé ce tour », sans vérifier que cet identifiant était réellement dans le
chevalet du joueur avant le coup. Reproduit avec le vrai moteur : un joueur
n'ayant pas encore ouvert, avec des points réels insuffisants au chevalet,
pouvait déclarer à tort comme posée une tuile venue du plateau et voir son
ouverture acceptée à tort. Aucun appelant réel (interface, cinq niveaux d'IA)
ne déclenchait ce cas en pratique, mais le moteur ne se protégeait pas
lui-même. L'étude avait aussi relevé l'absence de contrôle imposant qu'au
moins une tuile du chevalet soit posée. Décision d'Alain : ajouter ces deux
contrôles en défense en profondeur, sans changer le comportement de jeu
actuel. L'interdiction d'étendre une combinaison déjà posée pendant son
propre tour d'ouverture, évoquée par l'étude, est traitée par une autre
issue et reste hors périmètre ici.

## 1. `src/rummikub/moteur/partie.py`

- `_points_tuiles_posees(plateau, ids_posees, ids_chevalet_avant=None)` :
  nouveau paramètre optionnel. S'il est fourni, les identifiants posés hors
  de cet ensemble (donc jamais venus du chevalet avant ce coup) sont
  retirés avant le calcul des points — ils ne peuvent jamais compter comme
  tuiles de mise initiale.
- `jouer_tour` :
  - Calcule désormais `ids_chevalet_avant` (le chevalet du joueur avant ce
    coup, pas encore muté à ce stade de la fonction — même esprit que
    l'état d'avant coup déjà calculé pour le garde-fou #187).
  - **Nouveau contrôle (étape 2ter)** : si aucun identifiant posé n'est
    réellement présent dans `ids_chevalet_avant` (liste vide ou tuiles
    toutes étrangères au chevalet), le coup est refusé :
    `"Coup refusé : aucune tuile du chevalet n'est posée"`. La pioche et le
    passage de tour n'appellent pas `jouer_tour` et ne sont donc jamais
    concernés.
  - **Nouveau contrôle (étape 3, avant la mise initiale uniquement)** : si
    un identifiant déclaré posé n'était pas dans le chevalet avant ce coup
    (ex. une tuile déjà sur le plateau, à tort déclarée venir de la main),
    le coup est refusé directement : `"Coup refusé : tuile(s) posée(s) non
    présente(s) dans le chevalet avant ce coup (...)"`, avec la clé
    `tuiles_hors_chevalet` listant les identifiants en cause — au même
    style que le refus existant de #187. Une fois la mise initiale faite,
    ce contrôle ne s'applique plus : un joueur peut légitimement réarranger
    des combinaisons déjà posées sur la table (l'interface mélange alors
    tuiles de la main et tuiles déplacées dans `ids_tuiles`, comportement
    inchangé).

Aucun autre changement : règles de validité des combinaisons, calcul du
score, IA (`moteur/ia.py`, solveur, solveur exact), `moteur/niveaux.py` et
interface restent intacts.

## 2. Tests (`tests/test_moteur.py`)

Cinq nouveaux tests, rapides et déterministes (section « Origine des tuiles
de la mise initiale »), ajoutés sans retirer ni raccourcir aucun test
existant :

- `test_jouer_tour_refuse_mise_initiale_avec_tuile_du_plateau_declaree_a_tort` :
  scénario de l'étude #270 — chevalet réel de 24 points (rouge 7+8+9), une
  tuile déjà posée par un autre joueur (bleu_12, 12 points) déclarée à tort
  comme venant de la main (total gonflé à 36 ≥ 30) — refusé, avec
  `tuiles_hors_chevalet == ["bleu_12_a"]`, et aucun effet de bord (chevalet,
  mise initiale et plateau inchangés).
- `test_jouer_tour_accepte_ouverture_legitime_depuis_le_chevalet_seul` :
  scénario de contrôle — les mêmes 5 tuiles (rouge 7 à 11, 45 points), toutes
  réellement du chevalet — acceptée normalement.
- `test_jouer_tour_accepte_ouverture_a_exactement_30_points` : ouverture à
  exactement le minimum (rouge 9+10+11 = 30) — acceptée.
- `test_jouer_tour_refuse_coup_sans_aucune_tuile_posee` : liste de tuiles
  posées vide — refusée (`"aucune tuile du chevalet n'est posée"`).
- `test_jouer_tour_accepte_ajout_d_une_tuile_du_chevalet_apres_ouverture` :
  non-régression — après l'ouverture, ajouter une tuile du chevalet à une
  combinaison déjà posée sur la table reste accepté.

## 3. Documentation

- `docs/contexte/coups_rates_bilan.md` (§11quinquies) : la section « Limite
  connue, non corrigée » est remplacée par une note indiquant que le bug est
  corrigé par cette issue et que le moteur contrôle désormais lui-même
  l'origine des tuiles de la mise initiale.
- `docs/contexte/moteur_regles.md` (§3, description de `jouer_tour`) :
  ajout d'un paragraphe décrivant les deux nouveaux contrôles (issue #272).
- `src/rummikub/ui/api.py` (`jeu_jouer_coup`) : le commentaire expliquant
  que `ids_tuiles` mélange tuiles de la main et tuiles du plateau déplacées
  précisait « jamais corrigé pour le moteur » — mis à jour pour indiquer
  que `jouer_tour` refuse désormais lui-même, avant la mise initiale, tout
  identifiant qui ne serait pas réellement dans le chevalet.

`CONTEXTE.md` non modifié (aucune règle ni convention transverse n'en
dépendait).

## Points laissés pour décision

Aucun. L'interdiction d'étendre une combinaison déjà posée pendant son
propre tour d'ouverture (évoquée par l'étude #270) reste hors périmètre,
traitée par une autre issue à part.

## Vérifications

- `python3 -m py_compile` sur les trois fichiers modifiés
  (`src/rummikub/moteur/partie.py`, `src/rummikub/ui/api.py`,
  `tests/test_moteur.py`) : OK.
- `ruff check --select S main.py src` : tous les contrôles passent.
- Suite de tests complète (`pytest`, premier plan, `timeout 900`) :
  **552 passed, 13 skipped** en 128,4 s (contre 547 passed/13 skipped avant
  cette issue — les 5 nouveaux tests, aucune régression). Aucun test
  existant n'a révélé d'appelant réel mal alimenté (humain ou IA) : tous les
  appels existants à `jouer_tour` dans la suite déclarent déjà des
  identifiants réellement issus du chevalet avant le coup.
