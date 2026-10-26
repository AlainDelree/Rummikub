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
  ui/
    application.py          ApplicationRummikub : fenêtre pywebview, etat_jeu (public),
                            naviguer_vers_jeu/accueil, reprendre_jeu, load_url.
    api.py                  Classe Api : méthodes appelables depuis JS (voir §4).
    noms_ordinateur.py      choisir() : nom aléatoire pour un joueur IA.
    web/                    Front : accueil.html/css/js, jeu.html/css/js,
                            commun.css/js, avatars/.

tests/                      pytest : test_moteur.py + test_ia.py.
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
  **conserve score_cumul**. Rappelle `backup_debut_tour`.
- `est_fin_partie(etat)` : True si `nb_manches==1` et manche terminée, sinon
  `tour_numero > nb_manches` (simplifié).
- Helpers internes : `plateau_depuis_dict`, `_plateau_vers_dict`,
  `_points_tuiles_posees`, `_terminer_tour`, `_ajouter_historique`.

**score.py**
- `calculer_scores_manche(joueurs, valeur_joker)` : perdants = −somme pénalités
  de leur chevalet ; gagnant (chevalet vide) = +somme des pénalités adverses.
  Met à jour `score_manche` et `score_cumul` en place.
- `trouver_gagnant_manche(joueurs)` → index du meilleur `score_manche`.

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
- État actuel : **81 tests passent** (`pytest -q` → `81 passed`).

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
