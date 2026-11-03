# Issue #231 — Champion du Monde : stratégie « chances de poser au prochain tour » (anciennement « tuiles vivantes »)

Nouvelle stratégie **indépendante**, réservée à Champion du Monde et
**désactivée par défaut dans le jeu** (ABSENTE de
`STRATEGIES_CHAMPION_PAR_DEFAUT` — Expert et les niveaux inférieurs restent
strictement inchangés), activable en campagne par `--strategies-champion
chances_prochain_tour`. Aucune lecture de la main d'un adversaire (seule la
brique « Inconnues », #219, est utilisée). Valeurs de départ INDICATIVES
(`ECART_TUILES_SORTIES=0`, `SEUIL_GAIN_SORTIES=0,15`), réglables au seul
endroit `moteur/niveaux.py`.

Correction par rapport à l'idée initiale de « tuiles mortes »/« tuiles
vivantes » (une tuile dont les voisines seraient « sorties » du jeu) : au
Rummikub, les combinaisons du tapis sont réarrangeables — une tuile posée
n'est jamais indisponible. La notion retenue est donc inversée : les
« sorties » sont les tuiles qu'il ME reste à PIOCHER pour pouvoir jouer au
prochain tour.

## `src/rummikub/moteur/sorties.py` (nouveau)

- `sorties_chevalet(chevalet, plateau)` : ensemble des types de tuile
  (couleur + valeur, jokers compris) qui, piochés, permettraient de jouer —
  calcul DIRECT (paires du chevalet + brute force validé sur les
  combinaisons du tapis), jamais un appel au solveur exact.
- `score_chevalet(chevalet, plateau, etat, idx)` : somme, sur les sorties,
  de `exemplaires_restants / nb_total_inconnues` (brique « Inconnues »,
  #219) — jamais la main adverse.

## `src/rummikub/moteur/niveaux.py`

- `Bridage.chances_prochain_tour` (`False` par défaut) ; constantes
  `ECART_TUILES_SORTIES=0` (variante tolérante, désactivée par défaut) et
  `SEUIL_GAIN_SORTIES=0,15` (gain de score minimal exigé pour cette
  variante).
- Registre : entrée `chances_prochain_tour`, `niveaux=("Champion du
  Monde",)`, `active_par_defaut=False`. `bridage_champion_personnalise()`
  la câble.

## `src/rummikub/moteur/ia.py`

- `_candidats_sorties`/`_appliquer_chances_prochain_tour` : retire, tour à
  tour, chacune des tuiles que le coup du solveur pose, puis résout à
  nouveau (même mécanisme que `reserve_tuile`/`petits_chiffres`) — si le
  résultat pose le MÊME nombre de tuiles (coup équivalent), compare son
  score à celui du coup normal et garde le meilleur ; la variante tolérante
  accepte aussi un candidat posant une tuile de moins si le gain de score
  dépasse `SEUIL_GAIN_SORTIES`.
- Appliqué dans `jouer_niveau_bride` JUSTE APRÈS le coup normal (qui intègre
  déjà `petits_chiffres` s'il est actif) et AVANT `reserve_tuile`/
  `retenue_debut`/la variante tolérante de `petits_chiffres` — celles-ci
  peuvent réduire le nombre de tuiles posées.
- Ne s'applique que si le chevalet qui resterait après le coup compte
  STRICTEMENT plus d'une tuile ; un coup qui vide la main est toujours joué
  tel quel.
- Nouveau code solveur `SOLVEUR_CHANCES_PROCHAIN_TOUR` (journalisation).

## `scripts/comparer_niveaux_ia.py`

- Compteurs génériques (`stats_chances_prochain_tour`,
  `_compteurs_chances_prochain_tour`) + deux compteurs dédiés : score moyen
  du chevalet conservé, et, au tour suivant du même joueur après un coup
  changé, la part des fois où il a pu jouer plutôt que piocher
  (`suivi_chances_prochain_tour`, même mécanisme que `reserve_tuile`).
- Section dédiée dans `afficher_rapport`.

## Tests

- `tests/test_sorties.py` (nouveau) : tests directs de la brique, sans
  passer par l'IA — paire qui se complète vs paire isolée, sortie aux
  exemplaires tous connus (ne compte pas), règles de paire/rattachement.
- `tests/test_ia_chances_prochain_tour.py` (nouveau) : dilemme à nombre de
  tuiles posées égal (3) mais chevalets de scores différents (le meilleur
  score est choisi) ; désactivée (décision identique) ; Expert inchangé ;
  coup qui vide la main joué tel quel ; chevalet restant ≤ 1 tuile (sans
  effet).
- `tests/test_registre_strategies.py`/`tests/test_option_strategies_
  champion.py` : mis à jour pour la sixième entrée du registre (inventaire
  attendu, pas une régression).

## Essai (2 donnes, premier plan)

`--niveau-a Expert --niveau-b "Champion du Monde" --donnes 2 --seed 1
--strategies-champion chances_prochain_tour` : stratégie déclenchée 42 fois,
coup changé 2 fois, score moyen du chevalet conservé 0,336, 1/2 pioche
évitée au tour suivant. Temps de calcul par tour de Champion du Monde :
environ 28 ms sans la stratégie, environ 63 ms avec (surcoût dû aux appels
supplémentaires au modèle exact dans `_candidats_sorties`, au plus un par
tuile posée par le coup normal) — indicatif, aucun seuil fixé par l'issue.

## Documentation

- `CONTEXTE.md` §13, point 8 : définition, mécanisme (en dehors du modèle
  exact, à la différence de `petits_chiffres`), limites de l'heuristique
  (tapis réarrangeable → estimation prudente), compteurs, expérience
  prévue, et abandon du nom « tuiles vivantes ».
