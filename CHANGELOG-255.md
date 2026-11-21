# Issue #255 — Pioche vide : appliquer la vraie règle (on ne pioche plus, on passe, la manche ne s'arrête qu'au chevalet vide ou quand tout le monde est bloqué)

## Contexte

`_terminer_tour` (`moteur/partie.py`) terminait jusqu'ici la manche dès que
la pioche était vide, quel que soit le coup joué ce tour-là — une
« approximation de tous bloqués », documentée comme telle dans
`CONTEXTE.md` et `docs/contexte/ia_anti_don_joker.md`. Cette issue
implémente la vraie règle du Rummikub : pioche vide → on ne pioche plus,
on passe ; la manche ne se termine que par un chevalet vidé ou par un
blocage réel (tous les joueurs ont passé un tour complet sans qu'aucun
coup ne soit joué).

## 1. Fin « pioche vide » : où elle était codée

- `moteur/partie.py::_terminer_tour` — le seul endroit qui DÉCIDAIT
  réellement de la fin de manche. Réécrit (voir point 2).
- `moteur/ia.py` — ne décidait jamais la fin de manche, mais distinguait
  déjà « pioche vide » de « pioche non vide » pour ses propres choix
  (`_piocher_ou_passer`, règles du joker #253/#254) : CE CODE ÉTAIT DÉJÀ
  CORRECT (pioche vide → passe, jamais piocher), inchangé par #255. Seul le
  commentaire de doc (`docs/contexte/ia_anti_don_joker.md` §5) affirmant que
  ce chemin « ne se déclenche jamais en jeu réel tour par tour » est corrigé
  (il devient un cas fréquent, voir point 8).
- `scripts/comparer_niveaux_ia.py` — recalculait `pioche_vide` après coup
  (`len(etat["pioche"]) == 0 and all(...)`) plutôt que de lire la décision
  du moteur ; clé de rapport renommée `pioche_vide` → `manche_bloquee`,
  lue directement sur `etat["manche_bloquee"]`.
- `scripts/echelle_niveaux.py` — dict `fins` avec la même clé, renommée à
  l'identique (agrège les résultats de `comparer_niveaux_ia.comparer`).
- `scripts/simulation_ia.py` — ne distinguait pas du tout les deux fins ;
  ajout d'un champ `fin` par manche et d'un compteur agrégé `fins` dans le
  résumé (point 6).
- `scripts/profil_joueur.py`, `scripts/match_solveurs.py` — commentaires
  mentionnant « blocage / pioche vide » : toujours corrects conceptuellement
  (ils lisent `gagnant_manche_index`/`score_manche`, déjà valides pour une
  manche bloquée depuis le correctif de `score.py`, point 4) ; non modifiés.
- Pas de code dédié côté `ui/api.py` : `jeu_piocher`/`jeu_passer` existaient
  déjà et n'avaient pas besoin de changer.
- Front-end (`jeu.js`, issue #28, déjà en place AVANT #255) : le bouton
  fusionné Piocher/Passer devient déjà « ⏭ Passer » quand la pioche est
  vide — le point 3 de l'issue (« l'interface doit proposer passer ») était
  donc déjà satisfait ; #255 ajoute seulement une note explicative sur
  l'overlay de fin de manche quand elle est bloquée (`sous-titre-fin`).

Historique git / changelogs : `CHANGELOG.md` (issue #254, point 5) et
`CONTEXTE.md` présentaient déjà cette fin comme une « simplification »/
« approximation » assumée, jamais comme une règle voulue — confirmé par
`TACHES.md`.

**Tests qui en dépendaient** : aucun test unitaire de `tests/test_moteur.py`
ne testait directement la fin par pioche vide (elle n'était atteignable
qu'en reconstruisant un état avec `pioche: []`, jamais exercée par les
tests de manche existants, qui finissent tous par un chevalet vidé via
`_finir_manche`). Deux tests ont dû être adaptés pour la clé renommée
`pioche_vide` → `manche_bloquee` : `tests/test_comparer_niveaux_ia_rapport.py`
et `tests/test_export_trace.py`.

**Parties en cours sauvegardées avec pioche vide** : avant #255, un tel
état ne pouvait exister qu'au prix d'une manipulation manuelle (la manche
aurait déjà été marquée terminée par le moteur) — aucune partie réelle
sauvegardée ne peut donc être concernée. Couvert par un test dédié malgré
tout (point 7).

**Outils de duel/calibration à plus de 2 joueurs** : `comparer_niveaux_ia.py`
est structurellement à 2 joueurs (modèle « camp A / camp B », mesures du
joker par camp) — PAS de support 3/4 joueurs, inchangé par #255.
`scripts/simulation_ia.py` supporte déjà 2 à 4 joueurs (`--joueurs 2|3|4`,
argparse `choices`) — utilisé pour l'essai à 3/4 joueurs du point 6.

## 2. Nouvelle règle de fin de manche (`moteur/partie.py`)

- Nouveau champ d'état `passes_consecutives` (int, initialisé à 0 dans
  `creer_partie`/`nouvelle_manche`) : incrémenté par `passer_tour`, remis à
  0 par toute pose réussie (`jouer_tour`), et incrémenté par `piocher` quand
  aucune tuile n'est effectivement tirée (pioche déjà vide — équivalent
  fonctionnel d'un passage, voir point 3).
- Nouveau champ `manche_bloquee` (bool) : posé par `_terminer_tour`,
  `True` seulement si la pioche est vide ET `passes_consecutives >=
  nb_joueurs` (un tour complet de passes sans la moindre pose entre-temps).
- `_terminer_tour` termine la manche si `chevalet_vide` (inchangé) OU
  `manche_bloquee` (remplace l'ancien `pioche_vide`). Une pioche non vide
  ne peut plus jamais terminer la manche à elle seule.
- `normaliser_etat_reprise` : `etat.setdefault("passes_consecutives", 0)` /
  `etat.setdefault("manche_bloquee", False)` pour une reprise sans erreur
  d'un état antérieur à #255 (point 7).

## 3. Tour avec pioche vide

- `moteur/partie.piocher` : si la pioche est déjà vide, ne tire plus
  aucune tuile (comportement inchangé) MAIS compte désormais ce tour comme
  un passage pour le compteur de blocage — sinon un appel répété à
  `piocher()` avec une pioche vide ne ferait jamais progresser le blocage.
- IA (`moteur/ia.py`) : AUCUN changement de code nécessaire —
  `_piocher_ou_passer` décidait déjà correctement « pioche si non vide,
  sinon passe » dans tous les chemins de repli (niveaux non bridés,
  oubli, échange différé/joker libre forcés). Vérifié explicitement : la
  règle #254 point 5 (« offrir le joker plutôt que passer si la pioche est
  vide ») est désormais RÉELLEMENT atteinte en jeu normal (et plus
  seulement par les tests unitaires qui forcent `pioche: []`) — ses tests
  dédiés (`test_joue_malgre_joker_libre_si_pioche_vide`,
  `test_echange_differe_force_et_joue_si_pioche_vide_et_aucune_alternative`)
  restent verts sans modification.
- Humain (`jeu.js`) : le bouton fusionné Piocher/Passer (issue #28) était
  déjà correct ; seule une note explicative est ajoutée sur l'overlay de
  fin de manche bloquée (`jeu.html`/`jeu.js`/`jeu.css`, `#sous-titre-fin`).
- **Conséquence connue, non corrigée (signalée par l'issue elle-même)** :
  le mécanisme d'« oubli » des niveaux bridés peut faire passer une IA qui
  AVAIT un coup jouable (simulation d'une erreur humaine) — si, par
  malchance, tous les joueurs « oublient » en même temps pioche vide, la
  manche se termine bloquée alors qu'un coup existait. Les valeurs
  d'oubli/perturbation sont explicitement hors périmètre de cette issue ;
  ce comportement est un effet de bord accepté, pas un bug.

## 4. Score d'une manche bloquée (`moteur/score.py`)

`calculer_scores_manche` : si aucun chevalet n'est vide (manche bloquée),
le gagnant est désormais le joueur dont la pénalité des tuiles restantes
(même barème, joker à `valeur_joker_penalite`) est la PLUS FAIBLE ; il
reçoit la somme des pénalités des autres (même formule que pour un
chevalet vidé), les autres perdent chacun leur propre pénalité (barème
perdant inchangé). `trouver_gagnant_manche`/`score_cumul` fonctionnent sans
changement sur ce nouveau cas.

**Point douteux signalé** : en cas d'égalité stricte au plus bas total de
pénalité, AUCUNE règle d'égalité de manche n'existait avant #255 (une
manche se terminait jusqu'ici toujours par un chevalet vidé, gagnant
unique par construction). Choix retenu, documenté dans le docstring de
`calculer_scores_manche` : le premier joueur dans l'ordre (`joueurs`)
gagne — cohérent avec les conventions déjà en place ailleurs dans le
moteur (`trouver_gagnant_manche`, `trouver_gagnant_match`, qui tranchent
aussi par ordre à score égal via une comparaison stricte `>`). Ce choix
n'est pas tiré d'une règle officielle du Rummikub (qui ne détaille pas ce
cas précis) — c'est le plus simple, cohérent avec le reste du barème
existant (barème des pénalités et du tapis NON modifiés, comme demandé).

## 5. Aucune partie infinie

Le blocage est borné PAR CONSTRUCTION : `passes_consecutives` ne peut
dépasser `nb_joueurs` sans déclencher la fin de manche (vérifié par
`test_manche_bloquee_ne_peut_jamais_durer_indefiniment`, 4 joueurs). Le
garde-fou existant des scripts de simulation (`max_tours`) reste en place,
inchangé, en filet de sécurité supplémentaire (ne devrait plus jamais être
atteint par cette voie précise).

## 6. Mesure

`scripts/comparer_niveaux_ia.py` et `scripts/simulation_ia.py` distinguent
désormais `chevalet_vide` / `manche_bloquee` (clé renommée dans le premier,
ajoutée dans le second) dans leurs compteurs de fin de manche et leur
texte de rapport.

Essais réalisés (premier plan, limite de temps ferme, cette session) :

- **20 donnes, 2 joueurs, Débutant contre Débutant** (graine 42,
  `comparer_niveaux_ia.py --max-tours 500`) : 40 manches jouées (40/40
  décidées), **34 bloquées (85 %), 6 par chevalet vidé (15 %)**, 0 arrêt
  par garde-fou, 0 anomalie de conservation des tuiles, durée moyenne
  **112,2 tours/manche**, 24,2 s au total. Confirme que le blocage est
  désormais le cas FRÉQUENT avec une IA faible (beaucoup de jokers/coups
  retenus), pas un cas exceptionnel.
- **20 donnes, 2 joueurs, Expert contre Expert** (même graine, même
  commande) : lancé en tâche de fond pendant la rédaction de ce rapport —
  voir la synthèse finale du rapport de clôture pour le résultat chiffré
  (campagne plus lente : solveur exact à budget de production 1,5 s/tour).
- **3 joueurs, Débutant×3** (`simulation_ia.py --joueurs 3`, 5 graines
  1 à 5, `--max-tours 500`) : 5/5 manches terminées sans erreur, **5/5
  bloquées**, 92/95/94/97/99 tours, 0 anomalie.
- **4 joueurs, Débutant×4** (même script, 5 graines) : 5/5 manches
  terminées sans erreur, **5/5 bloquées**, 75 à 88 tours, 0 anomalie.
- **3 et 4 joueurs, Expert** (graine 7, 1 partie chacun, pour varier le
  niveau) : terminées par **chevalet vidé** (pas de blocage) en 17 et 34
  tours — une IA plus forte vide son chevalet avant que la pioche ne
  s'épuise, comme attendu.

Aucune campagne longue n'a été lancée (hors périmètre de l'agent, comme
demandé).

## 7. Parties sauvegardées

`normaliser_etat_reprise` retombe sur `passes_consecutives=0`/
`manche_bloquee=False` pour un état antérieur à #255 (clés absentes) — la
manche continue alors normalement sous la nouvelle règle, sans erreur,
jusqu'à un chevalet vidé ou un nouveau tour complet de passes. Une partie
déjà terminée (`terminee=True`) n'est jamais modifiée par la reprise
(inchangé). Couvert par
`test_reprise_partie_sauvegardee_avec_pioche_vide_continue_sans_erreur` et
`test_partie_deja_terminee_non_modifiee_par_la_reprise`
(`tests/test_moteur.py`).

## 8. Documentation

- `CONTEXTE.md` : §3bis (« Fin d'une manche »), §4 (clés de l'état,
  ajout de `manche_bloquee`/`passes_consecutives`), §5 (« gestion fine de
  tous bloqués » : retiré de la liste des choses restant à faire, marqué
  implémenté), §9 (texte décrivant le rapport de `comparer_niveaux_ia.py`),
  §« Piste 5 » (la règle qu'elle décrivait comme hypothétique est
  désormais réellement implémentée) — mis à jour sur place. Les chiffres
  de campagnes HISTORIQUES (#184/#186/#187, mesurés sous l'ancienne règle)
  ne sont volontairement pas réécrits (ce sont des résultats d'époque, pas
  une description de règle actuelle).
- `docs/contexte/ia_anti_don_joker.md` : §5, le paragraphe affirmant que
  la pioche vide en début de décision est « inatteignable en jeu réel » et
  « surtout exercée par les tests unitaires » est réécrit — c'est
  désormais un cas fréquent en fin de manche. Note ajoutée en §9 pour
  préciser que l'observation « ne se déclenche jamais en jeu réel » ne
  valait que pour la campagne #254 (jouée avant #255).

## Tests

Ajoutés (`tests/test_moteur.py`, `tests/test_score.py`) : fin par blocage
à 2 et 3 joueurs, un seul passage ne suffit pas, remise à zéro du compteur
par une pose, `piocher` sans tuile compte comme un passage, une vraie
pioche ne touche pas au compteur, garde-fou de non-infinité à 4 joueurs,
reprise d'une sauvegarde avec pioche vide, partie déjà terminée non
modifiée, gagnant d'une manche bloquée (barème, joker, égalité, 3 joueurs,
score cumulé). Adaptés : `tests/test_comparer_niveaux_ia_rapport.py`,
`tests/test_export_trace.py` (clé `pioche_vide` → `manche_bloquee`).

`pytest tests/ -q` : 498 passed, 13 skipped (hors `-m lent`) + 23 passed,
2 skipped (`-m lent`) — suite complète verte. `py_compile` OK sur tous les
fichiers modifiés.

Aucune valeur de perturbation/oubli ni règle du joker #253/#254 modifiée ;
aucun changement du tapis ni du barème des pénalités hors le point 4.
Rien poussé (`git push`).
