# Moteur de jeu — règles et conventions

## 3. Moteur de jeu — fonctions publiques clés

**tuiles.py**
- `Tuile` (dataclass) : `id, valeur, couleur, est_joker` + `as_dict()`,
  `valeur_penalite(valeur_joker=30)`.
- `tuile_depuis_dict(d)` : reconstruit une Tuile depuis son `as_dict()`.
- `creer_sac()` → 106 tuiles (2 séries × 4 couleurs × 13 + 2 jokers).
  IDs : `"rouge_7_a"`, `"joker_1"`.
- `melanger(sac)` (Fisher-Yates, ne mute pas l'entrée).
- `distribuer(sac, nb_joueurs)` → `{"chevalets": [[Tuile×14],...], "pioche":[...]}`.

**validation.py** (retournent des dicts)
- `valider_suite(tuiles)` → `{valide, points}` : ≥3, même couleur, consécutives,
  jokers en comblement (pas 2 jokers adjacents).
- `valider_groupe(tuiles)` → `{valide, points}` : 3-4 tuiles, même valeur,
  couleurs distinctes, max 1 joker.
- `valider_combinaison(tuiles)` → `{valide, type:"suite"|"groupe"|None, points}`.
- `valider_plateau(combinaisons)` → `{valide, erreurs:[str]}`.

**partie.py**
- `creer_partie(config_joueurs, config_regles)` → état dict complet (voir §4).
  `config_joueurs = [{"nom", "est_ia", "niveau"}, ...]`.
- `jouer_tour(etat, ids_tuiles_posees, nouveau_plateau)` → `{ok, etat}` ou
  `{ok:False, erreur}`. Valide le plateau, contrôle la mise initiale (≥30 pts
  au premier coup), retire les tuiles du chevalet, remplace le plateau,
  termine le tour. **Issue #272** (défense en profondeur, aucun changement
  de comportement de jeu) : refuse un coup qui ne pose aucune tuile
  réellement présente dans le chevalet avant ce coup (liste vide ou sans
  tuile du chevalet) ; avant la mise initiale, refuse aussi tout coup dont
  un identifiant déclaré posé n'était pas dans le chevalet avant le coup
  (ex. une tuile du plateau à tort déclarée venir de la main) — un tel
  identifiant ne compte jamais dans les points de la mise initiale. Voir
  §11quinquies de `coups_rates_bilan.md`.
- `piocher(etat, nb=1)` → `{ok, tuiles_piochees, etat}`.
- `passer_tour(etat)` → `{ok, etat}`.
- `backup_debut_tour(etat)` : deep-copy plateau + chevalet + index + tour_numero.
- `annuler_tour(etat)` : restaure depuis le backup.
- `nouvelle_manche(etat)` : démarre la manche suivante (issue #203) —
  incrémente `manche_numero`, redistribue, reset plateau/chevalets/mise/
  score_manche, **conserve score_cumul**, rappelle `backup_debut_tour`.
  **Rotation du donneur** : la manche N (1-based) commence par le joueur
  `(N-1) % nb_joueurs`. Appelée par `api.jeu_nouvelle_manche` (bouton
  « Manche suivante ») et par les scripts de simulation.
- `est_fin_partie(etat)` : True quand la manche courante est terminée ET que
  `manche_numero >= nb_manches` (issue #203, remplace l'ancienne comparaison
  fondée sur `tour_numero`). Avec `nb_manches == 1` (défaut), équivaut à
  `manche_terminee`.
- `normaliser_etat_reprise(etat)` : à la reprise d'une sauvegarde (issue
  #203) — une partie SANS `manche_numero` (état d'avant les manches
  multiples) est reprise en une seule manche ; une partie récente conserve
  son vrai nombre de manches, même reprise au milieu d'un match.
- Helpers internes : `plateau_depuis_dict`, `_plateau_vers_dict`,
  `_points_tuiles_posees`, `_terminer_tour`, `_ajouter_historique`.

**score.py**
- `calculer_scores_manche(joueurs, valeur_joker)` : perdants = −somme pénalités
  de leur chevalet ; gagnant (chevalet vide) = +somme des pénalités adverses.
  Met à jour `score_manche` et `score_cumul` en place.
