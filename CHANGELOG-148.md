# Issue #148 — IA : récupération d'un joker libérable lors d'une extension (Avancé/Expert)

## Contexte
Niveau "Expert" jugé trop faible : l'IA se contentait du premier coup simple trouvé
(`_coup_maximal`) même quand un joker du tapis était récupérable (échangeable contre une
tuile identique de la main) et aurait permis, une fois replacé ailleurs, un coup nettement
meilleur (plus de tuiles posées, plus de points). `_coup_scission` existait déjà mais
seulement en dernier recours, selon un seul patron.

## Modification (`src/rummikub/moteur/ia.py`)
- `_jokers_recuperables(plateau, chevalet)` : détecte les jokers du plateau échangeables
  contre une tuile identique de la main (même valeur/couleur pour une suite ; même valeur
  et une couleur absente du groupe pour un groupe).
- `_coup_avec_joker_recupere(etat, idx, ordre_points)` : pour chaque joker récupérable,
  simule l'échange puis tente de replacer le joker libéré ailleurs sur le plateau (nouvelle
  combinaison ou extension), et retourne le meilleur coup obtenu.
- `_valeur_coup(etat, idx, coup)` : valeur comparative d'un coup `(nb tuiles jouées, points
  posés)`, utilisée pour départager les coups candidats.
- `_meilleur_coup_avec_joker(etat, idx, ordre_points)` : compare le coup évident
  (`_coup_maximal`) et le coup de récupération de joker, retourne le meilleur des deux.
- `jouer_niveau_avance` et `jouer_niveau_expert` utilisent désormais
  `_meilleur_coup_avec_joker` à la place de `_coup_maximal`. Facile/Intermédiaire/Débutant
  ne sont pas modifiés — l'amélioration vise uniquement Avancé/Expert comme demandé.

## Tests (`tests/test_ia.py`)
Scénario dédié (`_etat_avec_joker_recuperable`) : suite rouge 4-5-(joker=6) au tapis ;
chevalet du bot avec un rouge 6 (reprise du joker), un noir 9 + un bleu 9 (groupe complet
uniquement avec le joker libéré), et un rouge 7 (extension évidente sans toucher au joker).
- Avancé/Expert choisissent le coup de récupération (4 tuiles posées, 31 pts) plutôt que
  l'extension évidente (1 tuile, 7 pts).
- Facile/Intermédiaire jouent toujours l'extension évidente (rouge 7 seul) — comportement
  inchangé.
