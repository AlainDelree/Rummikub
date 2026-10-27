# Issue #202 — Suite #201 : relier les fichiers d'une même partie reprise et enregistrer la mise initiale de chaque joueur

À la fermeture puis réouverture du jeu, une partie reprise repart sur un
NOUVEAU fichier de journal (le cache mémoire de `persistance/journal.py` est
perdu au redémarrage). L'ancienne analyse (`persistance/coups_rates.py`)
déduisait qu'un joueur avait fait sa mise initiale de la seule présence d'une
pose antérieure **dans le même fichier** : sur un fichier de reprise, elle
croyait donc à tort la mise initiale non faite, ce qui bride le solveur (avant
la mise, il ne peut pas utiliser le plateau) et fausse le résultat. Mesuré sur
trois cas réels (parties `…183714` tour 28, `…213723` tour 58, `…172338`
tour 16) : supposé avant la mise, le solveur trouvait 0/0/6 tuiles et l'outil
concluait à tort « le joueur bat le solveur » ; supposé après la mise, il
trouve 2/3/7 (autant ou plus que le joueur) — aucun n'était un vrai cas de
solveur battu. Le bilan (`persistance/bilan.py`) était lui aussi faussé : il
comptait le premier fichier d'une partie reprise comme une partie abandonnée
et le second comme une partie distincte.

## Corrections

1. **Journal** (`src/rummikub/persistance/journal.py`) : nouvelle clé
   `mises_initiales` sur chaque action — liste de booléens alignée sur
   `joueurs`, l'état « mise initiale faite » de chaque joueur au moment de
   l'action (helper `_mises_initiales`, calculé d'après l'état du jeu).
   Rétrocompatible : les anciens journaux n'ont pas cette clé. Docstring du
   module complétée.

2. **Nouveau module `src/rummikub/persistance/parties_liees.py`** (pur, sans
   pywebview) : regroupe les fichiers d'une même partie et les fusionne.
   - `grouper_journaux(journaux)` : groupe par `partie_id` (en-tête, conservé
     à la reprise car l'état restauré garde le même `id`), avec repli par
     mêmes joueurs + continuité des numéros de tour si l'identifiant est
     absent ou change ; classe chaque groupe dans l'ordre chronologique.
   - `fusionner_groupe` / `fusionner_journaux` : concatènent les `actions` en
     une seule suite (l'état de départ de la première action d'un fichier de
     reprise devient l'état de la dernière action du fichier précédent) et
     renvoient `debut_present` (faux si le plus ancien fichier commence
     au-delà du tour `SEUIL_DEBUT_PARTIE=2`, c.-à-d. en plein milieu de partie).

3. **Analyse** (`src/rummikub/persistance/coups_rates.py`) :
   - `_mise_initiale_avant(actions, i, idx, debut_present)` : lit la clé
     `mises_initiales` de l'action précédente quand elle existe (journal
     #202+), sinon repli #188 (pose antérieure dans la suite d'actions, qui
     est désormais FUSIONNÉE à travers la reprise). **Historique manquant** :
     si le début de partie est absent et qu'aucune pose n'est observée,
     retourne `None` (INCONNU) — on ne suppose jamais « non faite ».
   - `extraire_decisions_ia`, `extraire_toutes_decisions`,
     `extraire_decisions_ia_toutes`, `extraire_decisions_joueur` acceptent un
     paramètre `debut_present` (défaut `True` : comportement d'origine pour
     les appels directs existants). Une décision indéterminable reçoit
     `moment="inconnu"` et `mise_initiale_inconnue=True`.
   - `analyser_decision` / `analyser_decision_complete` court-circuitent les
     décisions « inconnu » (le solveur n'est pas interrogé — aucune hypothèse
     n'est faite) et portent toutes `mise_initiale_inconnue`.
   - `calculer_resume` / `calculer_resume_complet` comptent les décisions
     « inconnu » à part (`resume[niveau]["inconnu"]["decisions"]`), hors des
     buckets avant/après la mise. `resume_joueur_humain` exclut ces décisions
     des statistiques de style et des listes.

4. **Bilan** (`src/rummikub/persistance/bilan.py`,
   `charger_toutes_parties`) : regroupe les fichiers d'une partie reprise et
   fusionne leurs actions avant `extraire_partie` — la partie est comptée UNE
   SEULE FOIS, avec son nombre de tours réel et toutes les décisions ; le
   premier fichier n'est plus pris pour une partie abandonnée.

5. **Scripts** :
   - `scripts/analyser_coups_rates.py` : regroupe les fichiers par partie
     avant analyse, pour l'IA comme pour `--joueur` (`_charger_parties`,
     `_etiquette_partie`, `_decisions_ia_par_cle`) ; affiche le décompte des
     décisions « mise initiale inconnue » et signale les parties reprises
     réparties sur plusieurs fichiers. `--retenter-inconclusifs`,
     `--budget-mesure` et `--enregistrer-cas-reference` utilisent la même
     clé de partie que l'analyse.
   - `scripts/bilan_parties.py` : bénéficie automatiquement du regroupement
     via `charger_toutes_parties`.
   - **Nouveau** `scripts/verifier_cas_reference.py` (point 5) : vérifie le
     drapeau `mise_initiale_faite` figé dans `tests/donnees/cas_expert_*.json`,
     recalcule le drapeau correct à partir des journaux d'origine regroupés
     (`--dossier`) et corrige les cas faux (`--ecraser`). Les 9 cas existants
     portent déjà `mise_initiale_faite=True` pour le joueur concerné (aucun
     faux dans le sens dangereux). La régénération des cas reste possible via
     `analyser_coups_rates.py --enregistrer-cas-reference --ecraser`, qui
     utilise désormais l'analyse regroupée.

6. **CONTEXTE.md** : nouvelle sous-section §11sexies.

## Tests (nouveaux)

- `tests/test_journal_mise_initiale.py` : la clé `mises_initiales` reflète
  l'état des joueurs, est écrite par `logger_action` et via `ui/api.py`.
- `tests/test_coups_rates_parties_liees.py` : regroupement par `partie_id` et
  repli par continuité ; deux parties distinctes entre les mêmes joueurs non
  reliées ; deux fichiers reliés classant le second « après la mise » alors
  que seul il le classerait « avant » (avec et sans la clé `mises_initiales`) ;
  solveur recevant le bon drapeau bout en bout (coup raté détecté) ; historique
  manquant détecté, décision exclue et comptée à part.
- `tests/test_bilan.py` : une partie reprise en deux fichiers comptée une seule
  fois (tours réels, toutes les décisions) ; premier fichier non pris pour une
  partie abandonnée.

## Garanties

- Ne modifie jamais l'IA ni le moteur de jeu : journal enrichi + lecture/
  analyse/bilan en lecture pure.
- Rétrocompatible avec les anciens journaux (clé `mises_initiales` absente :
  repli #188 sur la suite d'actions fusionnée).
- Suite complète : 203 tests au vert (dont 17 nouveaux), hors Playwright (qui
  nécessite un navigateur).
