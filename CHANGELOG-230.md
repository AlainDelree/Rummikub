# Issue #230 — Champion du Monde : stratégie « petits chiffres » (garder les petites tuiles, hypothèse H4)

Nouvelle stratégie **indépendante**, réservée à Champion du Monde et
**désactivée par défaut dans le jeu** (ABSENTE de
`STRATEGIES_CHAMPION_PAR_DEFAUT` — Expert et les niveaux inférieurs restent
strictement inchangés), activable en campagne par `--strategies-champion
petits_chiffres`. Aucune lecture de la main d'un adversaire. Valeurs de
départ INDICATIVES (`VALEUR_MAX_PETITS=3`, `ECART_TUILES_PETITS=0`),
réglables au seul endroit `moteur/niveaux.py`.

## `src/rummikub/moteur/solveur_exact.py`

- `_resoudre_modele`/`resoudre_exact` acceptent `valeur_max_petits` (``None``
  par défaut, comportement inchangé pour tout appelant existant, y compris
  Expert) : nouvelle passe `_passe_petits_chiffres`, insérée JUSTE APRÈS le
  critère 1 (nombre de tuiles posées, TOUJOURS premier, jamais modifié) et
  AVANT la perturbation minimale (#199) — minimise le nombre de tuiles
  RÉELLES de valeur 1 à `valeur_max_petits` posées. Réutilise le mécanisme
  exact des autres passes de départage (fixation par égalité), sans toucher
  à l'objectif principal.

## `src/rummikub/moteur/niveaux.py`

- `Bridage.petits_chiffres` (`False` par défaut) ; constantes
  `VALEUR_MAX_PETITS=3` (seuil de « petite » tuile) et
  `ECART_TUILES_PETITS=0` (variante tolérante, désactivée par défaut).
- Registre : entrée `petits_chiffres` (H4), `niveaux=("Champion du
  Monde",)`, `active_par_defaut=False`. `bridage_champion_personnalise()`
  la câble.

## `src/rummikub/moteur/ia.py`

- Le critère de départage (point 2 de l'issue) est intégré DIRECTEMENT au
  coup normal : `jouer_niveau_bride` calcule `valeur_max_petits` (actif
  seulement si `bridage.petits_chiffres` et le chevalet, AVANT de jouer,
  compte strictement plus que `SEUIL_FIN_PARTIE_VERIF_FINITION`) et le
  relaie via `_coup_selon_perturbation`/`jouer_niveau_expert`/`_coup_exact`
  jusqu'au modèle exact — aucun post-traitement séparé nécessaire pour
  cette partie.
- Variante tolérante (point 3), désactivée par défaut
  (`ECART_TUILES_PETITS`) : `_coup_qui_garde_une_petite_tuile` retire, une à
  la fois, chaque petite tuile posée par le coup normal et résout à nouveau
  (même mécanisme que `reserve_tuile`, #229) ; `_appliquer_petits_chiffres`
  applique les conditions (a)-(d) de l'issue et joue le candidat retenu à
  la place du coup normal seulement s'il pose STRICTEMENT moins de petites
  tuiles.
- Nouveau code `SOLVEUR_PETITS_CHIFFRES` ; coup annoté
  `petits_chiffres_info` pour les compteurs de campagne.
- Garde-fous communs aux stratégies multi-tours, inchangés : un coup qui
  vide la main n'est jamais soumis à la stratégie.

## `scripts/comparer_niveaux_ia.py`

- `--strategies-champion petits_chiffres` (mécanisme générique de #228,
  aucun nouveau drapeau dédié nécessaire).
- Compteurs génériques (`_compteurs_petits_chiffres`) + section dédiée dans
  le rapport : tours examinés/coup changé (variante tolérante) et, point 5
  de l'issue, un compteur dédié à l'EFFET visé par la stratégie — nombre
  moyen de petites tuiles (valeur ≤ `VALEUR_MAX_PETITS`) dans le chevalet,
  à CHAQUE tour de CHAQUE joueur (`tuiles_petites_main`, mesure pure,
  toujours collectée, par niveau), pour vérifier que la stratégie les
  conserve réellement en main.

## `CONTEXTE.md`

- Nouvelle sous-section en fin de §13 : la stratégie, ses deux paramètres,
  son compteur dédié, la remarque d'Alain et Claude sur le faible coût en
  points (présentée explicitement comme une hypothèse non issue de la
  source), et l'expérience prévue (Champion avec `petits_chiffres` seule
  contre Expert, jugée par le compteur dédié avant le taux de victoire).

## Tests

- `tests/test_ia_petits_chiffres.py` (nouveau) : deux groupes de même
  taille (3 tuiles, l'un de valeur 3, l'autre de valeur 9) se disputant le
  seul joker du chevalet, plateau vide (perturbation à égalité pour les
  deux) — la stratégie garde les deux 3 en main ; désactivée (décision
  identique au solveur seul) ; chevalet ≤ seuil de fin de partie (décision
  inchangée) ; Expert inchangé ; coup qui vide la main joué tel quel ;
  variante tolérante activée (garde la petite tuile au prix d'une tuile de
  moins) et son inapplication hors de la fenêtre de chevalet ; départage
  seul (sans la variante tolérante) qui ne réduit jamais le nombre de
  tuiles posées.
- `tests/test_registre_strategies.py`/`tests/test_option_strategies_
  champion.py` : mis à jour pour les cinq entrées du registre.

## Vérifications

- Suite de tests complète : 508 passés, 14 ignorés (bibliothèque externe
  `rummikub_solver` et journal de partie absents de l'environnement de
  vérification — sans rapport avec cette issue).
- `node --check`/`py_compile` : sans objet pour JS (aucun fichier JS
  touché) ; `py_compile` OK sur tous les fichiers Python modifiés.
- Essai manuel de deux donnes (premier plan, pas de simulation longue) :
  `--strategies-champion petits_chiffres` (Expert vs Champion du Monde,
  seed 1) — aucune anomalie de conservation, aucun crash ; compteur dédié
  affiché dans le rapport (moyenne de petites tuiles en main, par niveau) ;
  sans l'option, la stratégie ne se déclenche pas (comportement par défaut
  du jeu inchangé).
