# Issue #138 — Reprendre individuellement une tuile du tour en cours (sans tout « Annuler »)

## Contexte

Le mécanisme pour reprendre une tuile posée ce tour (clic/double-clic sur le
tapis → `prendreTuileTapis`/`reprendreTuile`/`reprendreTuileRangee`) existait
déjà depuis les issues #128/#133/#136, mais contenait un bug qui en annulait
l'intérêt dans le cas précis visé par cette issue : une tuile venant de la
main, posée ce tour-ci, puis redéplacée au sein du tapis (ex. sortie d'une
combinaison pour la recombiner ailleurs), était marquée à tort comme
« origine tapis ». Une fois cette étiquette posée à tort, `reprendreTuileRangee`
refusait de la renvoyer à la main (règle légitime pour une VRAIE tuile du
tapis — elle n'appartient pas au joueur) — le seul recours redevenait alors
« Annuler », qui réinitialise tout le tour. C'est exactement le problème
décrit par l'issue.

## Correctif (`jeu.js`)

- `prendreTuileTapis(idxCombo, idxTuile)` : calcule désormais `venaitDeLaMain`
  (la tuile est déjà dans `tuilesCeTour` et n'est PAS encore taguée
  `tuilesOrigineTapis`) **avant** de muter l'état, puis n'ajoute la tuile à
  `tuilesOrigineTapis` que si elle ne vient pas de la main. Une tuile de main
  redéplacée au sein du tapis garde ainsi son identité « main » et peut
  toujours repartir au chevalet individuellement.
- `reprendreTuileRangee(id, indexRangee)` : ajout de l'appel symétrique
  `rendreAuChevaletServeur(d)` dans la branche « retour au chevalet », comme
  le fait déjà `reprendreTuile` pour le chemin direct `etendreTapis`/
  `insererTuileTapis`. Sans cet appel, une tuile de main posée directement sur
  une combinaison existante (chemin qui retire la tuile du chevalet serveur),
  puis reprise via le mécanisme de manipulation du tapis et renvoyée à la
  main, restait durablement absente du chevalet serveur — désynchronisant le
  compteur de tuiles affiché sur la fiche du joueur jusqu'à la fin du tour.
  Ce chemin n'était tout simplement pas atteignable avant la correction
  ci-dessus (la tuile y était toujours mal étiquetée « origine tapis »),
  donc le bug n'avait pas d'effet observable jusqu'ici.

## Résultat

Une tuile posée par erreur ce tour (qu'elle vienne de la main ou qu'elle ait
été déplacée depuis une combinaison déjà sur le tapis) peut désormais être
reprise individuellement et repositionnée ou rendue à la main, sans affecter
le reste des tuiles déjà placées ce tour — plus besoin de passer par
« Annuler » pour corriger une seule tuile mal placée.

## Vérifications

- `node --check src/rummikub/ui/web/jeu.js` : syntaxe valide.
- `pytest` (suite existante, moteur non touché) : 25 passés.
- Lecture manuelle de tous les chemins touchant `tuilesCeTour`/
  `tuilesOrigineTapis`/chevalet serveur (`placerTuileDansRangee`,
  `insererTuileRangee`, `placerRangee`, `viderRangee`, `etendreTapis`,
  `insererTuileTapis`, `reprendreTuile`, `prendreTuileTapis`,
  `reprendreTuileRangee`, `reinitTour`) pour confirmer l'absence de
  régression sur les tuiles réellement issues d'un tour précédent (elles
  restent non renvoyables à la main, comme attendu).
