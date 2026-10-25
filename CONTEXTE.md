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
  moteur/                   Logique de jeu pure (voir §3).
    tuiles.py               Dataclass Tuile + création/mélange/distribution.
    validation.py           valider_suite/groupe/combinaison/plateau.
    partie.py               État de partie, tours, pioche, backup, manches.
    score.py                calculer_scores_manche, trouver_gagnant_manche.
    ia.py                   5 niveaux d'IA (voir §5) + tactiques de
                            récupération de joker (voir §8).
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
- État actuel : **25 tests passent** (`pytest -q` → `25 passed`).

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

**Identifiées mais pas encore implémentées :**

- **Réduction de groupe de 4 à 3 (joker retiré)** : retirer le joker d'un
  groupe de 4 tuiles (3 réelles + 1 joker) *sans* tuile de remplacement —
  le groupe réduit à ses 3 tuiles réelles reste valide tel quel,
  contrairement à l'échange direct (#148) qui exige une tuile identique
  en main. Aucune issue dédiée ouverte à ce jour ; non couvert par
  `_jokers_recuperables` (qui ne traite que le remplacement) ni par #180
  (qui retire une tuile réelle, jamais le joker, pour l'utiliser
  ailleurs).
- **Scission en milieu de suite** : étendre `_coup_scission` (qui ne
  détache aujourd'hui qu'une tuile réelle en BOUT de suite, jamais un
  joker, pour former un nouveau groupe) afin de libérer une tuile ou un
  joker en position intérieure d'une suite. Mentionnée en discussion avec
  Alain, jamais formalisée en issue.
- **Démantèlement complet d'une courte suite contenant un joker** (#175) :
  retirer SES DEUX tuiles réelles (pas une seule comme dans les tactiques
  ci-dessus), chacune recombinée avec des tuiles de la main pour former
  deux NOUVELLES combinaisons (groupes ou suites) ailleurs sur le
  plateau — le joker est ainsi isolé et libéré sans qu'aucune tuile ne le
  remplace directement. Généralisable au cas sans joker : la même suite
  démantelée autour d'une tuile réelle (plutôt qu'un joker), dont les deux
  voisines sont recombinées ailleurs. Nettement plus complexe que les
  tactiques ci-dessus — recherche de recombinaison globale sur plusieurs
  combinaisons du plateau, pas un simple motif local — probablement une
  issue à part entière une fois les cas plus simples en place.

Note : `_coup_scission` existe déjà dans `ia.py` mais ne porte pas sur un
joker (elle exclut explicitement les jokers en bout de suite) — elle est
citée ici seulement comme mécanisme apparenté, pas comme tactique de
joker au sens de cette liste.
