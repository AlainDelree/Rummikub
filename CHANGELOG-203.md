# Issue #203 — Suite #192 : manches multiples réactivées, vrai décompte de manches et scores cumulés (une seule manche par défaut)

#192 avait masqué le réglage « Nombre de manches » et forcé une seule manche
partout, parce que la règle de fin de partie pour plus d'une manche
(`est_fin_partie`) comparait le numéro de tour au nombre de manches sans
qu'aucun compteur de manches correct n'existe. #203 ajoute un vrai compteur de
manches (`manche_numero`) et des scores cumulés par joueur, relie le tout au
réglage réaffiché (1 à 9, **défaut 1**), et met à jour journal, bilan,
analyse des coups ratés et scripts de simulation pour compter les manches. Le
comportement par défaut reste **une seule manche**.

## Règles des manches

- Une manche se termine quand un joueur vide son chevalet ou que la partie est
  bloquée (pioche épuisée — règle existante). Les scores de la manche (perdants
  en négatif, gagnant en positif, joker à la valeur du réglage) s'ajoutent aux
  cumuls.
- Si la manche n'est pas la dernière, le match continue : nouvelle donne, mise
  initiale remise à zéro pour tous, `score_cumul` conservé. **Qui commence** :
  rotation — la manche N commence par le joueur `(N-1) % nb_joueurs`.
- À la dernière manche, le match est terminé : le gagnant est le joueur au
  plus haut score cumulé ; en cas d'égalité, le classement affiche l'égalité.
- Avec une seule manche (défaut), les points restants ne départagent que les
  parties bloquées (le gagnant est celui qui vide son chevalet) ; l'écran de
  fin de partie reste celui d'avant #203.

## Moteur (`src/rummikub/moteur/`)

1. **`partie.py`** :
   - `creer_partie` lit `nb_manches` depuis les réglages (borné à [1, 9],
     défaut 1 — plus de forçage à 1), ajoute `manche_numero: 1`.
   - `_terminer_tour` : à la fin de la manche, calcule les scores et, si c'est
     la dernière manche (`est_fin_partie`), marque `terminee`, calcule
     `gagnant_match_index` (plus haut cumul) et `egalite_match`.
   - `est_fin_partie` : vrai si la manche est terminée ET `manche_numero >=
     nb_manches` (remplace la comparaison sur `tour_numero`).
   - `nouvelle_manche` : incrémente `manche_numero`, fait tourner le donneur,
     conserve `score_cumul`.
   - `normaliser_etat_reprise` (nouveau) : reprise d'une sauvegarde — un état
     sans `manche_numero` (d'avant #203) est repris en une seule manche ; un
     match récent au milieu d'un match conserve son nombre de manches.
2. **`score.py`** : `trouver_gagnant_match` (plus haut `score_cumul`) et
   `egalite_sommet_match` (égalité au sommet).

## Réglages et application

3. **`reglages.py`** : clé `nb_manches: 1` réintroduite dans `DEFAUTS`.
4. **`ui/application.py`** : `reprendre_jeu` n'force plus 1 manche ; il appelle
   `normaliser_etat_reprise`. `naviguer_vers_jeu` transmet les règles (dont
   `nb_manches`) à `creer_partie`.
5. **`ui/web/accueil.html` / `accueil.js`** : champ « Nombre de manches »
   (`<select>` 1-9, défaut 1) réaffiché dans l'onglet « Règles du jeu » ;
   lu/écrit dans les réglages (`lireNbManches`, bornage à 1) et transmis au
   lancement de la partie.

## Interface (`ui/web/jeu.html` / `jeu.js`)

6. Indicateur « Manche N / M » dans la barre supérieure, affiché uniquement
   quand le match compte plusieurs manches (`rafraichirIndicateurManche`).
7. Écrans de fin déjà en place (avant #192) de nouveau atteignables : écran de
   fin de manche intermédiaire (scores de la manche + cumul, bouton « Manche
   suivante ») et classement final (par cumul) ; l'égalité en tête est
   désormais affichée explicitement (`afficherClassementFinal`). Le rejeu, le
   pas-à-pas et le reste repartent proprement à chaque manche (`nouvelle_manche`
   réinitialise `dernier_coup_ia`, etc.).

## Journal, bilan et coups ratés (`src/rummikub/persistance/`)

8. **`journal.py`** : chaque action porte son numéro de `manche` ; `termine`
   n'est vrai qu'à la fin du MATCH, et `gagnant_index` y désigne alors le
   vainqueur du match (plus haut cumul).
9. **`bilan.py`** : décisions dédoublonnées par `(manche, tour)` (le `tour`
   repart à 1 à chaque manche) ; nouveau champ `nb_manches` par partie et
   `manches_moyennes` / `manches_total` par niveau. Un match de plusieurs
   manches est compté **une seule fois** ; une partie reprise reste un seul
   match (regroupement par `partie_id` existant).
10. **`coups_rates.py`** : une décision n'est jamais reconstituée à partir de
    l'état d'une autre manche (saut de frontière de manche) ; clé de
    dédoublonnage `(manche, tour, idx)`. La mise initiale repart de zéro à
    chaque manche.

Tous ces champs sont absents des journaux antérieurs → lus comme une manche
unique, sans régression.

## IA

11. Aucun changement de stratégie (issue #203, point 5) : les IA jouent chaque
    manche comme avant. Deux pistes d'Alain ajoutées en §13 de `CONTEXTE.md`
    (se débarrasser en priorité des 1 et des 13 ; tenir compte des points
    restants seulement en plusieurs manches, avec prudence).

## Simulations (`scripts/`)

12. **`simulation_ia.py`** : `--manches N` joue un match de N manches, avec
    résultat par manche et vainqueur du match (plus haut cumul).
13. **`comparer_niveaux_ia.py`** : nouveau `--manches N` — matchs de N manches
    joués en miroir ; rapport par match (victoires au cumul, score cumulé
    moyen) et par manche (fins, durée, pénalités du perdant).

## Tests

- `tests/test_moteur.py` : bornage de `nb_manches`, fin de manche
  intermédiaire vs match, scores cumulés, rotation du donneur, vainqueur au
  cumul ≠ gagnant de la dernière manche, égalité, reprise au milieu / reprise
  d'une ancienne sauvegarde (le test #192 de forçage à 1 est remplacé).
- `tests/test_bilan.py` : un match de plusieurs manches compté une seule fois.
- `tests/test_coups_rates.py` : manches non confondues.
- `tests/test_playwright_accueil_reglages.py` : réécrit pour le champ réaffiché
  (présent, rechargé/enregistré/transmis, bornage à 1).
- `tests/test_playwright_manches.py` (nouveau) : indicateur « Manche N / M »,
  écran de fin de manche intermédiaire, classement final, affichage de
  l'égalité.
- Suite complète : **227 tests passent** (`pytest -q`).

## CONTEXTE.md

- §3bis réécrit (statut ACTIF, règles des manches documentées) ; §3/§4
  (fonctions moteur, clés d'état) ; §9/§10 (scripts `--manches`, champ
  `manche` du journal) ; §13 enrichi des deux pistes IA d'Alain (pistes 6 et
  7) et constat du réglage corrigé par #203.
