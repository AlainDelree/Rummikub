# Issue #192 — Masquer le réglage « Nombre de manches » : le jeu se joue en une seule manche

## Constat

Les réglages de l'écran d'accueil proposaient un champ « Nombre de manches »
(1 à 99), mais plusieurs manches ne fonctionnaient pas : `est_fin_partie`
(`moteur/partie.py`) compare `tour_numero` au nombre de manches configuré
pour décider de la fin de partie dans ce cas, mais il n'existe aucun
compteur de manches nulle part dans l'application (`nouvelle_manche` n'est
jamais appelé). Un joueur choisissant plus d'une manche aurait donc un
comportement incorrect. Décision d'Alain : le jeu se joue sans manches
multiples, en une seule manche.

## Correctif

- **UI retirée** : le champ « Nombre de manches » a été retiré de
  `accueil.html` (onglet « Règles du jeu ») et de `accueil.js`
  (`remplirChampsReglages`, `sauvegarderReglages`, `lancerPartie` ne
  référencent plus `#rgl-manches`). La clé `nb_manches` a aussi été retirée
  de `reglages.DEFAUTS` (`reglages.py`) — une ancienne valeur déjà présente
  dans un `config.json` existant reste lisible sans erreur, simplement
  ignorée par l'application.
- **Forçage à 1 manche, point d'entrée unique** : `creer_partie`
  (`moteur/partie.py`) force désormais `"nb_manches": 1` dans l'état créé,
  sans jamais lire la valeur transmise par l'appelant (réglages UI,
  `config.json` ancien, script). Toute nouvelle partie a donc exactement
  une manche, quelle que soit la valeur enregistrée côté réglages.
- **Reprise d'une partie sauvegardée** : `ApplicationRummikub.reprendre_jeu`
  (`ui/application.py`) force aussi `etat["config"]["nb_manches"] = 1` sur
  l'état rechargé depuis SQLite, pour qu'une partie créée avant #192 avec
  une autre valeur ne retombe pas dans la branche incorrecte d'
  `est_fin_partie` une fois reprise.
- **Code moteur des manches conservé, signalé inactif** : `nouvelle_manche`,
  la branche `tour_numero > nb_manches` d'`est_fin_partie` et `score_cumul`
  restent en place tels quels (aucune suppression) — plus aucun appelant de
  l'application ne les atteint en pratique, puisque `nb_manches` vaut
  toujours 1. Un compteur de manches correct reste à écrire le jour où des
  manches multiples seraient réintroduites. Écran de fin de partie inchangé.
  `scripts/simulation_ia.py` et `scripts/comparer_niveaux_ia.py` continuent
  d'appeler directement `creer_partie`/`nouvelle_manche` en dehors de
  l'application pour leurs propres besoins de simulation — non concernés
  par le forçage à 1.
- `CONTEXTE.md` mis à jour : nouvelle section §3bis, notes sur
  `nouvelle_manche`/`est_fin_partie` (§3), compte de tests (§6).

## Tests

- `tests/test_moteur.py::test_creer_partie_force_une_seule_manche_meme_si_regles_en_demandent_plus` :
  une nouvelle partie a toujours exactement 1 manche même si
  `config_regles` en demande 5.
- `tests/test_playwright_accueil_reglages.py` (nouveau, Playwright sur
  `accueil.html` directement, jamais la vraie application pywebview, voir
  CONTEXTE.md §7) : champ absent du DOM et du texte affiché, panneau
  « Règles du jeu » sans trou (toujours exactement 2 réglages restants),
  réglages qui s'enregistrent et se rechargent sans erreur console même
  avec un ancien `nb_manches=5` simulé côté mock API.
- `pytest tests/ -q` → **122 passed** (119 précédemment + 3 nouveaux tests
  Playwright/moteur).

## Fichiers touchés

- `src/rummikub/moteur/partie.py` (`creer_partie`)
- `src/rummikub/ui/application.py` (`reprendre_jeu`)
- `src/rummikub/reglages.py` (`DEFAUTS`)
- `src/rummikub/ui/web/accueil.html`, `accueil.js`
- `tests/test_moteur.py`, `tests/test_playwright_accueil_reglages.py` (nouveau)
- `CONTEXTE.md`