- `trouver_gagnant_manche(joueurs)` → index du meilleur `score_manche`.
- `trouver_gagnant_match(joueurs)` → index du meilleur `score_cumul`
  (vainqueur du MATCH, toutes manches confondues — issue #203).
- `egalite_sommet_match(joueurs)` → True si au moins deux joueurs partagent
  le plus haut `score_cumul` (égalité en tête du classement final).

## 3bis. Manches multiples : réglage réactivé, vrai compteur de manches (issue #203, suite de #192)

> **Statut : ACTIF depuis #203.** #192 avait masqué le réglage et forcé une
> seule manche partout (faute d'un compteur de manches correct :
> `est_fin_partie` comparait alors `tour_numero` au nombre de manches, et
> aucun appel à `nouvelle_manche` n'existait dans l'application). #203 ajoute
> un vrai compteur (`manche_numero`), des scores cumulés par joueur, et relie
> le tout au réglage — le comportement **par défaut reste une seule manche**.

**Règles des manches (issue #203) :**

- Le joueur choisit le **nombre de manches** du match (1 à 9, défaut 1), via
  un contrôle compact « Nombre de manches » placé sur la carte principale de
  l'écran d'accueil, juste au-dessus du bouton « Lancer la partie » (issue
  #205 : choix propre à chaque match, au même endroit que les adversaires, et
  **retiré de l'onglet « Règles du jeu » des Réglages**). Le choix est persisté
  sous la clé `nb_manches` de `config.json` (`reglages.DEFAUTS`) dès qu'il
  change (événement `change` → `sauvegarder_reglages({nb_manches})`, sans
  toast), puis présélectionné à l'ouverture suivante (`remplirChampManches`).
  Un `config.json` ancien ou sans la clé, ou une valeur hors de [1, 9],
  retombe sur 1 (fusion `{**DEFAUTS, ...}` + bornage côté JS
  `lireNbManches`/`remplirChampManches` et côté moteur dans `creer_partie`).
  Code : `accueil.html`/`accueil.js`/`accueil.css` (`#choix-manches`,
  `#acc-manches`).
- **Fin d'une manche** (issue #255, vraie règle du Rummikub) : un joueur
  vide son chevalet, OU la manche est **bloquée** — la pioche est vide ET
  tous les joueurs ont passé un tour complet de suite sans qu'aucun coup
  n'ait été joué (`etat["passes_consecutives"] >= nb_joueurs`, remis à 0 par
  la moindre pose réussie, voir `moteur/partie._terminer_tour`/
  `jouer_tour`/`passer_tour`/`piocher`). Tant que la pioche n'est pas vide,
  on continue à piocher normalement — l'ancienne fin immédiate « pioche
  vide » (approximation) a disparu. `calculer_scores_manche` applique le
  barème (perdants : −somme des pénalités de leur chevalet, joker à la
  valeur du réglage ; gagnant : +total) ; pour une manche bloquée, le
  gagnant est celui dont les tuiles restantes valent le moins (même
  barème), `etat["manche_bloquee"]` est posé à `True` — et l'**ajoute aux
  `score_cumul`**. **Réglage de TEST** (issue #256, désactivé par défaut,
  jamais utilisé par le jeu/l'IA/l'interface, réservé aux scripts de
  mesure — voir §9) : `fin_manche_pioche_vide` rétablit, si activé,
  l'ancienne fin immédiate « pioche vide » (avant #255) pour borner la
  durée des campagnes de calibration ; même décompte que la manche
  bloquée.
- **Avec une seule manche** (défaut), les points restants ne départagent que
  les parties bloquées : le gagnant est celui qui vide son chevalet (plus
  haut `score_cumul` = plus haut `score_manche`). **Avec au moins deux
  manches**, les points restants du perdant s'accumulent et comptent pour la
  suite.
- **Manche intermédiaire** (pas la dernière) : `_terminer_tour` marque
  `manche_terminee` mais **pas** `terminee`. L'UI montre l'écran de fin de
  manche (scores de la manche + cumul, bouton « Manche suivante »), qui
  appelle `api.jeu_nouvelle_manche` → `nouvelle_manche` : nouvelle donne,
  mise initiale remise à zéro pour tous, `score_cumul` conservé, et
  **rotation du donneur** (la manche N commence par le joueur
  `(N-1) % nb_joueurs`).
- **Dernière manche** : `est_fin_partie` est vrai (`manche_numero >=
  nb_manches`), `terminee` passe à True, `gagnant_match_index` = joueur au
  plus haut `score_cumul`, `egalite_match` si égalité au sommet. L'UI montre
  le classement final (par `score_cumul` décroissant ; égalité affichée).
  Avec une seule manche, cet écran de fin reste celui d'avant #203.
- **Reprise d'une sauvegarde** : `normaliser_etat_reprise` (`moteur/
  partie.py`, appelé par `reprendre_jeu`) reprend un match récent au milieu
  d'un match en conservant son nombre de manches ; une partie sauvegardée
  AVANT #203 (sans `manche_numero`), même avec `nb_manches > 1`, est reprise
  en une seule manche (aucun point de départ fiable pour le décompte).
- **IA inchangée** (issue #203, point 5) : les IA jouent chaque manche
  comme avant, sans tenir compte du score cumulé ni du nombre de manches
  (deux pistes à ce sujet en §13).

**Journal / bilan / coups ratés (issue #203, point 4) :** chaque action du
journal porte désormais son numéro de `manche` ; `termine` n'est vrai qu'à la
fin du MATCH (jamais d'une manche intermédiaire), et `gagnant_index` y vaut
alors le vainqueur du match (plus haut cumul). `bilan.py` compte un match de
plusieurs manches **une seule fois** (dédoublonnage des décisions par
`(manche, tour)`, nouveau champ `nb_manches`/`manches_moyennes`) ; une partie
reprise après fermeture reste un seul match (regroupement par `partie_id`,
§10bis). `coups_rates.py` ne reconstitue jamais une décision à partir de
l'état d'une AUTRE manche (plateau remis à zéro : saut de frontière de
manche) et clôt chaque décision par `(manche, tour, idx)`. Tous ces champs
sont absents des journaux antérieurs → lus comme une manche unique, sans
régression.

**Simulations (issue #203, point 6) :** `scripts/simulation_ia.py`
(`--manches N`, déjà présent, enrichi d'un résultat par manche + vainqueur du
match) et `scripts/comparer_niveaux_ia.py` (`--manches N`, nouveau) jouent des
matchs de N manches ; `comparer` donne les résultats par match (victoires au
cumul, score cumulé moyen) et par manche, parties toujours jouées en miroir.

**Tests :** `tests/test_moteur.py` (nb_manches borné, fin de manche
intermédiaire vs match, scores cumulés, rotation du donneur, vainqueur au
cumul ≠ gagnant de la dernière manche, égalité, reprise au milieu / reprise
d'une ancienne sauvegarde) ; `tests/test_bilan.py` (un match de plusieurs
manches compté une seule fois) ; `tests/test_coups_rates.py` (manches non
confondues) ; `tests/test_playwright_accueil_reglages.py` (choix présent sur
l'accueil et absent des Réglages, valeur rechargée/enregistrée/transmise,
bornage à 1 — mis à jour par #205) ;
`tests/test_playwright_manches.py` (indicateur « Manche N / M », écran de fin
de manche intermédiaire, classement final, affichage de l'égalité).

## 4. Conventions importantes

- **Tuile** = dataclass avec `id/valeur/couleur/est_joker` + `as_dict()`.
- **État de partie** = **dict JSON-sérialisable** (jamais d'objets Python
  stockés dans l'état). Le moteur convertit Tuile ↔ dict aux frontières.
- **plateau** = `list[list[dict_tuile]]` côté état/API ;
  `list[list[Tuile]]` seulement à l'intérieur des fonctions de validation/moteur.
- Clés de l'état : `id, phase, tour_numero, manche_numero,
  index_joueur_actuel, joueurs[], pioche[], plateau[], plateau_debut_tour,
  chevalet_debut_tour, index_debut_tour, tour_debut_tour, historique[],
  manche_terminee, manche_bloquee, passes_consecutives,
  gagnant_manche_index, config{}` (`manche_bloquee`/`passes_consecutives` :
  vraie règle de blocage, issue #255, voir §3bis). À la fin du MATCH
  (dernière manche), s'ajoutent `terminee`, `gagnant_match_index` (plus haut
  score cumulé) et `egalite_match` (issue #203). Un joueur :
  `nom, est_ia, niveau, chevalet[], mise_initiale_faite, score_manche, score_cumul`.
- `etat["config"]` contient : `nb_manches, valeur_joker_penalite,
  mise_initiale_min` (+ `vitesse_ia` ajouté côté application.py, non utilisé
  par le moteur).
- **Le plateau ne perd jamais de tuile** (#187) : une fin de tour (humain ou
  IA, n'importe quel niveau) ne peut jamais faire disparaître une tuile
  présente sur le plateau en début de tour — elle peut changer de
  combinaison, jamais disparaître. Contrôlé de façon centrale dans
  `jouer_tour` (`moteur/partie.py`) : si l'ensemble des IDs du plateau
  proposé ne contient pas tous les IDs du plateau de début de tour, le coup
  est refusé (`{"ok": False, "erreur": "Coup refusé : des tuiles du
  plateau ont disparu (...)", "tuiles_disparues": [id, ...]}`), même si
  chaque combinaison proposée est individuellement valide. Ce contrôle
  protège aussi bien les coups humains que tous les niveaux d'IA présents
  et futurs, puisque `jouer_tour` est le point d'entrée unique pour poser
  un coup. Voir `test_jouer_tour_refuse_si_des_tuiles_du_plateau_
  disparaissent` (`tests/test_moteur.py`) et §8bis (bug d'origine côté
  solveur Expert).
- **`backup_debut_tour` est appelé dans `api.py`** après chaque coup
  (jouer/piocher/passer/reprendre/IA) — **pas** dans le moteur lui-même.
- Après chaque coup, `api.py` appelle `sauvegarder_partie` (SQLite).
- **Chemins toujours via `pathlib.Path`** (jamais `os.sep` codé en dur côté app).
- **Jamais de `git push`** : CCL committe en local, Alain vérifie et pousse.
- Toujours un **commit de sauvegarde `--allow-empty` AVANT** toute modification.
- **Suppressions de sécurité du linter (`ruff --select S`)** : corriger plutôt
  que supprimer quand possible, sinon suppression en ligne sur DEUX lignes
  avec raison en clair + `noqa`/`nosec` précis (jamais seuls) — voir
  `docs/contexte/linter_securite.md` (issue #248).

