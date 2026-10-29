# Issue #215 — Vérifier qu'Expert ne décompose jamais le plateau inutilement, et donner à Alain des exemples lisibles (suite de #199)

Le profil d'Expert (#213) montre qu'environ deux tiers de ses poses sont
« grandes » (elles **touchent** 3 combinaisons du plateau ou plus). Question
d'Alain : ces grosses recompositions sont-elles toutes NÉCESSAIRES, ou l'IA
décompose-t-elle parfois le plateau pour rien ? Le critère de simplicité de #199
(« à nombre de tuiles posées égal, préférer le coup qui perturbe le moins le
plateau ») est censé l'empêcher, mais cela n'avait été vérifié que sur quelques
cas isolés. Cette issue le vérifie **systématiquement** et fournit à Alain des
exemples lisibles qu'il peut examiner lui-même. **Aucun changement au moteur de
jeu, à l'IA ni au solveur — script d'analyse seulement.** Voir **CONTEXTE.md
§17**.

## 1. Script de vérification systématique

- Nouveau `scripts/verifier_simplicite_expert.py`. Pour chaque **pose
  d'Expert** :
  1. mesure la perturbation du coup **réellement joué**
     (`moteur/solveur.mesurer_perturbation`, #199 :
     `(tuiles du plateau déplacées, combinaisons modifiées)`) ;
  2. interroge **indépendamment** le solveur avec un budget **généreux**
     (`--budget-juge`, 5 s par défaut, > 1,5 s de production) pour obtenir « le
     coup le plus simple posant le plus de tuiles » — modèle exact
     `moteur/solveur_exact` si `highspy`/`numpy` dispo, sinon recherche
     arborescente `moteur/solveur` ;
  3. à nombre de tuiles **égal**, compare les deux perturbations → **écart de
     simplicité**. Un coup qui pose moins que l'optimum (budget / coup raté,
     cf. #188) est compté à part, hors sujet.
- Deux sources : **journaux** (`--journaux DIR`, poses d'Expert reliées comme
  #202 via `persistance/parties_liees`) ou, à défaut, **simulation** d'Expert
  contre lui-même (`--donnes N`, reproductible sous `--seed`). Dégradation
  propre si le dossier de journaux est absent/vide (message + commande à lancer,
  repli simulation).
- Sortie console : distribution par taille de coup, écart moyen/maximal, et la
  **proportion de gros coups qui sont des décompositions nécessaires**.
- **Si un écart non nul apparaît**, il est signalé clairement (cas concernés
  dans le fichier d'exemples) **sans corriger le solveur** (une correction fera
  l'objet d'une issue dédiée, conformément à la demande).

## 2. Fichier d'exemples lisibles pour Alain

- Le script écrit `exemples_simplicite_expert.txt` dans un **dossier de SORTIE**
  (`--sortie`, **hors du dépôt** : par défaut un sous-dossier du répertoire
  temporaire du système ; `_sortie_locale/` et `exemples_simplicite_expert.txt`
  ajoutés à `.gitignore`).
- Une **dizaine de cas variés** (des petits, des moyens, des grands ; au moins
  un où Expert décompose beaucoup — sélection équilibrée par taille, schémas
  distincts). Pour CHAQUE cas, en **français clair sans jargon** :
  - le **plateau de départ EN ENTIER** (toutes les combinaisons, une par une :
    « groupe de 9 (bleu, jaune, noir) », « suite rouge 5-6-7 », joker écrit
    « joker » à sa position) ;
  - la **main complète** de l'IA ;
  - le nombre de tuiles posables au maximum ce tour-là ;
  - le coup joué **étape par étape** comme dans le pas-à-pas (réutilise
    `moteur/description_coup.py`, mode « une modification » #214) + la
    perturbation ;
  - le **plateau d'arrivée EN ENTIER** ;
  - s'il existe un coup plus simple posant autant de tuiles, il est décrit avec
    **son** plateau d'arrivée entier, pour comparaison ;
  - une ligne de conclusion : « décomposition NÉCESSAIRE » ou « décomposition
    ÉVITABLE (écart de N combinaisons / M tuiles déplacées) ».

## 3. Résultat (réponse à la question d'Alain)

- Campagne par simulation (Expert en miroir, 12 parties, **323 poses**,
  budget-juge 5 s) : **100 % des poses sont au minimum de perturbation, 0
  décomposition évitable**. Parmi elles, **208 gros coups** (3+ combinaisons
  touchées, ~64 %, cohérent avec le ~68 % du profil) **tous nécessaires**.
- Nuance mise en évidence par les exemples : « toucher 3 combinaisons »
  (métrique du profil) n'est PAS « déplacer des tuiles » — beaucoup de gros
  coups prolongent/reforment des combinaisons **sans déplacer la moindre
  tuile** (perturbation nulle). Le critère de #199 **tient ses promesses** sur
  cet échantillon.

## 4. Tests

- `tests/test_verifier_simplicite_expert.py` (8 tests) : description française
  d'une combinaison (groupe, suite, suite avec joker) ; un coup **déjà minimal**
  → écart nul (« nécessaire ») ; un coup artificiellement **sur-décomposé**
  (combinaison éclatée en deux) → écart **bien détecté** (« évitable ») ; un coup
  posant moins que l'optimum exclu du calcul ; le juge indépendant et
  l'enchaînement complet (`analyser_coup` / `rediger_exemple`) sur un état
  jouable. Tournent sans dépendance externe (le juge se replie sur la recherche
  arborescente).

## Commande pour Alain

```
# Sur ses propres parties (journaux activés via la clé "log_parties") :
PYTHONPATH=src python3 scripts/verifier_simplicite_expert.py \
    --journaux data/logs_parties --sortie /tmp/simplicite_expert

# Sans journaux, par simulation :
PYTHONPATH=src python3 scripts/verifier_simplicite_expert.py --donnes 20
```
