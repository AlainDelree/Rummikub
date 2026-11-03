# Issue #229 — Champion du Monde : stratégies « réserve d'une tuile » et « retenue au début » (hypothèses H2 et H1)

Deux stratégies **indépendantes**, chacune activable seule, réservées à
Champion du Monde et **désactivées par défaut dans le jeu** (ABSENTES de
`STRATEGIES_CHAMPION_PAR_DEFAUT` — Expert et les niveaux inférieurs restent
strictement inchangés). Aucune lecture de la main d'un adversaire. Valeurs
de départ INDICATIVES, réglables au seul endroit `moteur/niveaux.py`.

## `src/rummikub/moteur/niveaux.py`

- `Bridage.reserve_tuile`/`Bridage.retenue_debut` (`False` par défaut) ;
  constantes `ECART_MAX_RESERVE=1`, `TOURS_RETENUE_DEBUT=4`,
  `TUILES_TAPIS_MAX_RETENUE=20`, `POSE_MAX_DEBUT=2`.
- Registre : entrées `reserve_tuile` (H2) et `retenue_debut` (H1), toutes
  deux `niveaux=("Champion du Monde",)`, `active_par_defaut=False`.
  `bridage_champion_personnalise()` les câble.

## `src/rummikub/moteur/solveur_exact.py`

- `resoudre_exact`/`_resoudre_modele` acceptent `max_tuiles_posees` (``None``
  par défaut, comportement inchangé) : ajoute UNE contrainte au programme
  linéaire bornant les tuiles DE LA MAIN posées — le plafond de
  `retenue_debut` exprimé proprement par le modèle exact, pas une logique de
  jeu réécrite à côté.

## `src/rummikub/moteur/verification_finition.py`

- `peut_poser_au_tour_suivant()` : sœur de `_peut_finir_au_tour_suivant``
  (#221), MOINS stricte (pose au moins une tuile, pas besoin de vider tout
  le chevalet) — condition (c) de `reserve_tuile`.

## `src/rummikub/moteur/ia.py`

- `reserve_tuile` (H2) : après le coup du solveur, `_coup_qui_garde_une_
  tuile` retire, une à la fois, chaque tuile posée par le coup normal et
  résout à nouveau le modèle exact sur la main réduite (généralisation de
  `_coup_sans_joker_chevalet`, #225, à une tuile quelconque). `_appliquer_
  reserve_tuile` applique les conditions (a)-(e) de l'issue et joue le
  candidat retenu à la place du coup normal.
- `retenue_debut` (H1) : `_nb_tours_joueur_depuis_ouverture` dérive, SANS
  modifier `moteur/partie.py`, le nombre de tours du joueur depuis SA PROPRE
  ouverture à partir de `etat["historique"]` (signal numérique `points` > 0,
  jamais une lecture de texte). `_appliquer_retenue_debut` plafonne le coup
  via `max_tuiles_posees` pendant la fenêtre, jamais une pioche si un coup
  existe au-delà du plafond.
- Nouveaux codes `SOLVEUR_RESERVE_TUILE`/`SOLVEUR_RETENUE_DEBUT` ; coups
  annotés `reserve_tuile_info`/`retenue_debut_info` pour les compteurs de
  campagne.

## `scripts/comparer_niveaux_ia.py`

- `--strategies-champion reserve_tuile`/`retenue_debut` (mécanisme générique
  de #228, aucun nouveau drapeau dédié nécessaire).
- Compteurs génériques (`_compteurs_reserve_tuile`/`_compteurs_retenue_
  debut`) + section dédiée par stratégie dans le rapport : tours examinés,
  coup changé, tuiles gardées en moyenne, et pour `reserve_tuile` le
  mécanisme visé (pioche évitée / tuile gardée effectivement posée au tour
  suivant du même joueur, suivi via un dict `suivi_reserve_tuile` créé frais
  à chaque manche).

## `CONTEXTE.md`

- Nouvelle sous-section en fin de §13 : les deux stratégies, leurs
  paramètres, leurs compteurs, le lien avec H1/H2, l'interaction si les deux
  sont actives ensemble, et l'expérience prévue (Champion avec chacune seule
  contre Expert, puis les deux ensemble avec retrait une à une).

## Tests

- `tests/test_ia_reserve_tuile.py` (nouveau) : groupe de 3 + 4e tuile
  gardée ; même cas chevalet < 6 tuiles (inchangé) ; coup qui vide la main
  (joué tel quel) ; stratégie désactivée (inchangé) ; Expert inchangé.
- `tests/test_ia_retenue_debut.py` (nouveau) : plafond respecté pendant la
  fenêtre ; aucun effet après la fenêtre, ni avant l'ouverture, ni si aucune
  combinaison ne tient dans le plafond ; stratégie désactivée (inchangé) ;
  Expert inchangé.
- `tests/test_registre_strategies.py`/`tests/test_option_strategies_
  champion.py` : mis à jour pour les quatre entrées du registre.

## Vérifications

- Suite de tests complète : 500 passés, 14 ignorés (dépendances
  `highspy`/`numpy` absentes de l'environnement de vérification).
- Essai manuel de deux donnes (premier plan, pas de simulation longue) :
  `--strategies-champion reserve_tuile` (6/6 pioches évitées et 6/6 tuiles
  gardées effectivement reposées sur cet essai) et `--strategies-champion
  retenue_debut` (coup plafonné observé) ; sans option, aucune des deux
  stratégies ne se déclenche (0 partout) — comportement par défaut du jeu
  inchangé.

## Point d'attention signalé dans le rapport de clôture

- Le plafond de `retenue_debut` a pu être exprimé proprement par le modèle
  exact (nouvelle contrainte `max_tuiles_posees`) : les DEUX stratégies
  demandées sont livrées, aucun repli sur `reserve_tuile` seule n'a été
  nécessaire.
