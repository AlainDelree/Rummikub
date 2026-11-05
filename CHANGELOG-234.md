# Issue #234 — Audit #96 (Diagnostique_Programme) : durcir le drapeau de mise à jour, consigner les constats, silences d'erreur et déclaration d'audit

## Contexte
Suite de l'audit #96 du projet Diagnostique_Programme sur Rummikub (commit
b7214b2). Travaux demandés dans l'ordre : durcir la lecture du flag Actualise
(SEC-003), consigner des constats (installeur, dépendances, données
versionnées, fichiers à données personnelles) sans les modifier, commenter
les captures d'erreur silencieuses (PRO-012), et poser une déclaration
d'audit minimale (`.audit.json`). Aucun changement de comportement du jeu, de
l'IA ni du solveur.

## 1. SEC-003 — Validation des chemins du flag Actualise
- Nouveau module `src/rummikub/actualise.py` :
  `valider_chemin_actualise(chemin, racine=None)` n'accepte un chemin que
  s'il existe, a l'extension `.bat`/`.exe`, et reste (une fois résolu —
  liens, `..`, casse) sous la racine autorisée (`RACINE_ACTUALISE`,
  `C:\Actualise` par défaut, paramétrable via l'argument `racine` ou en
  monkeypatchant le module — ce qui rend la validation testable sous Linux).
  Sinon : `None`, sans jamais lever d'exception.
- `main.py` (`_lancer_actualise_ui_si_flag`) et
  `src/rummikub/ui/application.py` (`_handler_fermeture_actualise`) : les
  chemins `actualise_ui` et `bat` lus dans `actualise_update.flag` passent
  désormais par cette validation avant tout `subprocess.Popen`. Un chemin
  invalide ou hors racine est ignoré avec une trace sur `stderr`
  (`[Rummikub] ... ignore ...`), sans lancer quoi que ce soit et sans
  bloquer le démarrage/la fermeture. Le lancement du `bat`
  (`application.py`) se fait maintenant **sans** `shell=True` (le chemin
  validé ne contient plus d'espace, cf. convention `updater_<nom>.bat` sous
  `C:\Actualise` depuis l'issue #84).
- Tests (`tests/test_actualise_securite.py`,
  `tests/test_actualise_flag_lancement.py`) : chemin valide (`.bat`/`.exe`),
  chemin inexistant, mauvaise extension, chemin hors racine, évasion par
  `..`, drapeau absent, drapeau illisible, racine par défaut paramétrable,
  et vérification explicite que `Popen` n'est jamais appelé avec
  `shell=True`.

## 5. PRO-012 — Captures d'erreur silencieuses commentées
Commentaire ajouté dans le corps de chaque `except` sans traitement listé par
l'audit, expliquant pourquoi l'erreur est volontairement ignorée (aucun
changement de comportement) : `autotest.py` (164, 176),
`moteur/solveur_exact.py` (443, 580), `persistance/journal.py` (136),
`ui/api.py` (260), `scripts/matrice_strategies.py` (514),
`scripts/_mesure_volume_222.py` (59), et les deux captures de `main.py`/
`application.py` traitées au point 1 ci-dessus. Aucun de ces `except` ne
cache, à l'examen, un véritable défaut (voir rapport de clôture de l'issue).

## 6. Déclaration d'audit
Ajout de `.audit.json` à la racine (`src/rummikub/ui`,
`src/rummikub/moteur`, `src/rummikub/persistance` vérifiés existants et
contenant du code Python) — contenu strictement conforme à la demande,
aucun champ supplémentaire.

## 2., 3., 4., 7. Constats (aucune modification)
Voir le rapport de clôture de l'issue #234 : constat sur
`installeur/rummikub.iss` (absence de permission `users-modify` sur `{app}`
et `C:\Actualise`), dépendances non épinglées (EXP-001, reporté), tri
recommandé des fichiers de banc d'essai versionnés à la racine, et liste
(sans valeurs) des fichiers à données personnelles.
