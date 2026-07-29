# TACHES — Projet Rummikub

## En cours

- Refonte UI accueil (panneau joueurs unifié, boutons d'ajout par niveau,
  section Parties simplifiée, suppression thème plateau)
- Zone de travail 4 rangées + extension des combinaisons du tapis

## À faire

- Polish UI général après tests visuels (couleurs, espacements, lisibilité)
- Icône application (assets/rummikub.ico) pour le build Windows
- Build Windows via CCW (pyinstaller rummikub.spec)
- Tests visuels avec pywebview sur Linux puis Windows

## Bugs connus / points d'attention

- Fin de manche simplifiée : "tous bloqués" est approximé par "pioche vide"
  (détection exacte nécessiterait un générateur de coups complet)
- jeu_nouvelle_manche non encore implémenté côté Python (stub dans api.py)

## Idées futures

- IA "God mode" : moteur de recherche arborescente avec élagage (minimax
  ou MCTS) pour un adversaire vraiment difficile à battre
- Statistiques de parties (tuiles moyennes posées par tour, taux de victoire)
- Variante multi-manches avec score cumulé et élimination
- Son/animation quand un joueur crie "Rummikub !"
- Thème visuel alternatif pour le plateau et les tuiles

## Fonctionnalités implémentées (notes)

- Récupération de joker du tapis (Issue #12) : le cas le plus courant de
  manipulation du tapis est désormais géré. Le joueur sélectionne une tuile
  du chevalet puis clique sur un joker posé (hors tuiles jouées ce tour) ;
  la tuile remplace le joker à sa position exacte et le joker atterrit dans
  la rangée active de la zone de travail (il doit être rejoué).
- Mode manipulation du tapis (Issue #23) : bouton « Mode tapis » (barre
  d'actions, à côté d'Annuler), activable seulement à son tour et après la
  mise initiale. Quand il est actif, toutes les tuiles du tapis (hors tuiles
  posées ce tour) deviennent « prenables » (curseur de déplacement) : un clic
  retire la tuile de sa combinaison, l'ajoute à tuilesCeTour/tuilesOrigineTapis
  et la place dans la rangée de travail active où elle est sélectionnée, prête
  à être envoyée vers une extension d'une autre combinaison ou à former une
  nouvelle combinaison. Une combinaison source réduite à moins de 3 tuiles
  reste affichée en rouge jusqu'à correction ou annulation. « Vérifier et
  calculer » et « Jouer » valident l'ensemble du plateau proposé ; « Annuler »
  restaure l'état complet de début de tour (backup serveur).

## Décisions d'architecture prises

- Pas de drag & drop HTML5 (incompatible pywebview) → clic-clic pour tout
- IA par heuristiques (pas minimax) : suffisant pour les 5 niveaux actuels
- Fenêtre unique pywebview avec load_url (pas de multi-fenêtre comme
  l'ancien Scrabble)
- État de partie = dict JSON-sérialisable pur (jamais d'objets Python
  dans l'état)
- backup_debut_tour appelé dans api.py, pas dans le moteur
