# Issue #280 — Nettoyage ruff : noqa E402 inutiles, corrections automatiques sûres, test de l'activation des règles S

## Contexte

Point 5 de l'audit de sécurité (projet Diagnostique_Programme), avant le
quatrième audit et la release finale. Ruff utilisé : celui du crochet
pre-push (`~/Diagnostique_Programme/.venv_outils/bin/ruff`), version
**0.17.3** — identique à la version de l'audit (372+ remarques, 140 RUF100),
aucun écart à signaler. Le dépôt n'a aucun fichier de configuration ruff
(`pyproject.toml`/`ruff.toml`/`setup.cfg`) : `ruff check` tourne avec la
sélection par défaut de l'installation locale (qui, empiriquement, inclut
RUF100 et une bonne partie de F/B/C4/PERF/PLW mais PAS `E402` ni les
règles `S` de sécurité).

## Partie 1 — Nettoyage sûr

- 123 `noqa: E402` retirés (123 confirmés par comptage avant/après,
  0 restant, les 17 noqa de sécurité S311/S603/S607 intacts) — commit dédié.
- Corrections automatiques limitées à 4 familles : tri des imports (I001,
  43 occurrences), f-strings sans variable (F541, 12), annotations entre
  guillemets inutiles (UP037, 11), imports inutilisés (F401, 4 sur 7 — voir
  ci-dessous) — commit dédié séparé.
- **I001 et F401 non appliqués** (fichiers exclus, listés avec raison) sur
  les 28 fichiers où du code s'exécute avant des imports (`sys.path.insert`,
  ou `try/except` d'import optionnel) : `main.py`, tous les scripts/tests
  qui font le classique `sys.path.insert(0, ...)` avant d'importer les
  modules locaux (`scripts/_campagne_186.py`, `_corpus_positions_222.py`,
  `analyser_coups_rates.py`, `calibrer_echelle.py`, `calibrer_niveaux.py`,
  `comparer_niveaux_ia.py`, `comparer_solveur_exact.py`,
  `echelle_niveaux.py`, `generer_corpus_positions_222.py`,
  `match_solveurs.py`, `mesurer_volume_solveur_222.py`, `profil_joueur.py`,
  `simulation_ia.py`, `solveur_exact.py`, `tournoi_niveaux.py`,
  `verifier_simplicite_expert.py`, `verifier_solveur_exhaustif.py`,
  `src/rummikub/moteur/solveur_exact.py` — import optionnel `try/except`
  de `highspy`/`numpy` —, et les tests correspondants
  `tests/test_analyser_phases.py`, `test_calibrer_echelle.py`,
  `test_comparer_niveaux_ia_rapport.py`, `test_condense_solveur.py`,
  `test_match_solveurs.py`, `test_playwright_pas_a_pas.py`,
  `test_solveur_exact.py`, `test_tournoi_niveaux.py`,
  `test_verif_solveur_exact.py`, `test_verifier_simplicite_expert.py`).
  Trois des 7 F401 tombaient dans cette liste (`scripts/calibrer_echelle.py`
  : `rummikub.moteur.ia` ; `scripts/generer_corpus_positions_222.py` :
  `piocher` ; `scripts/verifier_simplicite_expert.py` : `NIVEAUX`) et n'ont
  donc PAS été retirés, par précaution, même si ruff les signale réellement
  inutilisés — seul le retrait du `noqa: E402` (partie 1.1) les concerne.
- I001 a en revanche été appliqué à `src/rummikub/moteur/solveur.py` et
  `src/rummikub/moteur/niveaux.py` (aucun code avant leurs imports — tri
  pur, mêmes noms importés, zéro risque comportemental) : purement
  cosmétique (ordre alphabétique des imports, une ligne vide en moins dans
  `niveaux.py`), mais ce sont des fichiers sensibles — signalé ici pour
  qu'Alain puisse les exclure du commit s'il préfère ne pas y toucher.
