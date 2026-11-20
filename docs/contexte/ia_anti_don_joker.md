# IA — règle anti-don de joker (Intermédiaire/Avancé/Expert, issue #252)

> À lire avant de toucher à `moteur/ia.py` (section « Règle anti-don de
> joker (issue #252) »), `moteur/niveaux.py` (`Bridage.eviter_don_joker`,
> `LIMITE_ATTENTE_DON_JOKER`, `CLE_ATTENTE_DON_JOKER`), ou aux options
> `--sans-don-joker-a`/`-b` de `scripts/comparer_niveaux_ia.py`.

## Constat d'origine

En jouant contre Expert, Alain a observé l'IA poser un joker, ou le laisser
en place après son coup, à un endroit où l'adversaire peut le reprendre
facilement (bout de suite, groupe à qui il ne manque qu'une couleur) — un
cadeau qu'un joueur humain moyen n'offre pas. Avant #252, le choix d'Expert
(et d'Avancé, identique) maximisait uniquement le nombre de tuiles posées ;
l'économie de jokers n'intervenait qu'en tout dernier critère de départage
du solveur (§8bis), jamais comme un refus explicite d'un coup.

Une version antérieure (niveau « Champion du Monde », retirée sans effet
mesurable — #235/#236, CONTEXTE.md §13) calculait déjà une notion
d'« exposition » d'un joker, mais seulement à égalité de tuiles posées :
elle ne sacrifiait donc jamais rien. Ce code est archivé dans le tag git
`archive-strategies-champion` (`moteur/ia.py`, `moteur/inconnues.py`). #252
en reprend l'idée (tuiles encore inconnues qui permettraient la reprise)
mais directement dans `moteur/ia.py` (pas de module séparé), et en
acceptant, cette fois, de poser **moins** de tuiles pour l'éviter.

## Définition de « joker offert »

Un joker est **offert** sur un plateau donné si au moins UNE des voies de
récupération déjà codées pour l'IA elle-même le reprendrait avec une tuile
qui n'est visible NI sur le plateau NI dans le chevalet de l'IA (jamais la
main adverse — garde-fou anti-triche, comme l'ancienne brique
« Inconnues ») :

- échange direct (`_jokers_recuperables`) ;
- détachement en bout de suite par extension de l'autre bout
  (`_jokers_detachables_par_extension`) ;
- réduction d'un groupe de 4 à 3 **sans** remplacement — toujours offert,
  aucune tuile inconnue requise (`_jokers_liberables_par_groupe4_sans_
  remplacement`) ;
- scission en milieu de suite — idem, toujours offert
  (`_jokers_liberables_par_scission_milieu`).

`jokers_offerts_sur_plateau(plateau, chevalet)` construit un chevalet
**hypothétique** (`_chevalet_hypothetique_inconnu`) : une tuile de chaque
type réel dont au moins un exemplaire (sur `NB_SERIES=2`) n'est vu ni sur le
plateau ni dans le vrai chevalet, puis réutilise les fonctions ci-dessus
telles quelles pour voir si une récupération existe avec ce chevalet.

Un joker **nouvellement** offert par un coup (`jokers_offerts_par_coup`)
compare l'ensemble des jokers offerts sur le plateau APRÈS le coup à celui
d'AVANT : laisser en place un joker déjà offert avant le coup n'est pas un
cadeau fait PAR ce coup (nuance d'Alain).

## Règle de jeu et paramètres

Appliquée par `_appliquer_anti_don_joker` (`moteur/ia.py`), appelée depuis
`jouer_niveau_bride` juste après le calcul du meilleur coup, et seulement si
`Bridage.eviter_don_joker` est vrai :

1. si le coup choisi n'offre aucun nouveau joker → rien à faire ;
2. sinon, cherche une alternative qui n'en offre aucun
   (`_chercher_coup_sans_don_joker` : d'abord le coup sans réarrangement du
   plateau, puis le meilleur coup obtenu en retirant successivement chaque
   tuile jouée — jokers d'abord) — bornée par le même budget de temps que
   le coup normal (`budget_temps`/`BUDGET_TEMPS_EXPERT`), quelques
   résolutions supplémentaires au plus, jamais une recherche exhaustive ;
3. si une alternative est trouvée, elle est jouée à la place (quitte à
   poser moins de tuiles) ;
4. sinon, le niveau **pioche** plutôt que d'offrir, jusqu'à
   `niveaux.LIMITE_ATTENTE_DON_JOKER` (2 par défaut, réglable) tours
   **consécutifs** d'attente — compteur `niveaux.CLE_ATTENTE_DON_JOKER`
   persisté sur le joueur, remis à 0 dès qu'un coup est effectivement
   joué (alternative trouvée, coup forcé après la limite, ou coup sans
   problème) et à chaque nouvelle manche (`partie.nouvelle_manche`) ;
5. au-delà de la limite, le coup qui offre le joker est joué malgré tout.

**Exception absolue** : un coup qui **vide le chevalet** est toujours joué
tel quel, quel que soit le joker offert — jamais soumis à cette règle, ni à
l'oubli (§16). Vérifié avant même d'atteindre la règle anti-don dans
`jouer_niveau_bride`.

Activée (`Bridage.eviter_don_joker=True`) pour **Intermédiaire, Avancé et
Expert** ; **Débutant et Facile** restent à `False` (comportement d'avant
#252 inchangé — offrir un joker y reste une erreur plausible pour leur
niveau). Un joker reste par ailleurs toujours utilisable : la règle interdit
seulement de l'offrir, pas de le jouer — un joker posé sans tuile de
remplacement inconnue (donc non repris) est toujours autorisé. Les voies de
récupération de joker de l'IA elle-même (§8) ne changent pas.

`jouer_niveau_bride(..., eviter_don_joker=None|True|False)` permet de forcer
l'activation/désactivation indépendamment du réglage naturel du niveau —
utilisé par `scripts/comparer_niveaux_ia.py --sans-don-joker-a`/`-b` pour
comparer, à graines et donnes identiques, une campagne AVEC et SANS la
règle pour un même niveau (y compris A et B au même niveau). Le coup renvoyé
porte alors une clé `"don_joker"` (`{"declenchee", "evite", "attente",
"force_apres_attente", "tours_attente"}`) pour la mesure (absente si la
règle ne s'est pas appliquée — Débutant/Facile, ou coup gagnant).

## Mesure (`scripts/comparer_niveaux_ia.py`)

Le rapport affiche, **par CAMP** (A/B peuvent partager le même niveau avec
des réglages différents de la règle, pas seulement par nom de niveau) : le
nombre de coups joués qui offrent un nouveau joker / le nombre total de
coups joués (taux), et le nombre de tours d'attente (pioche plutôt que
d'offrir).

Essai court (2 donnes, fait par l'agent, PAS la campagne de 300 donnes de
mesure réelle — voir plus bas) :

```
python scripts/comparer_niveaux_ia.py --niveau-a Avancé --niveau-b Expert --donnes 2 --seed 42
# règle désactivée des deux côtés, pour comparaison :
python scripts/comparer_niveaux_ia.py --niveau-a Avancé --niveau-b Expert --donnes 2 --seed 42 \
    --sans-don-joker-a --sans-don-joker-b
```

Sur ce très petit échantillon (52-54 coups joués au total par camp, donc
non significatif, juste un test de fumée) : règle activée, 3/52 coups
offrent encore un joker (5,8 %, 6 tours d'attente) ; règle désactivée, 3/54
(5,6 %, 0 attente) — les parties divergent dès la première décision
différente, donc les deux lots ne sont pas directement comparables terme à
terme ; seule une campagne en miroir à graines identiques (ci-dessous) peut
conclure sur l'effet réel.

### Campagnes appariées (à lancer par Alain — voir CONTEXTE.md §19)

Voir CONTEXTE.md §19 pour les commandes complètes (≥ 300 donnes, premier
plan, limite de temps ferme) : Expert avec/sans la règle, Intermédiaire
avec/sans, et Intermédiaire contre Avancé avec la règle des deux côtés
comparé à sans des deux côtés.

## Contrainte de temps de calcul

`_chercher_coup_sans_don_joker` ne s'exécute QUE si le meilleur coup offre
effectivement un nouveau joker (minorité des tours, voir mesure ci-dessus) ;
elle essaie d'abord le coup sans réarrangement (aucun appel au solveur), puis
borne ses résolutions supplémentaires par une deadline dérivée du même
budget que le coup normal. Mesuré sur l'essai ci-dessus : temps moyen par
tour environ doublé sur les tours concernés (ex. Intermédiaire : 89 ms → 242
ms en moyenne, max 922 ms → 3,1 s) — borné (jamais de recherche illimitée),
mais perceptible sur le pire cas ; à surveiller si une future campagne
longue montre un temps par tour anormalement élevé.
