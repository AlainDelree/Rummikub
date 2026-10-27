# Issue #197 — Suite #191 : pas à pas, ne pas montrer les échanges de tuiles identiques

Le jeu contient deux exemplaires de chaque tuile. Le suivi tuile-par-tuile
du pas-à-pas (`moteur/description_coup.py`, #191) identifiait chaque tuile
par son identifiant individuel : un échange entre deux tuiles de même
aspect (même valeur/couleur) — invisible à l'écran — était donc montré
comme un vrai changement (« Le 3 jaune remplace le 3 jaune... »), et ce
même mécanisme causait un **plantage réel en jeu** (`KeyError`) quand une
tuile libérée par un échange ainsi annulé n'était jamais déposée dans le
cadre avant d'être consommée par une opération suivante.

0. **Cause réelle corrigée** : `_construire_operations` sépare désormais
   le suivi causal exact (listes brutes `retirees`/`ajoutees`, toujours
   utilisées pour le cadre et les dépendances — jamais d'exception) de ce
   qui est affiché (`retirees_vues`/`ajoutees_vues`, réduites par
   `_annuler_par_aspect` en annulant une tuile partie et une tuile arrivée
   de même aspect). Le cas réel qui plantait — deux combinaisons qui
   s'échangent leurs tuiles, chacune attendant une tuile libérée par
   l'autre (cycle de dépendances strict) — est détecté par
   `_composantes_fortement_connexes` (Tarjan) et traité en un seul bloc
   (`_detecter_blocs_silencieux`) : toutes les tuiles libérées du bloc
   ajoutées au cadre, puis toutes les tuiles consommées retirées, sans
   dépendre de l'ordre entre les deux combinaisons. Reproduit dans
   `tests/test_description_coup.py` à partir du cas réel capturé par le
   repli d'urgence (#196) dans `tests/donnees/erreur_description_*.json`.
1. **Tuiles interchangeables** : un échange de tuiles de même aspect, dans
   une même combinaison ou entre deux combinaisons, n'est plus compté
   comme un déplacement et ne produit plus aucune étape ni phrase.
2. **Cas de la main** : une tuile de la main identique à une tuile du
   plateau qui se déplace choisit automatiquement la description la plus
   courte (même mécanisme que le point 1, les deux listes s'annulant au
   sein d'une même opération) — la liste des tuiles réellement posées
   depuis la main (`tuiles_posees`, basée sur les identifiants réels)
   n'est jamais affectée.
3. **Jokers** : un joker remplacé par l'autre joker dans une même
   combinaison n'est plus un déplacement (`_jokers_deplaces` ne considère
   un joker comme déplacé que s'il figure dans les tuiles "vues" de sa
   propre opération) ; un joker qui change réellement de combinaison reste
   bien décrit comme un déplacement, même quand deux jokers existent.
4. **Étapes nettoyées** : toute étape sans effet visible est supprimée en
   amont (jamais ajoutée), le nombre d'étapes recalculé, et le seuil du
   bouton « Pas à pas » s'applique aux étapes nettoyées — inchangé par
   ailleurs.
5. **Indicateurs de complexité** (`persistance/coups_rates.py`) : réutilise
   tel quel `decrire_coup_ia`/`etapes_coup_ia` corrigés, donc un échange de
   tuiles identiques n'est plus compté dans `nb_combinaisons_touchees` ni
   `nb_etapes` — aucun changement de code nécessaire dans ce module.
6. **Tests** : échange main/plateau dans une même combinaison, échange
   cyclique entre deux combinaisons, régression bout en bout sur le cas
   réel ayant planté, deux jokers (un remplacé par l'autre — pas un
   déplacement — et un second qui change réellement de combinaison), et
   persistance des cas déjà couverts (chaîne Bruno/Expert, échange de
   joker, démantèlement de groupe) — même nombre d'étapes qu'avant.
   `tests/test_playwright_pas_a_pas.py` repassé sans modification (format
   des étapes inchangé, seulement moins d'étapes invisibles). Voir
   CONTEXTE.md §12bis.
