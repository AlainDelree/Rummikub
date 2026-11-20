## Issue #252 — Expert, Avancé et Intermédiaire : ne plus offrir un joker à l'adversaire

### Définition retenue de « joker offert »

Un joker est **offert** sur un plateau donné s'il serait repris par au
moins une des voies de récupération de joker déjà codées pour l'IA
(échange direct, détachement en bout de suite, réduction de groupe de 4 à 3
sans remplacement, scission en milieu de suite — §8 de CONTEXTE.md),
appliquées avec un chevalet **hypothétique** représentant toute tuile réelle
dont un exemplaire n'est vu ni sur le plateau ni dans le chevalet de l'IA
(jamais la main adverse). Un joker **nouvellement** offert par un coup
compare l'ensemble des jokers offerts après le coup à celui d'avant :
laisser en place un joker déjà offert avant ce coup n'est pas un cadeau
fait PAR lui. Détail complet : `docs/contexte/ia_anti_don_joker.md`
(nouveau fichier).

### Règle de jeu

`moteur/ia.py` : nouvelles fonctions `jokers_offerts_sur_plateau`,
`jokers_offerts_par_coup`, `_chercher_coup_sans_don_joker`,
`_appliquer_anti_don_joker`, appliquées dans `jouer_niveau_bride` juste
après le calcul du meilleur coup (et jamais sur un coup gagnant — exception
absolue conservée en premier) :

1. si le coup choisi n'offre aucun nouveau joker, rien ne change ;
2. sinon, cherche un coup équivalent qui n'en offre pas (coup sans
   réarrangement du plateau, puis meilleur coup en retirant chaque tuile
   jouée — jokers en premier), quitte à poser moins de tuiles, borné par
   le même budget de temps que le coup normal ;
3. si rien n'y échappe, pioche plutôt que d'offrir — jusqu'à 2 tours
   consécutifs (`niveaux.LIMITE_ATTENTE_DON_JOKER`, réglable), au-delà
   desquels le coup qui offre le joker est joué malgré tout. Compteur
   persisté par joueur (`niveaux.CLE_ATTENTE_DON_JOKER`), remis à 0 à
   chaque nouvelle manche (`partie.nouvelle_manche`).

### Paramètre et désactivation

`niveaux.Bridage.eviter_don_joker` (nouveau champ, défaut `False`) :
activé pour **Intermédiaire, Avancé et Expert** ; Débutant et Facile
inchangés (peuvent toujours offrir un joker). `jouer_niveau_bride(...,
eviter_don_joker=None|True|False)` force le réglage indépendamment du
niveau. `scripts/comparer_niveaux_ia.py --sans-don-joker-a`/`-b`
désactivent la règle pour un camp, quel que soit son niveau, pour comparer
une campagne AVEC et SANS la règle à seed et donnes identiques (y compris
quand A et B portent le même niveau). `scripts/calibrer_echelle.py` et
`scripts/calibrer_niveaux.py` préservent le réglage `eviter_don_joker`
actuel du niveau calibré (ces outils ne calibrent que
perturbation/oubli — aucune valeur de perturbation ou d'oubli n'a été
modifiée par cette issue).

### Mesure (`scripts/comparer_niveaux_ia.py`)

Nouveau compteur par camp : coups joués qui offrent un nouveau joker / total
de coups joués (taux), et tours d'attente (pioche plutôt que d'offrir).
Essai de fumée fait par l'agent (2 donnes, non significatif) :

- Avancé vs Expert, seed 42 : règle activée, 3/52 coups offrent encore un
  joker (5,8 %, 6 tours d'attente) ; règle désactivée, 3/54 (5,6 %, 0
  attente) — parties non comparables terme à terme (elles divergent dès la
  première décision différente).
- Intermédiaire vs Avancé, seed 7 : règle activée, Intermédiaire 3/46
  (6,5 %, 10 attentes), Avancé 2/52 (3,8 %, 21 attentes) ; règle désactivée,
  Intermédiaire 4/41 (9,8 %), Avancé 4/48 (8,3 %).

Commandes de campagne appariée (≥ 300 donnes) prêtes à copier pour Alain :
voir CONTEXTE.md §19 (nouvelle section) et `docs/contexte/
ia_anti_don_joker.md`.

### Temps de calcul

La recherche d'alternative ne s'exécute que sur les coups qui offrent
effectivement un joker (minorité des tours). Mesuré sur l'essai de fumée :
temps moyen par tour environ doublé sur ces tours (Intermédiaire : 89 ms →
242 ms en moyenne, max 922 ms → 3,1 s) — borné par la même deadline que le
coup normal (jamais de recherche illimitée), mais perceptible dans le pire
cas ; à surveiller sur une campagne longue.

### Tests

`tests/test_ia_anti_don_joker.py` (nouveau, 11 cas) : détection d'un joker
offert (bout de suite avec/sans remplacement inconnu, don déjà présent
avant le coup non recompté) ; Expert/Avancé/Intermédiaire évitent le don en
posant moins de tuiles ; aucune alternative → pioche 2 tours puis coup
forcé au 3e ; coup gagnant toujours joué même avec un don ; Débutant/Facile
non soumis à la règle ; règle désactivée (`eviter_don_joker=False`)
reproduit l'ancien comportement (coup le plus riche, jamais dégradé).
`tests/test_calibrer_echelle.py` mis à jour pour le nouveau champ
`Bridage.eviter_don_joker`. Suite complète : 479 passed, 13 skipped.

### Fichiers modifiés

`src/rummikub/moteur/ia.py`, `src/rummikub/moteur/niveaux.py`,
`src/rummikub/moteur/partie.py`, `scripts/comparer_niveaux_ia.py`,
`scripts/calibrer_echelle.py`, `scripts/calibrer_niveaux.py`,
`tests/test_calibrer_echelle.py` (modifiés) ; `tests/test_ia_anti_don_joker.py`,
`docs/contexte/ia_anti_don_joker.md` (nouveaux) ; `CONTEXTE.md` (§19
ajoutée).
