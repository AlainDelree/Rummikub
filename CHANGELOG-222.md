# Issue #222 — Solveur : mesurer des limites en volume de calcul plutôt qu'en secondes (mesure seule, sans changer le jeu)

Issue de **mesure et documentation uniquement** : aucun comportement du jeu,
des niveaux ni du solveur n'est modifié. Objectif : vérifier, par de petits
essais, si une limite en VOLUME de calcul (nœuds, itérations) peut un jour
remplacer le budget de TEMPS actuel (1,5 s) qui rend la force des niveaux
dépendante de la machine — la décision viendra dans une issue ultérieure.

## 1. Inventaire des limites disponibles sur le moteur réellement utilisé (highspy/HiGHS 1.15.1)

- `mip_max_nodes` : respecté (confirmé sur un MIP synthétique, arrêt pile au
  nombre de nœuds fixé), mais quasi INTERRUPTEUR plutôt que curseur sur les
  positions réelles du jeu — le modèle exact (1167 variables) ne dépasse
  presque jamais 1 à 3 nœuds, la relaxation LP étant déjà entière à la
  racine ; `mip_max_nodes=0` échoue instantanément, `mip_max_nodes>=1` donne
  le résultat optimal complet, même durée que sans limite.
- `simplex_iteration_limit` : accepté par l'API sans erreur, mais **non
  respecté** lors d'une résolution MIP par cette interface (deux essais
  indépendants, dont un MIP synthétique qui ne s'arrête jamais malgré la
  limite) — alors qu'il est bien respecté sur un LP continu pur.
- `mip_max_leaves`/`mip_max_improving_sols` : acceptés par l'API, respect non
  testé (« Non établi »).
- Moteur de repli (`moteur/solveur.py`, recherche arborescente maison) :
  **aucune limite de volume n'existe** dans son interface actuelle (seul un
  budget de temps) — « Non établi / inexistant », hors périmètre d'une
  mesure qui ne change rien.

## 2. Déterminisme

Vérifié déterministe avec les réglages de PRODUCTION actuels (`threads=1`,
`random_seed=0`, `parallel=off`) : même position + même limite → même coup,
même volume de travail, sur plusieurs exécutions. Rien à régler : c'est déjà
le cas. `solveur.py` (maison) est également déterministe (recherche pure,
sans aléa).

## 3. Corpus de 380 positions réelles (`tests/donnees/corpus_positions_222.json`)

Nouveau : `scripts/generer_corpus_positions_222.py` (constitution, réutilise
`scripts/simulation_ia.py`) et `scripts/_corpus_positions_222.py` (format
compact — positions réduites au strict nécessaire pour la résolution,
identifiants de tuile seuls). 380 positions (~283 Ko, dans le dépôt),
graines 0-6, 2/3/4 joueurs, phases début/milieu/fin (127/125/128), 198
plateaux « chargés » (≥ 30 tuiles). Entièrement régénérable à l'identique.

## 4-6. Script de mesure (`scripts/mesurer_volume_solveur_222.py`)

Nouveau (aidé de `scripts/_mesure_volume_222.py`) : résout chaque position en
RÉFÉRENCE (60 s), au BUDGET ACTUEL (1,5 s) et avec plusieurs limites
candidates `mip_max_nodes`, et agrège le taux de coups à l'optimum et la
perte moyenne par moment de partie. Résultats écrits en continu, lisibles y
compris partiels, en-tête avec le nom de la machine (réutilise
`scripts/_rapport_duels.py`). Limite de temps ferme globale optionnelle
(réutilise `scripts/_limite_temps_ferme.py`, comme l'issue #220).

## 7. Essai sur 20 positions (fait par l'agent) — mesure complète réservée à Alain

Script testé sur `--n 20` (fichier lisible, résumé correct) et sur une
limite de temps ferme très courte (arrêt propre, fichier `[partiel]`
toujours lisible). **La mesure complète (380 positions) n'a volontairement
PAS été lancée par l'agent** — seule une génération ponctuelle de corpus
(43,9 s) a tourné, qui n'est pas la mesure elle-même. Commande prête à
copier pour Alain (ThinkPad, puis PC fixe) dans `CONTEXTE.md` §18.

## 8. Documentation

Nouvelle section `CONTEXTE.md` §18 « Mesure de limites de volume de calcul du
solveur (issue #222) » : moteur réellement utilisé, tableau des limites
testées (respectées ou non), déterminisme, description du corpus et du
script, commande à lancer, et ligne « Résultats de la mesure complète : à
remplir après le passage d'Alain » sans aucun chiffre inventé.

## Nouveaux fichiers

- `scripts/_corpus_positions_222.py`, `scripts/generer_corpus_positions_222.py`
- `scripts/_mesure_volume_222.py`, `scripts/mesurer_volume_solveur_222.py`
- `tests/donnees/corpus_positions_222.json` (380 positions)
- `tests/test_mesure_volume_solveur_222.py`

Tests existants verts (393 passed, 14 skipped — inchangé). Aucun fichier de
`src/rummikub/` touché : le solveur, les niveaux et le jeu sont inchangés.
