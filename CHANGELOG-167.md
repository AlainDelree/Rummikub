# Issue #167 — Légende des pourtours : chiffres aléatoires + couleurs plus visibles

Deux retours sur la légende ajoutée par #159 (sous le sac de pioche) :

1. **Chiffre aléatoire sur les tuiles d'exemple** (`jeu.js`,
   `afficherLegendeCouleurs`) : chaque mini-tuile de la légende tirait un
   chiffre fixe (7, 7, 7, 5, 6). Remplacé par un tirage aléatoire 1-13 par
   tuile (`valeurAlea()`), à chaque construction de la légende — rend
   l'exemple plus parlant qu'un chiffre toujours identique.
2. **Pourtours vert/orange/bleu plus visibles dans la légende** (`jeu.css`) :
   à la taille réduite des mini-tuiles (22px), la bordure 1px + léger halo
   utilisés en jeu réel pour `.ce-tour`/`.deplacee-tapis`/`.tuile-ia-deplacee`
   passaient inaperçus. Ajout de règles `.legende-tuile-mini.ce-tour` /
   `.legende-tuile-mini.deplacee-tapis` (et renforcement de la règle
   `.tuile-ia-deplacee` existante) : bordure épaissie à 2.5px et halo
   (`box-shadow`) renforcé, appliqués **uniquement** via le préfixe
   `.legende-tuile-mini` — l'apparence des pourtours en jeu réel
   (`commun.css` / `jeu.css`) n'est pas modifiée, pour éviter qu'ils
   deviennent trop criards sur le tapis pendant une partie.

Fichiers touchés : `src/rummikub/ui/web/jeu.js`, `src/rummikub/ui/web/jeu.css`.
