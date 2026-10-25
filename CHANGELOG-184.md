# Issue #184 — Script de simulation : départager deux niveaux d'IA sur un grand nombre de parties

On ne savait pas si le niveau Expert est réellement plus fort qu'Avancé, sa
seule différence étant une règle qui lui fait piocher au lieu de poser
quand un adversaire n'a plus que 3 tuiles ou moins — ce qui pourrait le
désavantager autant que l'avantager. But : mesurer, sans toucher à l'IA ni
au moteur (voir #134 pour les scripts de simulation historiques).

## Ajout

`scripts/comparer_niveaux_ia.py` (nouveau script, aux côtés de
`scripts/simulation_ia.py` déjà existant) :

- CLI : `--niveau-a`, `--niveau-b` (obligatoires, un des 5 niveaux
  connus), `--donnes` (défaut 50), `--seed` (défaut 0, reproductible),
  `--max-tours` (garde-fou anti-blocage, défaut 300), `-v/--verbose`.
- Utilise uniquement le moteur Python (`rummikub.moteur.*`), jamais
  pywebview, conformément à `CONTEXTE.md` §7.
- **Parties à 2 joueurs jouées en miroir** : pour chaque donne, `random.seed`
  est réinitialisée à la même graine avant chaque partie du couple, ce qui
  produit exactement la même distribution de tuiles (`distribuer`
  consomme le module `random` global dans cet ordre) ; seules les places
  des deux niveaux sont échangées entre les deux parties du couple. 50
  donnes → 100 parties. Avec la même `--seed`, la campagne est reproductible
  à l'identique.
- **Fin de partie** : suit les règles du moteur (`_terminer_tour`) —
  chevalet vidé ou pioche épuisée (ce second cas, dit « bloqué », est déjà
  géré par `calculer_scores_manche`/`trouver_gagnant_manche` : le joueur
  avec le moins de pénalité l'emporte). Garde-fou `--max-tours` : les
  parties qui l'atteignent sont **comptées à part** (bucket
  `garde_fou`), exclues des statistiques de victoire/durée/pénalité plutôt
  que silencieusement ignorées ou faussement comptées comme décisives.
- **Résultats affichés** : victoires et taux par niveau avec marge d'erreur
  (IC 95 %, approximation normale de Wald) et verdict « significatif / NON
  significatif » par rapport à 50/50 ; nombre moyen de tuiles restantes et
  de points de pénalité du perdant ; durée moyenne en tours des parties
  décidées ; répartition des fins de partie (chevalet vidé / pioche
  épuisée / arrêtées par le garde-fou) ; temps de calcul moyen et maximal
  d'un tour de décision IA par niveau (chronométré autour de `jouer_ia`
  uniquement, pour repérer un emballement de la recherche combinatoire des
  libérations de joker, cf. `CONTEXTE.md` §8).
- Aucune modification de `moteur/ia.py` ni du reste du moteur : le script
  ne fait qu'orchestrer les fonctions publiques déjà exposées
  (`creer_partie`, `jouer_tour`, `piocher`, `passer_tour`,
  `backup_debut_tour`, `annuler_tour`, `jouer_ia`), à l'identique de
  `scripts/simulation_ia.py`.

## Première campagne : Avancé vs Expert

Lancée avec les valeurs par défaut (`--niveau-a Avancé --niveau-b Expert`,
50 donnes, graine 0, max-tours 300) :

```
COMPARAISON : Avancé (camp A) vs Expert (camp B)
50 donne(s) x 2 (miroir) = 100 partie(s) demandée(s), 100 partie(s) décidée(s)
----------------------------------------------------------------------
  Avancé (camp A) : 53/100 victoires — taux 53.0 % ± 9.8 pt (IC 95 %)
  Expert (camp B) : 47/100 victoires — taux 47.0 % ± 9.8 pt (IC 95 %)
  Écart par rapport à 50/50 NON significatif au seuil de confiance 95 %.
----------------------------------------------------------------------
  Fins de partie : 71 par chevalet vidé, 29 par pioche épuisée (bloqué),
  0 arrêtée(s) par le garde-fou (max tours).
  Durée moyenne d'une partie décidée : 113.9 tour(s).
  Perdant (parties décidées) : en moyenne 6.0 tuile(s) restante(s),
  43.8 point(s) de pénalité.
----------------------------------------------------------------------
  Temps de calcul par tour (décision IA), par niveau :
    Avancé          : moyenne 2.1 ms, max 26.9 ms, sur 5687 tour(s)
    Expert          : moyenne 3.0 ms, max 71.6 ms, sur 5702 tour(s)
======================================================================
Temps total de la campagne : 34.5s.
```

**Conclusion** : sur 100 parties, Avancé gagne 53 % contre 47 % pour
Expert, mais l'écart (± 9.8 pt) n'est PAS statistiquement significatif à
95 % — rien ne permet de conclure qu'Expert est plus fort ou plus faible
qu'Avancé. La règle « piocher au lieu de poser face à un adversaire à ≤3
tuiles » ne semble donc pas le désavantager de façon mesurable sur cet
échantillon ; aucun emballement de temps de calcul détecté (max 71.6 ms
pour Expert, cohérent avec la recherche combinatoire de libération de
joker, sans dérive). Aucune partie bloquée par le garde-fou.

## Documentation

`CONTEXTE.md` : nouvelle section §9 « Scripts de simulation IA vs IA »,
décrivant `scripts/simulation_ia.py` et `scripts/comparer_niveaux_ia.py`
(usage, options, résultats affichés, résumé de la première campagne).
