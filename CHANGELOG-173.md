## Issue #173 — "Vérifier et calculer" affiche les points du tour, pas du plateau

- `api.jeu_verifier_plateau` accepte désormais un second paramètre optionnel
  `ids_ce_tour` et retourne en plus `points_ce_tour` (somme des points des
  combinaisons valides contenant au moins une tuile posée ce tour).
- `jeu.js` (`onVerifierCalc`) : avant la mise initiale, affiche
  "✓ Plateau valide — N points" avec N = points posés CE TOUR uniquement
  (au lieu du total de tout le plateau). Une fois la mise initiale faite
  (`tapisManipulable()` vrai), affiche seulement "✓ Plateau valide", sans
  chiffre, puisque le seuil de 30 points ne s'applique plus.
- La vérification de validité globale du plateau (nécessaire pour "Jouer")
  reste inchangée.
