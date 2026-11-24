# Issue #263 — Suite #262 : mettre à jour les renvois « CONTEXTE.md §N » vers les fichiers de domaine

## Contexte

Depuis #260, `CONTEXTE.md` n'a plus de sections numérotées : le détail vit
dans `docs/contexte/<domaine>.md`. #262 avait laissé quelques renvois bruts
« (§N) » dans les fichiers de domaine eux-mêmes ; cette issue traite, en
plus, les commentaires/docstrings Python qui citaient encore « CONTEXTE.md
§N », ainsi que deux mentions obsolètes de README.md.

## 1. Correspondance ancienne numérotation → fichier de domaine

Reconstituée à partir de l'ancien `CONTEXTE.md` (commit `f2b46cc`, issue
#260) : §1/§2 → `architecture.md` ; §3/§3bis/§4 → `moteur_regles.md` ;
§6/§7 → `tests_frontend.md` ; §8 → `joker_tactiques.md` ;
§8bis/§8ter/§8quater/§8bis-bis/§17 → `solveur_expert.md` ; §9 →
`scripts_simulation.md` ; §10/§11 → `coups_rates_bilan.md` ; §12 →
`description_coup.md` ; §13 → `pistes_amelioration_ia.md` ;
§14/§15/§18 → `solveur_verification_exacte.md` ; §16 →
`niveaux_ia_calibrage.md` ; §19 → `ia_anti_don_joker.md`. Aucune citation de
« CONTEXTE.md §5 » n'a été trouvée dans le dépôt (ce cas théorique, signalé
par l'issue comme n'ayant plus de cible, ne s'est donc pas présenté).

## 2. Fichiers Python — 26 fichiers, 37 renvois réécrits (commentaires/docstrings uniquement)

Par fichier de domaine cible (un même fichier peut apparaître sous
plusieurs cibles, un renvoi double comptant pour les deux) :
- `pistes_amelioration_ia.md` : 13 renvois, 7 fichiers.
- `tests_frontend.md` : 9 renvois, 9 fichiers.
- `solveur_verification_exacte.md` : 5 renvois, 5 fichiers.
- `niveaux_ia_calibrage.md` : 4 renvois, 4 fichiers.
- `moteur_regles.md` : 3 renvois, 3 fichiers.
- `joker_tactiques.md` : 2 renvois, 1 fichier (`tests/test_ia.py`).
- `scripts_simulation.md` : 1 renvoi (moitié d'un renvoi double avec
  `pistes_amelioration_ia.md` dans `comparer_niveaux_ia.py`).

`src/rummikub/moteur/partie.py` avait un renvoi brut « (§3bis) », sans le
préfixe « CONTEXTE.md » mais dans la même situation (section disparue) :
corrigé par cohérence vers `moteur_regles.md §3bis`.

Laissés **pour décision** (hors scope strict « commentaires et
docstrings », ou ambigus) :
- 5 renvois dans des **chaînes de caractères exécutées** (aide `argparse`,
  message `print`, constante de message d'erreur), donc hors du périmètre
  « commentaires et docstrings uniquement » fixé par l'issue :
  `scripts/analyser_coups_rates.py` lignes 725 et 767,
  `scripts/match_solveurs.py` lignes 632 et 662, `scripts/solveur_exact.py`
  ligne 99 — toutes citent `CONTEXTE.md §14` ou `§13`, et pointeraient vers
  `solveur_verification_exacte.md` / `pistes_amelioration_ia.md` si leur
  correction était un jour demandée.
- `tests/test_ia_anti_don_joker.py` ligne 491 : renvoi brut « §13 » sans
  préfixe « CONTEXTE.md », mais dont le contenu (exception absolue du coup
  gagnant) correspond en fait à `ia_anti_don_joker.md §3`, pas à
  `pistes_amelioration_ia.md §13` — laissé tel quel, décision d'Alain
  nécessaire sur la bonne cible.

## 3. Fichiers de domaine — renvois bruts signalés par #262

- `scripts_simulation.md` ligne 19 : `(§7)` → `(tests_frontend.md §7)`.
- `architecture.md` ligne 41 (bilan.py) : `(§9)` → `(coups_rates_bilan.md
  §10)` — le chiffre d'origine était erroné (le contenu, calcul du bilan
  par niveau d'IA, correspond à l'ancien §10, pas §9) ; ligne 52
  (niveaux.py) : `(§16)` → `(niveaux_ia_calibrage.md §16)`.
- `solveur_expert.md` ligne 67 : `(§8)` → `(joker_tactiques.md §8)`.
- `niveaux_ia_calibrage.md` ligne 190 : `(§8)` → `(joker_tactiques.md §8)`.
- `pistes_amelioration_ia.md` : la reformulation laissée par #262 (« …
  conformément à l'usage habituel pour les campagnes de simulation
  (scripts_simulation.md) ») pointait vers le mauvais fichier — le même
  principe (« pas d'opération longue/bloquante lancée par l'agent sans
  supervision ») est cité ailleurs (`test_export_trace.py`,
  `test_analyser_phases.py`) comme venant de l'ancien §7, donc de
  `tests_frontend.md`. Corrigé en conséquence.

## 4. README.md

Les deux mentions de `CONTEXTE.md` (ligne 89, étapes de build Windows ;
ligne 116, index de documentation technique) décrivent maintenant
`CONTEXTE.md` comme contenant les règles impératives et l'index, le détail
étant dans `docs/contexte/`.

## Vérifications

- `py_compile` sur les 26 fichiers Python modifiés : OK.
- Suite de tests (`pytest -m "not lent"`) : 520 passed, 13 skipped, 23
  deselected.
- Recherche finale (`grep -rn 'CONTEXTE\.md.*§'` sur `*.py`) : ne subsiste
  que les 5 occurrences listées au §2 ci-dessus (chaînes exécutées, hors
  scope), toutes identifiées et non modifiées à dessein.
- `CONTEXTE.md`, `CHANGELOG.md`, `CHANGELOG-<N>.md` et
  `RAPPORT_SOLVEUR_EXACT_204.md` : non modifiés.
- Aucun changement hors commentaires/docstrings dans les fichiers Python
  (vérifié par relecture du diff complet).
