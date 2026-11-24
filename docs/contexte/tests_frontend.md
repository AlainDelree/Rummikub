# Tests et vérification front-end

## 6. Tests

- Lancer : `pytest tests/` (depuis la racine ; `pytest.ini` fixe
  `pythonpath=src`, `testpaths=tests`).
- `tests/test_moteur.py` : sac/distribution, suites/groupes/combinaisons,
  plateau, mise initiale, tours, pioche, backup/annulation.
- `tests/test_ia.py` : les niveaux ne plantent pas et renvoient une action
  valide (+ tactiques de joker testées directement sur les fonctions
  heuristiques). `tests/test_niveaux.py` (#213) : l'échelle des cinq niveaux et
  l'affaiblissement paramétré (perturbation, oubli, reproductibilité, repli).
- `tests/test_bilan.py` : lecture des journaux de parties et calcul du bilan
  par niveau d'IA (voir §9).
- `tests/test_description_coup.py` : résumé écrit d'un coup de l'IA (coup
  simple/extension/groupe créé, joker récupéré, coup touchant plusieurs
  combinaisons) et découpage en étapes du rejeu pas-à-pas (voir §12).
- `tests/test_playwright_pas_a_pas.py` et
  `tests/test_playwright_accueil_reglages.py` : vérifications front-end via
  Playwright (voir §7), sautées proprement si `playwright` ou chromium sont
  absents.
- **Fiabilité des tests dépendant de la vitesse machine ou de la source du
  scénario (issue #210, suite de #209).** Deux familles de tests pouvaient
  échouer par intermittence sans aucune régression réelle :
  - *Tests au budget de temps en secondes* (recherche de repli
    `moteur/solveur.py`, qui met plusieurs secondes sur les cas durs) : leur
    budget est multiplié par le `facteur_machine` mesuré une fois par session
    dans `tests/conftest.py` (micro-benchmark CPU, ≈ 1 sur la machine de dev,
    ≥ 1 sur une machine plus lente, plafonné à 30 — voir #206). Le RÉSULTAT
    exigé (coup trouvé, nombre de tuiles, conservation du plateau) est
    strictement inchangé ; seule la sensibilité à la charge disparaît.
    Vérifié sous charge CPU artificielle (8 cœurs saturés → `facteur_machine`
    ≈ 2,7 → tous les tests sensibles passent).
  - *Pas-à-pas condensé du coup de Bruno (tour 57)* : jugé désormais sur le
    coup du solveur **MAISON** (`moteur/solveur_exact.py`, celui réellement
    joué), déterministe (13 étapes condensées, borne « au plus 13 », contre
    27 en détaillé), et non plus sur la bibliothèque externe `rummikub-solver`
    qui proposait un arrangement un peu différent (12 étapes), d'où l'ancien
    seuil « < 11 » instable. Les propriétés GÉNÉRALES du condensé restent, elles,
    testées via la bibliothèque externe (insensibles à la source).
- **Marqueur `@pytest.mark.lent`** (déclaré dans `pytest.ini`) : posé sur les
  tests de solveur à gros budget (plusieurs secondes chacun : cas de
  référence #190/#194/#200, cascade de jokers #194, départage #199/#200).
  Ils restent exécutés par défaut avec toute la suite ; le marqueur sert
  uniquement à pouvoir les lancer ou les isoler à part (`pytest -m lent`,
  `pytest -m "not lent"`) sans jamais les exclure par défaut.
- **Deux pièges propres à Windows corrigés dans les tests (issue #244,
  jamais dans le code de production)** : les tests de dépassement de budget
  (`budget_temps=0.0` sur `resoudre_coup`/`solveur.py`) n'utilisent jamais
  l'horloge réelle de l'OS — sous Windows, `time.monotonic()` n'avance que
  par paliers d'environ 15 ms, ce qui peut manquer la comparaison stricte
  `> self.limite` d'une recherche très courte ; voir la fixture
  `horloge_solveur_deterministe` dans `tests/conftest.py` (horloge
  déterministe, pas fixe à chaque appel). Les tests de chemins de lancement
  (`tests/test_actualise_flag_lancement.py`) comparent des `Path` résolus
  entre eux, jamais un `Path.as_posix()` contre un `str(...)` écrit avec des
  barres inverses natives Windows. Troisième cas du même défaut trouvé après
  coup (issue #247) : `test_coups_rates_extensions.py::
  test_cas_reference_bruno_budget_trop_court_signale_inconclusif`
  (`budget_genereux=0.0` sur `analyser_decision_complete`, qui descend aussi
  jusqu'à `resoudre_coup`/`solveur.py`) — même fixture appliquée, aucun
  nouveau mécanisme nécessaire.
- État actuel : **282 tests passent** (`pytest -q` → `282 passed, 3 skipped`,
  les 3 sautés étant les tests Playwright quand chromium/playwright sont
  absents). Suite stable sur deux exécutions consécutives (issue #210).

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

