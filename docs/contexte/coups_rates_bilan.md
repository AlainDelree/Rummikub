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

### 11bis. Fiabilisation de l'analyse (issue #193, suite de #188)

L'analyse ci-dessus (#188) ne regardait que les pioches/passes d'une IA, avec
un seul budget fixe, et ne vérifiait jamais le solveur lui-même. #193 lève
ces trois limites, toujours dans `persistance/coups_rates.py` (fonctions
ajoutées, celles de #188 ci-dessus restent inchangées à l'identique) :

- **Poses sous-optimales** (`extraire_toutes_decisions`,
  `analyser_decision_complete`) : pour une pose (IA ou humain), compare le
  nombre de tuiles RÉELLEMENT posées (différence chevalet avant/après dans le
  journal) au maximum trouvé par le solveur. Trois issues possibles selon le
  signe de l'écart : `pose_sous_optimale` (le solveur fait mieux),
  `joueur_bat_solveur` (le joueur a posé PLUS que le solveur même au budget
  généreux — n'arrive en pratique que pour un humain, jamais pour une IA qui
  ne peut pas dépasser le solveur qui l'a produite), ou rien (pose optimale).
  `extraire_decisions_ia_toutes` généralise l'extraction aux poses pour une
  IA ; `extraire_decisions_joueur(data, nom)` fait de même pour un joueur
  HUMAIN nommé (option `--joueur` du script, voir plus bas) — les deux
  gèrent une pose annulée puis rejouée (même numéro de tour réutilisé,
  dédoublonnage par dernière occurrence, comme `bilan.py`) en reconstituant
  l'état même à travers une entrée `"annulation"` du journal (qui porte
  elle aussi un instantané complet). `calculer_resume_complet` agrège par
  niveau/phase en distinguant `pioche_passe_ratees` et `poses_sous_optimales`
  (avec le total de tuiles manquantes) ; `top_coups_rates_complet` classe les
  deux catégories ensemble.
- **Budget nécessaire** (`budget_necessaire`, `repartition_budget_necessaire`,
  `BUDGETS_SERIE_DEFAUT = (1.5, 3, 6, 10, 20, 30)` secondes) : pour un coup
  raté/une pose sous-optimale déjà identifié, cherche le plus petit budget de
  la série qui retrouve le même nombre de tuiles — coûteux (relance le
  solveur par palier), donc calculé seulement à la demande
  (`--budget-mesure` du script), jamais en routine sur toute une campagne.
- **Budget par défaut généreux (10 s) et avertissement** : le budget généreux
  par défaut du script reste 10 s (inchangé depuis #188, déjà conforme) ;
  `scripts/analyser_coups_rates.py` affiche désormais un AVERTISSEMENT
  explicite si l'utilisateur choisit `--budget` < 10 s, et répète dans le
  rapport final qu'une décision « inconclusive » (budget épuisé sans rien
  trouver, `BudgetDepasse`) n'est PAS un coup non raté — le nombre réel de
  coups ratés reste incertain dans l'intervalle
  `[coups_rates ; coups_rates + inconclusifs]` tant que les inconclusifs ne
  sont pas tous tranchés. `--retenter-inconclusifs` relance ces décisions
  avec un budget plus grand (`--budget-inconclusifs`, défaut 30 s) sous une
  limite de durée TOTALE ferme pour toute la passe
  (`--limite-temps-inconclusifs`, défaut 300 s) — dépassée, elle s'arrête en
  signalant combien de décisions n'ont pas pu être retentées, plutôt que de
  risquer une durée illimitée.
- **Vérification croisée indépendante du solveur** (`moteur/verif_solveur.py`,
  nouveau module pur) : `max_tuiles_posables_exhaustif(plateau, chevalet)`
  est une seconde implémentation volontairement lente (force brute sans
  AUCUNE des optimisations de `solveur.py` : essaie tous les sous-ensembles
  du chevalet du plus grand au plus petit, et pour chacun toutes les façons
  de partitionner plateau+sous-ensemble en combinaisons valides), praticable
  uniquement sur de petites positions. `generer_position_aleatoire(rng, ...)`
  fabrique une position aléatoire reproductible (graine fixe) : un petit
  plateau (0 ou une combinaison de 3-4 tuiles) et une petite main (1 à 5-6
  tuiles, jokers rares). `scripts/verifier_solveur_exhaustif.py --nb --seed
  --budget-solveur` compare les deux sur `--nb` positions et signale tout
  écart (sans jamais corriger le solveur automatiquement — seulement un bug
  évident le justifierait, voir l'issue). **Résultat sur 300 positions,
  graine 193 : 0 écart, 0 inconclusive** (`tests/test_verif_solveur.py`
  fixe une seconde campagne, graine 193, 60 positions, même conclusion) — le
  solveur retrouve bien le maximum réel sur toutes les positions testées à
  cette échelle ; ceci ne prouve rien sur les plateaux de taille réelle
  (largement hors de portée de la recherche exhaustive), seulement sur le
  petit périmètre couvert par les positions générées.
- **Cas de référence connus, tests robustes au temps de calcul de la
  machine** : `tests/test_coups_rates_extensions.py` fabrique une décision
  de pose (une seule tuile jouée) à partir de
  `tests/donnees/cas_expert_bruno_tour57.json` (`attendu_min_tuiles: 3`) et
  vérifie que `analyser_decision_complete` la détecte comme
  `pose_sous_optimale` (2 tuiles manquantes) avec un budget très généreux
  (15 s, large marge), et — point important de l'issue — qu'un budget
  délibérément minuscule (0,05 s) la classe `inconclusif`, JAMAIS « pose
  optimale » : ne jamais sous-compter un coup raté faute de budget plutôt
  que de l'afficher comme incertain.
- **Analyse d'un joueur HUMAIN** (`--joueur "Nom"` du script,
  `extraire_decisions_joueur`, `resume_joueur_humain`) : même analyse que
  pour une IA, mais deux listes séparées — (a) `coups_peut_etre_rates` (pose
  partielle ou pioche/passe alors qu'un coup existait, à vérifier à la main,
  jamais une certitude pour un humain qui peut avoir d'autres raisons de
  jouer ainsi) et (b) `solveur_bat` (le joueur a posé PLUS de tuiles que le
  solveur même au budget généreux — ce sont les cas les plus utiles pour
  améliorer le solveur, voir l'avertissement sur le gel des combinaisons en
  tête de fichier). Quelques statistiques de style PUREMENT DESCRIPTIVES
  (`resume["style"]`) : part des poses au maximum du solveur, tuiles posées
  en moyenne par tour contre le maximum, part des pioches alors qu'un coup
  existait, nombre de jokers joués et nombre moyen de tours d'attente avant
  d'être joués. **Aucune conclusion stratégique à en tirer sur un petit
  échantillon de parties** (rappelé dans le rapport du script) : ces
  chiffres ne sont là que pour reconnaître un style, pas pour le juger.
- **Technique de la « réserve » jamais confondue avec un coup raté**
  (`detecter_reserves_joueur`) : parmi les poses partielles/pioches avec
  coup possible d'un joueur humain, une tuile que le solveur aurait posée
  mais que le joueur a gardée, puis effectivement posée au tour SUIVANT de
  ce même joueur (même partie), est une « réserve réussie » ; si elle n'est
  pas posée au tour suivant (en main ou plus posable), c'est une « réserve
  perdue » — les deux catégories sont retirées des listes (a)/(b) ci-dessus
  (`indices_a_exclure`), jamais comptées comme coup raté ni comme cas où le
  solveur est battu. `--verifier-reserve-evite-pioche` ajoute, pour chaque
  réserve réussie, un appel solveur supplémentaire (contre-factuel : sans
  la tuile réservée, le solveur trouve-t-il encore un coup au tour suivant ?)
  — coûteux, désactivé par défaut. **Limite assumée** : la détection ne
  regarde que le tour immédiatement SUIVANT du même joueur (pas une fenêtre
  plus large), et ne distingue pas une vraie réserve stratégique d'un oubli
  qui se résout par hasard au tour suivant — a posteriori les deux sont
  indiscernables (déjà noté dans l'issue).
- **Enregistrement de nouveaux cas de référence** (`--enregistrer-cas-reference`
  du script) : écrit les coups ratés/poses sous-optimales les plus
  importants (IA) ou les cas où le joueur bat le solveur (`--joueur`) au
  même format que `tests/donnees/cas_expert_*.json` (clé
  `attendu_min_tuiles` = résultat du solveur pour l'IA, nombre de tuiles
  réellement posées par le joueur pour un humain) — **n'écrase jamais un
  fichier existant** (vérifié avant écriture).
- **Non exécuté sur les vrais journaux de `RACINE_DATA/logs_parties`** :
  cette issue a été traitée dans un **worktree isolé** dont le périmètre
  autorisé ne contient AUCUN journal réel (`data/logs_parties` du worktree
  est vide) — les vrais journaux de parties jouées vivent hors de ce
  périmètre. Le script a été vérifié de bout en bout (tous les modes, y
  compris `--joueur`, `--budget-mesure`, `--retenter-inconclusifs`,
  `--enregistrer-cas-reference`) sur des journaux fabriqués à la main, mais
  **les chiffres réels sur les parties déjà jouées (point 6 de l'issue)
  restent à produire par Alain lui-même**, en relançant
  `python scripts/analyser_coups_rates.py --tous --budget 10` (et, pour un
  joueur humain, `--joueur "Alain"`) depuis une install courante du projet
  (pas ce worktree).
- Tests (en plus de `test_coups_rates.py`, #188, inchangé) :
  `tests/test_coups_rates_extensions.py` (poses sous-optimales, joueur bat
  le solveur, résumé étendu, budget nécessaire, détection de réserve
  réussie/perdue, cas de référence Bruno avec budget suffisant/insuffisant) ;
  `tests/test_verif_solveur.py` (recherche exhaustive sur cas unitaires +
  campagne aléatoire à graine fixe contre le solveur de production).

### 11ter. Décrire et mesurer la complexité du coup proposé (issue #196, suite de #193)

#188/#193 ci-dessus disaient COMBIEN de tuiles un coup raté/une pose
sous-optimale ratait, jamais QUEL coup le solveur proposait à la place —
impossible donc de juger à l'œil si le coup raté était à la portée d'un
humain. #196 réutilise `moteur/description_coup.py` (#189/#191, voir §12)
pour décrire ce coup en français et en mesurer la complexité, toujours dans
`persistance/coups_rates.py` (aucun changement au solveur, à l'IA ni au
moteur).

- **Description** (`decrire_coup(plateau_avant, plateau_apres, nom=None)`) :
  appelle `description_coup.decrire_coup_ia` (texte) et
  `description_coup.etapes_coup_ia` (étapes du rejeu pas à pas) à partir du
  plateau avant la décision (`decision["etat"]["plateau"]`) et du plateau
  proposé par le solveur (`coup["nouveau_plateau"]`). Retourne
  `{"texte", "etapes", "complexite"}`.
- **Complexité** (`_complexite_coup`) : nombre de combinaisons du plateau
  touchées (défaites + créées + modifiées), présence d'au moins un échange
  de joker, nombre d'étapes RÉELLES du rejeu (celles à titre vide, comme
  `nbChangementsPasAPas` côté front-end). Un coup est `"complexe"` s'il
  touche 3 combinaisons ou plus, ou déplace un joker ; sinon `"simple"`
  (point 3 de l'issue).
- **Artefact du solveur corrigé en amont, jamais dans le moteur**
  (`_relabeler_tuiles_indiscernables`) : `moteur/solveur.py` ne raisonne que
  sur des « emplacements » (couleur, valeur), jamais sur l'identifiant
  physique exact d'une tuile (voir sa docstring) — il peut donc proposer un
  plateau où deux tuiles déjà posées, strictement indiscernables (même
  valeur/couleur, non joker), ont échangé leurs identifiants entre deux
  combinaisons SANS aucun changement réel. `description_coup.py`, qui suit
  chaque tuile par son identifiant, y lisait un cycle de dépendance (sa
  propre docstring : « dépendance cyclique improbable ») qui cassait son tri
  causal et plantait (`KeyError` dans `etapes_coup_ia`) — jamais rencontré
  avec un coup réellement joué (déterministe), mais systématique avec
  certains coups PROPOSÉS par le solveur (cas réel : `cas_expert_
  bruno_tour57.json`, voir #193). `decrire_coup` relabellise une COPIE du
  plateau proposé avant d'appeler le moteur : toute combinaison d'après dont
  le contenu (multiset valeur/couleur/joker, en ignorant l'identifiant) est
  IDENTIQUE à une combinaison d'avant encore non appariée reprend
  exactement les identifiants de cette dernière — elle devient un pur no-op
  pour le moteur, ce qui élimine l'artefact sans jamais perdre
  d'information (deux tuiles indiscernables échangées sans effet visible
  restent, par définition, indiscernables pour le joueur). Ne touche JAMAIS
  une combinaison contenant une tuile posée depuis la main (changement
  réel, jamais un artefact).
- **Intégration dans `analyser_decision_complete`** : `description_solveur`
  (texte + étapes + complexité du coup proposé) est calculé pour toute
  décision signalée (`coup_rate`, `pose_sous_optimale` ou
  `joueur_bat_solveur`) où le solveur a effectivement proposé un plateau ;
  `None` sinon (y compris si le solveur ne trouve absolument aucun coup).
  Pour `joueur_bat_solveur` uniquement, `description_reel` décrit en plus,
  de la même façon, le coup RÉELLEMENT joué par le joueur à partir de
  `plateau_apres_reel` (nouveau champ de `extraire_toutes_decisions`, le
  plateau tel qu'enregistré par l'action de pose elle-même) — pour
  comparaison. `calculer_resume_complet` et `resume_joueur_humain` ajoutent
  une répartition `coups_simples`/`coups_complexes` par niveau d'IA et pour
  un joueur humain (point 3 de l'issue) : c'est cette répartition qui dit si
  les coups ratés sont à la portée d'un humain.
- **Script CLI** : chaque coup raté/pose sous-optimale affiché (top N,
  listes (a)/(b) de `--joueur`) affiche désormais le texte français, les
  étapes et la complexité du coup proposé (et, pour `--joueur`, du coup
  réellement joué en cas (b)) via `afficher_description_coup`. Nouvelle
  option `--tour N` (point 2 de l'issue) : détaille un tour précis (nom du
  joueur, tuiles posées en réalité vs proposées par le solveur, description
  complète) — EN PLUS de l'affichage habituel, jamais à la place
  (`_detailer_tour`/`afficher_detail_tour`).
- Tests : `tests/test_coups_rates_description.py` — coup raté simple
  (journal fabriqué + vrai solveur, classé `"simple"`) ; pose sous-optimale
  complexe avec échange de joker (solveur simulé, classée `"complexe"`) ;
  joueur bat le solveur (description du coup proposé ET du coup réellement
  joué, comparées) ; régression ciblée sur l'artefact de tuiles
  indiscernables (`_relabeler_tuiles_indiscernables`, y compris le cas où il
  ne doit JAMAIS toucher une tuile posée depuis la main) ; régression bout
  en bout sur le vrai cas de référence Bruno (`cas_expert_bruno_tour57.json`)
  qui plantait avant la correction.

### 11quater. Classement par taille et filtre par date (issue #198, suite de #196)

Le simple/complexe binaire de #196 ci-dessus regroupait à tort, dans
« complexe », un échange de joker trivial (visible à l'œil par un humain,
ex. un échange direct) ET un coup à une douzaine de combinaisons — rendant
impossible de dire si les coups ratés d'Expert sont à la portée d'un
humain. #198 affine cette mesure et ajoute un filtre par date, toujours
dans `persistance/coups_rates.py` (aucun changement au solveur, à l'IA ni
au moteur) :

- **Classement par taille** (`_taille_coup`, nouveau champ `complexite["taille"]`
  de `_complexite_coup`) : d'après `nb_combinaisons_touchees` (défaites +
  créées + modifiées, après ignoré des échanges de tuiles identiques —
  inchangé depuis #197) — `"petit"` (1 ou 2), `"moyen"` (3 à 5), `"grand"`
  (6 ou plus). L'indicateur `a_joker` (déplacement d'au moins un joker) et
  `nb_etapes` restent des champs séparés, orthogonaux à la taille (un coup
  peut être « petit avec joker », ex. un échange direct). L'ancien
  `categorie` (`"simple"`/`"complexe"`, #196) est **conservé tel quel** pour
  la continuité des mesures déjà produites — les deux coexistent dans
  `complexite`.
- **Agrégation par taille/joker** (`calculer_resume_complet`,
  `resume_joueur_humain`) : en plus de `coups_simples`/`coups_complexes`
  (conservés), chaque bucket par niveau/phase (IA) ou le résumé d'un joueur
  humain porte désormais `coups_petits`/`coups_moyens`/`coups_grands` et
  `coups_avec_joker`/`coups_sans_joker` (clés `petits`/`moyens`/`grands`/
  `avec_joker`/`sans_joker` dans `resume_joueur_humain["complexite"]`).
- **Script CLI** : `afficher_tableau_tailles` (mode IA) affiche, après le
  résumé habituel, un tableau toutes phases confondues — une ligne par
  niveau d'IA, colonnes petit/moyen/grand/joker/sans joker ; le mode
  `--joueur` affiche le même tableau (une seule ligne) dans
  `afficher_resume_joueur`. `afficher_description_coup` affiche désormais la
  taille de chaque coup détaillé (top N, `--tour`, listes (a)/(b)) en plus
  de l'ancienne catégorie, explicitement marquée « conservée ».
- **Filtre par date** (`filtrer_journaux_depuis(chemins, depuis)`, nouvelle
  option `--depuis AAAAMMJJ` du script) : ne garde, parmi les journaux
  `partie_AAAAMMJJ_HHMMSS.json` (voir `persistance/journal.py`), que ceux
  dont la date dans le NOM DE FICHIER (jamais le contenu — fonction pure,
  aucune lecture de fichier) est égale ou postérieure à `depuis` — permet
  de limiter l'analyse aux parties jouées avec la dernière version d'une
  IA plutôt qu'un mélange de versions successives. Un nom hors du format
  attendu est exclu par prudence (pas de date fiable à comparer). Le script
  affiche sur stderr le nombre de journaux retenus après filtrage ; le
  filtre s'applique avant le choix du « plus récent » par défaut (donc le
  plus récent PARMI les journaux retenus), mais jamais à un fichier unique
  passé explicitement en argument.
- **Accords en français et suppression des pronoms genrés** : voir §12,
  nouvelle sous-section 12ter — modifications dans
  `moteur/description_coup.py`, pas dans ce module.
- Tests : `tests/test_coups_rates_description.py` (ajoutés à la suite de
  ceux de #196) — un coup petit sans joker, un petit AVEC joker (échange
  direct), un moyen sans joker (démantèlement en 3), un grand avec joker
  (reprise du cas Bruno/Expert en chaîne de §12) ; bout en bout,
  `calculer_resume_complet` répartit deux décisions résolues par un faux
  solveur dans les bons compteurs petit/moyen + simple/complexe conservés.
  `tests/test_coups_rates_filtre_date.py` (nouveau fichier) — sans
  `depuis` renvoie tout inchangé ; `depuis` garde la date exacte et les
  plus récentes, exclut tout ce qui est plus ancien, garde tout si `depuis`
  précède la plus ancienne ; un nom hors format est exclu dès qu'un filtre
  est demandé.

### 11quinquies. Compter les tuiles RÉELLEMENT posées depuis la main, pas les tuiles déplacées (issue #201, suite de #193)

**Bug corrigé** : pour un coup HUMAIN, `data["ids_tuiles"]` envoyé par
`jeu.js` (variable `tuilesCeTour`, voir `jeu.js:prendreTuileTapis`) mélange
les tuiles venues de la main ET celles du plateau déplacées pendant le
tour (le jeu s'en sert pour colorer « tuile du tapis déplacée ce tour »,
pas pour compter ce qui a été posé). Avant #201, `ui/api.py:jeu_jouer_coup`
journalisait `nb_tuiles_posees = len(data["ids_tuiles"])` : pour un coup
humain qui déplace des tuiles déjà posées, ce compte était donc GONFLÉ par
rapport au nombre réel de tuiles sorties de la main — faussant, dans
`persistance/coups_rates.py`, les listes « solveur battu », les poses
sous-optimales (masquées par l'inflation) et les statistiques de style
d'`--joueur` (cas réel observé : `posé 18, solveur 7`, alors que la
description du coup montrait 4 tuiles réellement sorties de la main). Pour
une IA, `ids_tuiles` vient du solveur (`moteur/solveur.py::resoudre_coup`,
qui le nomme explicitement `ids_main`) et ne contient JAMAIS de tuile
déplacée : son compte n'a jamais été affecté.

- **Analyse corrigée à la source** (`extraire_toutes_decisions`, qui
  alimente TOUTE l'analyse de #193/#196/#198 ci-dessus, IA comme humain) :
  `nb_tuiles_jouees` n'est plus lu depuis le champ `nb_tuiles_posees` du
  journal, mais calculé comme `len(ids_tuiles_reelles)` — la différence
  entre la main d'avant et la main d'après le coup, déjà calculée pour
  `ids_tuiles_reelles` (utilisée par `detecter_reserves_joueur`). Ce calcul
  corrige AUSSI les journaux ANCIENS (écrits avant la correction du journal
  ci-dessous) : il ne dépend jamais du champ `nb_tuiles_posees`/
  `nb_tuiles_deplacees` du journal, seulement des deux instantanés de main
  déjà présents dans tout journal post-#185. Une seule fonction corrigée
  répare donc, en cascade, `analyser_decision_complete` (détection
  `joueur_bat_solveur`/`pose_sous_optimale`), `resume_joueur_humain`
  (statistiques de style), `detecter_reserves_joueur`, et
  `_enregistrer_cas_reference` (`attendu_min_tuiles` des cas humains).
- **Journal corrigé** (`ui/api.py:jeu_jouer_coup`, `persistance/journal.py`)
  : capture la main du joueur AVANT d'appeler `jouer_tour` (qui la mute en
  place), puis journalise dans `nb_tuiles_posees` le nombre de tuiles de
  `ids_tuiles` réellement présentes dans cette main d'avant, et dans la
  nouvelle clé `nb_tuiles_deplacees` le reste (tuiles du plateau déplacées
  sans venir de la main). `logger_action` accepte le nouveau paramètre
  `nb_tuiles_deplacees` (défaut 0, rétrocompatible) ; un journal écrit avant
  #201 n'a simplement pas cette clé (lue comme 0 par convention, mais en
  pratique AUCUN lecteur ne s'appuie sur elle — voir point suivant).
  `ui/api.py:jeu_ia_jouer` (coup d'IA) reste inchangé : son calcul
  (`len(res_ia["ids_tuiles"])`) était déjà correct.
- **Autres lecteurs de `nb_tuiles_posees` vérifiés** : `persistance/bilan.py
  :extraire_partie` recopie ce champ dans `decisions[i]["nb_tuiles_posees"]`
  mais ne s'en sert JAMAIS dans `calculer_bilan`/`_finaliser` (seuls
  `action`/`moment` sont lus) — aucune adaptation nécessaire. Les deux
  vérifications `(a.get("nb_tuiles_posees") or 0) > 0` de
  `extraire_decisions_ia`/`extraire_toutes_decisions` (détection de
  « mise initiale déjà faite ») restent correctes : une pose RÉUSSIE
  implique toujours que `jouer_tour` a validé la mise initiale (ou qu'elle
  l'était déjà), donc `ids_tuiles` — gonflé ou non — y est toujours non vide ;
  ces vérifications ne portent que sur la présence d'une pose antérieure,
  jamais sur son nombre exact.
- **Usage de `ids_tuiles` par le moteur, VÉRIFIÉ, NON MODIFIÉ** (point 3 de
  l'issue — `moteur/partie.py`) : `jouer_tour(etat, ids_tuiles_posees,
  nouveau_plateau)` ne fait AUCUNE hypothèse sur l'origine des ids reçus.
  Étape 4 (retrait du chevalet) filtre `chevalet` par appartenance à
  `ids_posees` : un id qui n'est pas dans le chevalet (tuile déplacée, pas
  posée) n'y correspond simplement à rien et ne cause aucun effet. Étape 3
  (`_points_tuiles_posees(plateau, ids_posees)`, calcul des points de la
  MISE INITIALE) additionne la valeur de CHAQUE id de `ids_posees` trouvé
  dans une combinaison valide du nouveau plateau — **y compris un id de
  tuile DÉPLACÉE, pas posée depuis la main** : si un joueur n'ayant pas
  encore fait sa mise initiale rearrange des combinaisons déjà présentes
  sur le plateau (posées par d'autres joueurs lors de tours précédents) en
  y ajoutant peu de valeur depuis sa main, les points des tuiles déplacées
  s'additionnent À TORT à ceux de ses propres tuiles pour juger s'il
  atteint le minimum requis. **Signalé ici comme un bug potentiel de la
  RÈGLE DE MISE INITIALE** (distinct du bug de journalisation corrigé
  ci-dessus), mais PAS corrigé dans cette issue : son périmètre est
  volontairement limité à l'analyse/au journal (voir consigne de l'issue —
  « ne rien modifier au comportement du jeu sauf bug évident ») ; il
  nécessite d'exposer au moteur une distinction main/plateau que
  `jeu_jouer_coup` calcule désormais (`ids_main_avant`, voir ci-dessus) mais
  ne transmet pas à `jouer_tour`, qui continue de recevoir la liste brute
  `ids_tuiles` — à traiter dans une future issue dédiée si Alain le
  confirme. En pratique rare : il faut qu'un joueur n'ayant pas encore posé
  choisisse de manipuler le plateau plutôt que de simplement poser depuis
  sa main.
- **Cas de référence humains régénérables** (`--ecraser` du script,
  `_enregistrer_cas_reference(..., ecraser=False)`) : le comportement par
  défaut (ne jamais écraser un fichier `cas_expert_*.json` existant) est
  conservé ; la nouvelle option `--ecraser` lève ce garde-fou pour
  régénérer `tests/donnees/cas_expert_humain_*.json` (dont les trois
  fichiers déjà présents portent l'ancien `attendu_min_tuiles` gonflé,
  jamais vérifié par un test automatisé — voir `test_ia.py`, liste
  paramétrée de non-régression #199, qui n'utilise que `etat`/`idx` de ces
  fichiers, jamais leur `attendu_min_tuiles`). Marche à suivre pour Alain
  (hors de ce worktree, sur les vrais journaux de `RACINE_DATA/logs_parties`
  — absents de ce worktree isolé, voir note de #193 ci-dessus) :
  `python scripts/analyser_coups_rates.py --tous --joueur "Alain"
  --enregistrer-cas-reference --ecraser`. Le solveur n'est jamais modifié.
- Tests : `tests/test_coups_rates_tuiles_main.py` (nouveau fichier) —
  reproduit le cas réel (journal `nb_tuiles_posees=18`, main qui ne perd
  que 4 tuiles) et vérifie que l'analyse compte 4 et classe le coup en
  `pose_sous_optimale` (jamais `joueur_bat_solveur`, contrairement à ce que
  le champ gonflé aurait produit) ; un journal ANCIEN sans `nb_tuiles_posees`
  ni `nb_tuiles_deplacees` reste lisible ; un journal d'IA cohérent où le
  nombre recalculé coïncide avec le champ du journal.
  `tests/test_api_journal.py` (nouveau fichier) — appelle réellement
  `Api.jeu_jouer_coup` sur un coup qui fusionne deux combinaisons déjà
  posées (3 tuiles déplacées) en y ajoutant 1 tuile de la main, et vérifie
  que le journal écrit porte `nb_tuiles_posees=1`, `nb_tuiles_deplacees=3`.

### 11sexies. Relier les fichiers d'une partie reprise et enregistrer la mise initiale (issue #202, suite de #201)

- **Problème corrigé** : à la fermeture puis réouverture du jeu, une partie
  reprise repart sur un NOUVEAU fichier de journal (le cache mémoire de
  `persistance/journal.py` est perdu au redémarrage). L'ancienne analyse
  déduisait la mise initiale d'un joueur de la seule présence d'une pose
  antérieure **dans le même fichier** : sur un fichier de reprise, elle croyait
  donc à tort la mise initiale non faite, ce qui bride le solveur (avant la
  mise, il ne peut pas utiliser le plateau) et fausse le résultat. Mesuré sur
  trois cas réels où le solveur, supposé avant la mise, trouvait 0/0/6 tuiles
  et concluait à tort « le joueur bat le solveur » ; supposé après la mise, il
  trouve 2/3/7 (autant ou plus que le joueur) — aucun n'était un vrai cas de
  solveur battu.
- **Journal** (`persistance/journal.py`, `_mises_initiales`) : chaque action
  porte désormais `mises_initiales`, liste de booléens alignée sur `joueurs`
  (état « mise initiale faite » de chaque joueur au moment de l'action,
  d'après l'état du jeu). Rétrocompatible : les anciens journaux n'ont pas
  cette clé.
- **Regroupement** (`persistance/parties_liees.py`, nouveau module pur) :
  `grouper_journaux(journaux)` regroupe les fichiers d'une même partie par
  `partie_id` (en-tête — conservé à la reprise, l'état restauré gardant le
  même `id`), avec repli par mêmes joueurs + continuité des numéros de tour
  si l'identifiant est absent/change ; `fusionner_groupe`/`fusionner_journaux`
  concatènent les `actions` dans l'ordre chronologique en une seule suite.
  L'état de départ de la première action d'un fichier de reprise est alors
  l'état enregistré à la dernière action du fichier précédent (reconstitution
  inchangée dans `coups_rates.py`/`bilan.py`). `fusionner_groupe` renvoie
  aussi `debut_present` (faux si le plus ancien fichier commence au-delà du
  tour `SEUIL_DEBUT_PARTIE=2`, c.-à-d. en plein milieu de partie).
- **Déduction de la mise initiale** (`coups_rates.py`,
  `_mise_initiale_avant`) : si l'action précédente porte `mises_initiales`
  (journal #202+), elle est lue directement ; sinon repli #188 (pose
  antérieure dans la suite d'actions FUSIONNÉE). **Historique manquant**
  (point 3) : quand le début de partie est absent (`debut_present=False`) et
  qu'aucune pose n'est observée, l'état est INCONNU — on ne suppose JAMAIS
  « non faite » : la décision reçoit `moment="inconnu"` et
  `mise_initiale_inconnue=True`, est exclue du calcul (le solveur n'est pas
  interrogé) et comptée à part dans le résumé (`resume[niveau]["inconnu"]`).
- **Bilan** (`bilan.py`, `charger_toutes_parties`) : regroupe les fichiers
  d'une partie reprise et fusionne leurs actions avant `extraire_partie` — la
  partie est comptée UNE SEULE FOIS, avec son nombre de tours réel et toutes
  les décisions ; le premier fichier n'est plus pris pour une partie
  abandonnée (seule la dernière action de la partie fusionnée décide si elle
  est terminée).
- **Scripts** : `scripts/analyser_coups_rates.py` (IA et `--joueur`) regroupe
  désormais les fichiers par partie avant analyse (`_charger_parties`,
  `_decisions_ia_par_cle`) et affiche le décompte des décisions « mise
  initiale inconnue » ; `scripts/bilan_parties.py` en bénéficie via
  `charger_toutes_parties`. Nouveau `scripts/verifier_cas_reference.py`
  (point 5) : vérifie le drapeau `mise_initiale_faite` figé dans
  `tests/donnees/cas_expert_*.json`, recalcule le drapeau correct à partir des
  journaux d'origine regroupés (`--dossier`) et corrige les cas faux
  (`--ecraser`). Les 9 cas existants portent déjà `mise_initiale_faite=True`
  pour le joueur concerné (aucun faux dans le sens dangereux False→True). La
  régénération des cas eux-mêmes reste possible via
  `analyser_coups_rates.py --enregistrer-cas-reference --ecraser` (qui utilise
  désormais l'analyse regroupée).
- **Ne modifie jamais l'IA ni le moteur** : journal enrichi + lecture/analyse.
- Tests : `tests/test_journal_mise_initiale.py` (nouveau champ `mises_initiales`
  dans le journal et via `ui/api.py`), `tests/test_coups_rates_parties_liees.py`
  (regroupement par `partie_id` et repli par continuité ; deux fichiers reliés
  classant le second « après la mise » alors que seul il le classerait « avant »
  — avec et sans la clé ; solveur recevant le bon drapeau bout en bout ;
  historique manquant exclu et compté à part), et dans `tests/test_bilan.py`
  (une partie reprise en deux fichiers comptée une seule fois, premier fichier
  non pris pour une partie abandonnée).

