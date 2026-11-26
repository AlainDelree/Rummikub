# Issue #273 — Règle de l'ouverture : plus aucune modification de la table pendant le tour d'ouverture, pour l'IA comme pour le moteur

## Contexte

L'étude #270 avait trouvé un écart de règle réellement atteignable en jeu :
Facile, Intermédiaire et Avancé (en repli), via `ia._coup_maximal`, formaient
d'abord leur combinaison d'ouverture depuis le chevalet seul (correct), puis,
une fois les 30 points atteints pendant ce même tour, appelaient
`_appliquer_extensions` sur le **plateau complet**, y compris les
combinaisons déjà posées par d'autres joueurs aux tours précédents — exemple
reproduit : un joueur ouvre avec un groupe de 13 et prolonge au même tour la
suite 5-6-7 noir d'un adversaire en 5-6-7-8 noir. Le livre officiel du
Rummikub interdit d'ouvrir et de jouer sur la table pendant le même tour.
Décision d'Alain (26/11/2026) : interdire strictement, pour tous — IA et
moteur — avec une légère baisse de force acceptée pour Facile, Intermédiaire
et Avancé ; la vérification de l'échelle sera relancée par Alain sur le PC
fixe après cette issue.

## 1. `src/rummikub/moteur/ia.py`

- `_coup_maximal` : avant, une fois la mise initiale atteinte ce tour (`mise_ok`),
  `_appliquer_extensions` était appelée sur le plateau COMPLET (combinaisons
  préexistantes comprises). Désormais, tant que `mise_initiale_faite` est
  faux en entrée de fonction, les extensions ne portent plus que sur les
  combinaisons posées CE tour (celles ajoutées après `nb_combos_avant =
  len(plateau)`, capturé avant tout ajout) — jamais sur celles déjà
  présentes sur la table. Une fois la mise initiale faite (tours suivants),
  le comportement est inchangé (extensions sur tout le plateau).
- **Autres chemins examinés, déjà conformes, aucun changement** :
  - `_coup_scission`, `_meilleur_coup_liberations`/`_liberations_possibles`
    (tactiques de joker) : déjà gardés par `if not joueur["mise_initiale_
    faite"]: return None` — ne pouvaient déjà pas toucher le plateau avant
    l'ouverture.
  - `_combos_vers_coup` (Débutant) : n'ajoute que de nouvelles combinaisons
    depuis le chevalet, n'étend jamais une combinaison existante.
  - `jouer_niveau_expert` (solveur exact `solveur_exact.py`, et son repli la
    recherche arborescente `solveur.py`) : les deux gèlent déjà
    intégralement le plateau avant la mise initiale (documenté §8bis/§8ter
    de `solveur_expert.md`, vérifié dans le code — `mise_faite`/`deja_faite`
    gèle `plateau`/`combos_figes` et ne laisse la recherche porter que sur
    le chevalet).
  - `_appliquer_joker_utile`/`_appliquer_echange_differe`/`_appliquer_
    joker_libre` (gestion du joker, #253/#254) : rejouent le coup via
    `_coup_avec_chevalet` → `_coup_selon_perturbation`, qui retombe toujours
    sur l'un des chemins ci-dessus (déjà corrigés ou déjà gardés) — aucun
    chemin propre à elles ne touche directement le plateau.

## 2. `src/rummikub/moteur/partie.py` (`jouer_tour`)

Nouveau contrôle (étape « 3bis », défense en profondeur, après le contrôle
d'origine des tuiles de #272 et avant le calcul des points de mise
initiale) : si le joueur n'avait pas fait sa mise initiale avant ce coup,
chaque combinaison déjà présente sur la table en début de tour doit se
retrouver **à l'identique** (même ensemble exact de tuiles, comparé par
`frozenset` des identifiants) dans le plateau proposé ; sinon le coup est
refusé : `"Coup refusé : avant l'ouverture, aucune combinaison déjà
présente sur la table ne peut être modifiée ou prolongée (règle de
l'ouverture)"`. Ce contrôle couvre aussi bien l'extension d'une combinaison
que son démantèlement ou la récupération d'un joker qu'elle contenait. Une
fois la mise initiale faite (tour suivant), ce contrôle ne s'applique plus
— le jeu normal (réarrangements, extensions) reprend sans restriction.

## 3. Tests

