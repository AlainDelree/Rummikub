# Journal de parties, bilan et coups ratés de l'IA

## 10. Journal de parties et bilan par niveau d'IA (issue #185)

- **Journal** (`persistance/journal.py`) : optionnel, activé par la clé
  `log_parties` de `config.json` (défaut `False` → aucun overhead, aucun
  fichier créé). Une fois activé, chaque coup transitant par `api.py`
  (pose/pioche/passe/annulation/tour IA) est ajouté au fichier
  `RACINE_DATA/logs_parties/partie_AAAAMMJJ_HHMMSS.json` de la partie en
  cours (au plus `MAX_FICHIERS` fichiers conservés). En-tête : `joueurs`
  (liste de `{nom, est_ia, niveau}`). Chaque action porte désormais
  `auteur_index` (qui a décidé), `action` (`"pose"|"pioche"|"passe"|
  "annulation"`), `nb_tuiles_posees`, `manche` (numéro de manche, issue #203),
  `termine` et `gagnant_index` — une partie dont la DERNIÈRE action n'a pas
  `termine: True` est abandonnée (ou encore en cours) et ignorée du bilan.
  Depuis #203, `termine` n'est vrai qu'à la fin du MATCH (pas d'une manche
  intermédiaire) et `gagnant_index` y désigne alors le vainqueur du match
  (plus haut score cumulé) ; `manche` est absent des journaux antérieurs (lu
  comme une manche unique). Les journaux écrits avant #185
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
- **Script CLI, options complètes** (consolidées ici — certaines
  introduites par les sous-sections ci-dessous) :
  `python scripts/analyser_coups_rates.py [FICHIER] [--tous]
  [--dossier CHEMIN] [--budget SECONDES] [--budget-production SECONDES]
  [--top N] [--joueur NOM] [--tour N] [--depuis AAAAMMJJ]
  [--budget-mesure] [--retenter-inconclusifs]
  [--budget-inconclusifs SECONDES] [--limite-temps-inconclusifs SECONDES]
  [--verifier-reserve-evite-pioche] [--enregistrer-cas-reference]
  [--ecraser]`. Sans argument, analyse le journal le plus récent de
  `RACINE_DATA/logs_parties` ; `--tous` analyse tous les journaux du
  dossier (regroupés par partie, voir 11sexies). Un journal
  illisible/corrompu est signalé et ignoré sans interrompre l'analyse des
  autres. Options introduites par : `--joueur`/
  `--verifier-reserve-evite-pioche`/`--enregistrer-cas-reference`/
  `--budget-mesure`/`--retenter-inconclusifs`/`--budget-inconclusifs`/
  `--limite-temps-inconclusifs` (11bis) ; `--tour` (11ter) ; `--depuis`
  (11quater) ; `--ecraser` (11quinquies).
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

En plus des pioches/passes ratées (§11), `coups_rates.py` détecte aussi les
poses sous-optimales (IA ou joueur humain nommé via `--joueur`), calcule le
budget nécessaire par palier (`--budget-mesure`), dispose d'une
vérification croisée indépendante du solveur par force brute
(`moteur/verif_solveur.py`, `scripts/verifier_solveur_exhaustif.py` — 0
écart sur 300 positions testées, graine 193), distingue une « réserve »
(tuile gardée puis effectivement posée au tour suivant du même joueur)
d'un vrai coup raté, et peut enregistrer de nouveaux cas de référence sans
jamais écraser un fichier existant (`--enregistrer-cas-reference`). Une
décision « inconclusive » (budget épuisé sans rien trouver) n'est jamais
comptée comme un coup non raté ; `--retenter-inconclusifs` les relance à
budget plus grand (`--budget-inconclusifs`, `--limite-temps-inconclusifs`).
Voir CHANGELOG.md, issue #193.

### 11ter. Décrire et mesurer la complexité du coup proposé (issue #196, suite de #193)

Chaque coup raté/sous-optimal affiché est décrit en français
(`description_coup.decrire_coup_ia`/`etapes_coup_ia`, voir
description_coup.md §12) et mesuré simple/complexe (3 combinaisons
touchées ou plus, ou un joker déplacé = complexe), après relabellisation
des tuiles indiscernables du plateau proposé pour éviter un artefact du
solveur. `--tour N` détaille un tour précis. Voir CHANGELOG.md, issue #196.

### 11quater. Classement par taille et filtre par date (issue #198, suite de #196)

En plus du simple/complexe (conservé), chaque coup est classé par taille —
« petit » (1-2 combinaisons touchées), « moyen » (3-5), « grand » (6+) —
avec un indicateur joker séparé, orthogonal à la taille. `--depuis
AAAAMMJJ` ne garde, pour l'analyse, que les journaux dont la date dans le
NOM DE FICHIER est égale ou postérieure. Les accords en français et la
suppression des pronoms genrés, issus de la même issue #198, sont dans
`moteur/description_coup.py` (voir description_coup.md §12ter). Voir
CHANGELOG.md, issue #198.

### 11quinquies. Compter les tuiles réellement posées depuis la main, pas les tuiles déplacées (issue #201, suite de #193)

`nb_tuiles_jouees` est calculé par différence réelle de main (main avant
moins main après le coup), jamais depuis le champ `nb_tuiles_posees` du
journal — historiquement gonflé pour un coup humain qui déplace aussi des
tuiles déjà posées sur le plateau (sans venir de la main). `--ecraser`
lève le garde-fou qui empêche normalement d'écraser un fichier de cas de
référence existant.

**Limite connue, non corrigée (bug potentiel distinct, hors périmètre de
#201)** : le moteur (`moteur/partie.py`, calcul des points de la mise
initiale) additionne lui aussi la valeur de CHAQUE tuile de `ids_tuiles`
trouvée dans une combinaison valide du nouveau plateau — y compris une
tuile DÉPLACÉE, pas posée depuis la main. Un joueur n'ayant pas encore
fait sa mise initiale qui réarrange des combinaisons déjà présentes sur le
plateau (posées par d'autres joueurs) peut donc voir les points de ces
tuiles déplacées compter à tort vers son minimum requis. Voir CHANGELOG.md,
issue #201.

### 11sexies. Relier les fichiers d'une partie reprise et enregistrer la mise initiale (issue #202, suite de #201)

Une partie reprise sur plusieurs fichiers de journal (le cache mémoire du
journal est perdu au redémarrage) est regroupée par `partie_id`
(`persistance/parties_liees.py`) avant toute analyse, aussi bien côté
coups ratés que côté bilan — une partie reprise n'est donc plus comptée
comme abandonnée ni scindée en deux. La mise initiale d'un joueur est lue
directement dans le journal (clé `mises_initiales`) plutôt que déduite de
la seule présence d'une pose antérieure dans le MÊME fichier ; un
historique manquant est marqué « inconnu » (exclu du calcul), jamais
supposé « non faite ». `scripts/verifier_cas_reference.py` vérifie/corrige
le drapeau `mise_initiale_faite` figé dans les cas de référence existants.
Voir CHANGELOG.md, issue #202.
