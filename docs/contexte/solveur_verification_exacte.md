# Solveur exact de vérification et limites de calcul

## 14. Solveur exact de vérification — bibliothèque `rummikub-solver` (licence MIT, issue #204, suite de #201)

Notre solveur d'Expert (`moteur/solveur.py`) est à la fois le joueur **et** le
juge de l'analyse des coups ratés (§11) : s'il manque un coup, l'analyse ne le
voit pas non plus — ses résultats sont une **borne basse**. L'issue #204
ajoute une **mesure indépendante et exacte** à l'aide de la bibliothèque libre
`rummikub-solver` (PyPI, licence MIT), qui résout l'optimum d'un tour par
programmation linéaire en nombres entiers (den Hertog & Hulshof, *The Computer
Journal*, 2006). **Le solveur d'Expert, le jeu livré et les niveaux d'IA ne
sont pas modifiés.**

### Dépendance de DÉVELOPPEMENT seulement — NE PAS l'ajouter au jeu livré

- **Absente de `requirements.txt` et du build Windows** (`rummikub.spec`). À
  installer dans un venv de développement (Python 3.11+), isolé du jeu :

  ```
  python -m venv .venv-solveur-exact
  .venv-solveur-exact/bin/pip install 'rummikub-solver[highs]' pytest
  ```

  L'extra `highs` installe le solveur HiGHS (MIT, recommandé). **Ne jamais
  installer l'extra `glpk_mi`** (GLPK, GPL-3.0 — incompatible avec une
  distribution propriétaire).

- Tout le code qui en dépend se **saute proprement si elle est absente** (comme
  les tests Playwright) : `scripts/solveur_exact.DISPONIBLE` vaut alors
  `False`, les scripts affichent un message d'installation et s'arrêtent, et
  `tests/test_solveur_exact.py` se saute via `pytest.importorskip`.

### Fichiers (tous sous `scripts/` ou `tests/`, hors du paquet livré `src/`)