**`tests/test_ia.py`** (section « Règle de l'ouverture… ») : scénario exact
de l'étude #270 (groupe de 13, suite noire 5-6-7 préexistante, 8 noir en
main) pour Facile et Intermédiaire (`jouer_niveau_facile`/
`jouer_niveau_intermediaire`) — ouvre sans toucher la suite, le 8 noir reste
en main ; même scénario pour le repli heuristique d'Avancé
(`jouer_niveau_avance`) ; non-régression : le même joueur, une fois
`mise_initiale_faite` à `True`, peut prolonger la même suite avec le 8 noir
(`test_intermediaire_peut_prolonger_la_meme_combinaison_au_tour_suivant`).

**`tests/test_moteur.py`** (section « Règle de l'ouverture… ») :
`jouer_tour` refuse un coup d'ouverture qui prolonge la suite noire
préexistante même si le groupe de 13 seul suffirait
(`test_jouer_tour_refuse_ouverture_qui_prolonge_une_combinaison_
preexistante`) ; accepte la même ouverture quand la suite reste intacte
(`test_jouer_tour_accepte_ouverture_qui_laisse_intacte_une_combinaison_
preexistante`) ; refuse la récupération d'un joker de la table avant
l'ouverture (`test_jouer_tour_refuse_recuperation_de_joker_avant_
ouverture`) ; accepte la prolongation de la même combinaison au tour
suivant, une fois la mise initiale faite
(`test_jouer_tour_accepte_extension_d_une_combinaison_au_tour_suivant`).
Les tests déjà présents couvrant l'ouverture normale sur table vide/avec
combinaisons préexistantes intactes
(`test_jouer_tour_accepte_ouverture_legitime_depuis_le_chevalet_seul`,
`test_jouer_tour_accepte_ajout_d_une_tuile_du_chevalet_apres_ouverture`)
continuent de passer sans modification — ils servaient déjà de contrôle
négatif pour cette règle. Rapides et déterministes (aucun appel au solveur
exact, aucune dépendance aux réglages calibrés de `niveaux.py`), aucun test
existant retiré ni raccourci.

Suite complète exécutée une fois au premier plan (`timeout 900`, sortie dans
un fichier) — voir le rapport de clôture pour le résultat détaillé.

## 4. Mesure d'impact (indicative)

Script de mesure autonome, **hors dépôt** (pas un livrable, supprimé après
la mesure) : 40 donnes à 2 joueurs, niveaux Facile/Intermédiaire/Avancé
répartis cycliquement, jouées directement via les fonctions heuristiques
visées par le bug (`jouer_niveau_facile`/`jouer_niveau_intermediaire`/
`jouer_niveau_avance`, sans solveur exact — rapide et déterministe),
jusqu'à l'ouverture de chaque joueur. Pour une mesure « avant » cohérente
(le monde d'avant #273 n'avait pas non plus le nouveau contrôle moteur),
`ia.py` ET `partie.py` ont été rechargés depuis le commit de sauvegarde
(avant toute modification de cette issue) pour cette passe ; la passe
« après » utilise les modules réels, déjà corrigés, du dépôt.

| | Tours d'ouverture joués | … modifiant une combinaison préexistante |
|---|:--:|:--:|
| AVANT correctif | 80 | 22 (27,5 %) |
| APRÈS correctif | 80 | 0 (0,0 %) |

Résultat strictement indicatif (petit échantillon, chemin heuristique
direct plutôt que la chaîne de production complète via `jouer_niveau_bride`)
: la vraie vérification de l'échelle (duels entre niveaux voisins,
`scripts/echelle_niveaux.py`) sera relancée par Alain sur le PC fixe.

## 5. `niveaux.py` et calibrage

Non touchés, comme demandé. Aucune campagne de calibration lancée.

## 6. Documentation

- `docs/contexte/moteur_regles.md` : nouvelle règle consignée (à la suite de
  la règle « le plateau ne perd jamais de tuile »).
- `docs/contexte/joker_tactiques.md` : note précisant que les tactiques de
  joker étaient déjà gardées, et identifiant `_coup_maximal` comme le seul
  chemin fautif.
- `docs/contexte/niveaux_ia_calibrage.md` : note sur la baisse de force
  attendue et le rappel que l'échelle de #267 doit être revérifiée après
  cette issue.
- `CONTEXTE.md` : non touché (hors périmètre de cette issue).

## Points d'attention pour Alain

- L'échelle calibrée de #267 (Débutant/Facile/Intermédiaire/Avancé/Expert)
  doit être **revérifiée** sur le PC fixe (`scripts/echelle_niveaux.py`) :
  Facile, Intermédiaire et Avancé perdent une option d'ouverture auparavant
  (à tort) disponible, donc une légère baisse de force est attendue, assumée
  par la décision de ce correctif.
- La mesure d'impact (§4) est strictement indicative : échantillon réduit et
  chemin heuristique direct (pas la chaîne de production complète avec
  solveur exact).
