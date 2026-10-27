# Issue #201 — Suite #193 : compter les tuiles réellement posées depuis la main (et non les tuiles déplacées) pour un coup humain

Cas réel (tour 66) : `scripts/analyser_coups_rates.py --joueur` annonçait
« posé 18, solveur 7 » (le joueur « bat le solveur » de +11), alors que la
description du coup réellement joué montrait seulement 4 tuiles posées
depuis la main — c'est le solveur qui posait plus de tuiles (7 contre 4),
pas l'inverse.

Cause : `jeu_jouer_coup` (`ui/api.py`) journalisait `nb_tuiles_posees =
len(data["ids_tuiles"])`. Or `ids_tuiles` vient de `tuilesCeTour` côté
interface (`jeu.js`), qui mélange les tuiles venues de la main ET celles du
plateau déplacées pendant le tour (le jeu s'en sert pour colorer « tuile du
tapis déplacée ce tour »). Pour un humain, le journal comptait donc des
tuiles déplacées comme des tuiles posées ; pour une IA, `ids_tuiles` ne
contient que des tuiles de la main, donc son compte était déjà correct.

1. **Analyse corrigée à la source** (`persistance/coups_rates.py`,
   `extraire_toutes_decisions`) : `nb_tuiles_jouees` est désormais calculé
   comme `len(ids_tuiles_reelles)` (différence main avant/après le coup),
   jamais depuis le champ `nb_tuiles_posees` du journal — corrige aussi les
   journaux ANCIENS, puisqu'il ne dépend que des deux instantanés de main
   déjà présents dans tout journal post-#185. Une seule fonction corrigée
   répare en cascade la détection « solveur battu »/pose sous-optimale, les
   statistiques de style, la détection de la réserve, et
   `attendu_min_tuiles` des cas de référence enregistrés.
2. **Journal corrigé** (`ui/api.py:jeu_jouer_coup`, `persistance/journal.py`)
   : capture la main AVANT le coup, puis journalise dans `nb_tuiles_posees`
   le nombre de tuiles de `ids_tuiles` réellement présentes dans cette main,
   et dans la nouvelle clé `nb_tuiles_deplacees` le reste. `logger_action`
   accepte ce nouveau paramètre (défaut 0, rétrocompatible). Vérifié :
   `persistance/bilan.py` recopie `nb_tuiles_posees` mais ne s'en sert
   jamais dans le calcul du bilan — aucune adaptation nécessaire.
3. **Usage de `ids_tuiles` par le moteur vérifié, non modifié** :
   `moteur/partie.py:jouer_tour` ne distingue jamais une tuile de la main
   d'une tuile déplacée. Signalé (voir rapport de clôture) un bug potentiel
   distinct, de la RÈGLE de mise initiale (`_points_tuiles_posees` peut
   compter à tort la valeur de tuiles déplacées, pas posées, dans le total
   requis) — volontairement NON corrigé ici (hors périmètre de cette issue,
   à confirmer par Alain).
4. **Cas de référence régénérables** (`scripts/analyser_coups_rates.py`) :
   nouvelle option `--ecraser` pour `--enregistrer-cas-reference`, qui lève
   le garde-fou "jamais écraser" par défaut — permet de régénérer
   `tests/donnees/cas_expert_humain_*.json` avec le bon `attendu_min_tuiles`
   une fois relancé sur les vrais journaux (hors de ce worktree). Le
   solveur n'est jamais modifié.
5. Tests : `tests/test_coups_rates_tuiles_main.py` (cas réel reproduit,
   journal ancien sans la nouvelle clé, journal d'IA cohérent) ;
   `tests/test_api_journal.py` (journal corrigé de `jeu_jouer_coup` avec
   des tuiles du plateau déplacées). `CONTEXTE.md` §11quinquies.
