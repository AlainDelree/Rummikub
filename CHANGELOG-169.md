# Issue #169 — L'IA ignore des jokers récupérables alors qu'elle a en main la tuile nécessaire

Suite de #148 (échange direct) et #150 (détachement en bout de suite) :
Alain a observé que l'IA Avancé/Expert ignorait un joker récupérable alors
qu'elle avait pourtant la tuile nécessaire en main, quand **plusieurs**
jokers étaient simultanément récupérables sur le plateau.

## Cause

`_coup_avec_joker_recupere` et `_coup_avec_joker_detache` (`ia.py`)
traitaient chaque joker récupérable **indépendamment** : pour chaque
candidat, elles construisaient un coup qui ne récupérait/replaçait QUE ce
joker-là, puis ne gardaient que le meilleur de ces coups à un seul joker.
Quand deux jokers étaient récupérables (sur deux combinaisons distinctes du
plateau), le second était donc toujours purement et simplement abandonné,
même si le chevalet permettait de récupérer les deux dans le même tour et
même si c'était la seule façon de jouer quoi que ce soit.

Reproduit avec un plateau à deux suites (`rouge 4-5-(joker=6)` et
`bleu 7-8-(joker=9)`) et un chevalet contenant les deux tuiles de reprise
(`rouge 6`, `bleu 9`) plus deux paires insuffisantes pour une combinaison
seules (`noir 2`/`jaune 2`, `noir 3`/`jaune 3`) : avant le correctif,
l'IA Avancé ne récupérait qu'un seul joker, replaçant l'autre libéré nulle
part et abandonnant la seconde récupération ; en réalité les deux jokers
libérés peuvent former ensemble une suite `1-2-3-4` en noir
(`joker-noir_2-noir_3-joker`), ce qui permet de jouer les deux à la fois.

## Correctif

`src/rummikub/moteur/ia.py` : remplacement de `_coup_avec_joker_recupere`
et `_coup_avec_joker_detache` par une approche combinatoire :

- `_liberations_possibles(plateau, chevalet)` : rassemble, sous une forme
  uniforme, toutes les libérations de joker possibles — échange direct
  (`_jokers_recuperables`, inchangée) **et** détachement en bout de suite
  (`_jokers_detachables_par_extension`, inchangée).
- `_coup_depuis_liberations(...)` : applique un sous-ensemble donné de
  libérations simultanément (plateau copié une fois, chaque joker libéré
  devant être replacé ailleurs sous peine de rejet du sous-ensemble), puis
  cherche le meilleur placement des tuiles restantes comme avant.
- `_meilleur_coup_liberations(...)` : essaie TOUS les sous-ensembles non
  conflictuels de libérations (combinaisons distinctes du plateau, tuiles
  de reprise/extension distinctes) — borné en pratique par le nombre de
  jokers en jeu (2 au maximum) donc sans coût de performance notable — et
  garde celui dont `_valeur_coup` (nb tuiles jouées, points) est le
  meilleur.
- `_meilleur_coup_avec_joker` délègue maintenant à
  `_meilleur_coup_liberations` au lieu de comparer séparément échange et
  détachement ; elle peut donc retourner un coup combinant les deux
  mécanismes à la fois si le plateau s'y prête.

Deux libérations portant sur la MÊME combinaison du plateau ne sont jamais
combinées (cas rare — deux jokers dans une même suite — laissé de côté par
prudence, sans régression puisque chacun restait déjà testé seul comme
avant).

## Tests

`tests/test_ia.py` : deux nouveaux tests de régression
(`test_avance_recupere_les_deux_jokers_a_la_fois`,
`test_expert_recupere_les_deux_jokers_a_la_fois`) vérifient que, face à un
plateau avec deux jokers récupérables par échange direct sur deux suites
distinctes, l'IA Avancé/Expert les récupère tous les deux dans le même
coup (seule façon de jouer dans ce scénario). Les tests existants de #148
et #150 (joker unique, échange ou détachement) passent toujours sans
modification. Suite complète : 35 tests, tous au vert.
