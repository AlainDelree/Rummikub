# Issue #151 — Le blocage par clic sur "Piocher" pendant le tour de l'IA persiste malgré #146

## Contexte
#146 avait posé une garde serveur (`_tour_est_humain`) et une garde client (`estMonTour()`,
bouton désactivé par défaut) contre le blocage du jeu provoqué par un clic sur "Piocher" pendant
le tour de l'IA. Après fusion, le blocage se reproduisait toujours, mais UNIQUEMENT quand l'IA
pose des tuiles sur le tapis, jamais quand elle pioche — ce qui pointait vers l'animation de pose
tuile par tuile (`animerPoseTuiles()`, ralentie depuis #149).

## Cause confirmée (`src/rummikub/ui/web/jeu.js`, `jouerIA()`)
`jeu_ia_jouer()` renvoie un état déjà avancé par le serveur (le coup de l'IA est entièrement
traité côté serveur avant la réponse) : `etat = nouvelEtat;` est donc exécuté en tout début de
`jouerIA()`, AVANT que l'animation de pose (`animerPoseTuiles()`, 1 à plusieurs secondes selon le
nombre de tuiles) ne commence. `estMonTour()` lit cet `etat` déjà à jour et redevient vraie
immédiatement — or `jouerIA()` appelait `rafraichirBoutons()` (qui réactive "Piocher" selon
`estMonTour()`) juste avant de lancer `animerPoseTuiles()`, et non après. Résultat : une fenêtre
d'environ 1 à plusieurs secondes où le bouton "Piocher" est RÉACTIVÉ alors que l'animation visuelle
de pose de l'IA est encore en cours. Un clic dans cette fenêtre est accepté par le serveur (c'est
réellement déjà le tour de l'humain côté serveur) mais entre en course avec la boucle asynchrone
de `animerPoseTuiles()` qui continue de réécrire `plateauLocal`/le chevalet en arrière-plan,
provoquant la désynchronisation visuelle puis le blocage. Cette fenêtre est différente de celle
testée par #146 (latence AVANT le coup de l'IA, pas durée de l'animation APRÈS le coup).

## Correctif (`src/rummikub/ui/web/jeu.js`)
- Nouveau drapeau de module `animationCoupIAEnCours`, pris en compte par `estMonTour()` en plus
  de `index_joueur_actuel` et `manche_terminee` : tant qu'il est vrai, `estMonTour()` renvoie
  faux quel que soit l'état serveur déjà reçu.
- `jouerIA()` pose ce drapeau à `true` dès son tout début (avant même l'appel réseau) et ne le
  repasse à `false` qu'immédiatement avant chacun de ses appels à `rafraichirTout()` — y compris
  sur le chemin d'erreur (`catch`) et sur le cas pioche/passe de l'IA — de sorte qu'il reste vrai
  pendant toute la durée de `animerPoseTuiles()`.
- Suppression de l'appel prématuré à `rafraichirBoutons()` juste avant `animerPoseTuiles()` :
  comme les boutons d'action sont déjà désactivés depuis le tour précédent (celui de l'IA) et que
  rien ne les réactive plus tôt que prévu, ils ne sont désormais réactivés que par le
  `rafraichirTout()` final, une fois l'animation terminée.
- Comme `tapisManipulable()` et toutes les gardes d'action (`onPiocher`, `onPasser`,
  `onJouerCoup`, `onAnnuler`, réorganisation du tapis par glisser-déposer, etc.) s'appuient toutes
  sur `estMonTour()`, la correction couvre non seulement "Piocher" mais aussi les autres actions
  mentionnées dans la demande.

## Vérification
`node --check src/rummikub/ui/web/jeu.js` : syntaxe valide. Lecture de code ciblée confirmant
que plus aucun appel à `rafraichirBoutons()`/`rafraichirTout()` ne peut survenir, dans quelque
chemin de `jouerIA()`, avant la fin réelle de `animerPoseTuiles()` — le drapeau
`animationCoupIAEnCours` est la seule source de vérité pendant cette fenêtre, indépendamment de
l'état déjà avancé côté serveur. Pas de test automatisé ajouté : la logique concernée est de
l'orchestration d'animation côté JS (pas de harnais de test JS dans ce projet, seul pytest est
configuré pour le code Python).