- Import à réexportation/effet de bord : aucun des 7 F401 ne correspond à
  un `__init__.py`, à une réexportation ou à un import cité dans
  `rummikub.spec` (vérifié par grep) — les 4 retirés sont sans risque
  (dont `import json` dans `src/rummikub/ui/api.py`, redondant avec un
  `import ... json` local au bloc `except` qui s'en sert réellement).
- `py_compile` sur tous les fichiers modifiés : OK. `ruff --select S
  main.py src` : `All checks passed!` après les deux commits.
- Suite de tests relancée après les corrections automatiques : 597 passed,
  13 skipped — identique à la référence « avant ».

## Partie 2 — Test d'activation des règles S (réponse : OUI, mais non appliqué)

Testé dans une copie jetable sous `/tmp` (hors dépôt), avec un
`ruff.toml` temporaire `extend-select = ["S"]` +
`per-file-ignores: "tests/*" = ["S101"]` :

1. **RUF100** : passe de 17 à **1** sous la sélection par défaut avec S
   actif. Le seul RUF100 restant est le `# noqa: S603` de
   `scripts/tournoi_niveaux.py` ligne 592 — confirmé réellement inutile
   (S603 ne s'y déclenche pas). **Non retiré** (décision laissée à Alain,
   comme demandé). 0 RUF100 n'est donc atteignable qu'en le retirant aussi.
2. **Crochet pre-push** (`ruff --select S main.py src`) : reste
   `All checks passed!` avec et sans le `ruff.toml` temporaire. Testé aussi
   en retirant expérimentalement les 17 noqa dans la copie jetable : le
   crochet détecte alors des avertissements, IDENTIQUEMENT avec et sans la
   config — **mais seulement 7 des 17 emplacements**, car le crochet est
   scopé à `main.py src` et **ne couvre pas `scripts/` ni `tests/`** (10 des
   17 noqa de sécurité y résident). Ceci est une limite préexistante du
   crochet, indépendante de ce test et inchangée par la config testée :
   le périmètre du crochet n'est ni réduit ni masqué par l'activation de S.
3. **Coût réel sur le reste du dépôt** : seulement **3** nouvelles
   remarques S une fois `S101` ignoré dans `tests/*` (comme mesuré en
   externe) : `S603` à `scripts/construire_deb.py` lignes 59 et 160, `S108`
   à `tests/test_coups_rates_filtre_date.py` ligne 16. Confirmé exact,
   fichiers et lignes identiques à la mesure externe. **Aucun de ces 3 n'a
   été corrigé** (pas de nouveau noqa non plus) — listés seulement.

Les trois points sont satisfaits (le point 2 avec la réserve ci-dessus,
qui ne bloque rien puisque le périmètre du crochet n'est pas affecté).
**Mais le dépôt n'a aucune configuration ruff existante** : conformément à
la consigne, aucune configuration n'a été créée. `docs/contexte/
linter_securite.md` a été mis à jour pour décrire cet état et le contenu
exact qu'il faudrait créer (`extend-select = ["S"]` +
`per-file-ignores: "tests/*" = ["S101"]`), décision à prendre par Alain.
Les 17 noqa de sécurité n'ont pas été touchés dans le dépôt réel.

## Partie 3 — Inventaire (non corrigé, à relire)

Comptes réels (ruff 0.17.3, mêmes fichiers que l'audit) :

### BLE001 — `except` trop larges (33 occurrences)

`main.py:39,78` ; `scripts/analyser_coups_rates.py:122,134,745` ;
`scripts/analyser_partie.py:49` ; `scripts/bilan_parties.py:45,53` ;
`scripts/comparer_solveur_exact.py:272` ; `scripts/match_solveurs.py:
173,204,219` ; `scripts/profil_joueur.py:164` ; `scripts/solveur_exact.py:81` ;
`src/rummikub/autotest.py:83,91,98,112,123,172` ;
`src/rummikub/moteur/description_coup.py:741,974` ;
`src/rummikub/moteur/ia.py:935` ; `src/rummikub/moteur/solveur_exact.py:112` ;
`src/rummikub/reglages.py:30` ; `src/rummikub/ui/api.py:257` ;
`src/rummikub/ui/application.py:32` ; `tests/test_autotest.py:33` ;
`tests/test_playwright_accueil_reglages.py:68` ;
`tests/test_playwright_manches.py:43` ; `tests/test_playwright_pas_a_pas.py:70` ;
`tests/test_playwright_tri_automatique.py:54` ;
`tests/test_playwright_vitesse_ia.py:29`.

**Risque de relecture** : plusieurs sont des filets de sécurité
DÉLIBÉRÉS, commentés comme tels (`src/rummikub/ui/api.py:257` : « une
erreur ici ne doit JAMAIS bloquer le tour de l'IA » ; lancements
d'Actualise dans `main.py`/`application.py` : ne doivent jamais bloquer le
démarrage). Les resserrer à une exception précise changerait le
comportement si le filet était pensé pour TOUTE exception — à juger
fichier par fichier, pas en masse.

### PLW1510 — `subprocess.run` sans `check` (2 occurrences)

`scripts/_limite_temps_ferme.py:96` ; `tests/test_autotest.py:149`.

**Risque de relecture** : `tests/test_autotest.py:149` lit ensuite
`proc.returncode in (0, 1)` — ajouter `check=True` ferait lever une
exception sur retour 1 au lieu de laisser le test l'évaluer, cassant le
test. `scripts/_limite_temps_ferme.py:96` est un `taskkill` best-effort sur
un process déjà peut-être terminé : `check=True` pourrait faire planter un
arrêt pourtant normal.

### F841 — variables inutilisées (4 occurrences)

`src/rummikub/persistance/coups_rates.py:1148` ; `tests/test_coups_rates.py:364` ;
`tests/test_coups_rates_parties_liees.py:59` ; `tests/test_export_trace.py:47`.

**Risque de relecture** : faible a priori, mais à vérifier si la variable
documente une valeur intermédiaire utile à la lecture (déstructuration
partielle) avant suppression.

### RUF013 — `Optional` implicite (33 occurrences)

`scripts/comparer_niveaux_ia.py:209,210,211,213,214,215,455,456,457,459,
460,461,527,528,529,530,531,532,599,600,601,603` ;
`src/rummikub/moteur/description_coup.py:717,759,923(×2)` ;
`src/rummikub/persistance/bilan.py:194,195(×2)` ;
`src/rummikub/persistance/coups_rates.py:109,598` ;
`src/rummikub/persistance/journal.py:160,161`.

**Risque de relecture** : nul en comportement (pure annotation de type,
non vérifiée à l'exécution) — relecture de confort typage seulement.

### EXE001 — scripts avec shebang non exécutables (24 occurrences, permissions non touchées)

Ligne 1 de chacun : `scripts/_campagne_186.py`,
`scripts/_corpus_positions_222.py`, `scripts/_limite_temps_ferme.py`,
`scripts/_mesure_volume_222.py`, `scripts/_rapport_duels.py`,
`scripts/_verif_solveur_exact.py`, `scripts/analyser_coups_rates.py`,
`scripts/analyser_partie.py`, `scripts/analyser_phases.py`,
`scripts/bilan_parties.py`, `scripts/calibrer_echelle.py`,
`scripts/calibrer_niveaux.py`, `scripts/comparer_campagnes_appariees.py`,
`scripts/comparer_solveur_exact.py`, `scripts/echelle_niveaux.py`,
`scripts/generer_corpus_positions_222.py`, `scripts/match_solveurs.py`,
`scripts/mesurer_volume_solveur_222.py`, `scripts/profil_joueur.py`,
`scripts/solveur_exact.py`, `scripts/tournoi_niveaux.py`,
`scripts/verifier_cas_reference.py`, `scripts/verifier_simplicite_expert.py`,
`scripts/verifier_solveur_exhaustif.py`.

**Risque de relecture** : faible — ces scripts sont invoqués via
`python3 scripts/<nom>.py`, pas exécutés directement ; la permission
manquante est probablement volontaire ou sans conséquence. Aucune
permission de fichier n'a été changée dans cette issue.
