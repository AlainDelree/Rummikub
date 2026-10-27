# Issue #196 — Suite #193 : afficher en français le coup proposé par le solveur et mesurer sa complexité

`scripts/analyser_coups_rates.py` disait combien de tuiles un coup raté/une
pose sous-optimale ratait, jamais QUEL coup le solveur proposait à la place
— impossible de juger à la main si ce coup était simple (à la portée d'un
humain) ou hors de portée. Réutilise `moteur/description_coup.py` (#191)
pour décrire ce coup en français et mesurer sa complexité, sans rien
changer au solveur, à l'IA ni au moteur.

1. **Description du coup proposé** (`persistance/coups_rates.decrire_coup`)
   : texte français + étapes du rejeu pas à pas, calculés à partir du
   plateau avant la décision et du plateau proposé par le solveur. Pour
   chaque décision signalée (coup raté, pose sous-optimale, et pour un
   joueur humain, cas où le solveur est battu), `analyser_decision_complete`
   expose désormais `description_solveur` ; pour le cas « solveur battu »,
   `description_reel` décrit en plus le coup RÉELLEMENT joué par le joueur
   (nouveau champ `plateau_apres_reel` dans `extraire_toutes_decisions`),
   pour comparaison.
2. **Complexité** (`_complexite_coup`) : nombre de combinaisons du plateau
   touchées, présence d'un échange de joker, nombre d'étapes réelles. Un
   coup touchant 3 combinaisons ou plus, ou déplaçant un joker, est
   `"complexe"` ; sinon `"simple"`. `calculer_resume_complet` et
   `resume_joueur_humain` ajoutent une répartition `coups_simples`/
   `coups_complexes` par niveau d'IA et pour un joueur humain.
3. **Option `--tour N`** : détaille un tour précis (nom du joueur, tuiles
   posées en réalité vs proposées par le solveur, description complète),
   en plus de l'affichage habituel (top 5, listes `--joueur`).
4. **Artefact du solveur corrigé en amont** (`_relabeler_tuiles_
   indiscernables`) : le solveur (`moteur/solveur.py`) ne raisonne que sur
   des emplacements (couleur, valeur), jamais sur l'identifiant physique
   exact d'une tuile — il peut proposer un plateau où deux tuiles déjà
   posées, strictement indiscernables, échangent leurs identifiants sans
   aucun changement réel. `moteur/description_coup.py`, qui suit chaque
   tuile par son identifiant, y lisait un cycle de dépendance et plantait
   (`KeyError`, cas réel : `cas_expert_bruno_tour57.json`). Corrigé
   uniquement côté `persistance/coups_rates.py` (relabellisation d'une
   copie du plateau avant l'appel au moteur) — aucun changement au moteur,
   au solveur ni à l'IA, conformément au périmètre de l'issue.

## Fichiers touchés

- `src/rummikub/persistance/coups_rates.py` : + `decrire_coup`,
  `_complexite_coup`, `_relabeler_tuiles_indiscernables`, champ
  `plateau_apres_reel` ; `analyser_decision_complete` expose
  `description_solveur`/`description_reel` ; `calculer_resume_complet` et
  `resume_joueur_humain` ajoutent la répartition simple/complexe.
- `scripts/analyser_coups_rates.py` : affichage des descriptions +
  complexité (top N, `--joueur`), nouvelle option `--tour`.
- `tests/test_coups_rates_description.py` (nouveau) : coup raté simple,
  pose sous-optimale complexe avec joker, joueur bat le solveur (description
  proposée + réelle comparées), régression sur l'artefact de tuiles
  indiscernables (y compris bout en bout sur le cas Bruno réel).
- `CONTEXTE.md` : + section 11ter.

## Non fait / limites

- Non exécuté sur les vrais journaux de `RACINE_DATA/logs_parties` (issue
  traitée dans un worktree isolé sans journaux réels, comme #193) : les
  chiffres réels de complexité restent à produire par Alain lui-même.
