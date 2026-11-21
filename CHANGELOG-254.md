# Issue #254 — Joker : corriger la réserve, l'échange après délai, le compteur de l'échange différé, l'évaluation joker par joker, la pioche vide et la fin de match (suite de #253)

## Contexte

La relecture du rapport de #253 et de `docs/contexte/ia_anti_don_joker.md`
a fait apparaître sept points où le code ou le texte s'écartaient des
règles voulues par Alain. Cette issue les corrige sur le code de #253 déjà
fusionné, sans modifier aucune valeur de perturbation ou d'oubli, ni le
tapis, l'interface ou les règles du jeu.

## 1. Joker « en réserve » : test complet

`_joker_en_reserve` (`moteur/ia.py`) vérifiait seulement (a) l'autre
exemplaire de la tuile de remplacement visible sur le plateau et (b) le
joker pas déjà libre. Ajout d'une troisième condition : aucune libération
SANS tuile de main (`_liberations_possibles(plateau, [])`, chevalet vide —
réutilisé tel quel, aucune réécriture) ne doit exister pour ce joker — ceci
couvre en particulier la réduction d'un groupe de 4 DÉJÀ complet
(`_jokers_liberables_par_reduction_groupe4`), absente des trois voies de
`jokers_libres_sur_plateau`. La question « l'autre exemplaire peut-il se
trouver dans la main de l'IA elle-même » est traitée explicitement dans le
fichier de domaine (§7bis) : avec `NB_SERIES=2`, les deux seuls exemplaires
existants sont déjà intégralement comptés par la condition (a) — 1 en main
de l'IA (c'est de là que vient `rec["remplacement"]`) + 1 visible sur le
plateau — la réserve n'en est donc que PLUS sûre, jamais remise en cause.

## 2. Échange après délai soumis à la règle du joker libre

#253 exemptait l'échange forcé par le délai expiré de la règle du joker
libre (§5/point 4), au motif qu'elle annulerait toujours la décision de
forcer. Ce motif est faux en général : la règle ne se déclenche QUE si le
coup rend RÉELLEMENT un nouveau joker libre. `jouer_niveau_bride` applique
désormais systématiquement `_appliquer_joker_libre` à l'échange forcé
(sauf si un débarras de fin de match a eu lieu ce même tour, point 7).

## 3. Échange différé : compter les pioches

Quand l'échange était le seul coup possible du tour, l'IA piochait sans
que le compteur d'attente n'avance — attente sans limite. `_appliquer_
echange_differe` incrémente désormais ce compteur même dans ce cas.
Vérifié cohérent dans les trois cas : autre coup joué (avance), pioche
faute d'alternative (avance aussi, NOUVEAU), tour de l'adversaire entre
deux décisions (inchangé, le compteur est propre au joueur).

## 4. Plusieurs jokers en main : évaluation séparée

`_appliquer_joker_utile` évaluait l'utilité de TOUS les jokers de la main
ENSEMBLE (chevalet privé de tous les jokers à la fois) : un joker utile
pouvait entraîner la pose de l'autre, inutile. Réécrit pour évaluer chaque
joker SÉQUENTIELLEMENT (retirer un joker confirmé non utile de l'ensemble
disponible avant de juger le suivant — nécessaire car deux jokers sont
interchangeables pour le solveur, voir le fichier de domaine §4 pour le
raisonnement complet). Un joker inutile reste en main même si l'autre est
posé ; le coup qui vide le chevalet reste toujours joué (inchangé, géré en
amont).

## 5. Pioche vide : jouer plutôt que passer sans fin

Quand la pioche est vide et qu'aucune alternative n'évite un joker libre,
`_appliquer_joker_libre` (et le point 6 de #253 dans son propre cas de
blocage) jouait quand même la pioche, qui devenait alors un simple passage
sans effet. Les deux fonctions jouent désormais le meilleur coup
disponible (`_meilleur_candidat_si_pioche_impossible`) plutôt que de
passer. Détection : `not etat.get("pioche")`, visible de tous. Un test
confirme que `moteur/partie._terminer_tour` termine déjà la manche dès que
la pioche est vide, quelle que soit l'action jouée ce tour-là
(comportement existant, non modifié) — ce chemin n'est donc normalement
observable qu'en test unitaire (état construit), jamais par un
enchaînement naturel de tours réels, mais reste nécessaire comme filet de
robustesse (replay, analyse de coups ratés).

