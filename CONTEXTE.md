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
- `nouvelle_manche(etat)` : redistribue, reset plateau/chevalets/mise,
  **conserve score_cumul**. Rappelle `backup_debut_tour`. **Inactif depuis
  #192** (voir §3bis) : plus aucun appelant de l'application ne l'invoque,
  conservé pour une éventuelle réintroduction future des manches
  multiples.
- `est_fin_partie(etat)` : True si `nb_manches==1` et manche terminée, sinon
  `tour_numero > nb_manches` (simplifié). **Depuis #192, `nb_manches` vaut
  toujours 1** (voir §3bis) : la branche `else` n'est donc plus jamais
  empruntée en pratique dans l'application, mais reste en place.
- Helpers internes : `plateau_depuis_dict`, `_plateau_vers_dict`,
  `_points_tuiles_posees`, `_terminer_tour`, `_ajouter_historique`.

**score.py**
- `calculer_scores_manche(joueurs, valeur_joker)` : perdants = −somme pénalités
  de leur chevalet ; gagnant (chevalet vide) = +somme des pénalités adverses.
  Met à jour `score_manche` et `score_cumul` en place.
- `trouver_gagnant_manche(joueurs)` → index du meilleur `score_manche`.

## 3bis. Manches multiples : réglage retiré, code moteur inactif (issue #192)

Le jeu se joue désormais **toujours en une seule manche** — décision
d'Alain, suite au constat que la règle de fin de partie pour plusieurs
manches (`est_fin_partie`) comparait `tour_numero` au nombre de manches
sans qu'aucun compteur de manches correct n'existe par ailleurs (aucun
appel à `nouvelle_manche` nulle part dans l'application) : un joueur qui
aurait choisi plus d'une manche depuis les réglages avait donc un
comportement incorrect.

- **Réglage retiré de l'UI** : le champ « Nombre de manches » (1-99) a été
  retiré de `accueil.html` (onglet « Règles du jeu ») et des handlers JS
  associés dans `accueil.js` (`remplirChampsReglages`, `sauvegarderReglages`,
  `lancerPartie`). La clé `nb_manches` a aussi été retirée de
  `reglages.DEFAUTS` (`reglages.py`) : elle n'est plus écrite par
  l'application, mais une ancienne valeur déjà présente dans un
  `config.json` existant reste lue sans erreur (fusion `{**DEFAUTS,
  **json.loads(...)}`), simplement ignorée.
- **Point d'enforcement unique : `creer_partie`** (`moteur/partie.py`) force
  désormais `"nb_manches": 1` sans jamais lire `config_regles.get(
  "nb_manches", ...)` — toute nouvelle partie a donc exactement une manche,
  quelle que soit la valeur transmise par l'appelant (réglages UI,
  `config.json` ancien, script). **Reprise d'une partie sauvegardée** :
  `ApplicationRummikub.reprendre_jeu` (`ui/application.py`) force aussi
  `etat["config"]["nb_manches"] = 1` sur l'état rechargé depuis SQLite, pour
  qu'une partie créée avant #192 avec une autre valeur ne retombe pas dans
  la branche `else` incorrecte de `est_fin_partie` une fois reprise.
- **Code moteur lié aux manches volontairement conservé, mais inactif** :
  `nouvelle_manche` et la branche `tour_numero > nb_manches` d'
  `est_fin_partie` (`moteur/partie.py`), ainsi que `score_cumul`
  (`score.py`, `partie.py`) restent en place tels quels — aucun appelant de
  l'application ne les atteint plus en pratique puisque `nb_manches` vaut
  toujours 1. Un compteur de manches correct (actuellement absent) reste à
  écrire le jour où des manches multiples seraient réintroduites. L'écran
  de fin de partie n'a pas été modifié.
