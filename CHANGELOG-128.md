# Issue #128 — Bouton « Placer » par zone de pose + mise en évidence des tuiles du tour en cours sur le tapis

## Contexte
Jusqu'ici, les tuiles composées dans une zone de pose restaient dans un
espace totalement séparé du tapis jusqu'au clic sur « Jouer », qui les
transférait toutes d'un coup et validait le tour. Il était donc impossible
de combiner les tuiles d'une zone de pose avec celles déjà présentes sur le
tapis (ex. étendre une suite existante) avant la validation définitive.

## Ajouts / changements
- **Bouton « ⬆ Placer » par zone de pose** (`jeu.html`, `jeu.css`,
  `jeu.js` : fonction `placerRangee()`) : transfère immédiatement les tuiles
  de la zone sur le tapis (`plateauLocal`), sans valider le tour — rien n'est
  envoyé au serveur à ce stade, seul « Jouer » le fait. N'apparaît que si la
  zone n'est pas vide (même convention que « Vider »/« Trier »).
- **Pourtour coloré sur le tapis** : les tuiles posées ce tour (via « Placer »,
  une extension de combinaison ou une récupération de joker) portent déjà la
  classe `.ce-tour` (bordure verte) — ce rendu s'applique désormais aussi aux
  tuiles transférées par « Placer ».
- **Réarrangement unifié** (`rafraichirPlateau()`) : une fois la mise initiale
  faite, une tuile du tour en cours se manipule avec EXACTEMENT le même
  mécanisme que les tuiles des tours précédents (clic pour la prendre,
  double-clic, insertion ciblée) — y compris en la combinant avec d'autres
  tuiles du tour en cours ou déjà présentes. Avant la mise initiale (où ce
  mécanisme de réarrangement n'existe pas encore), le comportement précédent
  (reprise directe vers la main) est conservé à l'identique.
- **« Jouer »** reste inchangé : il valide l'ensemble du tapis
  (`plateauLocal` + zones de pose encore non placées), fige les combinaisons
  et retire le pourtour coloré (`tuilesCeTour` est vidé par `reinitTour()`
  après succès).
- **« Annuler »** : vérifié sans changement nécessaire — comme les tuiles
  « Placées » ne vivent que dans l'état local (`plateauLocal`/`travail`)
  jusqu'à « Jouer », `onAnnuler()` les efface déjà intégralement en
  réinitialisant `plateauLocal` depuis l'état serveur (`reinitTour()`).
- **2 zones de pose au lieu de 4** (`jeu.html`, `jeu.css`) : la grille passe
  d'un agencement 2×2 à une seule ligne de 2 colonnes. La hauteur libérée est
  réattribuée au tapis : `#zone-plateau-scroll` passe de 260px à 330px de
  hauteur maximale.

## Validation
- `node --check src/rummikub/ui/web/jeu.js` : OK.
- `python3 -m pytest` : 25 tests, tous au vert (aucune régression — ce
  changement est entièrement côté client, aucun fichier Python modifié).
- Relecture manuelle du flux complet : chevalet → zone de pose → « Placer »
  (tuiles sur le tapis avec pourtour vert) → réarrangement sur le tapis avec
  le mécanisme existant (prise, insertion, combinaison avec d'autres tuiles
  du tour) → « Jouer » (validation, pourtour retiré) ou « Annuler » (retour
  complet à l'état de début de tour, y compris les tuiles déjà « Placées »).
