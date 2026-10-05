## Issue #129 — Suite #128 : pourtour coloré sur extension directe + masquage "Jouer" pendant le jeu auto de l'IA

- **Pourtour du tour en cours (`.ce-tour`) peu visible sur une extension directe d'une combinaison du tapis.**
  Investigation approfondie (tests automatisés Playwright couvrant tous les chemins d'extension :
  zone début/fin/interne, avant/après mise initiale, plusieurs combinaisons) : la classe `.ce-tour`
  est en réalité déjà appliquée correctement par le JS (`jeu.js`) dans tous les cas, y compris
  l'extension directe — ce n'est donc pas un bug de logique. En revanche, une fois la mise initiale
  faite, la tuile du tapis reçoit *aussi* la classe `.tapis-manipulable` (contour pointillé bleu,
  2px, hors-bordure), qui écrase visuellement le pourtour vert de 1px de `.ce-tour` — exactement
  le cas de figure systématique lors d'une extension directe (impossible avant la mise initiale).
  Correction : `.tuile-jeu.ce-tour.tapis-manipulable` reprend désormais la couleur verte pour son
  contour au lieu du bleu, rendant le pourtour du tour en cours incontestable même combiné à l'état
  « manipulable » (`jeu.css`).
- **Bouton « Jouer » de l'IA masqué pendant le jeu automatique.** Quand le réglage "Jouer
  automatiquement le tour de l'ordinateur" (#126) est actif et que c'est au tour de l'IA, le bouton
  manuel `.btn-jouer-ia` n'est plus affiché le temps que le coup automatique se déroule — il
  réapparaît normalement dès que c'est de nouveau au tour d'un joueur humain ou que le réglage est
  désactivé (`jeu.js`, `rafraichirFichesJoueurs`). Supprime le risque de déclenchement concurrent
  identifié dans l'issue.