- **Non concerné** : `scripts/simulation_ia.py` et
  `scripts/comparer_niveaux_ia.py` (§9) appellent directement
  `creer_partie`/`nouvelle_manche` en dehors de l'application pour simuler
  plusieurs manches IA vs IA — ces scripts de test/mesure restent
  inchangés, seule l'application (UI + moteur côté parties jouées par un
  humain) est concernée par le forçage à 1.
- Tests : `tests/test_moteur.py::
  test_creer_partie_force_une_seule_manche_meme_si_regles_en_demandent_plus`
  (nouvelle partie toujours à 1 manche même si `config_regles` en demande
  plus) ; `tests/test_playwright_accueil_reglages.py` (Playwright sur
  `accueil.html`, voir §7 : champ absent du DOM, pas de trou dans le
  panneau « Règles du jeu », réglages enregistrés/rechargés sans erreur
  console même avec un ancien `nb_manches` > 1 simulé côté mock API).

## 4. Conventions importantes

- **Tuile** = dataclass avec `id/valeur/couleur/est_joker` + `as_dict()`.
- **État de partie** = **dict JSON-sérialisable** (jamais d'objets Python
  stockés dans l'état). Le moteur convertit Tuile ↔ dict aux frontières.
- **plateau** = `list[list[dict_tuile]]` côté état/API ;
  `list[list[Tuile]]` seulement à l'intérieur des fonctions de validation/moteur.
- Clés de l'état : `id, phase, tour_numero, index_joueur_actuel, joueurs[],
  pioche[], plateau[], plateau_debut_tour, chevalet_debut_tour,
  index_debut_tour, tour_debut_tour, historique[], manche_terminee,
  gagnant_manche_index, config{}`. Un joueur :
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
- État actuel : **122 tests passent** (`pytest -q` → `122 passed`).

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

## 8bis. Solveur de réarrangement global du plateau — niveau Expert (#186)

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

## 9. Scripts de simulation IA vs IA (`scripts/`)

- `scripts/simulation_ia.py` : fait jouer 2 à 4 IA sur une ou plusieurs
  manches, journalise les anomalies (coup invalide, blocage). Utile pour un
  test de fumée ponctuel.
- `scripts/comparer_niveaux_ia.py` (#184) : compare deux niveaux d'IA sur un
  grand nombre de parties à 2 joueurs, pour savoir si l'un est réellement
  plus fort que l'autre. Chaque donne (même distribution de tuiles) est
  jouée deux fois en miroir (places échangées), pour annuler l'effet du
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
  "annulation"`), `nb_tuiles_posees`, `termine` et `gagnant_index` — une
  partie dont la DERNIÈRE action n'a pas `termine: True` est abandonnée (ou
  encore en cours) et ignorée du bilan. Les journaux écrits avant #185
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
  « <Nom> a posé... » plutôt que par un « Il » impersonnel. Un coup simple
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
- [ ] **Constat (non corrigé ici) — fiabilité du réglage « Nombre de
  manches »** : ce réglage a existé dans les réglages de l'écran d'accueil,
  mais la règle de fin de partie pour plus d'une manche (`est_fin_partie`
  dans `moteur/partie.py`) comparait le numéro de tour au nombre de manches,
  ce qui ne compte pas de vraies manches (aucun compteur de manches
  n'existe) — plusieurs manches ne fonctionnaient donc pas correctement.
  **Décision d'Alain** (#192, §3bis) : le jeu se joue désormais en une seule
  manche, et le réglage est masqué côté UI. La piste 5 ci-dessus ne vaut
  donc, en pratique, que pour les parties bloquées. Entre joueurs humains,
  Alain n'a jamais observé de partie bloquée : les fins de partie bloquées
  vues en simulation (29 % au départ selon #184, environ 5 à 10 % avec le
  solveur d'Expert selon #186/#187, §9) sont un signe de faiblesse de l'IA
  plutôt qu'un phénomène normal du jeu, et leur proportion est un
  **indicateur de qualité à suivre** : elle doit baisser quand l'IA
  progresse.
