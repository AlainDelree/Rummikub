# Issue #170 — Boutons de vitesse du rejeu : ordre Lente / Moyenne / Rapide

Les 3 boutons de vitesse du rejeu du dernier coup IA (#164), affichés
jusqu'ici dans l'ordre Rapide / Moyenne / Lente, suivent maintenant une
gradation croissante de gauche à droite : **Lente / Moyenne / Rapide**.

Changement purement visuel (ordre des balises `<button>` dans le HTML) :
le comportement, les valeurs `data-vitesse` et les multiplicateurs associés
à chaque niveau (`MULTIPLICATEURS_REJEU_IA` dans `jeu.js`) sont inchangés —
la logique JS sélectionne les boutons via `querySelectorAll` et
`dataset.vitesse`, sans dépendre de leur position dans le DOM.

Fichier touché : `src/rummikub/ui/web/jeu.html`.
