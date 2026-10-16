# Issue #165 — Pourtour bleu IA affiché après chaque tour, même en cas de simple pioche

## Cause

Dans `jouerIA()` (`jeu.js`), les listes de tuiles « ajoutées » et
« déplacées » étaient calculées par simple comparaison avant/après plateau
(`trouverTuilesAjoutees`/`trouverTuilesDeplacees`), puis le code décidait
*après coup* si le dernier coup de l'IA était une pose, une pioche ou un
passage — en se basant sur la description textuelle du dernier événement de
l'historique (`action.includes("pioch")`) plutôt que sur le champ fiable
`dernier_coup_ia.type` introduit par #157. Cette inférence textuelle était
fragile et pouvait se tromper, déclenchant à tort `animerPoseTuiles()` (donc
le pourtour bleu `tuile-ia-deplacee` sur l'ensemble des tuiles reconstruites)
même quand l'IA s'était contentée de piocher.

## Correction

`typeCoupIA` est maintenant lu directement depuis
`nouvelEtat.dernier_coup_ia.type` (valeurs fiables côté serveur : `"pose"`,
`"piocher"`, `"passer"`, cf. `api.py::jeu_ia_jouer`) **avant** tout calcul de
tuiles ajoutées/déplacées. `trouverTuilesAjoutees()` et
`trouverTuilesDeplacees()` ne sont désormais appelées que si
`typeCoupIA === "pose"` ; dans tous les autres cas (pioche, passage), les
deux listes restent vides par construction et aucune tuile du tapis ne reçoit
de pourtour bleu ou doré. La détection du message toast (« pioche » vs
« passe son tour ») utilise elle aussi directement `typeCoupIA === "piocher"`
plutôt que l'ancien texte d'historique.

La logique de `trouverTuilesDeplacees()` elle-même (issue #149 : ne marquer
comme déplacées que les tuiles qui rejoignent une combinaison différente de
la « continuation » majoritaire de leur ancienne combinaison) n'était pas en
cause et reste inchangée — pour une pose normale sans réarrangement, elle
continue de ne renvoyer aucune tuile puisque toutes restent dans leur
combinaison de continuation.

### Fichier modifié

- `src/rummikub/ui/web/jeu.js` — fonction `jouerIA()` : calcul de
  `typeCoupIA` déplacé avant celui de `tuiAjoutees`/`tuilesDeplacees`, ces
  deux listes conditionnées à `typeCoupIA === "pose"`, et la branche
  pioche/passe simplifiée pour utiliser directement `typeCoupIA` au lieu de
  parser l'historique.