## 6. Camouflage limité au joker du tapis

Confirmé : le camouflage ne s'applique jamais à un joker de main (celui-ci
n'est joué que s'il est utile, §4). Pour le cas forcé du point 5
ci-dessus, `_meilleur_candidat_si_pioche_impossible` essaie réellement de
camoufler en minimisant le nombre de nouveaux jokers libres parmi les
candidats déjà calculés. La préférence « recombinaison la plus profonde »
parmi plusieurs placements d'un même joker repris, demandée par l'issue,
N'EST PAS implémentée (signalée comme limite connue, inchangée depuis
#253 — risque pour l'objectif interne du solveur exact, cas rares).

## 7. Fin de match : débarras du joker inutile

Nouvelle règle (`_fin_de_match_proche_pour_debarras`, `moteur/ia.py`) :
en match à PLUSIEURS manches (`etat["config"]["nb_manches"] > 1`), si au
moins un adversaire a au plus 2 tuiles en main et que la pioche contient
moins de 30 tuiles, un joker inutile pour lequel une pose existait déjà
dans le coup de base est posé quand même (sa pénalité compterait sinon
dans le score cumulé). Sans effet à une seule manche. Seuils réglables
(`niveaux.SEUIL_TUILES_ADVERSAIRE_FIN_MATCH=2`,
`niveaux.SEUIL_PIOCHE_FIN_MATCH=30`), désactivables en bloc
(`niveaux.DEBARRAS_JOKER_FIN_MATCH_ACTIF`).

## 8. Documentation

`docs/contexte/ia_anti_don_joker.md` réécrit en profondeur : renvois
d'étapes corrigés (l'oubli est l'étape 5, pas 4), contradiction entre
« sans recomposer » et « par une recombinaison du plateau seul »
harmonisée (libre = prise immédiate, zéro recombinaison ; en réserve =
aucune recombinaison, même complexe, ne la rend possible), et toutes les
sections mises à jour pour refléter les points 1 à 7. `CONTEXTE.md` §19
mis à jour (quelques lignes).

## Mesure

20 donnes, premier plan, graine 42, Expert contre Expert, limite de temps
ferme (`timeout 900`) :

```
# AVANT (règle désactivée des deux côtés) :
python scripts/comparer_niveaux_ia.py --niveau-a Expert --niveau-b Expert \
    --donnes 20 --seed 42 --sans-don-joker-a --sans-don-joker-b
# → 1/524 coup(s) (0,2 %) laissent un joker libre ; 0 pioche forcée ;
#   0 joker de main gardé ; 0 échange différé ; 0 débarras de fin de
#   match. Temps de calcul Expert : moyenne 74,7 ms, max 1259,8 ms.

# APRÈS (règle activée, #254 appliqué) :
python scripts/comparer_niveaux_ia.py --niveau-a Expert --niveau-b Expert \
    --donnes 20 --seed 42
# → 0/531 coup(s) (0,0 %) laissent un joker libre ; 2 pioches forcées ;
#   5 jokers de main gardés ; 1 échange différé (ayant forcé 1 pioche) ;
#   0 débarras de fin de match (nb_manches=1 par défaut). Temps de
#   calcul Expert : moyenne 78,2 ms, max 1386,9 ms.
```

Compteurs IDENTIQUES à ceux déjà publiés par #253 (même graine/donnes) :
attendu, aucun des 7 points n'est exercé par les coups rencontrés dans
CETTE campagne précise à une seule manche (voir le détail dans le fichier
de domaine, §9). Chacun des 7 points reste couvert par un test unitaire
dédié qui l'exerce directement (12 nouveaux tests dans
`tests/test_ia_anti_don_joker.py`, 39 au total, tous verts). Compteur
`jokers_debarrasses_fin_match` ajouté à `scripts/comparer_niveaux_ia.py`
(rapport et export).

## Tests

39 tests dans `tests/test_ia_anti_don_joker.py` (12 nouveaux + 3 adaptés
pour refléter le nouveau comportement attendu des points 2/3), suite
complète du projet verte (507 passés, 13 ignorés — inchangé).
