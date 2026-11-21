# Issue #253 — Joker : ne poser un joker en main que s'il est utile, ne plus laisser de joker libre, camoufler le joker repris (REMPLACE la règle d'attente de #252)

## Constat

La mesure de #252 (16 donnes) montrait que sa définition de « joker
offert » était trop large (joker au milieu d'une suite de 3/4 tuiles
compté comme offert) et que l'essentiel des cas relevés (40/44) étaient des
jokers de la MAIN posés par l'IA elle-même sans que cela lui serve — pas
des jokers laissés accessibles sur le tapis. La règle de #252 faisait
perdre des tours (~9 %) pour un résultat presque nul.

## Nouvelle définition d'un joker LIBRE (REMPLACE « joker offert »)

Un joker est **libre** si N'IMPORTE QUI peut le reprendre à son tour SANS
poser aucune tuile ET sans recomposer le tapis : bout de suite d'au moins
4 tuiles, groupe de 4, ou scission en milieu d'une suite d'au moins 7
tuiles. Un joker au milieu d'une suite de 3/4 tuiles, ou dans un groupe de
3, n'est PAS libre. `jokers_libres_sur_plateau`/`jokers_rendus_libres_par_
coup` (`moteur/ia.py`) remplacent `jokers_offerts_sur_plateau`/`jokers_
offerts_par_coup` — le chevalet hypothétique de #252 (tuiles non vues) est
supprimé, la nouvelle définition ne dépendant plus d'aucune main.

## Quatre règles, appliquées dans cet ordre (`jouer_niveau_bride`)

1. **Joker en main utile** (`_appliquer_joker_utile`) : un joker de main
   n'est joué que si le meilleur coup avec lui pose STRICTEMENT plus de
   tuiles réelles (jokers exclus) que le meilleur coup sans aucun joker de
   main (ouverture rendue possible comprise) — sinon il est gardé.
2. **Échange différé** (`_appliquer_echange_differe`) : un échange
   facultatif (l'IA détient la tuile exacte) « en réserve » (autre
   exemplaire visible sur le plateau, aucune recombinaison du plateau seul
   ne le libère) et inemployable avec la main est différé au plus 3 tours
   (2 si un adversaire a moins de 5 tuiles) — compteur par joker
   (`niveaux.CLE_ATTENTE_ECHANGE_DIFFERE`), remis à 0 une fois l'échange
   fait ou la réserve cessée.
3. **Joker libre évité** (`_appliquer_joker_libre`) : si le coup rend
   libre un nouveau joker, cherche une alternative (sans réarrangement,
   puis en retirant chaque tuile jouée), quitte à poser moins de tuiles ;
   sinon pioche — **sans compteur ni limite** (l'attente bornée à 2 tours
   de #252, `LIMITE_ATTENTE_DON_JOKER`/`CLE_ATTENTE_DON_JOKER`, est
   SUPPRIMÉE).
4. **Camouflage du joker repris** : effet du point 3 ci-dessus, appliqué
   génériquement (pas de fonction séparée) — voir limite assumée dans le
   fichier de domaine (préférence pour la recombinaison la plus profonde
   NON implémentée, scope explicitement documenté).

Exception absolue inchangée : un coup qui vide le chevalet est TOUJOURS
joué, avant toute vérification ci-dessus.

## Paramètres et désactivation (noms conservés de #252)

`niveaux.Bridage.eviter_don_joker` (activé pour Intermédiaire/Avancé/
Expert) gouverne maintenant l'ensemble ci-dessus. `jouer_niveau_bride(...,
eviter_don_joker=...)` et `scripts/comparer_niveaux_ia.py --sans-don-
joker-a`/`-b` (noms de drapeau conservés) permettent de désactiver la
règle pour comparer.

## Mesure (`scripts/comparer_niveaux_ia.py`)

Nouveaux compteurs par camp : jokers libres laissés (hors coup gagnant) /
coups joués, pioches dues à un joker libre, jokers de main gardés,
échanges différés et pioches qu'ils ont forcées. Essai de 20 donnes, Expert
contre Expert, graine 42 : sans aucune règle, 1/524 (0,2 %) laissent un
joker libre (confirme l'observation d'Alain : le problème est quasi
inexistant sous la nouvelle définition) ; avec la règle, 0/531 (0,0 %), 2
pioches forcées, 5 jokers de main gardés, 1 échange différé. Temps de
calcul Expert : 78,3 ms → 91,5 ms en moyenne (+17 %), maximum inchangé
(1496 ms → 1462 ms) — bien plus léger que #252 (qui doublait le temps
moyen). Commandes de campagne appariée (≥ 300 donnes, Expert contre
Expert et Intermédiaire contre Avancé) ajoutées dans `CONTEXTE.md` §19,
à lancer par Alain.

## Documentation

`docs/contexte/ia_anti_don_joker.md` réécrit sur place : nouvelle
définition, arbre de décision complet (ordre exact des étapes, bornes en
toutes lettres), un exemple par règle et par branche (cas limites inclus :
égalité, deux jokers, ouverture non faite, adversaire à 5 tuiles, coup
gagnant), les points où la formulation de l'issue laissait un doute (choix
fait, à confirmer par Alain), et la correspondance condition → test.
`CONTEXTE.md` §19 remplacé (les textes de #252 sur l'attente devenaient
faux).

## Tests

`tests/test_ia_anti_don_joker.py` entièrement réécrit (26 tests) : chaque
cas fixe demandé par l'issue (joker utile/gardé, coup gagnant avec/sans
joker, les trois définitions de « libre » et leurs trois contre-exemples,
alternative sans joker libre, pioche sans compteur ni limite, échange
facultatif repris/camouflé/décliné/gagnant, échange différé jusqu'à 3 ou 2
tours, immédiat si utilisable/gagnant/hors réserve, compteur retiré si la
réserve cesse, Débutant/Facile inchangés, règle désactivée). Suite complète
(494 tests) verte.

## Limite assumée (à confirmer par Alain)

La préférence, parmi plusieurs placements non libres d'un joker repris,
pour celui exigeant la recombinaison la plus profonde n'est PAS implémentée
(analyse structurelle + risque de modifier l'objectif lexicographique du
solveur exact, voir le fichier de domaine §6). Le choix d'interprétation
du point 6 (l'échange forcé après expiration du délai n'est plus resoumis
au point « joker libre évité », pour éviter qu'il annule systématiquement
la décision de forcer) est aussi documenté dans le fichier de domaine et
reste à confirmer.