- **`scripts/solveur_exact.py`** — adaptateur. Convertit un de nos états
  (plateau, main, drapeau de mise initiale) vers la bibliothèque et
  inversement. Correspondance des couleurs : **noir → BLACK, bleu → BLUE,
  jaune → ORANGE, rouge → RED** ; entier d'une tuile = `couleur_index*13 +
  valeur` (noir=0…rouge=3), joker = 53. La bibliothèque renvoie des ensembles
  **non ordonnés** : `_ordonner_combinaison` les **remet dans l'ordre** (suite
  triée par valeur, joker inséré dans chaque trou puis aux extrémités ; groupe
  indifférent). `resoudre_exact` renvoie un `ResultatExact` (nombre de tuiles
  posées, combinaisons `Tuile` ordonnées, `nouveau_plateau` dict, durée) après
  **deux contrôles indépendants** : chaque combinaison validée par
  `valider_combinaison`, et conservation des tuiles du plateau.
  `resoudre_coup_exact(etat, idx, budget_temps=None)` est une variante
  « drop-in » à la signature de `moteur/solveur.resoudre_coup` (budget ignoré :
  l'exact n'a pas de budget), pour servir de juge (voir ci-dessous).

- **`scripts/comparer_solveur_exact.py`** — comparaison. Pour chaque
  `tests/donnees/cas_expert_*.json` **et** `reference_*.json`, affiche le
  nombre de tuiles de notre solveur à **1,5 s** (production) et **10 s**
  (généreux), celui du solveur exact et sa durée, et l'écart ; en fin de
  sortie : cas ratés à 1,5 s, écart moyen/maximal, temps total exact,
  résultats des deux contrôles. Option `--journaux [--tous] [--dossier …]`
  pour comparer sur de **vrais journaux de parties** (l'utilisateur fournit
  les journaux ; le dossier de travail de l'agent n'en contient pas).

- **`scripts/analyser_coups_rates.py --juge-exact`** — utilise le solveur
  exact comme **juge** à la place du solveur maison (§11) : plus aucune
  décision « inconclusive » ni coup manqué par gel de combinaisons. Désactivé
  par défaut ; signale clairement si la bibliothèque est absente. Mécanisme :
  `persistance/coups_rates.analyser_decision_complete` accepte un paramètre
  `solveur` (callable, défaut = solveur maison) — **le module `coups_rates`
  n'importe jamais la bibliothèque**, il reçoit un simple callable, injecté
  seulement par le script.

- **`tests/donnees/*.json`** — clé **`attendu_exact_tuiles`** (maximum exact)
  ajoutée à côté de `attendu_min_tuiles` (conservée). Le cas pivot
  `reference_victoire_manquee_ines_tour85.json` (Expert avec 2 tuiles en main
  n'en pose qu'une ; exact = 2, victoire manquée) est le **test de
  non-régression** de la suite.

- **`RAPPORT_SOLVEUR_EXACT_204.md`** — rapport complet : répartition des
  écarts, durées, taille d'installation et démarrage, deux voies
  d'embarquement éventuel (a : la bibliothèque telle quelle avec cvxpy/scipy ;
  b : modèle maison direct sur `highspy`+`numpy`, ~3× plus léger), et licences.

### Ce que la mesure exacte établit (voir le rapport pour le détail chiffré)

Sur les 10 cas de référence : notre solveur rate des tuiles sur **5/10 cas à
1,5 s** ; le solveur exact calcule l'optimum prouvé en **~84 ms/cas**. Deux cas
restent sous l'optimum **même à 10 s** (faiblesse d'algorithme, pas de
budget) : **Bruno tour 57** (3 vs 4 — tuile manquante `rouge_12`, obtenue en
scindant la suite rouge 6–10) et **Ines tour 85** (1 vs 2). Le solveur exact
trouve donc le maximum **nettement plus vite** que le nôtre — c'est le chiffre
qui décidera s'il faut un jour remplacer le solveur d'Expert (voie b du
rapport : `highspy` direct, embarquable et MIT).

### Suite #206 : la « voie (b) » est désormais DANS le jeu

L'issue #206 a **remplacé la recherche d'Expert par un modèle exact maison**
(la voie (b) : `highspy` + `numpy` en direct, sans `cvxpy` ni `scipy`), décrit
en **§8ter**. Conséquences pour cette section :

- `highspy` (MIT) et `numpy` (BSD) sont maintenant dans `requirements.txt` et
  embarqués par le build Windows (avis de copyright dans
  `THIRD_PARTY_LICENSES.txt`, distribué avec le jeu). Le modèle exact du jeu
  vit dans **`src/rummikub/moteur/solveur_exact.py`** (paquet livré), distinct
  de l'adaptateur de vérification ci-dessous.
- La bibliothèque **`rummikub-solver` reste, elle, une dépendance de
  DÉVELOPPEMENT seulement** (jamais embarquée) : `scripts/solveur_exact.py`,
  `scripts/comparer_solveur_exact.py` et `scripts/analyser_coups_rates.py
  --juge-exact` continuent de servir d'**oracle de vérification indépendant**
  du modèle maison. `tests/test_solveur_exact_maison.py` compare d'ailleurs le
  modèle maison à cette bibliothèque quand elle est installée (sinon sauté).
- Le juge d'analyse des coups ratés (§11) peut désormais utiliser soit la
  bibliothèque (dev), soit le modèle maison exact du jeu — tous deux
  renvoient l'optimum.

## 15. Match « notre solveur » vs bibliothèque sur parties entières (issue #212, suite de #206)

Nos deux solveurs exacts posent le **même nombre** de tuiles à chaque tour
(#204), mais **départagent** différemment à nombre égal : le nôtre préfère la
**perturbation minimale** du plateau (#199) puis **économise les jokers** ; la
bibliothèque applique ses propres règles. L'issue #212 répond à la question
*« ces choix de départage nous désavantagent-ils sur une partie entière ? »* en
faisant jouer des parties entières, l'une pilotée par notre solveur, l'autre par
la bibliothèque.

**Portée — à ne pas sur-interpréter.** Les deux solveurs n'optimisent qu'UN
tour. Ce match ne mesure donc PAS les stratégies sur plusieurs tours (réserve,
joker gardé, rétention — §13), ni la force d'un humain : seulement si, à jeu
« un tour » égal, nos critères de départage tiennent la route.

### Outil (dev-only, hors jeu livré)

- **`scripts/match_solveurs.py`** — joue des parties à deux joueurs en
  **miroir** (mêmes donnes, places échangées : la graine est réappliquée avant
  chaque `creer_partie`, donc chaque solveur joue une fois chaque main et une
  fois chaque position — avantage de la main et de l'ouverture neutralisés).
  - **« Joueur bibliothèque »** (`decider_bibliotheque`) bâti sur l'adaptateur
    `scripts/solveur_exact.py` (#204) : renvoie un coup complet (tuiles posées +
    nouveau plateau) remis dans l'ordre et validé par `valider_combinaison`,
    conservation du plateau contrôlée. **Mise initiale** : la bibliothèque
    réarrange table + main au second temps (interdit avant la mise) ; on la
    **contraint à n'utiliser que la main** (résolution sur plateau vide puis
    recollage du plateau intact), cas compté à part (`mise_contrainte`).
  - **« Notre solveur »** = niveau **Expert livré** (`jouer_niveau_expert`).
  - **Contrôles à chaque coup** : conservation des **106 tuiles**, et comparaison
    du nombre maximal de tuiles posables des deux solveurs sur le même état (tout
    écart = écart d'optimalité à investiguer, ne devrait jamais arriver).
  - **Limite de temps ferme** (`--limite-temps`), arrêt propre entre deux
    parties, **résultats partiels** écrits en continu (rapport `.txt` + `.json`).
  - **Indicateurs** : taux de victoire + **IC 95 % (Wilson)**, tuiles restantes
    en main du perdant (serrage), tuiles posées/tour, tours/partie, parties
    bloquées, temps moyen/max par coup. Lancement :

    ```
    .venv-solveur-exact/bin/python scripts/match_solveurs.py \
        --donnes 100 --limite-temps 4000 --sortie resultats_match_212.txt
    ```

- **`tests/test_match_solveurs.py`** — tests du script, sautés proprement si la
  bibliothèque est absente (`pytest.importorskip`) ; le petit match complet est
  marqué `lent`.

### Résultat de la campagne

Campagne du 2026-10-29 (graine 20212, budget Expert 1,5 s), arrêtée à la limite
ferme de 2100 s : **83 donnes = 164 parties**.

- **Notre solveur (Expert)** : 89/164 = **54,3 %**, IC 95 % **[46,6 ; 61,7] %**.
- **Bibliothèque** : 75/164 = **45,7 %**, IC 95 % **[38,3 ; 53,4] %**.
- Égalités 0, parties bloquées 0. Tours/partie moyen 64,9. Tuiles restantes du
  perdant : 2,44 (notre) vs 2,45 (biblio). Tuiles posées/tour : 0,978 vs 0,975.
  Temps/coup moyen : 0,093 s (notre) vs 0,039 s (biblio). Conservation : 0 erreur.

**Conclusion.** Les IC 95 % **se chevauchent** → **aucun avantage démontré** au
jeu « un tour » : nos critères de départage (perturbation minimale #199, économie
de jokers) **ne nous désavantagent pas de façon mesurable**. Le progrès est à
chercher dans le jeu sur plusieurs tours (§13). 1 écart d'optimalité signalé sur
~10 000 états (donne 20B, tour 64), **non reproductible en rejeu propre
monothread déterministe** → artefact temporel du solveur maison borné en temps
sous charge concurrente, pas un défaut structurel (égalité exacte vérifiée #204).
*Résultats complets : `resultats_match_212.txt` / `.json`.*

## 18. Mesure de limites de volume de calcul du solveur (issue #222)

**Objectif de l'issue, et ce qu'elle N'EST PAS.** La force des niveaux
d'IA dépend aujourd'hui d'un budget de **temps** par coup (1,5 s, voir §8bis/
§8ter) : sur une machine lente, le solveur s'arrête plus tôt et trouve un
moins bon coup — le niveau devient plus faible selon la machine, ce qu'Alain
veut éviter (une machine lente doit être plus LENTE, pas plus FAIBLE). La
piste est de borner le solveur par un **volume de calcul** (nœuds, itérations)
identique sur toutes les machines. **Cette issue ne fait QUE mesurer et
documenter** : aucun comportement du jeu, des niveaux ni du solveur n'est
changé. L'application d'une limite retenue est reportée à une issue
ultérieure, après lecture du rapport ci-dessous avec Alain.

### Moteur réellement utilisé en production

Les CINQ niveaux d'IA passent tous par `ia.jouer_niveau_bride` →
`jouer_niveau_expert` (§8ter, issue #213), qui résout le coup avec le modèle
**exact HiGHS** (`highspy`, `moteur/solveur_exact.py`, fonction
`resoudre_exact`) **en premier et dans l'immense majorité des cas** : c'est
donc le SEUL moteur dont la force de tous les niveaux dépend réellement. La
recherche arborescente maison (`moteur/solveur.py`, fonction `resoudre_coup`)
n'intervient qu'en **repli silencieux** (`SOLVEUR_RECHERCHE`), uniquement si
`highspy`/`numpy` sont absents ou si le modèle exact échoue sans solution dans
son budget — un cas rare en usage normal (highspy installé, 1,5 s largement
suffisant sur l'immense majorité des positions, voir ci-dessous). Les deux
moteurs sont donc traités, mais la mesure de VOLUME (tâches 4 à 6 de l'issue)
ne porte que sur `highspy`, le seul pour lequel une limite de volume existe et
est testée (voir plus bas).

### 1. Inventaire des limites de volume disponibles (highspy 1.15.1)

Testé par de petits essais directs sur l'objet `highspy.Highs()` construit
par `solveur_exact._nouveau_highs` (même configuration que la production :
`threads=1`, `random_seed=0`, `parallel=off`, `presolve=on`, gaps nuls) :

| Réglage HiGHS              | Respecté par cette interface ? | Observation |
|-----------------------------|---------------------------------|--------------|
| `mip_max_nodes`             | **Oui**, mais quasiment un INTERRUPTEUR sur les positions réelles du jeu, pas un curseur | Test synthétique (MIP aléatoire, 300 variables) : limite à 50 → arrêt PILE à 50 nœuds (`mip_node_count=50`, statut `kSolutionLimit`), au lieu de tourner indéfiniment sans limite. Sur les positions RÉELLES du corpus (voir plus bas) et sur les cas de référence `tests/donnees/cas_expert_*.json` (déjà difficiles pour `solveur.py`) : le modèle exact ne dépasse JAMAIS 1 à 3 nœuds au total (toutes passes lexicographiques confondues) même sans aucune limite — la relaxation LP du modèle (1167 variables, catalogue fixe des ensembles valides, indépendant de l'état) est presque toujours déjà entière à la racine. Conséquence mesurée sur le cas `cas_expert_humain_261026172338_tour66.json` : `mip_max_nodes=0` → échec immédiat (aucune solution, 0,28 s) ; `mip_max_nodes=1` → résultat **optimal complet**, dans le MÊME temps qu'illimité (~0,86 s contre ~0,89 s). Aucune valeur intermédiaire testée (2, 3, 5, 10, 50) ne change ni le résultat ni la durée. |
| `simplex_iteration_limit`   | **Non**, sans erreur ni avertissement | Accepté par `setOptionValue` (confirmé par `getOptionValue`), et RESPECTÉ sur un LP continu pur (test synthétique : limite à 5 → arrêt à 5 itérations, statut `kIterationLimit`). Mais sur le MODÈLE EXACT du jeu (MIP), AUCUN effet mesuré : `cas_expert_humain_261026172338_tour66.json` avec limite à 10 → 232 itérations simplex quand même (identique à la limite à 500 ou sans limite). Confirmé une deuxième fois sur un MIP synthétique sans `time_limit` : limite à 5, mais le calcul ne s'est TOUJOURS PAS arrêté après 2 min 30 (processus tué manuellement) — la limite n'est tout simplement pas appliquée aux résolutions internes du branch-and-bound par cette interface/version. |
| `mip_max_leaves`, `mip_max_improving_sols` | Non établi | Acceptés par `setOptionValue` (aucune erreur), mais aucun essai de respect effectif n'a été fait — hors périmètre faute de temps, à tester si une piste de curseur graduel est recherchée. |
| `time_limit`                | Oui (déjà le réglage de production) | Fonctionnement déjà vérifié par l'usage ; c'est la limite qui domine RÉELLEMENT le temps de calcul sur une position difficile (coût de la résolution de la relaxation LP elle-même, répétée sur 3-4 passes lexicographiques — voir `_resoudre_modele`), pas le nombre de nœuds. |

**Conséquence importante pour la suite (issue ultérieure de décision) :**
sur ce modèle et ces positions, `mip_max_nodes` ne fournit PAS le curseur
graduel espéré (« plus la limite est basse, moins bonne la qualité ») — il
se comporte en interrupteur marche/arrêt tant que la recherche n'a pas
BESOIN de brancher, ce qui est le cas normal observé. Une limite de volume
qui rendrait vraiment le temps indépendant de la machine devra soit cibler
autre chose (taille du modèle, nombre de passes lexicographiques exécutées),
soit s'appuyer sur les positions du corpus qui nécessitent RÉELLEMENT plus
de 1 à 3 nœuds (si la mesure complète en trouve), soit explorer d'autres
réglages HiGHS non testés ici. **Non établi : aucune limite de volume
testée ne reproduit le rôle gradué de `time_limit` sur ce modèle.**

**Moteur de repli (`solveur.py`) :** `resoudre_coup(etat, idx, budget_temps=…)`
n'expose AUCUNE limite de volume — seul un budget de temps (secondes). Le
code interne compte déjà les appels récursifs (`_Contexte.appels`,
`moteur/solveur.py`), mais ce compteur n'est ni renvoyé à l'appelant ni
utilisable comme limite d'ENTRÉE sans modifier l'interface — **Non établi /
inexistant**, et hors périmètre d'une mesure qui ne doit rien changer.

### 2. Déterminisme

| Moteur / réglage | Résultat |
|---|---|
| `highspy`, réglages de PRODUCTION (`threads=1`, `random_seed=0`, `parallel=off`) | **Déterministe** : 5 résolutions successives de la même position (cas réel chargé, `cas_expert_humain_261026172338_tour66.json`) renvoient EXACTEMENT le même coup (mêmes `ids_tuiles`) et le même volume de travail à chaque fois, avec ou sans `mip_max_nodes`. |
| `highspy`, `threads=4` + `parallel=on` (HORS production, essai de contrôle) | Sur l'unique cas testé qui a abouti dans le budget élargi (60 s), résultat IDENTIQUE sur 3 runs — mais avec un budget de 30 s (confortable à `threads=1`), le MÊME cas a parfois échoué par dépassement de budget en mode parallèle, ce qui n'arrive jamais à `threads=1`. Le réglage de production (`threads=1`) reste donc le bon choix pour la reproductibilité ET la fiabilité ; ne pas le changer sans mesure dédiée plus large. |
| `solveur.py` (maison, repli) | **Déterministe** (recherche pure, aucun aléa) : 4 résolutions successives d'un cas de référence renvoient le même coup à chaque fois. |

**Conclusion : le calcul EST déterministe avec les réglages de production
actuels (`threads=1`, `random_seed=0`), sans qu'aucun réglage supplémentaire
ne soit nécessaire — rien à changer sur ce point.**

### 3. Corpus de positions réelles (tâche 3)

`tests/donnees/corpus_positions_222.json` (**380 positions**, ~283 Ko, dans
le dépôt) — généré par `scripts/generer_corpus_positions_222.py`, à partir de
parties IA vs IA simulées (réutilise `scripts/simulation_ia.py`), graines 0 à
6, 2/3/4 joueurs, plusieurs décalages de niveaux, 1 à 2 manches par partie.
Répartition obtenue : phases **127 début / 125 milieu / 128 fin** (tiers de
chaque partie), joueurs **246×2 / 86×3 / 48×4**, et **198/380 plateaux
« chargés »** (≥ 30 tuiles posées, `SEUIL_CHARGE`). Entièrement
**régénérable à l'identique** (graines fixes, aucune horloge).

Format compact : chaque position ne garde que ce dont les deux solveurs ont
réellement besoin (plateau, chevalet du joueur au trait, mise initiale
faite/non faite, réglages de mise/manches), et chaque tuile est réduite à son
seul identifiant (`"rouge_7_a"`, `"joker_2"`) — `valeur`/`couleur`/`est_joker`
s'en déduisent intégralement (format figé, voir `tuiles.creer_sac`), d'où
une taille ~5× plus petite que le dict complet. Reconstruction et validation :
`scripts/_corpus_positions_222.py` (`etat_depuis_position`), vérifié identique
à une résolution directe sur l'état de simulation d'origine.

### 4-6. Script de mesure (référence / budget actuel / candidats)

`scripts/mesurer_volume_solveur_222.py` (aidé de `scripts/_mesure_volume_222.py`
pour l'injection de `mip_max_nodes` et le comptage de nœuds/itérations — voir
docstrings) résout chaque position du corpus trois façons :

1. **Référence** : `resoudre_exact` avec un budget de temps large
   (`--ref-temps`, 60 s par défaut) — nombre de tuiles posées (prouvé optimal
   ou non) et volume de travail effectué.
2. **Budget actuel** : budget de production (`--budget-actuel`, 1,5 s).
3. **Candidats** : plusieurs limites `mip_max_nodes` (`--candidats`, défaut
   `1,5,50,500` — à ajuster après lecture des résultats complets vu le
   constat du point 1 ci-dessus), avec un plafond de temps large en sécurité
   (`--securite-temps`, 20 s) qui ne doit normalement jamais mordre.

Résultats écrits en CONTINU (réécriture complète du fichier après chaque
position, comme `scripts/echelle_niveaux.py`, issue #220) dans `--sortie` :
toujours lisible, y compris partiel, avec le nom de la machine en en-tête
(`scripts/_rapport_duels.py`). Limite de temps FERME globale optionnelle
(`--limite-temps`, garde-fou externe `scripts/_limite_temps_ferme.py`).

**Essai sur 20 positions** (fait par l'agent, tâche 7) : `--n 20` termine en
~1,3 s, fichier lisible avec résumé agrégé (taux à l'optimum, perte moyenne
par phase, plus petite limite candidate suffisante). Essai de la limite de
temps ferme (`--limite-temps 2`, `--n 200`) : arrêt propre après 24 positions,
fichier marqué `[partiel]` / `ARRÊTÉ SUR LA LIMITE DE TEMPS`, toujours
lisible. Tests automatisés : `tests/test_mesure_volume_solveur_222.py` (sauté
si `highspy`/`numpy` absents).

**Commande pour Alain — mesure COMPLÈTE sur le corpus entier (380 positions),
au premier PLAN, avec `tee` vers un fichier HORS du dépôt et notification à la
fin (identique sous Windows — même commande sur le PC fixe, pour vérifier que
les coups trouvés sont les MÊMES avec la limite de volume) :**

```
python scripts/mesurer_volume_solveur_222.py --limite-temps 3600 \
    --sortie /tmp/mesure_volume_222_$(hostname).txt \
    2>&1 | tee /tmp/mesure_volume_222_$(hostname)_log.txt ; \
    echo "TERMINÉ (code $?)" ; \
    (command -v notify-send >/dev/null && notify-send "Mesure #222 terminée")
```

(Sous Windows, remplacer la ligne `notify-send` par un simple
`echo TERMINÉ` ou un `msg %username% "Mesure #222 terminée"` ; adapter le
chemin `--sortie` hors du dépôt, p. ex. `%TEMP%\mesure_volume_222_pc-fixe.txt`.)

### Résultats de la mesure complète

À remplir après le passage d'Alain (ThinkPad, puis PC fixe) — aucun chiffre
inventé ici : la part de coups sous-optimaux due au budget de 1,5 s par
moment de partie, et la plus petite limite candidate qui égale au moins
cette qualité, se lisent dans le fichier `--sortie` produit par la commande
ci-dessus, pas dans ce paragraphe.

