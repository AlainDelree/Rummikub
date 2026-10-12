# Issue #157 — Suite #144/#149 : « Dernier coup » affichait parfois une pose périmée au lieu de la pioche réellement jouée

## Contexte
Le bouton « Dernier coup joué par l'ordinateur » (issue #144) ne mémorisait `dernier_coup_ia`
que lorsque l'IA posait réellement des tuiles. Si le tour suivant de l'IA se soldait par une
pioche ou un passage, ce champ n'était jamais mis à jour : le bouton continuait donc d'afficher
(et de proposer le rejeu animé) d'une ancienne pose, alors que le dernier coup réellement joué
n'avait rien posé sur le tapis.

## Correctif (`api.py`, `jeu.js`)

### `jeu_ia_jouer` (`api.py`)
`dernier_coup_ia` est désormais toujours réécrit après le tour de l'IA, quel que soit le
résultat, avec un nouveau champ `"type"` : `"pose"`, `"piocher"` ou `"passer"`. Le cas du coup
invalide proposé par l'IA (repli sur une pioche de secours) est bien étiqueté `"piocher"`, pas
`"jouer"` (l'action initialement proposée par `jouer_ia`).

### Bouton et rejeu (`jeu.js`)
- `rafraichirBoutonRejouerIA()` distingue maintenant les 3 types : seul `"pose"` active le
  bouton avec le libellé de rejeu habituel ; `"piocher"`/`"passer"` désactivent le bouton et
  affichent un libellé fidèle au coup réel (« X a pioché » / « X a passé son tour »).
- `rejouerDernierCoupIA()` refuse désormais explicitement de rejouer un coup dont le type n'est
  pas `"pose"` (garde défensive, le bouton étant de toute façon désactivé dans ce cas).
- Compatibilité : les parties sauvegardées avant ce correctif n'ont pas de champ `"type"` dans
  `dernier_coup_ia` — il est alors traité comme `"pose"` (comportement historique, ce champ
  n'étant auparavant renseigné que pour une pose).

## Résultat
Le bouton « Dernier coup » reflète toujours exactement le tout dernier coup joué par l'IA, que
ce soit une pose (rejouable), une pioche ou un passage (affichés mais non rejouables).
