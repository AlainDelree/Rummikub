# CONTEXTE — Projet Rummikub

> Ce fichier est injecté automatiquement dans le prompt de chaque future issue
> CCL du projet. Il décrit l'architecture, les conventions et l'état du projet
> afin qu'aucun agent ne reparte de zéro. **Le tenir à jour** quand une issue
> modifie l'architecture ou les conventions.

## 1. Stack technique

- **Python 3.12** (aucune dépendance web côté serveur JS : pas d'Electron, pas de Node).
- **pywebview** : fenêtre native unique. Navigation entre écrans par
  `window.load_url(...)` (pas de routeur SPA). Le back-end Python expose une
  API à JS via `js_api` → `window.pywebview.api.*`.
- **PyInstaller** (`rummikub.spec`, mode **onedir** via `COLLECT`) : produit
  `dist/Rummikub/`. Build : `pyinstaller rummikub.spec` depuis la racine.
- **SQLite** (module standard `sqlite3`) pour la persistance des parties.
- **Portable Linux ET Windows** : aucun séparateur de chemin codé en dur,
  tout passe par `pathlib.Path` (côté app) ou `os.path` (côté `.spec`).
- Dépendances (`requirements.txt`) : `pywebview`, `pyinstaller`, `pytest`.

## 2. Architecture générale

```
main.py                     Point d'entrée. Ajoute src/ au sys.path (sauf si frozen),
                            puis appelle rummikub.ui.application.main().
config.json                 Réglages utilisateur persistés (à la racine).
rummikub.spec               Spec PyInstaller onedir (embarque ui/web/).
pytest.ini                  pythonpath=src, testpaths=tests.
data/parties.db             Base SQLite (créée à la volée).

src/rummikub/
  config.py                 Constantes globales + chemins frozen/dev (RACINE_PROJET
                            via sys._MEIPASS si gelé, sinon parents). COULEURS,
                            VALEUR_MIN/MAX, NB_JOKERS(2), NB_TUILES_DEPART(14),
                            MISE_INITIALE_MIN(30), NIVEAUX (5 libellés IA), AVATARS.
  reglages.py               charger()/sauvegarder(data) de config.json (fusion DEFAUTS).
  persistance/stockage.py   SQLite : sauvegarder_partie, charger_parties(5 derniers),
                            charger_partie, marquer_terminee, supprimer_partie.
  persistance/journal.py   Journal JSON optionnel par partie (debug + bilan, voir §9).
  persistance/bilan.py      Lecture des journaux + calcul du bilan par niveau d'IA (§9).
  persistance/coups_rates.py  Détection des coups ratés de l'IA via le solveur
                            d'Expert, à partir des journaux (§11).
  moteur/                   Logique de jeu pure (voir §3).
    tuiles.py               Dataclass Tuile + création/mélange/distribution.
    validation.py           valider_suite/groupe/combinaison/plateau.
    partie.py               État de partie, tours, pioche, backup, manches.
    score.py                calculer_scores_manche, trouver_gagnant_manche.
    ia.py                   5 niveaux d'IA (voir §5) + tactiques de
                            récupération de joker (voir §8, niveau Avancé
                            et repli d'Expert).
    solveur.py              Solveur de réarrangement global du plateau,
                            utilisé par Expert (voir §8bis, #186).
    description_coup.py     Résumé écrit + étapes du rejeu pas-à-pas d'un
                            coup de l'IA, à partir du plateau avant/après
                            (voir §12, #189).
  ui/
    application.py          ApplicationRummikub : fenêtre pywebview, etat_jeu (public),
                            naviguer_vers_jeu/accueil, reprendre_jeu, load_url.
    api.py                  Classe Api : méthodes appelables depuis JS (voir §4).
    noms_ordinateur.py      choisir() : nom aléatoire pour un joueur IA.
    web/                    Front : accueil.html/css/js, jeu.html/css/js,
                            commun.css/js, avatars/.

tests/                      pytest : test_moteur.py + test_ia.py + test_description_coup.py.
```

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
  termine le tour.
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
- **Fin d'une manche** : un joueur vide son chevalet, ou la partie est
  bloquée (pioche épuisée — règle existante, approximation de « tous
  bloqués »). `calculer_scores_manche` applique alors le barème (perdants :
  −somme des pénalités de leur chevalet, joker à la valeur du réglage ;
  gagnant : +total) et l'**ajoute aux `score_cumul`**.
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
  manche_terminee, gagnant_manche_index, config{}`. À la fin du MATCH
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

## 5. État des issues (au 2026-07-28)

Tout le cœur du projet est en place et testé :
- ✅ Moteur (tuiles, validation, partie, tours, pioche, backup/annulation,
  scores, manches).
- ✅ **IA implémentée** (`moteur/ia.py`) : 5 niveaux — Débutant, Facile,
  Intermédiaire, Avancé, Expert. Point d'entrée `jouer_ia(etat, joueur_index)`
  → `{"action": "jouer"|"piocher"|"passer", "ids_tuiles": [...],
  "nouveau_plateau": [...]}`. Les fonctions ne mutent jamais l'état ; tout coup
  proposé est revalidé (`_coup_valide`) pour ne jamais être rejeté par
  `jouer_tour`. `api.py::jeu_ia_jouer` a une pioche de secours si l'IA propose
  un coup invalide.
- ✅ Persistance SQLite, réglages JSON.
- ✅ UI pywebview : accueil (réglages, reprise de partie) + jeu (câblé à l'API).

Reste possible / à confirmer selon les futures issues : polish UI, équilibrage
IA, gestion fine de « tous bloqués » (actuellement approximée par pioche vide),
icône `assets/rummikub.ico` (facultative, absente → aucune icône).

## 6. Tests

- Lancer : `pytest tests/` (depuis la racine ; `pytest.ini` fixe
  `pythonpath=src`, `testpaths=tests`).
- `tests/test_moteur.py` : sac/distribution, suites/groupes/combinaisons,
  plateau, mise initiale, tours, pioche, backup/annulation.
- `tests/test_ia.py` : les 5 niveaux ne plantent pas et renvoient une action
  valide.
- `tests/test_bilan.py` : lecture des journaux de parties et calcul du bilan
  par niveau d'IA (voir §9).
- `tests/test_description_coup.py` : résumé écrit d'un coup de l'IA (coup
  simple/extension/groupe créé, joker récupéré, coup touchant plusieurs
  combinaisons) et découpage en étapes du rejeu pas-à-pas (voir §12).
- `tests/test_playwright_pas_a_pas.py` et
  `tests/test_playwright_accueil_reglages.py` : vérifications front-end via
  Playwright (voir §7), sautées proprement si `playwright` ou chromium sont
  absents.
- État actuel : **164 tests passent** (`pytest -q` → `164 passed`).

## 7. Vérification empirique d'un comportement front-end

- **Ne jamais lancer l'application pywebview réelle** (`python3 main.py`,
  qui appelle `webview.start()`) **ni un navigateur piloté sur
  l'application réelle** pour vérifier visuellement un comportement
  front-end (`jeu.js`/`jeu.html`/`jeu.css`, `accueil.js`/`accueil.html`...).
  Dans l'environnement headless sans affichage, ces commandes bloquent
  indéfiniment et provoquent un dépassement de TIMEOUT (vécu sur #140,
  #155 et d'autres issues avant elles).
- **Méthode à utiliser systématiquement** (déjà appliquée avec succès sur
  #128, #135, #140, #146, #151) : charger directement le fichier front
  concerné (`src/rummikub/ui/web/jeu.html`, `accueil.html`, etc.) via
  **Playwright**, en fournissant un **mock minimal de
  `window.pywebview.api`** (objet JS injecté avant chargement de la page,
  avec les méthodes utilisées par le script comme stubs/fausses promesses).
- Si le scénario a besoin d'un état de partie réaliste (plateau, chevalets,
  scores...), le **construire via le moteur réel** (`creer_partie`,
  `jouer_tour`, etc., importés côté Python et sérialisés en JSON pour le
  mock) plutôt que de bidouiller un DOM vide ou des données inventées à la
  main.
- Cette règle s'applique à **toute** vérification front-end future sur ce
  projet, sans qu'il soit nécessaire de la rappeler dans la consigne de
  l'issue.

## 8. Tactiques de récupération/libération de joker de l'IA (`moteur/ia.py`)

> Liste à tenir à jour par toute future issue qui ajoute ou modifie une
> tactique de joker (objectif : pouvoir un jour revoir les niveaux de
> difficulté de l'IA — jugés trop faibles actuellement — une fois
> l'ensemble des tactiques couvert).

> **Depuis #186, cette liste ne décrit plus que le niveau Avancé.** Expert
> ne les utilise plus comme chaîne de tactiques principale : il appelle le
> solveur de réarrangement global (§8bis), nettement plus fort, et ne se
> replie sur le comportement d'Avancé ci-dessous que si ce solveur dépasse
> son budget de temps par tour (ou échoue à trouver quoi que ce soit).

**Implémentées :**

- **Échange direct** (#148) — `_jokers_recuperables` : un joker posé dans
  une suite ou un groupe est remplacé par la tuile réelle identique déjà
  en main (même valeur/couleur pour une suite ; même valeur + couleur
  absente du groupe pour un groupe). Validité et points de la combinaison
  inchangés ; le joker est libéré pour un usage ailleurs sur le plateau.
- **Détachement en bout de suite** (#150) — `_jokers_detachables_par_extension` :
  un joker à une extrémité d'une suite est détaché *sans* tuile de
  remplacement, quand une tuile de la main jouée à l'extrémité OPPOSÉE
  allonge la portion de tuiles réelles restante à au moins 3 — celle-ci
  reste alors valide seule une fois le joker retiré.
- **Combinaison de plusieurs libérations dans le même coup** (#169) —
  `_liberations_possibles` / `_meilleur_coup_liberations` /
  `_coup_depuis_liberations` : les deux mécanismes ci-dessus sont
  recherchés simultanément sur des combinaisons distinctes du plateau,
  pour récupérer plusieurs jokers en un seul coup plutôt qu'un seul à la
  fois (corrige un bug où le second joker récupérable d'un même tour était
  systématiquement ignoré). Limite assumée : deux libérations sur la MÊME
  combinaison du plateau (ex. deux jokers dans une même suite) ne sont pas
  combinées — cas rare, laissé de côté pour borner la complexité.
- **Libération par réduction de groupe de 4 à 3** (#180) —
  `_jokers_liberables_par_reduction_groupe4` : un groupe de 4 tuiles de
  couleurs distinctes — déjà présent sur le plateau, ou complété à 4 par
  une tuile de la main de la 4e couleur manquante — perd une de ses
  tuiles RÉELLES (le groupe réduit à 3 reste valide) ; cette tuile libérée
  sert alors de remplacement pour un échange direct avec un joker
  récupérable ailleurs sur le plateau (même critère que
  `_jokers_recuperables`). Le joker ainsi libéré doit être rejoué dans le
  même tour. Intégré au même format unifié que #169
  (`_liberations_possibles`), qu'il a fallu généraliser pour supporter des
  libérations modifiant DEUX combinaisons du plateau à la fois (le groupe
  réduit et la combinaison du joker échangé), au lieu d'une seule pour les
  deux mécanismes précédents. À ne pas confondre avec la « réduction de
  groupe de 4 à 3 (joker retiré) » ci-dessous : ici on retire une tuile
  RÉELLE pour s'en servir comme remplaçante ailleurs, jamais le joker
  lui-même sans remplacement.
- **Scission en milieu de suite** (#181) — extension de `_coup_scission`
  (tuile réelle) et `_jokers_liberables_par_scission_milieu` (joker) :
  pour une suite d'au moins 7 tuiles, retirer une tuile intérieure (ni en
  tête ni en queue) peut laisser DEUX suites valides (chacune d'au moins 3
  tuiles, jokers éventuels compris) à la place de l'unique suite
  d'origine — une combinaison devient deux. Cas tuile réelle : la tuile
  libérée forme un nouveau groupe avec des tuiles de la main, comme pour
  le cas bout de suite déjà géré par `_coup_scission` (comportement
  inchangé pour ce cas bout). Cas joker : intégré au même format unifié
  que #169/#180 (`_liberations_possibles`), qu'il a fallu étendre pour
  qu'une libération puisse remplacer une combinaison du plateau par DEUX
  (au lieu de la modifier en place ou d'en modifier deux existantes) tout
  en gardant la détection de conflit (combinaisons touchées, tuiles de la
  main consommées) correcte ; le joker ainsi libéré doit être rejoué dans
  le même tour.
- **Réduction de groupe de 4 à 3 (joker retiré)** (#183) —
  `_jokers_liberables_par_groupe4_sans_remplacement` : un groupe de 4
  tuiles du plateau contenant un joker (3 tuiles réelles de couleurs
  distinctes + 1 joker) reste un groupe valide une fois le joker retiré —
  *sans* aucune tuile de remplacement, contrairement à l'échange direct
  (#148) qui exige une tuile identique en main, et à #180 qui retire une
  tuile RÉELLE (jamais le joker) pour l'utiliser ailleurs. Intégré au même
  format unifié que #169/#180/#181 (`_liberations_possibles`) ; le joker
  ainsi libéré doit être rejoué dans le même tour. Ne s'applique qu'aux
  groupes de 4 : un groupe de 3 avec joker (2 réelles + 1 joker) ne peut
  pas perdre son joker sans tomber sous le minimum de 3 tuiles.

**Identifiées mais pas encore implémentées pour Avancé :**

- **Démantèlement complet d'une courte suite contenant un joker** (#175) :
  retirer SES DEUX tuiles réelles (pas une seule comme dans les tactiques
  ci-dessus), chacune recombinée avec des tuiles de la main pour former
  deux NOUVELLES combinaisons (groupes ou suites) ailleurs sur le
  plateau — le joker est ainsi isolé et libéré sans qu'aucune tuile ne le
  remplace directement. Généralisable au cas sans joker. Nettement plus
  complexe que les tactiques ci-dessus — recherche de recombinaison
  globale sur plusieurs combinaisons du plateau, pas un simple motif
  local. Avancé ne le trouve toujours pas (tactiques locales inchangées,
  voir `test_avance_ne_demantele_pas_une_courte_suite_avec_joker`) ;
  **Expert le trouve désormais**, via le solveur de réarrangement global
  (§8bis) — voir `test_expert_demantele_completement_une_courte_suite_
  avec_joker` dans `tests/test_ia.py`.

Note : `_coup_scission` (`ia.py`) couvre le cas « tuile réelle » (bout ou
milieu de suite, #181) ; elle n'est plus limitée aux seuls bouts de suite,
mais reste étrangère aux jokers (dont la libération, bout ou milieu, passe
par `_liberations_possibles`).

## 8bis. Solveur de réarrangement global du plateau — niveau Expert (#186, #206)

> **Depuis #206, Expert joue avec un MODÈLE EXACT** (programmation linéaire
> en nombres entiers, `moteur/solveur_exact.py`, voir §8ter ci-dessous). La
> recherche arborescente décrite dans cette section (`moteur/solveur.py`)
> reste en place comme **repli** (import de `highspy`/`numpy` impossible,
> budget dépassé sans solution, ou erreur) et n'est PAS modifiée. Elle reste
> donc le comportement de secours exact décrit ici.

Depuis #186, Expert ne joue plus la chaîne de tactiques ci-dessus : il
appelle `moteur/solveur.py::resoudre_coup(etat, idx, budget_temps)`, qui
reconstruit librement tout le plateau (toutes les tuiles déjà posées
peuvent changer de combinaison, aucune ne peut disparaître) pour y poser le
plus grand nombre possible de tuiles du chevalet, jokers compris.

- **Principe** : on raisonne sur des compteurs par emplacement
  `(couleur, valeur)` (0 à 2 tuiles réelles possibles) et sur les 2 jokers
  du jeu, chacun marqué « obligatoire » s'il vient du plateau (doit
  impérativement finir dans une combinaison valide) ou « optionnel » s'il
  vient du chevalet (peut rester en main). Une recherche récursive
  mémoïsée choisit, à chaque étape, une combinaison (groupe ou suite)
  consommant un emplacement obligatoire restant — si aucune n'existe, la
  branche échoue, aucune tuile du plateau ne doit disparaître — puis, une
  fois tous les emplacements obligatoires traités, tente d'y ajouter le
  plus de tuiles optionnelles (chevalet) possible.
- **Départage** (plusieurs réarrangements posant le même nombre de
  tuiles) : d'abord le plus de points posés (valeur des tuiles du
  chevalet effectivement jouées), puis, à égalité, celui qui utilise le
  moins de jokers du chevalet — un joker reste une ressource précieuse
  même quand il ne change pas le nombre de tuiles posées ce tour-ci.
- **Mise initiale pas faite** : la RECHERCHE ignore alors le plateau (une
  règle du jeu interdit d'y toucher avant la mise initiale) et cherche la
  meilleure combinaison formable depuis la seule main, sous la contrainte
  des points posés ≥ `mise_initiale_min` — avec un repli en 2 passes documenté
  dans `solveur.py` quand le réarrangement qui pose le plus de tuiles
  n'atteint pas ce minimum (limite documentée : pas nécessairement
  l'optimum exact sous cette contrainte, voir docstring de
  `_meilleur_rearrangement`). **Le plateau existant (posé par d'autres
  joueurs) est intégralement gelé et reconduit tel quel dans le résultat**
  — bug corrigé par #187 : avant ce correctif, `resoudre_coup` l'omettait
  purement et simplement du plateau renvoyé, ce qui faisait disparaître ses
  tuiles (constaté en jeu : un groupe de 12 déjà posé effacé par Expert à
  sa première pose). Voir §4 (règle « le plateau ne perd jamais de tuile »)
  et les tests `test_expert_conserve_le_plateau_quand_la_mise_initiale_n_
  est_pas_faite` / `test_expert_conserve_plusieurs_combinaisons_du_
  plateau_sans_mise_initiale` (`tests/test_ia.py`).
- **Combinaisons gelées** (`_separer_combos_figees`) : une combinaison du
  plateau qui ne partage aucune couleur/valeur avec la main et ne contient
  aucun joker est reconduite telle quelle, hors recherche — borne
  nécessaire pour la combinatoire (principal facteur de ralentissement en
  milieu/fin de partie), au prix de réarrangements à travers une chaîne de
  combinaisons toutes étrangères à la main courante (cas non rencontré par
  les scénarios couverts par les tests).
- **Dégradation progressive sous budget de temps** (`BudgetDepasse`,
  `_resoudre`) : au-delà d'une dizaine de combinaisons pertinentes pour la
  main courante, l'arbre de recherche dépasse largement ce qu'un budget
  d'1 à 2 secondes permet de parcourir en entier (voir le rapport de
  clôture #186 pour l'analyse). Deux mesures en atténuent l'effet : les
  candidats de chaque emplacement sont essayés en priorité dans l'ordre
  décroissant de tuiles de main consommées (atteint le plafond optimiste,
  donc la coupure de branche, plus vite) ; et si le budget s'épuise EN
  COURS d'exploration, la meilleure branche déjà trouvée à ce niveau est
  conservée (réarrangement valide, pas nécessairement optimal) plutôt que
  tout perdre. `BudgetDepasse` n'est donc levée, et `jouer_niveau_expert`
  ne se replie sur le comportement d'Avancé (§8) pour ce tour, que si
  RIEN n'a été trouvé nulle part dans l'arbre avant expiration du budget
  (`BUDGET_TEMPS_EXPERT`, 1.5s par défaut, `moteur/ia.py`) — idem si le
  solveur conclut lui-même qu'aucun coup n'existe (filet de sécurité,
  coût négligeable).
- **Règle supprimée** (#186, suite de #184) : Expert ne refuse plus de
  poser quand un adversaire a ≤ 3 tuiles (ancien comportement, retiré —
  la campagne de #184 n'a montré aucun avantage mesurable à la prudence).
- **Recherche rendue « progressive » (#190, suite de #187)** : sur un
  plateau chargé (≈ 70 tuiles, ~19 combinaisons), la quasi-totalité des
  combinaisons se retrouvait « flexible » (`_separer_combos_figees` ne
  gèle que celles ne partageant AUCUNE couleur/valeur avec la main — avec
  seulement 4 couleurs, une main de 2-3 couleurs distinctes suffit à
  déflexibiliser presque tout le plateau), forçant ~45 emplacements
  obligatoires avec une quarantaine de candidats chacun. Dans cet arbre,
  le premier chemin DFS (candidats triés pour maximiser l'usage de la
  main, voir `_score_rapide`) tombait régulièrement sur une impasse
  (emplacement obligatoire sans aucun candidat compatible avec l'état
  réduit), forçant un retour en arrière coûteux — avant qu'AUCUN
  réarrangement complet n'ait jamais été trouvé nulle part dans l'arbre,
  le budget de production (1.5s) s'épuisait : repli systématique sur
  Avancé, perte de l'essentiel de la force d'Expert en milieu/fin de
  partie (mesuré sur `tests/donnees/cas_expert_budget_tour81.json`, avec
  le solveur d'avant #190 : `BudgetDepasse` toujours levée jusqu'à 2.5s de
  budget ; premier coup trouvé (3 tuiles) entre 2.5s et 3.0s — la mention
  « 3 tuiles en 20s » du cas de test d'origine (#187) ne reflétait qu'une
  marge large choisie pour le test à gros budget, pas le temps minimal
  réellement nécessaire). Cause : la plupart des emplacements obligatoires ne touchent
  en rien la main (aucun gain possible à les restructurer), mais la
  recherche les traitait comme n'importe quel autre, essayant toutes les
  régularisations possibles avant celle, triviale, qui reconduit la
  combinaison déjà posée. Correctif : chaque candidat généré
  (`_candidats_groupe`, `_candidats_suite`, et leurs variantes « joker »)
  porte désormais une signature `(type, couleur/valeur, taille)`
  (`_signatures_originales`) ; parmi les candidats ex-aequo sur
  `_score_rapide` (typiquement ceux qui n'utilisent aucune tuile de la
  main), celui qui reproduit une combinaison déjà posée avant ce tour est
  tenté EN PREMIER — réduit radicalement les impasses/retours en arrière
  sur les zones du plateau non concernées par la main, et donc le temps
  nécessaire pour trouver un premier réarrangement complet valide. Sur le
  cas de test ci-dessus, le solveur retrouve désormais le coup de 3
  tuiles (11 noir, 11 noir, 7 rouge) dès 56 ms de budget, et le confirme
  toujours au budget de production de 1.5s (aucun autre coup meilleur
  trouvé en continuant à chercher jusqu'à expiration — voir « anytime »
  ci-dessous) — au lieu de `BudgetDepasse` sans rien trouver jusqu'à 2.5s
  avant #190. Soit environ 45 à 50× plus vite pour atteindre un premier
  coup valide, pour une qualité de résultat au moins égale (mêmes 3
  tuiles). La recherche continue ensuite d'essayer de faire mieux jusqu'à
  expiration du budget (comportement « anytime » déjà en place via
  `BudgetDepasse`, désormais effectif dès les tout premiers appels plutôt
  qu'après plusieurs secondes — ce qui, sur un plateau chargé, consomme
  maintenant systématiquement tout le budget restant même après avoir
  trouvé un premier coup, puisque la recherche ne s'arrête que sur borne
  prouvée ou budget épuisé). Ne change jamais le résultat OPTIMAL trouvé
  avec un budget suffisant pour explorer exhaustivement, seulement la
  vitesse pour l'atteindre (et, en cas d'égalité stricte de la valeur de
  départage entre plusieurs réarrangements équivalents, lequel des deux
  est renvoyé). **Important, voir CHANGELOG-190 pour le détail** : ce gain
  ciblé ne se traduit PAS par une amélioration visible sur une campagne
  Avancé vs Expert avec des plateaux tirés au hasard (taux de repli
  d'Expert sur Avancé et temps moyen par tour, mesurés avant/après,
  inchangés ou légèrement dégradés à cette taille d'échantillon) : le
  correctif n'accélère que les nœuds à candidats ex-aequo sur
  `_score_rapide` (plateaux structurellement proches du cas visé —
  beaucoup de combinaisons non pertinentes pour la main), pas l'ensemble
  des situations ; et le comportement « anytime » fait désormais consommer
  tout le budget restant après un premier succès, ce qui tend à augmenter
  le temps moyen par tour plutôt qu'à le réduire.
- **Performance** : rapide en début de partie (plateau simple, < quelques
  ms) ; sur un plateau chargé, trouve désormais un premier coup jouable
  en quelques dizaines de ms (voir ci-dessus), puis continue de chercher
  mieux jusqu'à expiration du budget — le repli total sur Avancé par
  manque de temps, fréquent avant #190, devient rare — voir le rapport
  de clôture #190 (et #186 pour les mesures d'origine, temps moyen/
  maximal par tour).
- **Tests** : `tests/test_ia.py` — le solveur retrouve au moins aussi bien
  chaque scénario déjà couvert par Avancé (échange direct, détachement en
  bout, libérations combinées, groupe de 4, scission en milieu de suite,
  groupe de 4 avec joker retiré), plus le démantèlement complet (#175),
  un scénario de mise initiale, un scénario sans aucun coup possible, et
  le repli sur budget de temps dépassé. Un ancien test spécifique à Expert
  (`test_expert_ne_detache_pas_un_joker_en_bout_de_suite_par_scission`) a
  été remplacé : le solveur y trouve légitimement un meilleur coup qu'« 
  aucun » (voir `test_expert_trouve_un_groupe_pour_le_joker_en_bout_de_
  suite`).
- **Nouvelle stratégie de recherche (#194, suite de #190)** : #190
  n'accélérait que les nœuds à candidats ex-aequo sur `_score_rapide` — ne
  réglait pas le cas où le coup optimal exige d'enchaîner plusieurs
  échanges de jokers à travers des zones différentes du plateau. Cas réel
  (tour 57 de Bruno, `tests/donnees/cas_expert_bruno_tour57.json`) : Expert
  n'avait posé qu'UNE tuile en partie, alors que le solveur en trouve 3
  (joker d'un groupe de 4 remplacé par la tuile d'une suite voisine) — mais
  seulement avec 10s de budget ; rien à 1.5s/3s/6s. Deux changements,
  combinés (voir la docstring de `moteur/solveur.py` pour le détail
  technique) :
  1. **Recherche par paliers croissants** (`_meilleur_rearrangement`,
     `_Contexte.objectif`, `_seuil_atteint`) : au lieu de viser l'optimum
     en une seule passe, le solveur cherche d'abord « au moins 1 tuile
     posable », puis si trouvé « au moins 2 », etc. Chaque palier coupe la
     recherche dès qu'il est atteint n'importe où dans l'arbre — prouver
     un petit palier est beaucoup moins coûteux que prouver l'optimum
     exact d'un coup. Le dernier palier PROUVÉ atteignable avant expiration
     du budget est renvoyé (comportement anytime déjà présent depuis #186,
     affiné ici par palier plutôt que par nœud).
  2. **Ordre de visite des emplacements par VALEUR** (`_ordre_slot`) plutôt
     que par couleur : visiter toutes les valeurs d'une seule couleur avant
     de passer à la suivante forçait la recherche à épuiser un bloc de
     couleur combinatoire avant d'atteindre un groupe utile à la main d'une
     tout autre couleur ; visiter par valeur croissante atteint ce groupe
     dès que sa valeur revient, et le palier correspondant coupe alors la
     recherche immédiatement.

  Ni l'un ni l'autre ne change le résultat optimal trouvé avec un budget
  suffisant pour explorer exhaustivement — seulement la vitesse pour
  l'atteindre. Les pistes « zones indépendantes du plateau » et
  « élagage anticipé sur une borne globale » évoquées par l'issue n'ont
  **pas** été retenues : la mémoïsation par nœud (déjà en place depuis
  #186) et le découpage en combinaisons gelées/flexibles
  (`_separer_combos_figees`, #190) couvraient déjà l'essentiel de ce
  gain pour un coût d'implémentation moindre — voir le rapport de clôture
  #194 pour la mesure avant/après sur les deux cas de référence
  (`cas_expert_budget_tour81.json` et `cas_expert_bruno_tour57.json`) et sur
  des parties réelles.
  Budget de production (`BUDGET_TEMPS_EXPERT`) **inchangé à 1.5s** : les
  deux cas de référence sont désormais résolus dans ce budget.
  Tests ajoutés : `test_solveur_cascade_joker_trouve_trois_tuiles_avec_
  gros_budget` et `test_solveur_cascade_joker_trouve_un_coup_avec_budget_
  de_production` (`tests/test_ia.py`), sur le nouveau cas de référence
  `cas_expert_bruno_tour57.json`.
- **Préférer le coup le plus simple à nombre de tuiles posées égal (#199,
  suite de #194)** : aucun des critères de départage ci-dessus ne tenait
  compte de la PERTURBATION du plateau — parmi toutes les solutions posant
  le même nombre de tuiles, le solveur pouvait renvoyer n'importe laquelle,
  y compris une qui défait et recrée plusieurs combinaisons pour ne poser,
  au final, qu'une seule tuile de la main. Cas réel (David, tour 31,
  `tests/donnees/cas_expert_coup_simple_david_tour31.json`) : un 1 noir à
  poser, qu'il suffisait d'ajouter au groupe de 1 (rouge, bleu, jaune) déjà
  posé pour en faire un groupe de 4 couleurs en un seul geste — Expert
  avait pourtant joué un coup en 12 étapes de pas-à-pas, fragmentant ce
  groupe pour reformer une suite jaune ailleurs. Réglage `preferer_simple`
  (`solveur.PREFERER_SIMPLICITE`, activé par défaut, exposé en paramètre de
  `resoudre_coup`/`jouer_niveau_expert` pour comparer les deux versions par
  simulation) :
  - **Mesure de perturbation** `(tuiles_déplacées, combinaisons_modifiées)` :
    nulle si un candidat n'utilise aucune tuile du plateau, ou si les
    tuiles du plateau qu'il utilise reproduisent EXACTEMENT une combinaison
    déjà posée avant ce tour (il ne fait qu'ajouter des tuiles de la main à
    cette combinaison, ou la reconduire à l'identique) ; non nulle sinon
    (fragmente ou fusionne des combinaisons existantes). Deux tuiles de
    même aspect (même valeur, même couleur, ou deux jokers quelconques)
    sont interchangeables, comme pour le pas-à-pas (#197,
    `description_coup.py::_aspect`) — calculée directement sur les
    compteurs par emplacement de la recherche (`_perturbation_candidat`),
    sans jamais reconstruire le plateau concret. `mesurer_perturbation`
    (API publique de `solveur.py`) calcule la même mesure, mais sur un
    plateau avant/après concret — utilisée par les tests et par
    `scripts/comparer_niveaux_ia.py`, pas par la recherche elle-même.
  - **Nouvel ordre de départage** : nombre de tuiles posées, puis
    perturbation minimale, puis points posés, puis économie de jokers
    (`_meilleur_rearrangement`, `ctx.cle`).
  - **Tri des candidats** (`_resoudre`) : la perturbation REMPLACE, plutôt
    que compléter, le critère de signature d'origine (#190) — la signature
    (forme + taille seulement, pas la composition exacte) aurait sinon pu
    faire gagner, par coïncidence de forme, un candidat qui FRAGMENTE une
    combinaison d'origine sur celui qui l'ÉTEND proprement, exactement le
    bug observé. Mesuré sur un cas déjà difficile pour la recherche
    (`cas_expert_ia_261026172338_tour61.json`, cascade de jokers à travers
    tout le plateau, #194) : AJOUTER la perturbation en plus de la
    signature (sans même réordonner les deux) suffisait déjà à faire
    manquer, à budget identique, le palier que trouvait de justesse
    l'ancien comportement — ce cas est nativement sans la moindre marge
    pour un coût supplémentaire par nœud de recherche ; REMPLACER la
    signature (plutôt que l'additionner) évite ce coût.
  - **Limite documentée** : un candidat qui ne reconstitue qu'une FRACTION
    d'une combinaison d'origine (celle-ci ayant été fragmentée entre
    plusieurs candidats) compte sa propre perturbation indépendamment de
    l'autre fragment — peut compter deux combinaisons modifiées là où un
    œil humain n'en verrait qu'une scindée en deux, sans jamais fausser la
    distinction nulle/non-nulle qui est l'essentiel de ce critère.
  - **Tests** (`tests/test_ia.py`) : le cas de David (coup trouvé touchant
    au plus une combinaison, zéro tuile déplacée) ; un petit plateau
    fabriqué où deux solutions posent la même seule tuile et où la plus
    simple est retenue (démarche de réduction du cas réel documentée dans
    le rapport de clôture #199) ; non-régression sur tous les cas de
    référence existants (`cas_expert_budget_tour81.json`,
    `cas_expert_bruno_tour57.json`, `cas_expert_humain_*`,
    `cas_expert_ia_*`) — au budget de production pour tous sauf
    `cas_expert_ia_261026172338_tour61.json`, structurellement instable à
    ce budget (le solveur y trouve souvent RIEN en 1.5s, avec ou sans le
    nouveau critère, bien avant #199 déjà) et donc testé séparément à
    budget large (12s).
  - **Mesure** (campagne Avancé vs Expert, 10 donnes x 2 miroir, seed 42,
    voir rapport de clôture #199 pour le détail) : taux de victoire
    d'Expert 95.0 % ± 9.6 pt AVEC le critère contre 80.0 % ± 17.5 pt SANS
    (IC qui se recoupent largement, écart non démontrable à cet
    échantillon — comme pour #190/#194, aucune baisse, donc le critère
    reste activé par défaut) ; perturbation moyenne par coup d'Expert
    2.43 tuiles déplacées / 2.19 combinaisons modifiées AVEC, contre
    3.00 / 2.63 SANS (baisse mesurée, conforme à l'objectif) ; temps moyen
    par tour d'Expert comparable (204 ms AVEC contre 221 ms SANS, maximum
    ~1.5 s dans les deux cas) ; replis sur Avancé par dépassement de budget
    légèrement MOINDRES avec le critère (0.6 % contre 1.5 % des tours
    d'Expert) — aucune dégradation observée.

### 8ter. Modèle EXACT d'Expert — programmation linéaire en nombres entiers (issue #206, suite de #204)

Depuis #206, Expert joue avec un **modèle exact** (`moteur/solveur_exact.py`)
qui trouve TOUJOURS le coup posant le plus grand nombre de tuiles, y compris
les victoires immédiates et les recombinaisons multi-zones que la recherche
arborescente de §8bis ratait (vérifié par le solveur exact de #204 : Bruno
tour 57 — 4 tuiles au lieu de 3, en coupant une suite rouge ; Ines tour 85 —
victoire immédiate de 2 tuiles manquée). La recherche de §8bis reste le
**repli** (voir plus bas), inchangée.

- **Méthode** : programmation linéaire en nombres entiers (den Hertog &
  Hulshof, *The Computer Journal*, 2006), résolue par **HiGHS** via `highspy`
  (licence MIT) + `numpy` (BSD) — **sans** `cvxpy` ni `scipy` (la « voie (b) »
  du rapport de #204, ≈3× plus légère : ~+55 Mo et ~+65 ms au démarrage, au
  lieu de ~+150-200 Mo et ~+0,8 s). On énumère une fois pour toutes tous les
  ensembles valides possibles (suites de longueur 3 à 5, groupes de 3-4,
  jokers en remplacement ; ~1170 ensembles — les suites plus longues sont
  recomposées par le modèle à partir des courtes, borne reprise de la
  bibliothèque de #204). Une variable entière `x_s ∈ {0,1,2}` par ensemble ;
  pour chaque type de tuile `i`, contrainte de conservation
  `t_i ≤ Σ a_{s,i} x_s ≤ t_i + r_i` (toutes les tuiles du plateau restent
  posées, on n'utilise pas plus de tuiles qu'on n'en a).
- **Critères de départage** (lexicographiques, par passes successives figeant
  l'optimum entier de la précédente ; le nombre de tuiles posées reste
  TOUJOURS le premier critère) : (1) tuiles posées, (2) perturbation minimale
  du plateau (#199 : tuiles déplacées puis combinaisons modifiées, via des
  variables d'affectation `cover`), (3) points posés, (4) économie de jokers
  de la main. Le cas de David tour 31 reste joué en un seul geste (extension
  d'un groupe, 0 tuile déplacée).
- **Mise initiale pas faite** : le plateau est GELÉ (reconduit à l'identique),
  les ensembles ne sont formés que depuis la main, avec la contrainte
  `Σ points_s x_s ≥ mise_initiale_min`. Contrairement à la bibliothèque de
  #204 (qui réarrange le plateau au second temps), le modèle maison respecte
  la règle ; un test le vérifie.
- **Reproductibilité & budget** : HiGHS en `threads=1`, `random_seed=0`,
  sortie muette, limite de temps ferme = budget de production d'Expert
  (`BUDGET_TEMPS_EXPERT`, 1,5 s). Toute combinaison renvoyée est remise dans
  l'ordre (suites, jokers aux bons endroits) puis **revalidée par
  `valider_combinaison`**, et la conservation des tuiles du plateau est
  contrôlée (comme l'adaptateur de #204) — un résultat qui échouerait n'est
  jamais joué.
- **Repli, sans jamais bloquer le jeu ni lever** : `jouer_niveau_expert`
  tente le modèle exact ; en cas d'absence de `highspy`/`numpy`
  (`SolveurExactIndisponible`), de budget dépassé sans solution
  (`BudgetExactDepasse`) ou d'erreur, il se replie sur la recherche de §8bis
  (`solveur.py`, conservée telle quelle), puis sur Avancé. `UTILISER_SOLVEUR_
  EXACT` (dans `ia.py`) ou `jouer_niveau_expert(..., utiliser_exact=False)`
  fige Expert sur l'ancienne recherche (campagne « avant / après »,
  `scripts/comparer_niveaux_ia.py --sans-exact`).
- **Chiffres (#206)** : sur les 10 cas de référence, le modèle exact atteint
  `attendu_exact_tuiles` sur **10/10** (écart nul avec l'optimum), en **406 ms
  en moyenne, 916 ms au plus** (budget 1,5 s). Campagne Avancé vs Expert
  (20 donnes × 2 miroir, graine 206) : voir le rapport de clôture #206 pour
  les chiffres avant/après (taux de victoire, replis, temps par tour,
  perturbation, démarrage). Tests : `tests/test_solveur_exact_maison.py`
  (optimum sur tous les cas, accord avec `verif_solveur` et avec la
  bibliothèque de #204 si installée, mise initiale, départage, replis).

### 8bis-bis. Coups de grande envergure et bug de mesure côté humain (issue #200, suite de #194)

- **Contexte** : `scripts/analyser_coups_rates.py --joueur "Alain" --budget 10`
  (#193) signalait 10 tours où le joueur humain aurait posé plus de tuiles
  que le solveur n'en trouve même à budget généreux, dont deux écarts
  énormes (+11, +15 tuiles) enregistrés comme cas de référence
  (`tests/donnees/cas_expert_humain_*.json`, clé `attendu_min_tuiles`).
  L'hypothèse de départ était une incomplétude du solveur sur les grandes
  mains (plusieurs dizaines de tuiles posées d'un coup, chevalet presque
  plein).
- **Diagnostic (voir le rapport de clôture #200 pour le détail des mesures
  par budget 1.5/10/30/60/120s)** : sur les 3 cas enregistrés, le chevalet
  réellement capturé ne contenait que 7, 3 et 3 tuiles — `attendu_min_tuiles`
  (18, 7, 18) dépassait donc la taille du chevalet lui-même, une cible
  **physiquement impossible** pour n'importe quel solveur (on ne peut jamais
  poser plus de tuiles que n'en contient la main). Le solveur trouvait déjà,
  en quelques centaines de ms à ~2s, le maximum réel (= la main entière) sur
  les 3 cas : aucune incomplétude démontrée, la limite était dans la MESURE,
  pas dans l'algorithme.
- **Cause réelle** : `analyser_decision_complete`
  (`persistance/coups_rates.py`) comparait le solveur au champ
  `nb_tuiles_posees` du journal (`"nb_tuiles_jouees"` une fois extrait), lui-
  même `len(data["ids_tuiles"])` côté `ui/api.py::jeu_jouer_coup` — la
  longueur BRUTE de la liste d'ids envoyée par le client JS pour une pose
  humaine (`tuilesCeTour`, `ui/web/jeu.js`), qui peut dépasser la taille
  réelle du chevalet d'avant-coup (mécanisme exact non élucidé côté JS —
  pas nécessaire pour la correction : il suffit de ne plus se fier à ce
  compteur). `jouer_tour` lui-même n'est jamais en cause : il ne retire du
  chevalet que les ids qui y figurent réellement (`set()`), donc aucune
  tuile n'a jamais été dupliquée ou perdue en jeu réel. Le module calculait
  pourtant déjà, juste à côté, une mesure fiable et bornée par construction
  (`ids_tuiles_reelles`, différence entre le chevalet d'avant et celui
  d'après la pose — déjà utilisée par `detecter_reserves_joueur`) sans
  jamais s'en servir pour `nb_tuiles_reel`. **Corrigé** : `nb_tuiles_reel`
  utilise désormais `len(ids_tuiles_reelles)` pour une pose, plus jamais le
  champ brut — corrige à la source le calcul de `joueur_bat_solveur`/
  `pose_sous_optimale` et tout ce qui en dépend (résumé, enregistrement des
  cas de référence). Les 3 `attendu_min_tuiles` corrigés (7, 3, 3,
  désormais égaux à la taille du chevalet) ; les 3 fichiers restent des
  tests de non-régression légers (plus des cas « grande envergure »).
- **Les 3 cas `cas_expert_ia_*.json` (IA Expert d'avant #194, jugée par le
  solveur actuel), eux, étaient authentiques dès l'origine** (chevalet et
  `attendu_min_tuiles` cohérents) : `tour37` déjà trouvé au budget de
  production (1.5s) ; `tour59` manquait sa dernière tuile (6/7) ; `tour61`
  (cascade de jokers à travers 13 combinaisons, déjà documentée #194 comme
  à la limite du budget) ne trouvait souvent RIEN en 1.5s, jusqu'à 10s
  nécessaires pour les 4 tuiles attendues.
- **Optimisation appliquée (profilage `cProfile` sur ces deux cas)** :
  `_candidats_suite` dominait le temps (jusqu'à 40% du temps total) en
  reconstruisant l'intégralité des tokens de l'intervalle `[v1, v2]` depuis
  zéro pour CHAQUE largeur testée (coût quadratique dans la largeur de la
  fenêtre `_FENETRE_SUITE`, pour chaque ancre). Réécrit pour construire les
  tokens une seule fois par `v1`, en étendant `v2` d'une position à la fois
  (le nombre de jokers ne pouvant que croître avec la fenêtre, un
  dépassement du nombre de jokers disponibles ou deux jokers consécutifs le
  reste pour toute extension ultérieure — on arrête alors d'étendre ce `v1`
  au lieu de continuer à générer des candidats rejetés). Équivalence avec
  l'ancienne version vérifiée par comparaison exhaustive sur 20000 états
  aléatoires et par la suite de tests complète (187 tests, aucune
  régression) — ce n'est qu'une accélération, jamais un changement de
  résultat, donc valable à tous les niveaux et toutes tailles de main (les
  petites mains, déjà rapides, ne sont pas pénalisées).
- **Résultat mesuré** : `tour59` passe de ~3s à ~2s pour sa dernière tuile
  (reste juste AU-DESSUS du budget de production strict de 1.5s : parfois
  atteint de justesse, parfois non selon la charge machine — fiable à
  partir de ~2s) ; `tour61` passe de ~10s à ~5s (reste nettement hors de
  portée du budget de production). Le budget de production n'a PAS été
  augmenté (dernier recours, non justifié pour un gain qui resterait de
  toute façon loin de la cible pour `tour61`, et marginal pour `tour59`) —
  ces deux cas restent documentés comme hors de portée du budget de
  production de 1.5s, pas corrigés plus avant dans cette issue.
- **Pas de piste « grande main » retenue parmi celles envisagées** : sur
  les cas réels disponibles, geler moins de combinaisons pour une main
  large n'aurait rien changé (une main qui touche déjà les 4 couleurs gèle
  déjà 0 combinaison, voir `_separer_combos_figees` — c'est automatique, pas
  un réglage à ajuster) ; faire monter les paliers plus vite (bonds de 2+
  plutôt que +1) a été écarté : si le palier visé n'est pas atteignable, la
  recherche dégénère vers l'ancien comportement pré-#194 (preuve exhaustive,
  justement ce que #194 avait corrigé) ; chercher d'abord en partant du
  haut (toute la main, puis main-1...) a été écarté pour la même raison (le
  plafond optimiste est une borne, pas une garantie d'atteignabilité).
  Aucun cas réel de « grande main » authentiquement bloquée par le solveur
  n'a été trouvé pour justifier ces pistes plus risquées — voir le rapport
  de clôture #200 si un nouveau cas apparaît.
- **Tests** (`tests/test_ia.py`) : un test à gros budget (10s) et un test
  au budget de production (tolérance ×6, comme #190/#194) par cas de
  référence pour les 5 cas désormais atteints
  (`cas_expert_humain_261026172338_tour66.json`,
  `cas_expert_humain_261026174101_tour81.json`,
  `cas_expert_humain_261026213723_tour65.json`,
  `cas_expert_ia_261026172338_tour37.json`,
  `cas_expert_ia_261026172338_tour59.json`) ; un test à gros budget (12s)
  seul pour `cas_expert_ia_261026172338_tour61.json` (volontairement pas de
  test au budget de production pour ce cas, qui serait soit flaky soit
  trompeur avec une tolérance large).

## 9. Scripts de simulation IA vs IA (`scripts/`)

- `scripts/simulation_ia.py` : fait jouer 2 à 4 IA sur un match de `--manches`
  N manches (défaut 1), journalise les anomalies (coup invalide, blocage) et
  affiche, pour plusieurs manches, le résultat par manche et le vainqueur du
  match (plus haut score cumulé — issue #203). Utile pour un test de fumée
  ponctuel.
- `scripts/comparer_niveaux_ia.py` (#184, `--manches` N depuis #203) : compare
  deux niveaux d'IA sur un grand nombre de **matchs** de N manches à 2
  joueurs, pour savoir si l'un est réellement plus fort que l'autre. Avec
  plusieurs manches, le vainqueur d'un match est le joueur au plus haut score
  cumulé ; le rapport donne les résultats par match (victoires, score cumulé
  moyen) ET par manche (fins, durée, pénalités). Chaque donne (même
  distribution de tuiles) est jouée deux fois en miroir (places échangées),
  pour annuler l'effet du
  tirage ; avec la même graine, la campagne est reproductible à l'identique.
  Toujours via le moteur Python seul, jamais pywebview (§7). Usage :

  ```
  python scripts/comparer_niveaux_ia.py --niveau-a Avancé --niveau-b Expert
  python scripts/comparer_niveaux_ia.py --niveau-a Avancé --niveau-b Expert \
      --donnes 200 --seed 7 --max-tours 500
  ```

  Affiche : victoires/taux/marge d'erreur (IC 95 %) par niveau, nombre
  moyen de tuiles/points de pénalité du perdant, durée moyenne en tours,
  répartition des fins de partie (chevalet vidé / pioche épuisée / arrêtée
  par le garde-fou anti-blocage), temps de calcul moyen/maximal d'un
  tour de décision par niveau (repérage d'un emballement de la recherche de
  libération de joker), et, **depuis #187**, le nombre d'anomalies de
  conservation des tuiles : à chaque coup, les 106 tuiles de référence
  doivent être présentes exactement une fois (mains + plateau + pioche,
  voir `_anomalies_conservation`) ; un coup refusé par le garde-fou
  anti-disparition de `jouer_tour` (§4) est compté à part et clairement
  signalé dans le rapport (ne doit normalement jamais arriver, puisque
  l'IA revalide ses propres coups avant de les proposer). **Depuis #190**,
  le rapport affiche aussi le nombre de tours où Expert s'est replié sur
  Avancé (`jouer_un_tour` appelle `jouer_niveau_expert(..., on_repli=...)`
  directement pour le niveau Expert plutôt que le `jouer_ia` générique,
  afin de compter ces replis sans dupliquer la logique de décision), **en
  distinguant deux causes très différentes** : (1) le solveur dépasse son
  budget sans avoir rien trouvé nulle part dans l'arbre
  (`BudgetDepasse` — un problème de vitesse, la seule cause que
  l'accélération de #190 peut réduire) et (2) le solveur conclut
  légitimement qu'aucun réarrangement ne pose la moindre tuile (coup
  impossible — Avancé ne fera pas mieux, aucun rapport avec la vitesse de
  recherche). Les deux premières versions de ce compteur (avant la
  distinction) les confondaient, ce qui rendait la mesure peu
  interprétable : le taux de repli « toute cause » restait élevé et quasi
  inchangé avant/après #190 (la plupart des replis étaient déjà, avant
  tout correctif, de cause (2), sans rapport avec la vitesse) — voir
  CHANGELOG-190 pour les chiffres corrigés. Première
  campagne (#184, Avancé vs Expert avant le solveur de réarrangement
  global, 50 donnes) : écart non significatif à 95 % (53 % / 47 % sur
  100 parties). **#186** (Expert = solveur de réarrangement global,
  §8bis), à budget de production (1.5s/tour), 40 parties (2 lots) : écart
  significatif, Expert 80.0 % ± 12.4 pt, part de parties bloquées (pioche
  épuisée) 10 % (contre 29 % en #184) — mesure **invalidée a posteriori**
  par #187 (bug de disparition de tuiles non détecté à l'époque, faute du
  contrôle de conservation ci-dessus). **#187** (mêmes paramètres, rejoués
  après correctif) : Expert 72.5 % ± 13.8 pt (29/40, IC qui recouvre
  largement celui de #186 — écart non démontrable comme un effet du
  correctif avec cet échantillon), 0 anomalie de conservation des tuiles
  sur l'ensemble de la campagne — voir CHANGELOG-187 pour le détail
  complet. **#190** (solveur rendu progressif, mêmes paramètres) : voir
  CHANGELOG-190 pour les chiffres avant/après (taux de victoire, parties
  bloquées, replis d'Expert sur Avancé, temps par tour).
## 10. Journal de parties et bilan par niveau d'IA (issue #185)

- **Journal** (`persistance/journal.py`) : optionnel, activé par la clé
  `log_parties` de `config.json` (défaut `False` → aucun overhead, aucun
  fichier créé). Une fois activé, chaque coup transitant par `api.py`
  (pose/pioche/passe/annulation/tour IA) est ajouté au fichier
  `RACINE_DATA/logs_parties/partie_AAAAMMJJ_HHMMSS.json` de la partie en
  cours (au plus `MAX_FICHIERS` fichiers conservés). En-tête : `joueurs`
  (liste de `{nom, est_ia, niveau}`). Chaque action porte désormais
  `auteur_index` (qui a décidé), `action` (`"pose"|"pioche"|"passe"|
  "annulation"`), `nb_tuiles_posees`, `manche` (numéro de manche, issue #203),
  `termine` et `gagnant_index` — une partie dont la DERNIÈRE action n'a pas
  `termine: True` est abandonnée (ou encore en cours) et ignorée du bilan.
  Depuis #203, `termine` n'est vrai qu'à la fin du MATCH (pas d'une manche
  intermédiaire) et `gagnant_index` y désigne alors le vainqueur du match
  (plus haut score cumulé) ; `manche` est absent des journaux antérieurs (lu
  comme une manche unique). Les journaux écrits avant #185
  (joueurs = liste de noms, pas de `termine`) restent lisibles : ils sont
  juste exclus du bilan plutôt que de faire planter sa lecture.
- **Lecture/calcul** (`persistance/bilan.py`, pur, sans pywebview) :
  `charger_toutes_parties(dossier)` → parties terminées normalisées ;
  `calculer_bilan(parties, nom_joueur=None, depuis=None, jusqu=None)` →
  stats par niveau d'IA (victoires/défaites humain, taux, marge moyenne en
  tuiles restantes, tours moyens, part des tours IA pioche/passe et leur
  répartition début/milieu/fin de partie).
- **Script CLI** : `python scripts/bilan_parties.py [--joueur NOM]
  [--depuis AAAA-MM-JJ] [--jusqu AAAA-MM-JJ] [--dossier CHEMIN]`. Lit
  `RACINE_DATA/logs_parties` par défaut. Pour générer des journaux à
  analyser, activer `log_parties` dans les réglages (pas d'UI dédiée : clé à
  ajouter à la main dans `config.json`) puis jouer des parties jusqu'à leur
  terme.
- Tests : `tests/test_bilan.py` (lecture tolérante aux formats anciens/
  corrompus, dédoublonnage après annulation, calcul du bilan, intégration
  réelle `journal.logger_action` → `bilan`).

## 11. Analyse des « coups ratés » de l'IA (issue #188)

- **Objectif** : à partir d'un journal de partie (§10), dire si une IA qui a
  pioché ou passé aurait pu jouer — notamment avant sa mise initiale, où un
  joueur humain ne peut pas juger (il ne voit pas le chevalet de l'IA).
- **Calcul** (`persistance/coups_rates.py`, pur, sans pywebview) :
  `extraire_decisions_ia(data)` reconstitue, pour chaque décision de piocher/
  passer d'une IA, l'état exact affronté (chevalet + plateau enregistrés par
  l'action PRÉCÉDENTE dans le journal — la toute première action d'un
  journal est donc ignorée, faute d'état antérieur). La mise initiale d'un
  joueur est considérée faite s'il a déjà posé au moins une tuile plus tôt
  dans le même journal (impossible de poser avant de l'avoir atteinte en une
  fois). `analyser_decision(decision, budget_genereux=10.0,
  budget_production=1.5)` interroge alors le solveur d'Expert
  (`moteur/solveur.py::resoudre_coup`) sur cet état : s'il trouve un coup qui
  pose au moins une tuile, la décision est un « coup raté » (nombre de
  tuiles posables, et avant la mise initiale, points que l'ouverture aurait
  rapportés). Pour Expert uniquement, le solveur est interrogé une seconde
  fois avec le budget de production réel (1,5 s) afin de distinguer un coup
  raté par faiblesse de l'algorithme (le budget de production l'aurait
  trouvé aussi) d'un coup raté par manque de temps de calcul (seul le budget
  généreux le trouve — champ `budget_limite`). `calculer_resume(resultats)`
  agrège par niveau d'IA et par phase (avant/après mise initiale) ;
  `top_coups_rates(resultats, n=5)` retient les coups ratés les plus
  importants (tuiles ratées) pour examen manuel.
- **Script CLI** : `python scripts/analyser_coups_rates.py [FICHIER]
  [--tous] [--dossier CHEMIN] [--budget SECONDES]
  [--budget-production SECONDES] [--top N]`. Sans argument, analyse le
  journal le plus récent de `RACINE_DATA/logs_parties` ; `--tous` analyse
  tous les journaux du dossier. Un journal illisible/corrompu est signalé et
  ignoré sans interrompre l'analyse des autres.
- **Limite documentée, répétée à l'affichage** : le solveur gèle certaines
  combinaisons déjà posées sur le plateau pour limiter la combinatoire (voir
  docstring de `moteur/solveur.py`, `_separer_combos_figees`) — un coup non
  trouvé ne prouve pas qu'aucun coup n'existe. Les coups ratés détectés sont
  une **borne basse**, jamais une liste exhaustive. Autre limite : le
  journal ne conserve pas la configuration de la partie (`mise_initiale_min`
  notamment) — `config.MISE_INITIALE_MIN` (valeur par défaut) est utilisée
  pour toutes les parties rejouées.
- **Ne modifie jamais l'IA ni le moteur** : lecture pure des journaux +
  appels en lecture au solveur existant.
- Tests : `tests/test_coups_rates.py` (coup raté détecté après mise
  initiale, pioche justifiée sans aucun coup trouvable, coup raté avant la
  mise initiale avec points d'ouverture, journaux anciens/corrompus ignorés
  proprement, distinction budget de production/généreux pour Expert, résumé
  et classement des coups ratés les plus importants).

### 11bis. Fiabilisation de l'analyse (issue #193, suite de #188)

L'analyse ci-dessus (#188) ne regardait que les pioches/passes d'une IA, avec
un seul budget fixe, et ne vérifiait jamais le solveur lui-même. #193 lève
ces trois limites, toujours dans `persistance/coups_rates.py` (fonctions
ajoutées, celles de #188 ci-dessus restent inchangées à l'identique) :

- **Poses sous-optimales** (`extraire_toutes_decisions`,
  `analyser_decision_complete`) : pour une pose (IA ou humain), compare le
  nombre de tuiles RÉELLEMENT posées (différence chevalet avant/après dans le
  journal) au maximum trouvé par le solveur. Trois issues possibles selon le
  signe de l'écart : `pose_sous_optimale` (le solveur fait mieux),
  `joueur_bat_solveur` (le joueur a posé PLUS que le solveur même au budget
  généreux — n'arrive en pratique que pour un humain, jamais pour une IA qui
  ne peut pas dépasser le solveur qui l'a produite), ou rien (pose optimale).
  `extraire_decisions_ia_toutes` généralise l'extraction aux poses pour une
  IA ; `extraire_decisions_joueur(data, nom)` fait de même pour un joueur
  HUMAIN nommé (option `--joueur` du script, voir plus bas) — les deux
  gèrent une pose annulée puis rejouée (même numéro de tour réutilisé,
  dédoublonnage par dernière occurrence, comme `bilan.py`) en reconstituant
  l'état même à travers une entrée `"annulation"` du journal (qui porte
  elle aussi un instantané complet). `calculer_resume_complet` agrège par
  niveau/phase en distinguant `pioche_passe_ratees` et `poses_sous_optimales`
  (avec le total de tuiles manquantes) ; `top_coups_rates_complet` classe les
  deux catégories ensemble.
- **Budget nécessaire** (`budget_necessaire`, `repartition_budget_necessaire`,
  `BUDGETS_SERIE_DEFAUT = (1.5, 3, 6, 10, 20, 30)` secondes) : pour un coup
  raté/une pose sous-optimale déjà identifié, cherche le plus petit budget de
  la série qui retrouve le même nombre de tuiles — coûteux (relance le
  solveur par palier), donc calculé seulement à la demande
  (`--budget-mesure` du script), jamais en routine sur toute une campagne.
- **Budget par défaut généreux (10 s) et avertissement** : le budget généreux
  par défaut du script reste 10 s (inchangé depuis #188, déjà conforme) ;
  `scripts/analyser_coups_rates.py` affiche désormais un AVERTISSEMENT
  explicite si l'utilisateur choisit `--budget` < 10 s, et répète dans le
  rapport final qu'une décision « inconclusive » (budget épuisé sans rien
  trouver, `BudgetDepasse`) n'est PAS un coup non raté — le nombre réel de
  coups ratés reste incertain dans l'intervalle
  `[coups_rates ; coups_rates + inconclusifs]` tant que les inconclusifs ne
  sont pas tous tranchés. `--retenter-inconclusifs` relance ces décisions
  avec un budget plus grand (`--budget-inconclusifs`, défaut 30 s) sous une
  limite de durée TOTALE ferme pour toute la passe
  (`--limite-temps-inconclusifs`, défaut 300 s) — dépassée, elle s'arrête en
  signalant combien de décisions n'ont pas pu être retentées, plutôt que de
  risquer une durée illimitée.
- **Vérification croisée indépendante du solveur** (`moteur/verif_solveur.py`,
  nouveau module pur) : `max_tuiles_posables_exhaustif(plateau, chevalet)`
  est une seconde implémentation volontairement lente (force brute sans
  AUCUNE des optimisations de `solveur.py` : essaie tous les sous-ensembles
  du chevalet du plus grand au plus petit, et pour chacun toutes les façons
  de partitionner plateau+sous-ensemble en combinaisons valides), praticable
  uniquement sur de petites positions. `generer_position_aleatoire(rng, ...)`
  fabrique une position aléatoire reproductible (graine fixe) : un petit
  plateau (0 ou une combinaison de 3-4 tuiles) et une petite main (1 à 5-6
  tuiles, jokers rares). `scripts/verifier_solveur_exhaustif.py --nb --seed
  --budget-solveur` compare les deux sur `--nb` positions et signale tout
  écart (sans jamais corriger le solveur automatiquement — seulement un bug
  évident le justifierait, voir l'issue). **Résultat sur 300 positions,
  graine 193 : 0 écart, 0 inconclusive** (`tests/test_verif_solveur.py`
  fixe une seconde campagne, graine 193, 60 positions, même conclusion) — le
  solveur retrouve bien le maximum réel sur toutes les positions testées à
  cette échelle ; ceci ne prouve rien sur les plateaux de taille réelle
  (largement hors de portée de la recherche exhaustive), seulement sur le
  petit périmètre couvert par les positions générées.
- **Cas de référence connus, tests robustes au temps de calcul de la
  machine** : `tests/test_coups_rates_extensions.py` fabrique une décision
  de pose (une seule tuile jouée) à partir de
  `tests/donnees/cas_expert_bruno_tour57.json` (`attendu_min_tuiles: 3`) et
  vérifie que `analyser_decision_complete` la détecte comme
  `pose_sous_optimale` (2 tuiles manquantes) avec un budget très généreux
  (15 s, large marge), et — point important de l'issue — qu'un budget
  délibérément minuscule (0,05 s) la classe `inconclusif`, JAMAIS « pose
  optimale » : ne jamais sous-compter un coup raté faute de budget plutôt
  que de l'afficher comme incertain.
- **Analyse d'un joueur HUMAIN** (`--joueur "Nom"` du script,
  `extraire_decisions_joueur`, `resume_joueur_humain`) : même analyse que
  pour une IA, mais deux listes séparées — (a) `coups_peut_etre_rates` (pose
  partielle ou pioche/passe alors qu'un coup existait, à vérifier à la main,
  jamais une certitude pour un humain qui peut avoir d'autres raisons de
  jouer ainsi) et (b) `solveur_bat` (le joueur a posé PLUS de tuiles que le
  solveur même au budget généreux — ce sont les cas les plus utiles pour
  améliorer le solveur, voir l'avertissement sur le gel des combinaisons en
  tête de fichier). Quelques statistiques de style PUREMENT DESCRIPTIVES
  (`resume["style"]`) : part des poses au maximum du solveur, tuiles posées
  en moyenne par tour contre le maximum, part des pioches alors qu'un coup
  existait, nombre de jokers joués et nombre moyen de tours d'attente avant
  d'être joués. **Aucune conclusion stratégique à en tirer sur un petit
  échantillon de parties** (rappelé dans le rapport du script) : ces
  chiffres ne sont là que pour reconnaître un style, pas pour le juger.
- **Technique de la « réserve » jamais confondue avec un coup raté**
  (`detecter_reserves_joueur`) : parmi les poses partielles/pioches avec
  coup possible d'un joueur humain, une tuile que le solveur aurait posée
  mais que le joueur a gardée, puis effectivement posée au tour SUIVANT de
  ce même joueur (même partie), est une « réserve réussie » ; si elle n'est
  pas posée au tour suivant (en main ou plus posable), c'est une « réserve
  perdue » — les deux catégories sont retirées des listes (a)/(b) ci-dessus
  (`indices_a_exclure`), jamais comptées comme coup raté ni comme cas où le
  solveur est battu. `--verifier-reserve-evite-pioche` ajoute, pour chaque
  réserve réussie, un appel solveur supplémentaire (contre-factuel : sans
  la tuile réservée, le solveur trouve-t-il encore un coup au tour suivant ?)
  — coûteux, désactivé par défaut. **Limite assumée** : la détection ne
  regarde que le tour immédiatement SUIVANT du même joueur (pas une fenêtre
  plus large), et ne distingue pas une vraie réserve stratégique d'un oubli
  qui se résout par hasard au tour suivant — a posteriori les deux sont
  indiscernables (déjà noté dans l'issue).
- **Enregistrement de nouveaux cas de référence** (`--enregistrer-cas-reference`
  du script) : écrit les coups ratés/poses sous-optimales les plus
  importants (IA) ou les cas où le joueur bat le solveur (`--joueur`) au
  même format que `tests/donnees/cas_expert_*.json` (clé
  `attendu_min_tuiles` = résultat du solveur pour l'IA, nombre de tuiles
  réellement posées par le joueur pour un humain) — **n'écrase jamais un
  fichier existant** (vérifié avant écriture).
- **Non exécuté sur les vrais journaux de `RACINE_DATA/logs_parties`** :
  cette issue a été traitée dans un **worktree isolé** dont le périmètre
  autorisé ne contient AUCUN journal réel (`data/logs_parties` du worktree
  est vide) — les vrais journaux de parties jouées vivent hors de ce
  périmètre. Le script a été vérifié de bout en bout (tous les modes, y
  compris `--joueur`, `--budget-mesure`, `--retenter-inconclusifs`,
  `--enregistrer-cas-reference`) sur des journaux fabriqués à la main, mais
  **les chiffres réels sur les parties déjà jouées (point 6 de l'issue)
  restent à produire par Alain lui-même**, en relançant
  `python scripts/analyser_coups_rates.py --tous --budget 10` (et, pour un
  joueur humain, `--joueur "Alain"`) depuis une install courante du projet
  (pas ce worktree).
- Tests (en plus de `test_coups_rates.py`, #188, inchangé) :
  `tests/test_coups_rates_extensions.py` (poses sous-optimales, joueur bat
  le solveur, résumé étendu, budget nécessaire, détection de réserve
  réussie/perdue, cas de référence Bruno avec budget suffisant/insuffisant) ;
  `tests/test_verif_solveur.py` (recherche exhaustive sur cas unitaires +
  campagne aléatoire à graine fixe contre le solveur de production).

### 11ter. Décrire et mesurer la complexité du coup proposé (issue #196, suite de #193)

#188/#193 ci-dessus disaient COMBIEN de tuiles un coup raté/une pose
sous-optimale ratait, jamais QUEL coup le solveur proposait à la place —
impossible donc de juger à l'œil si le coup raté était à la portée d'un
humain. #196 réutilise `moteur/description_coup.py` (#189/#191, voir §12)
pour décrire ce coup en français et en mesurer la complexité, toujours dans
`persistance/coups_rates.py` (aucun changement au solveur, à l'IA ni au
moteur).

- **Description** (`decrire_coup(plateau_avant, plateau_apres, nom=None)`) :
  appelle `description_coup.decrire_coup_ia` (texte) et
  `description_coup.etapes_coup_ia` (étapes du rejeu pas à pas) à partir du
  plateau avant la décision (`decision["etat"]["plateau"]`) et du plateau
  proposé par le solveur (`coup["nouveau_plateau"]`). Retourne
  `{"texte", "etapes", "complexite"}`.
- **Complexité** (`_complexite_coup`) : nombre de combinaisons du plateau
  touchées (défaites + créées + modifiées), présence d'au moins un échange
  de joker, nombre d'étapes RÉELLES du rejeu (celles à titre vide, comme
  `nbChangementsPasAPas` côté front-end). Un coup est `"complexe"` s'il
  touche 3 combinaisons ou plus, ou déplace un joker ; sinon `"simple"`
  (point 3 de l'issue).
- **Artefact du solveur corrigé en amont, jamais dans le moteur**
  (`_relabeler_tuiles_indiscernables`) : `moteur/solveur.py` ne raisonne que
  sur des « emplacements » (couleur, valeur), jamais sur l'identifiant
  physique exact d'une tuile (voir sa docstring) — il peut donc proposer un
  plateau où deux tuiles déjà posées, strictement indiscernables (même
  valeur/couleur, non joker), ont échangé leurs identifiants entre deux
  combinaisons SANS aucun changement réel. `description_coup.py`, qui suit
  chaque tuile par son identifiant, y lisait un cycle de dépendance (sa
  propre docstring : « dépendance cyclique improbable ») qui cassait son tri
  causal et plantait (`KeyError` dans `etapes_coup_ia`) — jamais rencontré
  avec un coup réellement joué (déterministe), mais systématique avec
  certains coups PROPOSÉS par le solveur (cas réel : `cas_expert_
  bruno_tour57.json`, voir #193). `decrire_coup` relabellise une COPIE du
  plateau proposé avant d'appeler le moteur : toute combinaison d'après dont
  le contenu (multiset valeur/couleur/joker, en ignorant l'identifiant) est
  IDENTIQUE à une combinaison d'avant encore non appariée reprend
  exactement les identifiants de cette dernière — elle devient un pur no-op
  pour le moteur, ce qui élimine l'artefact sans jamais perdre
  d'information (deux tuiles indiscernables échangées sans effet visible
  restent, par définition, indiscernables pour le joueur). Ne touche JAMAIS
  une combinaison contenant une tuile posée depuis la main (changement
  réel, jamais un artefact).
- **Intégration dans `analyser_decision_complete`** : `description_solveur`
  (texte + étapes + complexité du coup proposé) est calculé pour toute
  décision signalée (`coup_rate`, `pose_sous_optimale` ou
  `joueur_bat_solveur`) où le solveur a effectivement proposé un plateau ;
  `None` sinon (y compris si le solveur ne trouve absolument aucun coup).
  Pour `joueur_bat_solveur` uniquement, `description_reel` décrit en plus,
  de la même façon, le coup RÉELLEMENT joué par le joueur à partir de
  `plateau_apres_reel` (nouveau champ de `extraire_toutes_decisions`, le
  plateau tel qu'enregistré par l'action de pose elle-même) — pour
  comparaison. `calculer_resume_complet` et `resume_joueur_humain` ajoutent
  une répartition `coups_simples`/`coups_complexes` par niveau d'IA et pour
  un joueur humain (point 3 de l'issue) : c'est cette répartition qui dit si
  les coups ratés sont à la portée d'un humain.
- **Script CLI** : chaque coup raté/pose sous-optimale affiché (top N,
  listes (a)/(b) de `--joueur`) affiche désormais le texte français, les
  étapes et la complexité du coup proposé (et, pour `--joueur`, du coup
  réellement joué en cas (b)) via `afficher_description_coup`. Nouvelle
  option `--tour N` (point 2 de l'issue) : détaille un tour précis (nom du
  joueur, tuiles posées en réalité vs proposées par le solveur, description
  complète) — EN PLUS de l'affichage habituel, jamais à la place
  (`_detailer_tour`/`afficher_detail_tour`).
- Tests : `tests/test_coups_rates_description.py` — coup raté simple
  (journal fabriqué + vrai solveur, classé `"simple"`) ; pose sous-optimale
  complexe avec échange de joker (solveur simulé, classée `"complexe"`) ;
  joueur bat le solveur (description du coup proposé ET du coup réellement
  joué, comparées) ; régression ciblée sur l'artefact de tuiles
  indiscernables (`_relabeler_tuiles_indiscernables`, y compris le cas où il
  ne doit JAMAIS toucher une tuile posée depuis la main) ; régression bout
  en bout sur le vrai cas de référence Bruno (`cas_expert_bruno_tour57.json`)
  qui plantait avant la correction.

### 11quater. Classement par taille et filtre par date (issue #198, suite de #196)

Le simple/complexe binaire de #196 ci-dessus regroupait à tort, dans
« complexe », un échange de joker trivial (visible à l'œil par un humain,
ex. un échange direct) ET un coup à une douzaine de combinaisons — rendant
impossible de dire si les coups ratés d'Expert sont à la portée d'un
humain. #198 affine cette mesure et ajoute un filtre par date, toujours
dans `persistance/coups_rates.py` (aucun changement au solveur, à l'IA ni
au moteur) :

- **Classement par taille** (`_taille_coup`, nouveau champ `complexite["taille"]`
  de `_complexite_coup`) : d'après `nb_combinaisons_touchees` (défaites +
  créées + modifiées, après ignoré des échanges de tuiles identiques —
  inchangé depuis #197) — `"petit"` (1 ou 2), `"moyen"` (3 à 5), `"grand"`
  (6 ou plus). L'indicateur `a_joker` (déplacement d'au moins un joker) et
  `nb_etapes` restent des champs séparés, orthogonaux à la taille (un coup
  peut être « petit avec joker », ex. un échange direct). L'ancien
  `categorie` (`"simple"`/`"complexe"`, #196) est **conservé tel quel** pour
  la continuité des mesures déjà produites — les deux coexistent dans
  `complexite`.
- **Agrégation par taille/joker** (`calculer_resume_complet`,
  `resume_joueur_humain`) : en plus de `coups_simples`/`coups_complexes`
  (conservés), chaque bucket par niveau/phase (IA) ou le résumé d'un joueur
  humain porte désormais `coups_petits`/`coups_moyens`/`coups_grands` et
  `coups_avec_joker`/`coups_sans_joker` (clés `petits`/`moyens`/`grands`/
  `avec_joker`/`sans_joker` dans `resume_joueur_humain["complexite"]`).
- **Script CLI** : `afficher_tableau_tailles` (mode IA) affiche, après le
  résumé habituel, un tableau toutes phases confondues — une ligne par
  niveau d'IA, colonnes petit/moyen/grand/joker/sans joker ; le mode
  `--joueur` affiche le même tableau (une seule ligne) dans
  `afficher_resume_joueur`. `afficher_description_coup` affiche désormais la
  taille de chaque coup détaillé (top N, `--tour`, listes (a)/(b)) en plus
  de l'ancienne catégorie, explicitement marquée « conservée ».
- **Filtre par date** (`filtrer_journaux_depuis(chemins, depuis)`, nouvelle
  option `--depuis AAAAMMJJ` du script) : ne garde, parmi les journaux
  `partie_AAAAMMJJ_HHMMSS.json` (voir `persistance/journal.py`), que ceux
  dont la date dans le NOM DE FICHIER (jamais le contenu — fonction pure,
  aucune lecture de fichier) est égale ou postérieure à `depuis` — permet
  de limiter l'analyse aux parties jouées avec la dernière version d'une
  IA plutôt qu'un mélange de versions successives. Un nom hors du format
  attendu est exclu par prudence (pas de date fiable à comparer). Le script
  affiche sur stderr le nombre de journaux retenus après filtrage ; le
  filtre s'applique avant le choix du « plus récent » par défaut (donc le
  plus récent PARMI les journaux retenus), mais jamais à un fichier unique
  passé explicitement en argument.
- **Accords en français et suppression des pronoms genrés** : voir §12,
  nouvelle sous-section 12ter — modifications dans
  `moteur/description_coup.py`, pas dans ce module.
- Tests : `tests/test_coups_rates_description.py` (ajoutés à la suite de
  ceux de #196) — un coup petit sans joker, un petit AVEC joker (échange
  direct), un moyen sans joker (démantèlement en 3), un grand avec joker
  (reprise du cas Bruno/Expert en chaîne de §12) ; bout en bout,
  `calculer_resume_complet` répartit deux décisions résolues par un faux
  solveur dans les bons compteurs petit/moyen + simple/complexe conservés.
  `tests/test_coups_rates_filtre_date.py` (nouveau fichier) — sans
  `depuis` renvoie tout inchangé ; `depuis` garde la date exacte et les
  plus récentes, exclut tout ce qui est plus ancien, garde tout si `depuis`
  précède la plus ancienne ; un nom hors format est exclu dès qu'un filtre
  est demandé.

### 11quinquies. Compter les tuiles RÉELLEMENT posées depuis la main, pas les tuiles déplacées (issue #201, suite de #193)

**Bug corrigé** : pour un coup HUMAIN, `data["ids_tuiles"]` envoyé par
`jeu.js` (variable `tuilesCeTour`, voir `jeu.js:prendreTuileTapis`) mélange
les tuiles venues de la main ET celles du plateau déplacées pendant le
tour (le jeu s'en sert pour colorer « tuile du tapis déplacée ce tour »,
pas pour compter ce qui a été posé). Avant #201, `ui/api.py:jeu_jouer_coup`
journalisait `nb_tuiles_posees = len(data["ids_tuiles"])` : pour un coup
humain qui déplace des tuiles déjà posées, ce compte était donc GONFLÉ par
rapport au nombre réel de tuiles sorties de la main — faussant, dans
`persistance/coups_rates.py`, les listes « solveur battu », les poses
sous-optimales (masquées par l'inflation) et les statistiques de style
d'`--joueur` (cas réel observé : `posé 18, solveur 7`, alors que la
description du coup montrait 4 tuiles réellement sorties de la main). Pour
une IA, `ids_tuiles` vient du solveur (`moteur/solveur.py::resoudre_coup`,
qui le nomme explicitement `ids_main`) et ne contient JAMAIS de tuile
déplacée : son compte n'a jamais été affecté.

- **Analyse corrigée à la source** (`extraire_toutes_decisions`, qui
  alimente TOUTE l'analyse de #193/#196/#198 ci-dessus, IA comme humain) :
  `nb_tuiles_jouees` n'est plus lu depuis le champ `nb_tuiles_posees` du
  journal, mais calculé comme `len(ids_tuiles_reelles)` — la différence
  entre la main d'avant et la main d'après le coup, déjà calculée pour
  `ids_tuiles_reelles` (utilisée par `detecter_reserves_joueur`). Ce calcul
  corrige AUSSI les journaux ANCIENS (écrits avant la correction du journal
  ci-dessous) : il ne dépend jamais du champ `nb_tuiles_posees`/
  `nb_tuiles_deplacees` du journal, seulement des deux instantanés de main
  déjà présents dans tout journal post-#185. Une seule fonction corrigée
  répare donc, en cascade, `analyser_decision_complete` (détection
  `joueur_bat_solveur`/`pose_sous_optimale`), `resume_joueur_humain`
  (statistiques de style), `detecter_reserves_joueur`, et
  `_enregistrer_cas_reference` (`attendu_min_tuiles` des cas humains).
- **Journal corrigé** (`ui/api.py:jeu_jouer_coup`, `persistance/journal.py`)
  : capture la main du joueur AVANT d'appeler `jouer_tour` (qui la mute en
  place), puis journalise dans `nb_tuiles_posees` le nombre de tuiles de
  `ids_tuiles` réellement présentes dans cette main d'avant, et dans la
  nouvelle clé `nb_tuiles_deplacees` le reste (tuiles du plateau déplacées
  sans venir de la main). `logger_action` accepte le nouveau paramètre
  `nb_tuiles_deplacees` (défaut 0, rétrocompatible) ; un journal écrit avant
  #201 n'a simplement pas cette clé (lue comme 0 par convention, mais en
  pratique AUCUN lecteur ne s'appuie sur elle — voir point suivant).
  `ui/api.py:jeu_ia_jouer` (coup d'IA) reste inchangé : son calcul
  (`len(res_ia["ids_tuiles"])`) était déjà correct.
- **Autres lecteurs de `nb_tuiles_posees` vérifiés** : `persistance/bilan.py
  :extraire_partie` recopie ce champ dans `decisions[i]["nb_tuiles_posees"]`
  mais ne s'en sert JAMAIS dans `calculer_bilan`/`_finaliser` (seuls
  `action`/`moment` sont lus) — aucune adaptation nécessaire. Les deux
  vérifications `(a.get("nb_tuiles_posees") or 0) > 0` de
  `extraire_decisions_ia`/`extraire_toutes_decisions` (détection de
  « mise initiale déjà faite ») restent correctes : une pose RÉUSSIE
  implique toujours que `jouer_tour` a validé la mise initiale (ou qu'elle
  l'était déjà), donc `ids_tuiles` — gonflé ou non — y est toujours non vide ;
  ces vérifications ne portent que sur la présence d'une pose antérieure,
  jamais sur son nombre exact.
- **Usage de `ids_tuiles` par le moteur, VÉRIFIÉ, NON MODIFIÉ** (point 3 de
  l'issue — `moteur/partie.py`) : `jouer_tour(etat, ids_tuiles_posees,
  nouveau_plateau)` ne fait AUCUNE hypothèse sur l'origine des ids reçus.
  Étape 4 (retrait du chevalet) filtre `chevalet` par appartenance à
  `ids_posees` : un id qui n'est pas dans le chevalet (tuile déplacée, pas
  posée) n'y correspond simplement à rien et ne cause aucun effet. Étape 3
  (`_points_tuiles_posees(plateau, ids_posees)`, calcul des points de la
  MISE INITIALE) additionne la valeur de CHAQUE id de `ids_posees` trouvé
  dans une combinaison valide du nouveau plateau — **y compris un id de
  tuile DÉPLACÉE, pas posée depuis la main** : si un joueur n'ayant pas
  encore fait sa mise initiale rearrange des combinaisons déjà présentes
  sur le plateau (posées par d'autres joueurs lors de tours précédents) en
  y ajoutant peu de valeur depuis sa main, les points des tuiles déplacées
  s'additionnent À TORT à ceux de ses propres tuiles pour juger s'il
  atteint le minimum requis. **Signalé ici comme un bug potentiel de la
  RÈGLE DE MISE INITIALE** (distinct du bug de journalisation corrigé
  ci-dessus), mais PAS corrigé dans cette issue : son périmètre est
  volontairement limité à l'analyse/au journal (voir consigne de l'issue —
  « ne rien modifier au comportement du jeu sauf bug évident ») ; il
  nécessite d'exposer au moteur une distinction main/plateau que
  `jeu_jouer_coup` calcule désormais (`ids_main_avant`, voir ci-dessus) mais
  ne transmet pas à `jouer_tour`, qui continue de recevoir la liste brute
  `ids_tuiles` — à traiter dans une future issue dédiée si Alain le
  confirme. En pratique rare : il faut qu'un joueur n'ayant pas encore posé
  choisisse de manipuler le plateau plutôt que de simplement poser depuis
  sa main.
- **Cas de référence humains régénérables** (`--ecraser` du script,
  `_enregistrer_cas_reference(..., ecraser=False)`) : le comportement par
  défaut (ne jamais écraser un fichier `cas_expert_*.json` existant) est
  conservé ; la nouvelle option `--ecraser` lève ce garde-fou pour
  régénérer `tests/donnees/cas_expert_humain_*.json` (dont les trois
  fichiers déjà présents portent l'ancien `attendu_min_tuiles` gonflé,
  jamais vérifié par un test automatisé — voir `test_ia.py`, liste
  paramétrée de non-régression #199, qui n'utilise que `etat`/`idx` de ces
  fichiers, jamais leur `attendu_min_tuiles`). Marche à suivre pour Alain
  (hors de ce worktree, sur les vrais journaux de `RACINE_DATA/logs_parties`
  — absents de ce worktree isolé, voir note de #193 ci-dessus) :
  `python scripts/analyser_coups_rates.py --tous --joueur "Alain"
  --enregistrer-cas-reference --ecraser`. Le solveur n'est jamais modifié.
- Tests : `tests/test_coups_rates_tuiles_main.py` (nouveau fichier) —
  reproduit le cas réel (journal `nb_tuiles_posees=18`, main qui ne perd
  que 4 tuiles) et vérifie que l'analyse compte 4 et classe le coup en
  `pose_sous_optimale` (jamais `joueur_bat_solveur`, contrairement à ce que
  le champ gonflé aurait produit) ; un journal ANCIEN sans `nb_tuiles_posees`
  ni `nb_tuiles_deplacees` reste lisible ; un journal d'IA cohérent où le
  nombre recalculé coïncide avec le champ du journal.
  `tests/test_api_journal.py` (nouveau fichier) — appelle réellement
  `Api.jeu_jouer_coup` sur un coup qui fusionne deux combinaisons déjà
  posées (3 tuiles déplacées) en y ajoutant 1 tuile de la main, et vérifie
  que le journal écrit porte `nb_tuiles_posees=1`, `nb_tuiles_deplacees=3`.

### 11sexies. Relier les fichiers d'une partie reprise et enregistrer la mise initiale (issue #202, suite de #201)

- **Problème corrigé** : à la fermeture puis réouverture du jeu, une partie
  reprise repart sur un NOUVEAU fichier de journal (le cache mémoire de
  `persistance/journal.py` est perdu au redémarrage). L'ancienne analyse
  déduisait la mise initiale d'un joueur de la seule présence d'une pose
  antérieure **dans le même fichier** : sur un fichier de reprise, elle croyait
  donc à tort la mise initiale non faite, ce qui bride le solveur (avant la
  mise, il ne peut pas utiliser le plateau) et fausse le résultat. Mesuré sur
  trois cas réels où le solveur, supposé avant la mise, trouvait 0/0/6 tuiles
  et concluait à tort « le joueur bat le solveur » ; supposé après la mise, il
  trouve 2/3/7 (autant ou plus que le joueur) — aucun n'était un vrai cas de
  solveur battu.
- **Journal** (`persistance/journal.py`, `_mises_initiales`) : chaque action
  porte désormais `mises_initiales`, liste de booléens alignée sur `joueurs`
  (état « mise initiale faite » de chaque joueur au moment de l'action,
  d'après l'état du jeu). Rétrocompatible : les anciens journaux n'ont pas
  cette clé.
- **Regroupement** (`persistance/parties_liees.py`, nouveau module pur) :
  `grouper_journaux(journaux)` regroupe les fichiers d'une même partie par
  `partie_id` (en-tête — conservé à la reprise, l'état restauré gardant le
  même `id`), avec repli par mêmes joueurs + continuité des numéros de tour
  si l'identifiant est absent/change ; `fusionner_groupe`/`fusionner_journaux`
  concatènent les `actions` dans l'ordre chronologique en une seule suite.
  L'état de départ de la première action d'un fichier de reprise est alors
  l'état enregistré à la dernière action du fichier précédent (reconstitution
  inchangée dans `coups_rates.py`/`bilan.py`). `fusionner_groupe` renvoie
  aussi `debut_present` (faux si le plus ancien fichier commence au-delà du
  tour `SEUIL_DEBUT_PARTIE=2`, c.-à-d. en plein milieu de partie).
- **Déduction de la mise initiale** (`coups_rates.py`,
  `_mise_initiale_avant`) : si l'action précédente porte `mises_initiales`
  (journal #202+), elle est lue directement ; sinon repli #188 (pose
  antérieure dans la suite d'actions FUSIONNÉE). **Historique manquant**
  (point 3) : quand le début de partie est absent (`debut_present=False`) et
  qu'aucune pose n'est observée, l'état est INCONNU — on ne suppose JAMAIS
  « non faite » : la décision reçoit `moment="inconnu"` et
  `mise_initiale_inconnue=True`, est exclue du calcul (le solveur n'est pas
  interrogé) et comptée à part dans le résumé (`resume[niveau]["inconnu"]`).
- **Bilan** (`bilan.py`, `charger_toutes_parties`) : regroupe les fichiers
  d'une partie reprise et fusionne leurs actions avant `extraire_partie` — la
  partie est comptée UNE SEULE FOIS, avec son nombre de tours réel et toutes
  les décisions ; le premier fichier n'est plus pris pour une partie
  abandonnée (seule la dernière action de la partie fusionnée décide si elle
  est terminée).
- **Scripts** : `scripts/analyser_coups_rates.py` (IA et `--joueur`) regroupe
  désormais les fichiers par partie avant analyse (`_charger_parties`,
  `_decisions_ia_par_cle`) et affiche le décompte des décisions « mise
  initiale inconnue » ; `scripts/bilan_parties.py` en bénéficie via
  `charger_toutes_parties`. Nouveau `scripts/verifier_cas_reference.py`
  (point 5) : vérifie le drapeau `mise_initiale_faite` figé dans
  `tests/donnees/cas_expert_*.json`, recalcule le drapeau correct à partir des
  journaux d'origine regroupés (`--dossier`) et corrige les cas faux
  (`--ecraser`). Les 9 cas existants portent déjà `mise_initiale_faite=True`
  pour le joueur concerné (aucun faux dans le sens dangereux False→True). La
  régénération des cas eux-mêmes reste possible via
  `analyser_coups_rates.py --enregistrer-cas-reference --ecraser` (qui utilise
  désormais l'analyse regroupée).
- **Ne modifie jamais l'IA ni le moteur** : journal enrichi + lecture/analyse.
- Tests : `tests/test_journal_mise_initiale.py` (nouveau champ `mises_initiales`
  dans le journal et via `ui/api.py`), `tests/test_coups_rates_parties_liees.py`
  (regroupement par `partie_id` et repli par continuité ; deux fichiers reliés
  classant le second « après la mise » alors que seul il le classerait « avant »
  — avec et sans la clé ; solveur recevant le bon drapeau bout en bout ;
  historique manquant exclu et compté à part), et dans `tests/test_bilan.py`
  (une partie reprise en deux fichiers comptée une seule fois, premier fichier
  non pris pour une partie abandonnée).

## 12. Rendre lisible un coup complexe de l'IA (issue #189, puis #191)

Depuis le solveur de réarrangement global (#186), un coup de l'IA peut
défaire et recomposer plusieurs combinaisons du plateau en un seul tour. Le
rejeu animé existant (tuile par tuile, #144/#149) reste le comportement PAR
DÉFAUT du bouton « ▶ Dernier coup joué par... », inchangé pour tous les
coups — les aides ci-dessous sont des options accessibles à côté de ce
bouton, jamais imposées, et ne modifient jamais l'état de la partie.

L'issue #191 a entièrement revu le moteur `description_coup.py` introduit par
#189 : le classement par simple comparaison avant/après donnait des étapes
incohérentes (une même tuile visible deux fois à la fois, des phrases avec
des tournures de message automatique). Le nouveau moteur suit **chaque
tuile individuellement, par son identifiant**, de sa position d'avant à sa
position d'après.

- **Moteur commun** (`_construire_operations`, privé, partagé par les deux
  fonctions publiques) : pour chaque combinaison d'avant, la destination
  d'après qui reçoit une **majorité stricte** (`> moitié`) de ses tuiles est
  sa continuation ("update" : elle garde son identité, peut à la fois perdre
  et gagner des tuiles en un seul changement, ex. joker remplacé par une
  tuile réelle). Sans majorité claire, elle se dissout et chacune de ses
  tuiles est libérée par une opération **"retrait"** distincte, regroupée
  par destination (jamais tout d'un coup si plusieurs destinations se
  partagent ses tuiles — c'est ce qui permet d'afficher un état
  "provisoire" entre deux retraits). Une combinaison d'après sans
  continuation est "create" (entièrement recomposée depuis le cadre). Les
  opérations sont ensuite triées par un **tri topologique causal** (une
  tuile doit être libérée avant d'être réutilisée) qui **privilégie les
  échanges de jokers dès qu'ils sont possibles** (issue #191, point 3bis) —
  priorité aux opérations qui libèrent/consomment un joker, puis
  update > create > retrait, puis ordre stable. Deux combinaisons
  distinctes qui porteraient le même nom (ex. deux « groupe de 11 » à des
  moments différents du coup) sont désambiguïsées en listant leurs couleurs
  (`_desc_fabrique`, en comptant les identités distinctes — pas les simples
  libellés — pour ne pas confondre une combinaison avec sa propre
  continuation).
- **Résumé écrit** (`decrire_coup_ia(plateau_avant, plateau_apres, nom=None)`)
  : renvoie `{"texte", "tuiles_posees", "nb_combinaisons_defaites",
  "nb_combinaisons_creees", "nb_combinaisons_modifiees", "jokers_deplaces"}`.
  `nom` (le nom du joueur IA, passé par `api.py`) permet de commencer par
  « <Nom> a posé... » plutôt que par « A posé... » (sujet omis). Depuis
  #198 (voir §12ter), AUCUNE phrase du résumé n'utilise de pronom
  « il »/« elle » pour désigner le joueur. Un coup simple
  (une seule combinaison touchée, aucun joker déplacé) reste **une seule
  phrase** ; au-delà, plusieurs phrases courtes en français naturel, avec
  contractions (« du groupe de 3 », « au groupe de 11 » — jamais « de le »/
  « à le », cf. `_contracter`).
- **Rejeu pas-à-pas** (`etapes_coup_ia`, PRIORITÉ de l'issue) : une suite
  d'états où chaque tuile n'est qu'à un seul endroit à la fois — sur le
  plateau (`"plateau"`, même format qu'avant) ou dans le cadre **« tuiles à
  placer »** (`"cadre"` : `[{"tuile": dict, "origine": "main"|"plateau"}]`).
  Structure : un écran **« Départ »** (titre dédié, plateau d'avant, cadre
  rempli des tuiles de la main) ; si des jokers changent de combinaison, un
  écran **« Les jokers »** juste après (vue d'ensemble : d'où chaque joker
  vient, par quelle tuile il est remplacé et d'où elle vient, où il finit —
  ne change rien à l'écran, titre dédié) ; puis une étape par opération
  (titre vide), chacune avec `"provisoires"` (index dans `"plateau"` des
  combinaisons mi-démantelées, temporairement invalides) et `"surbrillance"`
  (ids des tuiles juste posées/libérées à cette étape, pour réutiliser la
  surbrillance existante côté front). La toute dernière étape correspond
  exactement au plateau d'après, cadre vide. `etapes_coup_ia([], [])` (ou
  tout coup sans la moindre tuile posée) renvoie `[]`.
- **Seuil d'affichage du bouton** : ce n'est PLUS `coup.etapes.length >= 2`
  (les écrans "Départ"/"Les jokers" existent même pour un coup simple) mais
  le nombre d'étapes à **titre vide** (changements réels) — voir
  `nbChangementsPasAPas()` côté JS, dupliquant la même logique que `simple`
  côté Python dans `decrire_coup_ia`.
- **Calcul unique côté `api.py`** : `jeu_ia_jouer` appelle les deux fonctions
  ci-dessus immédiatement après une pose (avec `nom=etat["joueurs"][idx]
  ["nom"]`) et stocke `resume`/`etapes` dans `etat["dernier_coup_ia"]` —
  aucun aller-retour JS → Python supplémentaire.
- **Front-end** (`jeu.js`/`jeu.html`/`jeu.css`) :
  - `#resume-coup-ia` affiche `coup.resume` tel quel (inchangé depuis #189).
  - `#zone-cadre-pas-a-pas`/`#cadre-tuiles-pas-a-pas` (NOUVEAU, au-dessus de
    l'aperçu du plateau dans `#overlay-pas-a-pas`) : rendu par
    `rendreCadrePasAPas`, une tuile par entrée de `etape.cadre`, pourtour
    **vert `.ce-tour`** (tuile de la main) ou **orange `.deplacee-tapis`**
    (tuile libérée du plateau) — mêmes classes que la légende existante
    (`#legende-couleurs`), aucune nouvelle couleur introduite. Cadre vide
    affiché comme tel (`.cadre-vide`, texte "vide").
  - `#soustitre-etape-pas-a-pas` affiche `etape.titre` ("Départ"/"Les
    jokers"/vide pour un changement normal).
  - `rendreApercuPlateauPasAPas` ajoute `.combi-provisoire` (liseré ambre
    pointillé + mention, visuellement distinct de `.combi-invalide` qui
    reste réservée aux vraies erreurs du joueur sur le vrai tapis) sur les
    combinaisons listées dans `etape.provisoires`, et `.tuile-ia-highlight`
    (surbrillance déjà existante) sur les tuiles listées dans
    `etape.surbrillance`.
  - `#btn-pas-a-pas-coup-ia` démasqué par `rafraichirBoutonRejouerIA()`
    seulement si `nbChangementsPasAPas(coup.etapes) >= 2`.
  - `#overlay-pas-a-pas` reste une carte modale en LECTURE SEULE, totalement
    indépendante de `rejouerDernierCoupIA` (bouton de rejeu animé,
    inchangé) ; navigation Suivant/Précédent par index local
    (`indexEtapePasAPas`), « Quitter » referme sans effet sur la partie.
  - **Bascule Avant/Après (point 2 de l'issue #189) : toujours NON
    implémentée**, hors périmètre de #191 également.
- Tests : `tests/test_description_coup.py` — contractions (`_contracter`,
  du/au/des/aux, groupe/suite) ; coups simples (extension de suite, groupe
  créé depuis la main, aucun changement) ; joker récupéré puis rejoué dans
  un nouveau groupe (avec vérification explicite que le joker transite par
  le cadre AVANT d'être repris) ; démantèlement complet d'un groupe en 3
  nouvelles combinaisons (désambiguïsation par couleurs, état provisoire
  visible) ; le cas Bruno (3 bleu/11 bleu/11 noir) décrit dans l'issue, texte
  du résumé comparé mot pour mot à l'exemple de l'issue ; le coup en chaîne
  Bruno/Expert à 5 combinaisons d'avant (jokers + double suite coupée en
  deux), avec vérification tuile par tuile de l'ordre causal (le 11 jaune
  sort de la suite jaune avant de remplacer le joker, etc.) et que le 11
  jaune est bien présenté comme venant du plateau, jamais de la main. Un
  helper `_verifier_invariants` commun vérifie sur chaque scénario : aucune
  tuile à deux endroits à aucune étape, pas d'étape sans changement visible,
  cadre vide et plateau identique à `plateau_apres` à la toute dernière
  étape. `tests/test_playwright_pas_a_pas.py` (nécessite `pip install
  playwright` + `playwright install chromium`, absent de requirements.txt
  — sauté proprement sinon) : charge `jeu.html` directement (jamais la
  vraie app pywebview), injecte un `dernier_coup_ia` fictif et pilote les
  boutons réels ; vérifie le cadre qui se vide progressivement avec les
  bonnes couleurs de pourtour, l'absence de tuile commune cadre/plateau à
  chaque étape, et que « Quitter » ne modifie rien.

### 12bis. Tuiles identiques interchangeables (issue #197)

Le jeu contient deux exemplaires de chaque tuile (même valeur/couleur). Le
suivi tuile-par-tuile de `description_coup.py` (§12), qui identifie chaque
tuile par son identifiant individuel, prenait littéralement « la tuile A
sort, la tuile B entre » comme un changement réel même quand A et B sont
visuellement indiscernables — bruit supplémentaire dans le pas-à-pas, et
**plantage réel en jeu** (`KeyError` sur `del cadre[...]`, une tuile libérée
par un échange annulé n'étant jamais déposée dans le cadre avant d'être
consommée ailleurs).

- **Séparation bookkeeping/affichage** (`_retrait_ajout_bruts` +
  `_annuler_par_aspect`, dans `_construire_operations`) : pour chaque
  continuation ("update"), les tuiles RÉELLEMENT parties/arrivées
  (`retirees`/`ajoutees`, par identifiant — toujours utilisées pour le
  cadre et le graphe de dépendances, donc JAMAIS d'exception) sont
  distinctes des tuiles À AFFICHER (`retirees_vues`/`ajoutees_vues` —
  réduites en annulant deux à deux une tuile partie et une tuile arrivée de
  même aspect, `_aspect()` : même valeur/couleur, ou n'importe quel joker).
  Une opération dont les deux listes "vues" sont vides est ajoutée au
  cadre/plateau comme d'habitude mais n'affiche AUCUNE étape
  (`etapes_coup_ia`) et ne compte dans aucun total (`decrire_coup_ia`,
  `_desc_fabrique`, `_jokers_deplaces`) — couvre l'échange dans une même
  combinaison (point 1), une tuile de la main identique à une tuile du
  plateau qui se déplace (point 2 : les deux « tuiles » s'annulent au sein
  d'une même opération), et deux jokers qui se remplacent dans une même
  combinaison (point 3, premier cas — `_jokers_deplaces` ne considère un
  joker comme déplacé que s'il figure dans `retirees_vues` de sa propre
  opération, jamais via `libere` brut).
- **Échange cyclique entre deux combinaisons** (`_composantes_fortement_
  connexes` — Tarjan, puis `_detecter_blocs_silencieux`) : quand deux
  combinaisons s'échangent leurs tuiles (chacune a besoin d'une tuile
  libérée par l'autre), le graphe de dépendances causales a un cycle
  strict, impossible à sérialiser normalement — **c'est le cas réel qui
  faisait planter le jeu**. Un cycle où TOUTES les opérations impliquées
  sont des "update" entièrement invisibles est traité comme un seul
  **bloc** : le tri topologique le place comme une unité, et
  `etapes_coup_ia` applique en un seul geste toutes les tuiles libérées du
  bloc au cadre, PUIS toutes les tuiles consommées du bloc, sans jamais
  dépendre de l'ordre interne entre ses membres. Un cycle qui ne qualifie
  pas (un "retrait"/"create" dedans, ou une "update" partiellement
  visible) reste sur le repli pré-existant (ordre arbitraire) — cas
  extrême resté hors de portée, jamais rencontré avec un coup réellement
  joué.
- **Repli d'urgence déjà en place côté `ui/api.py`** (`jeu_ia_jouer`,
  issue #196) : si malgré tout `decrire_coup_ia`/`etapes_coup_ia` levaient
  une exception, le tour de l'IA n'est jamais bloqué — résumé/étapes vides,
  et les deux plateaux sont sauvegardés dans
  `RACINE_DATA/erreurs_description/<horodatage>.json`
  (`{"erreur", "plateau_avant", "plateau_apres"}`) pour reproduire le cas.
  `tests/donnees/erreur_description_20261027_115033.json` est un exemple
  réel ainsi capturé (le `KeyError: 'jaune_3_a'` ci-dessus), rejoué dans
  `tests/test_description_coup.py` comme test de non-régression.
- **Complexité des coups ratés** (`persistance/coups_rates.py`,
  `_complexite_coup`) : réutilise tel quel `decrire_coup_ia`/
  `etapes_coup_ia` corrigés — un échange de tuiles identiques n'est donc
  plus compté dans `nb_combinaisons_touchees` ni `nb_etapes`, sans
  changement de code dans `coups_rates.py` lui-même.
- **Tests** (`tests/test_description_coup.py`) : échange main/plateau dans
  une même combinaison, échange cyclique entre deux combinaisons (sans
  autre changement), régression bout en bout sur le cas réel ayant
  planté, deux jokers (un remplacé par l'autre dans une même combinaison —
  pas un déplacement — et un second qui change réellement de combinaison
  — reste un déplacement). `tests/test_coups_rates_description.py` : un
  échange de tuiles identiques, seul changement d'un coup, est classé
  "simple" (0 combinaison touchée, 0 étape). Les cas déjà couverts avant
  #197 (chaîne Bruno/Expert, échange de joker, démantèlement de groupe)
  gardent EXACTEMENT le même nombre d'étapes qu'avant (pas de régression).

### 12ter. Accords en français et suppression des pronoms genrés (issue #198)

Deux défauts grammaticaux relevés sur de vraies descriptions produites par
#189/#191/#197 ci-dessus, corrigés dans `moteur/description_coup.py` SANS
toucher au moteur tuile-à-tuile (`_construire_operations`) ni à la logique
de complexité (§11quater) :

- **Accord de la couleur avec « suite »** (`_couleur_suite`, table
  `_COULEURS_FEMININES = {"noir": "noire", "bleu": "bleue"}`) : « suite »
  est féminin, donc « suite noire », « suite bleue » (« rouge »/« jaune »
  sont déjà identiques au féminin, inchangés). Appliqué partout où une
  couleur qualifie « suite » : `_decrire_combo` (résumé, étapes, écran
  « Les jokers ») et `_label_combo` (désambiguïsation par couleurs,
  §12 point `_desc_fabrique`). **Jamais appliqué à « groupe »** (masculin,
  ou simple liste de couleurs par tuile, ex. « groupe de 11 bleu, jaune et
  noir ») : accord uniquement sur le mot « suite » lui-même, jamais sur la
  liste de couleurs d'un groupe.
- **Suppression des pronoms « il »/« elle »** : plus aucune phrase du
  résumé (`decrire_coup_ia`) ne présuppose le genre du joueur. La branche
  « coup complexe » (plusieurs phrases) utilisait `"Il a créé..."`,
  `"Il a complété..."`, `"Il a retiré..."` quel que soit `nom` — corrigé en
  tournures impersonnelles : une création devient nominale (`"Création
  d'un groupe de 11."`, avec élision « de » → « d' » devant voyelle, voir
  extension de `_contracter` ci-dessous), les autres changements d'une
  combinaison reprennent les TUILES comme sujet de la phrase (`"Le 3 bleu
  remplace le joker dans le groupe de 3."`), exactement comme le fait déjà
  le pas-à-pas (`etapes_coup_ia`) depuis #191. Les deux fonctions
  partagent désormais le même texte pour un changement « update »
  (nouveau helper privé `_texte_update(op, desc)`, extrait de la logique
  dupliquée) — pur regroupement de code, aucun changement de comportement
  côté pas-à-pas. `_contracter` gère en plus l'élision de « de » devant un
  article indéfini à initiale vocalique (« un »/« une » → « d'un »/« d'une »,
  jamais pour « à », qui ne s'élide pas en français).
- **Non concerné** : l'écran « Les jokers » et les phrases sur les
  combinaisons défaites (`_phrase_sujet`) n'utilisaient déjà aucun pronom
  (sujet = les tuiles ou « le joker ») — aucun changement nécessaire
  au-delà de l'accord de couleur ci-dessus.
- Tests (`tests/test_description_coup.py`) : accord de « suite » avec
  chacune des quatre couleurs (texte ET étiquette courte `_label_combo`) ;
  « groupe » reste invariable avec les quatre couleurs (jamais de « e »
  final ajouté). Mise à jour nécessaire de deux tests existants devenus
  obsolètes par construction (texte comparé mot pour mot) : la contraction
  de référence attendait `"suite noir"` (désormais `"suite noire"`), et le
  cas Bruno (#191) attendait `"Il a créé..."`/`"Il a complété..."`
  (désormais `"Création d'un groupe de 11."`/`"Le 3 bleu remplace le
  joker dans le groupe de 3."`) — même contenu, formulation différente.

## 13. Pistes d'amélioration de l'IA à tester (issue #195)

Idées formulées par Alain au fil des parties de calibrage contre Expert,
tirées de sa façon de jouer. **Aucune n'est implémentée** : ce sont des
pistes pour la future révision des niveaux de difficulté, à cocher une par
une au fur et à mesure que de futures issues les testent/implémentent.

- [ ] **Piste 1 — Réserve d'un coup (garder un coup pour le tour
  suivant)** : plutôt que de poser toutes les tuiles possibles en un tour,
  en garder une pour le tour suivant afin d'éviter de piocher (deux tours à
  une tuile plutôt qu'une pose de deux tuiles suivie d'une pioche).
  **Risque** : l'adversaire peut occuper la place laissée libre entre les
  deux tours. **Test** : nécessite d'évaluer un coup sur deux tours, pas un
  seul ; l'analyse des coups d'un joueur humain (§11, et la fiabilisation à
  venir de cette analyse) donnera les premières statistiques sur
  l'efficacité réelle de cette technique chez un humain avant d'envisager
  de l'implémenter côté IA.
- [ ] **Piste 2 — Éliminer en priorité les doublons de la main** : quand la
  main contient deux tuiles identiques (même valeur, même couleur), chercher
  à en poser une le plus vite possible, car deux tuiles identiques ne
  peuvent jamais entrer dans la même combinaison et sont donc plus
  difficiles à placer. Exemple d'Alain : main `1 rouge, 2 rouge, 2 rouge,
  3 rouge, 3 bleu, 3 noir` → jouer la suite 1-2-3 rouge plutôt que le groupe
  de 3, pour faire partir un des deux `2 rouge`. **Hypothèse** : à nombre de
  tuiles posées égal, préférer le coup qui laisse la main restante la plus
  facile à placer (moins de doublons, moins de tuiles isolées).
  **Test** : le départage actuel du solveur entre coups équivalents se fait
  par points puis par économie de jokers (§8bis) ; ajouter un critère
  d'évaluation de la main restante, puis comparer les deux versions avec
  `scripts/comparer_niveaux_ia.py` (§9, donnes jouées en miroir, plusieurs
  dizaines de donnes) pour voir si le taux de victoire change de façon
  significative.
- [ ] **Piste 3 — Plus de temps de réflexion pour Expert, ou un niveau
  au-dessus** : la force d'Expert dépend directement de son budget de temps
  (voir les mesures de #187 et #190, §8bis/§9). Un niveau supplémentaire qui
  réfléchirait plus longtemps, ou qui calculerait sur deux tours, pourrait
  se situer au-dessus du niveau de jeu d'un humain.
- [ ] **Piste 4 — Procédure commune d'évaluation d'une piste** : comparer
  deux versions de l'IA avec les parties jouées en miroir de
  `scripts/comparer_niveaux_ia.py` (§9), vérifier le nombre de parties et la
  marge d'erreur (IC 95 %) affichés par le script, et ne retenir une piste
  que si le gain est significatif ET que le temps de calcul par tour reste
  raisonnable.
- [ ] **Piste 5 — Rôle des points dans le départage** : le solveur
  départage aujourd'hui les coups équivalents en préférant celui qui pose
  le plus de points (§8bis). Dans une partie d'une seule manche (§3bis,
  configuration actuelle de l'application), ces points ne changent le
  vainqueur que si la partie se termine **bloquée** (pioche épuisée, plus
  aucun coup possible) : gagne alors celui dont les tuiles restantes valent
  le moins. Sinon, la partie est gagnée par celui qui vide son chevalet en
  premier, et les points ne changent que la marge affichée en fin de
  partie. **Hypothèse** : le critère des points ne devrait passer en
  premier que si la pioche est vide ou presque, ou si plusieurs manches
  sont jouées (score cumulé) ; le reste du temps, il devrait laisser la
  place à l'évaluation de la main restante (piste 2). **Test** : comparaison
  par simulation, comme pour la piste 2.
- [ ] **Piste 6 — Se débarrasser en priorité des 1 et des 13** (idée d'Alain,
  #203) : les tuiles de valeur 1 et 13 entrent dans **moins de combinaisons**
  que les valeurs intermédiaires (un 1 ne peut prolonger une suite que par le
  haut, un 13 que par le bas ; comme toute valeur, chacune n'entre que dans un
  seul groupe de sa valeur) — elles sont donc plus difficiles à placer et
  plus coûteuses si elles restent en main à la fin d'une manche. **Hypothèse** :
  à nombre de tuiles posées égal, préférer le coup qui fait partir un 1 ou un
  13. Proche de la piste 2 (éliminer les doublons) : un critère d'évaluation
  de la main restante au départage du solveur. **Test** : comparer deux
  versions avec `scripts/comparer_niveaux_ia.py` (§9), en miroir.
- [ ] **Piste 7 — Tenir compte des points restants, mais seulement en
  plusieurs manches** (idée d'Alain, #203, précision de la piste 5) : depuis
  #203, un match peut compter plusieurs manches et les points restants
  s'accumulent au `score_cumul` — ils comptent alors réellement pour la
  suite, pas seulement pour la marge affichée. L'IA pourrait en tenir compte
  (se défausser des grosses tuiles, limiter la casse quand elle ne peut pas
  gagner la manche) **uniquement quand `nb_manches > 1`**. **Prudence
  explicite d'Alain** : ne pas accorder trop d'importance aux points au
  risque de **perdre des manches** qu'on aurait gagnées en vidant son
  chevalet — le premier objectif reste de finir la manche. En une seule
  manche, ce critère ne vaut que pour les parties bloquées (voir piste 5).
  **Test** : simulation en miroir avec `--manches N` (§9).
- [ ] **Constat — fiabilité du réglage « Nombre de manches » (corrigé par
  #203)** : ce réglage comparait jadis le numéro de tour au nombre de manches
  sans vrai compteur, si bien que plusieurs manches ne fonctionnaient pas
  (#192 l'avait alors masqué, §3bis). **#203 l'a corrigé** : vrai compteur
  `manche_numero`, scores cumulés, classement final au cumul — le réglage est
  de nouveau disponible (défaut 1 manche). La piste 5 ci-dessus reste donc
  valable telle quelle pour les parties d'une seule manche (où les points ne
  départagent que les parties bloquées) ; les pistes 6 et 7 en découlent.
  Entre joueurs humains, Alain n'a jamais observé de partie bloquée : les
  fins de partie bloquées vues en simulation (29 % au départ selon #184,
  environ 5 à 10 % avec le solveur d'Expert selon #186/#187, §9) sont un
  signe de faiblesse de l'IA plutôt qu'un phénomène normal du jeu, et leur
  proportion est un **indicateur de qualité à suivre** : elle doit baisser
  quand l'IA progresse.
- [x] **Traitée (#199) — simplicité du coup à nombre de tuiles posées
  égal** : observation d'Alain qui a motivé cette issue (voir §8bis pour le
  détail technique) — complexifier le plateau (défaire/recréer des
  combinaisons pour poser le même nombre de tuiles) n'a **aucun bénéfice
  stratégique démontré** : la campagne Avancé vs Expert avec et sans le
  critère de simplicité (§8bis, §9) ne montre aucune baisse du taux de
  victoire d'Expert en le préférant systématiquement, et sa perturbation
  moyenne du plateau par coup baisse nettement. La simplicité est donc
  désormais un critère MESURÉ (`mesurer_perturbation`, `moteur/solveur.py`)
  et appliqué par défaut, pas seulement une préférence de lisibilité pour
  le pas-à-pas — contrairement aux pistes 2 et 5 ci-dessus (évaluation de
  la main restante, rôle des points), qui restent, elles, à tester.

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
