# Issue #191 — Suite #189 : pas-à-pas du rejeu cohérent + cadre « tuiles à placer »

## Constat

Le pas-à-pas introduit par #189 comparait seulement les combinaisons
avant/après, sans suivre les tuiles individuellement. Conséquences
constatées en jeu sur un coup de Bruno (Expert) :
- une même tuile (un joker) apparaissait sur deux combinaisons à la même
  étape — impossible dans la réalité du jeu ;
- des étapes n'affichaient aucun changement visible par rapport à la
  précédente ;
- les textes avaient des tournures de message automatique (« Combinaison
  modifiée : le groupe de 3 », « Joker déplacé de le groupe de 3 vers le
  groupe de 11 ») plutôt que du français naturel ;
- sur un coup plus complexe (plusieurs combinaisons défaites/reformées),
  rien n'indiquait si deux combinaisons de même nom à des moments
  différents étaient les mêmes tuiles ou non, et le joueur ne voyait jamais
  l'état de départ ni la provenance des tuiles.

## Correctif

Réécriture complète de `moteur/description_coup.py` : chaque tuile est
suivie individuellement par son identifiant, de sa position d'avant à sa
position d'après (`_construire_operations`). Les combinaisons dont une
majorité stricte des tuiles continue ensemble sont des « update » (elles
gardent leur identité, swap possible en un seul changement) ; les autres se
dissolvent tuile par tuile via des opérations « retrait » regroupées par
destination (jamais toutes en une fois) ; les combinaisons sans continuation
sont des « create ». Un tri topologique causal ordonne ces opérations en
privilégiant les échanges de jokers dès qu'ils sont possibles, sans jamais
exiger qu'une tuile soit consommée avant d'avoir été libérée.

Le rejeu pas-à-pas (`etapes_coup_ia`) expose désormais, à chaque étape, un
cadre **« tuiles à placer »** (`etape["cadre"]`) qui contient les tuiles pas
encore reposées (venues de la main ou libérées du plateau, taguées
différemment) : chaque tuile n'est donc jamais, à aucune étape, à la fois
sur le plateau ET dans le cadre. La suite commence par un écran « Départ »
(plateau d'avant, cadre rempli) suivi, si des jokers bougent, d'un écran
« Les jokers » qui donne la vue d'ensemble de leur trajet. Les combinaisons
mi-démantelées sont marquées « provisoires » (distinct de « combinaison
invalide ») tant qu'elles ne sont pas résolues.

`decrire_coup_ia` (résumé affiché sous « Dernier coup joué par... ») est
réécrit en français naturel avec les contractions correctes (du/au/des/aux)
et désambiguïse par les couleurs deux combinaisons de même nom apparues à
des moments différents du coup (« le groupe de 11 rouge, bleu et noir est
défait » / « un nouveau groupe de 11 bleu, jaune et noir est formé »).

Front-end (`jeu.js`/`jeu.html`/`jeu.css`) : nouvelle zone « Tuiles à
placer » au-dessus de l'aperçu du plateau dans l'overlay pas-à-pas,
réutilisant les pourtours vert/orange de la légende existante pour
distinguer tuile de la main et tuile libérée du plateau ; marquage visuel
« provisoire » distinct de « combinaison invalide » ; surbrillance des
tuiles juste posées/libérées à chaque étape (réutilise `.tuile-ia-highlight`
existant). Le seuil d'affichage du bouton « Pas à pas » passe de
`etapes.length >= 2` au nombre de changements réels (hors écrans
« Départ »/« Les jokers », qui n'existaient pas avant cette issue).

## Tests

`tests/test_description_coup.py` : contractions, coups simples, joker
récupéré puis rejoué (avec vérification explicite de l'ordre causal), cas
Bruno simple (texte comparé mot pour mot à l'exemple de l'issue), coup en
chaîne Bruno/Expert (5 combinaisons d'avant, vérification tuile par tuile),
et un helper d'invariants communs (aucune tuile à deux endroits, pas
d'étape sans effet, cadre vide et plateau exact à la dernière étape).
`tests/test_playwright_pas_a_pas.py` (nouveau, nécessite `pip install
playwright` + `playwright install chromium`, absent de requirements.txt —
sauté proprement sinon) : vérifie sur `jeu.html` seul (jamais la vraie app
pywebview) le remplissage/vidage du cadre, les couleurs de pourtour, et
l'absence d'effet du bouton « Quitter ».

CONTEXTE.md §12 mis à jour.
