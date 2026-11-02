# Issue #226 — Mesure : où se décident les parties (trace par tour et analyse par phases)

Issue de **MESURE uniquement** : aucun changement de comportement du jeu,
des niveaux, du solveur ni de l'interface. Motivation : sur 600 matchs
Expert/Champion du Monde (#221 + #225), aucune des deux stratégies de fin de
partie n'a jamais changé un coup, et 58 % des tours de fin de partie sont des
pioches — avant de choisir les prochaines pistes de l'arbre (CONTEXTE.md
§13 : Ouverture, Tuiles vivantes, Modèle adverse, Course, Rétention), il
fallait savoir OÙ se décident réellement les manches.

## 1. Trace par tour (`scripts/comparer_niveaux_ia.py`)

- Nouvelle option `--export-trace FICHIER`, **indépendante** d'
  `--export-resultats` et **désactivée par défaut** — sans elle, rien ne
  change (ni le déroulement d'une partie, ni la sortie existante).
- Format JSON Lines : une ligne par tour (`donne`, `ordre` des joueurs,
  `niveau_a`/`niveau_b`, `manche`, `tour`, `camp`, `niveau`, `index_joueur`,
  `chevalet_avant`/`chevalet_apres`, `ouvert_avant`/`ouvert_apres`, `action`
  RÉELLEMENT exécutée (`pose`/`pioche`/`passe` — un coup rejeté qui retombe
  sur une pioche de secours est tracé comme une pioche, jamais comme le coup
  invalide proposé), `nb_tuiles_posees`, `points_poses`,
  `taille_pioche_avant`, `joker_en_main_avant`) + une ligne de résultat par
  manche effectivement terminée (`vainqueur_camp`/`vainqueur_niveau`,
  `perdant_camp`/`perdant_niveau`, `tuiles_restantes_perdant`, `fin`
  — `chevalet_vide`/`pioche_vide`, `tours`). Les manches arrêtées par le
  garde-fou anti-blocage n'ont pas de ligne de résultat (abandonnées comme
  avant, juste sans ligne terminale).
- Lit l'état complet de la partie (chevalets, mise initiale faite) à des
  fins de MESURE seulement : jamais consulté par une décision d'IA, jamais
  transmis à `jouer_ia`/`jouer_niveau_bride`.
- Implémentation : `jouer_un_tour` capture l'état avant/après pour le joueur
  qui vient de jouer et écrit la ligne via `_ecrire_trace_tour` ; `jouer_
  match` écrit la ligne de résultat de chaque manche via `_ecrire_trace_
  resultat`, après `_jouer_une_manche`. `trace_ctx` (fichier + identifiants
  de match) descend `comparer` → `jouer_match` → `_jouer_une_manche` →
  `jouer_un_tour`, `None` par défaut à chaque niveau.

## 2. Script d'analyse (`scripts/analyser_phases.py`, nouveau)

- Découpe chaque manche, **joueur par joueur** (l'ouverture d'un joueur est
  indépendante de celle de l'autre), en trois phases :
  1. **Prologue** : tous les tours d'un joueur avant sa propre ouverture (y
     compris le tour de l'ouverture elle-même).
  2. **Développement** : après l'ouverture, chevalet de plus de N tuiles au
     début du tour.
  3. **Fin** : chevalet de N tuiles ou moins au début du tour, après
     l'ouverture.
- N est un **seuil réglable à l'analyse**, jamais figé dans la trace —
  `--seuil N` (répétable, défaut 5 ; `--seuil 5 --seuil 6` compare les deux
  découpages en un seul passage sur le fichier).
- Rapporte, par phase et pour le gagnant/le perdant de chaque manche : durée
  moyenne en tours, tuiles posées par tour, fréquence des pioches ; plus le
  tour d'ouverture (moyenne/médiane/min/max), le nombre de pioches avant
  l'ouverture et la taille du chevalet à ce moment.
- **Question centrale** : l'écart de tuiles restantes en main entre les deux
  joueurs (a) à la FIN du prologue (quand le SECOND joueur à ouvrir vient
  d'ouvrir) et (b) à l'ENTRÉE en phase Fin de CHAQUE joueur (deux événements
  possibles par manche, regroupés) — et, à chacun de ces moments, le taux de
  victoire du joueur alors en avance (moins de tuiles en main ; égalités
  comptées à part, jamais mêlées au taux de victoire).
- Pure lecture/regroupement par manche (clé : donne, ordre, numéro de
  manche) : ne rejoue jamais rien, ne modifie aucun fichier.

## 3. Tests

- `tests/test_export_trace.py` : option désactivée par défaut (aucun
  fichier créé, résultat inchangé) ; une partie courte réelle (Débutant
  contre Débutant) produit des lignes cohérentes (action/chevalet/points
  cohérents entre eux, ouverture monotone, une ligne de résultat par
  manche) ; `--export-trace` et `--export-resultats` fonctionnent ensemble
  sans interférer.
- `tests/test_analyser_phases.py` : classification aux bornes exactes du
  seuil (`phase_du_tour`, y compris un cas où N=5 et N=6 classent le MÊME
  tour différemment) ; analyse de principe sur une manche fabriquée à la
  main (calcul de référence détaillé en commentaire) couvrant durées de
  phase, tour/chevalet/pioches d'ouverture, et les deux points de bascule
  (fin du prologue, entrée en phase Fin) ; manche sans ligne de résultat
  correctement ignorée (et comptée) ; lecture d'un fichier fabriqué.
- Suite complète inchangée : `pytest tests/` toujours vert.

## 4. Documentation

- CONTEXTE.md §13 : nouvelle entrée « Réalisée (#226) » — découpage en trois
  phases, contenu de la trace, question posée par l'analyse, rappel que
  l'issue ne modifie pas le jeu, et correspondance pistes/phases pour
  mémoire (Prologue → Ouverture ; Développement → Tuiles vivantes, Modèle
  adverse ; Fin → vérification de finition #221 et joker gardé #225).

## 5. Essai de validation (par l'agent, sans campagne longue)

Un essai de 2 donnes (4 matchs) Expert contre Champion du Monde, au premier
plan, a validé toute la chaîne trace → analyse sur du vrai jeu (voir le
rapport de clôture de l'issue pour le détail). Les commandes de campagne
(300 donnes, analyse à N=5 et N=6) sont fournies à Alain dans ce même
rapport — aucune campagne longue n'a été lancée par l'agent.
