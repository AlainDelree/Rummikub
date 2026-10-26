# Issue #189 — Suite #149 : rejeu du dernier coup de l'IA, rendre les coups complexes compréhensibles

Depuis le solveur de réarrangement global (#186), l'IA peut défaire et
recomposer plusieurs combinaisons du plateau en un seul tour. Le rejeu animé
existant (tuile par tuile, #144/#149) suffit pour un coup simple mais pas
pour un coup complexe : le joueur ne parvient plus à suivre ce que
l'ordinateur a fait. Deux aides optionnelles, accessibles à côté du bouton de
rejeu existant (qui garde son comportement inchangé par défaut, pour tous
les coups) :

## Résumé écrit (`moteur/description_coup.py::decrire_coup_ia`)

Fonction pure, testable séparément de l'UI : compare le plateau juste avant
et juste après un coup de pose et renvoie un résumé en français, calculé à
partir de ce diff (jamais du moteur ni de l'IA, qui restent inchangés) :

- Pour chaque combinaison d'avant, sa destination d'après recevant une
  majorité stricte de ses tuiles est sa continuation (elle « survit »,
  éventuellement modifiée) ; sans majorité claire, elle est « défaite ».
- Une combinaison d'après sans continuation unique est « créée ».
- Un joker qui quitte la continuation de sa combinaison d'origine est
  signalé nommément (d'où → vers), qu'il ait été échangé contre une tuile
  réelle (issue #148) ou libéré sans remplacement (#180/#181/#183).
- Un coup ne touchant qu'une seule combinaison et sans joker déplacé reste
  résumé en une seule phrase courte ; au-delà, plusieurs phrases.

## Rejeu pas-à-pas (`moteur/description_coup.py::etapes_coup_ia`, priorité de l'issue)

Découpe le même diff en une liste d'étapes (`{"texte", "plateau"}`) :
combinaisons défaites retirées une à une, puis combinaisons créées/modifiées
ajoutées dans leur forme finale, puis déplacements de joker signalés
(informatif, même plateau). La dernière étape correspond exactement au
plateau d'après. Le bouton « 📋 Pas à pas » (`jeu.html`/`jeu.js`) ne
s'affiche que si le coup comporte au moins 2 étapes distinctes, et son clic
(`ouvrirPasAPas`) est totalement indépendant du bouton de rejeu animé —
aucun des deux ne déclenche jamais l'autre. L'overlay (`#overlay-pas-a-pas`)
est strictement en lecture seule (aucun écouteur d'interaction de jeu dans
l'aperçu du plateau) et peut être quitté à tout moment sans effet sur la
partie ; navigation Suivant/Précédent/Quitter.

## Câblage (`ui/api.py`)

`jeu_ia_jouer` (seul point d'entrée qui construit `dernier_coup_ia`) calcule
`resume` et `etapes` une seule fois, immédiatement après une pose, et les
stocke directement dans `etat["dernier_coup_ia"]` aux côtés de
`plateau_avant`/`plateau_apres` déjà existants — aucun nouvel aller-retour
JS → Python.

## Reporté : bascule Avant/Après (point 2 de l'issue)

Par manque de temps, comme explicitement autorisé par l'issue elle-même
("si le temps manque, livrer d'abord le pas à pas et le résumé écrit"). À
traiter dans une issue séparée.

## Tests

- `tests/test_description_coup.py` (nouveau, 5 tests) : coup simple
  (extension de suite, groupe créé depuis la main, aucun changement), joker
  récupéré puis rejoué dans un nouveau groupe, démantèlement complet d'un
  groupe de 12 en 3 nouvelles combinaisons (vérifie le nombre d'étapes et
  l'identité exacte de la dernière étape avec le plateau d'après).
- Vérification complémentaire via un scénario Playwright ad hoc sur
  `jeu.html` (méthode CONTEXTE.md §7, script non committé, conformément à
  la convention du projet) : résumé affiché, bouton Pas à pas visible
  seulement pour le coup complexe (absent pour le coup simple), navigation
  Suivant/Précédent/Quitter, plateau réel inchangé après fermeture de
  l'overlay.
- `pytest -q` : 105 passed (81 → 105, +5 nouveaux + aucune régression).

## Fichiers touchés

- `src/rummikub/moteur/description_coup.py` (nouveau)
- `tests/test_description_coup.py` (nouveau)
- `src/rummikub/ui/api.py` (calcul résumé/étapes dans `jeu_ia_jouer`)
- `src/rummikub/ui/web/jeu.html` (résumé, bouton Pas à pas, overlay)
- `src/rummikub/ui/web/jeu.css` (styles associés)
- `src/rummikub/ui/web/jeu.js` (affichage résumé, navigation pas-à-pas)
- `CONTEXTE.md` (nouvelle section §12)
