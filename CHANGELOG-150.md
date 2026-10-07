# Issue #150 — IA : détacher un joker en bout de suite quand une extension à l'autre bout rend la portion réelle suffisamment longue

## Contexte
#148 a ajouté la récupération d'un joker par échange direct (tuile de la main identique au
joker). Cas distinct et non couvert : un joker en BOUT de suite (ex. 3-4-joker, le joker
représentant le 5) peut devenir détachable SANS aucune tuile de remplacement, si l'IA pose une
tuile à l'AUTRE bout de la suite qui allonge suffisamment la portion réelle (ex. ajouter un 2 →
2-3-4-joker) pour qu'elle atteigne seule la longueur minimale de 3 tuiles (2-3-4, valide sans le
joker). Une tuile en bout de suite peut toujours être retirée sans casser la validité, tant que
ce qui reste respecte la longueur minimale — contrairement à une tuile au milieu (`_coup_scission`)
ou à l'échange direct (`_jokers_recuperables`, #148).

## Modification (`src/rummikub/moteur/ia.py`)
- `_jokers_detachables_par_extension(plateau, chevalet)` : détecte, pour chaque suite du
  plateau ayant un joker en bout, si une tuile réelle du chevalet jouée à l'extrémité opposée
  permet à la portion réelle restante (joker exclu) d'atteindre seule la longueur minimale
  (≥3) et de rester valide.
- `_coup_avec_joker_detache(etat, idx, ordre_points)` : pour chaque détachement possible,
  simule l'extension (qui retire le joker de la suite d'origine), puis tente de replacer ce
  joker ailleurs sur le plateau (nouvelle combinaison ou extension) ; retourne le meilleur coup
  obtenu, ou `None` si le joker détaché ne peut être replacé nulle part (dans ce cas le
  détachement n'a pas lieu — le coup simple d'extension reste seul candidat).
- `_meilleur_coup_avec_joker` compare désormais trois coups : l'extension/combinaison évidente
  (`_coup_maximal`), la récupération de joker par échange direct (#148,
  `_coup_avec_joker_recupere`) et le détachement en bout de suite (`_coup_avec_joker_detache`) ;
  retourne le meilleur des trois via `_valeur_coup`.
- `jouer_niveau_avance` et `jouer_niveau_expert` restent les seuls niveaux à bénéficier de
  `_meilleur_coup_avec_joker` — Facile/Intermédiaire/Débutant ne sont pas modifiés.
- Le joker détaché n'est jamais gardé en main au-delà du tour en cours : soit il est replacé
  dans le même coup (`ids_tuiles` ne contient que les tuiles réelles jouées depuis la main, le
  joker étant déjà sur le plateau), soit le détachement entier est abandonné.

## Tests (`tests/test_ia.py`)
Scénario dédié (`_etat_avec_joker_detachable`) : suite rouge 3-4-(joker=5) au tapis ; chevalet
du bot avec un rouge 2 (extension de l'autre bout qui libère le joker), un noir 9 + un bleu 9
(groupe complet uniquement avec le joker libéré), et un rouge 6 (extension évidente directement
après le joker, sans le détacher).
- Avancé/Expert choisissent le détachement (3 tuiles posées : rouge 2, noir 9, bleu 9) plutôt
  que la double extension évidente (rouge 2 + rouge 6, 2 tuiles, qui laisse le joker coincé).
- Facile/Intermédiaire étendent toujours les deux bouts de la suite (rouge 2 et rouge 6) sans
  jamais détacher le joker — comportement inchangé.
