# Issue #188 — Suite #185 : script d'analyse des « coups ratés » de l'IA à partir des journaux de parties

Objectif : pouvoir dire, après coup, si une IA qui a pioché ou passé aurait
pu jouer — un joueur humain ne voit pas le chevalet de l'IA et ne peut pas en
juger lui-même. Le journal de partie (`persistance/journal.py`, #185)
enregistre à chaque action les chevalets de tous les joueurs et le plateau :
on peut donc reconstituer l'état exact affronté par l'IA avant chaque
décision et vérifier ce qu'un solveur disposant de beaucoup de temps de
calcul y aurait trouvé.

## Détection (`persistance/coups_rates.py`, pur, sans pywebview)

- `extraire_decisions_ia(data)` : pour chaque décision de piocher/passer
  d'une IA dans un journal brut, reconstitue l'état précédent (chevalet du
  joueur + plateau, enregistrés par l'action JUSTE AVANT dans le journal —
  la toute première action d'un journal est donc toujours ignorée, faute
  d'état antérieur). La mise initiale d'un joueur est considérée faite s'il
  a déjà posé au moins une tuile plus tôt dans le même journal (impossible,
  en jeu réel, de poser quoi que ce soit avant d'avoir atteint le minimum en
  une seule fois). Tolère les formats anciens/corrompus (en-tête `joueurs`
  absent ou à l'ancien format, champs `plateau`/`mains_joueurs` manquants) :
  retourne une liste vide plutôt que de lever une exception.
- `analyser_decision(decision, budget_genereux=10.0, budget_production=1.5)` :
  interroge `moteur/solveur.py::resoudre_coup` sur l'état reconstitué. Si le
  solveur trouve un coup posant au moins une tuile, la décision est un
  « coup raté » (nombre de tuiles posables ; avant la mise initiale, points
  que l'ouverture aurait rapportés). Pour le niveau Expert uniquement,
  interroge en plus le solveur avec le budget de production réel (1,5 s,
  `moteur/ia.py::BUDGET_TEMPS_EXPERT`) afin de distinguer un coup raté par
  faiblesse de l'algorithme (le budget de production l'aurait trouvé aussi)
  d'un coup raté par manque de temps de calcul (seul le budget généreux le
  trouve — champ `budget_limite`).
- `calculer_resume(resultats)` : agrège par niveau d'IA et par phase (avant/
  après mise initiale) — décisions analysées, coups ratés et pourcentage.
- `top_coups_rates(resultats, n=5)` : les coups ratés les plus importants
  (tuiles ratées), pour examen manuel.

## Script CLI (`scripts/analyser_coups_rates.py`)

```
python scripts/analyser_coups_rates.py                      # journal le plus récent
python scripts/analyser_coups_rates.py chemin/vers/partie.json
python scripts/analyser_coups_rates.py --tous --dossier DIR  # tous les journaux d'un dossier
python scripts/analyser_coups_rates.py --budget 20 --budget-production 1.5
```

Un journal illisible ou corrompu est signalé sur stderr et ignoré sans
interrompre l'analyse des autres. Affiche le résumé par niveau/phase, le
détail des 5 coups ratés les plus importants (numéro de coup, joueur, tuiles
ratées), et un avertissement systématique.

## Limite documentée (répétée à l'affichage)

Le solveur gèle certaines combinaisons déjà posées sur le plateau pour
limiter la combinatoire (`moteur/solveur.py::_separer_combos_figees`) : un
coup non trouvé ne prouve pas qu'aucun coup n'existe. Les coups ratés
détectés sont une **borne basse**, jamais une liste exhaustive. Par ailleurs,
le journal ne conserve pas la configuration de la partie (`mise_initiale_min`
notamment) : `config.MISE_INITIALE_MIN` (valeur par défaut) est utilisée pour
toutes les parties rejouées.

**Aucune modification de l'IA ni du moteur** : lecture pure des journaux +
appels en lecture au solveur existant.

## Tests (`tests/test_coups_rates.py`)

Journaux fabriqués à la main couvrant : coup raté détecté après la mise
initiale, pioche justifiée (aucun coup trouvable), coup raté avant la mise
initiale avec points d'ouverture rapportés, journal ancien/corrompu ignoré
proprement (format d'avant #185, champs manquants), distinction budget de
production/généreux pour Expert (par substitution du solveur, indépendante
du chronométrage réel), résumé et classement des coups ratés les plus
importants. 16 tests, tous passants ; suite complète du projet (100 tests)
non régressée.

## Mise à jour de la documentation

`CONTEXTE.md` : nouvelle section §11 décrivant le script, son fonctionnement
et ses limites ; entrée ajoutée dans l'arborescence (§2).
