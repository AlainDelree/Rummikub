# Issue #256 — Mesures et calibration : réglage de test « fin de manche à la pioche vide » (désactivé par défaut, la vraie règle du jeu ne change pas)

## Contexte

La vraie règle de fin de manche de #255 (blocage : pioche vide ET tous les
joueurs ont passé un tour complet sans jouer) est correcte pour le jeu,
mais rend les campagnes de calibration par paliers (`calibrer_echelle.py`)
beaucoup trop lentes entre niveaux bridés proches (Intermédiaire contre
Intermédiaire notamment, plateaux/chevalets qui grossissent, coût du
solveur par tour en forte hausse) : plus de 300 s pour 3 donnes sans
coupure, contre 35 minutes pour 100 donnes d'Avancé contre Expert. Cette
issue ajoute un réglage de TEST, désactivé par défaut et réservé aux
scripts de mesure, qui rétablit l'ancienne fin de manche « à la pioche
vide » (avant #255) pour borner la durée d'une campagne — sans toucher au
jeu réel, à l'IA ni à l'interface.

## 1. Réglage de test dans le moteur (`moteur/partie.py`)

- Nouveau paramètre mot-clé `fin_manche_pioche_vide: bool = False` sur
  `jouer_tour`, `piocher`, `passer_tour` et `_terminer_tour` — transmis de
  bout en bout, jamais passé par `ui/api.py` (donc jamais actif en jeu
  réel). Défaut `False` partout : comportement strictement identique à
  #255 pour tout appelant existant.
- `_terminer_tour` : la manche se termine aussi si
  `fin_pioche_vide_test = fin_manche_pioche_vide and pioche_vide and not
  chevalet_vide` — l'exception absolue du chevalet vidé reste prioritaire
  et inchangée (un coup gagnant n'est jamais intercepté par cette
  nouvelle voie). Le décompte des points réutilise TEL QUEL
  `calculer_scores_manche` (aucun changement dans `score.py`, sa docstring
  signale juste cette réutilisation) : comme pour une manche bloquée,
  aucun chevalet n'est vide, donc le gagnant est celui dont les tuiles
  restantes valent le moins de points.
- `etat["manche_terminee_pioche_vide_test"]` n'est posé (`True`) QUE si
  cette voie a déclenché la fin — absent dans tous les autres cas, y
  compris quand le réglage est actif mais n'a pas déclenché la fin
  (chevalet vidé normal, ou réglage inactif) : l'état d'une partie par
  défaut reste donc identique BYTE-POUR-BYTE à celui de #255.
  `nouvelle_manche` efface ce champ entre deux manches (comme
  `manche_bloquee`), pour qu'il ne traîne jamais d'une manche à l'autre.
- Jamais enregistré dans une partie sauvegardée : `persistance/
  stockage.py::sauvegarder_partie` sérialise `etat` tel quel, et aucun
  appelant du jeu ne passe ce paramètre ni ne pose ce champ.

## 2. Options en ligne de commande

- `--fin-manche-pioche-vide-test` (désactivé par défaut) ajouté à
  `scripts/simulation_ia.py` et `scripts/comparer_niveaux_ia.py` :
  transmis tel quel jusqu'aux appels `jouer_tour`/`piocher`/`passer_tour`
  (`jouer_un_tour` → `_jouer_une_manche`/`simuler` → `jouer_match` →
  `comparer`, selon le script). Sans l'option, comportement actuel (vraie
  règle, inchangé).
- `scripts/calibrer_echelle.py` : même option, transmise à `comparer()`
  via `jouer_tache`/`jouer_campagne`/`_executer`.

## 3. Visible dans les rapports ; paramètre de campagne

- Chaque script affiche en tête du rapport la règle de fin de manche
  utilisée : « Règle de fin de manche : réelle (blocage, #255). » ou
  « ... : fin à la pioche vide (TEST, #256) — ne remplace pas une
  vérification finale avec la vraie règle. ».
- `comparer_niveaux_ia.py`/`simulation_ia.py` : la répartition des fins de
  manche gagne un troisième compteur `pioche_vide_test`, jamais mélangé à
  `chevalet_vide`/`manche_bloquee` (catégorisation lue directement sur
  `etat["manche_terminee_pioche_vide_test"]`/`etat["manche_bloquee"]`,
  jamais recalculée).
- `calibrer_echelle.py` : `fin_manche_pioche_vide_test` fait désormais
  partie de `reglages.json` (`construire_empreinte`), au même titre que la
  graine/`--max-tours`/budget du solveur/cible — reprendre ou prolonger un
  dossier existant avec l'AUTRE règle est refusé avec le même message
  d'erreur que pour ces autres paramètres (`ReglagesIncompatibles`). Un
  dossier écrit AVANT #256 (sans la clé) est considéré comme la règle
  RÉELLE (`verifier_ou_ecrire_empreinte` l'ajoute avec `setdefault` avant
  comparaison ; `commande_statut` fait de même en lecture).

## 4. Mesure (agent, premier plan, limite de temps ferme, Python du projet)

```
timeout 300 python scripts/comparer_niveaux_ia.py --niveau-a Intermédiaire \
    --niveau-b Intermédiaire --donnes 3 --seed 0 --fin-manche-pioche-vide-test
```

- Durée totale : **218,1 s** pour 6 manches décidées (3 donnes x 2 miroir,
  toutes décidées — aucune n'a atteint le garde-fou `--max-tours 300`).
- Durée moyenne d'une manche décidée : 81,0 tours.
- Répartition des fins de manche : 4/6 par chevalet vidé, 2/6 par pioche
  vide (réglage de test), 0/6 par blocage réel, 0/6 arrêtées par le
  garde-fou.
- Temps de calcul par tour (Intermédiaire) : moyenne 448,3 ms, maximum
  3028,9 ms, sur 486 tours.
- **Comparaison avec la vraie règle** (chiffres de l'issue, pas remesurés
  ici — hors périmètre) : plus de 300 s pour la MÊME commande sans
  l'option, avec 4 manches sur 6 encore indécises à la coupure de 100
  tours. Le réglage de test apporte donc un gain réel et net (218 s contre
  « ne termine pas » en pratique), mais le résultat (218,1 s) dépasse
  l'ordre de grandeur attendu par l'issue (« une à deux minutes ») — signalé
  tel quel, sans chercher à l'optimiser davantage dans cette issue.

## 5. Documentation

- `CONTEXTE.md` (§3bis, §9) : courte mention du réglage de test dans la
  description de la fin de manche (§3bis) et paragraphe dédié dans la
  section des scripts de mesure (§9 — option, quand l'utiliser,
  avertissement, pointeur vers le fichier de domaine).
- `docs/contexte/ia_anti_don_joker.md` : nouvelle section « 10. Réglage de
  TEST « fin de manche à la pioche vide » (issue #256) » (motivation,
  implémentation, options CLI, avertissement, mesure chiffrée).

## 6. Tests

- `tests/test_moteur.py` : option désactivée par défaut (comportement de
  #255 conservé, champ de test absent de l'état) ; option activée via
  `piocher`/`passer_tour` (la manche se termine dès la pioche vide,
  gagnant au moins de points, `manche_bloquee` resté `False`) ; priorité
  du chevalet vidé sur le réglage de test même quand la pioche est vide en
  même temps ; `nouvelle_manche` efface le drapeau de test entre deux
  manches.
- `tests/test_calibrer_echelle.py` : refus de reprendre un dossier avec
  une autre règle de fin de manche ; un dossier écrit sans la clé est
  traité comme la règle réelle (reprise acceptée, rapport cohérent) ;
  rapport affichant la règle de test quand elle est active, et la clé
  persistée dans `reglages.json`.
- `tests/test_comparer_niveaux_ia_rapport.py` : en-tête du rapport selon
  la règle (réelle par défaut, test quand activée + compteur
  `pioche_vide_test` affiché).
- `python -m py_compile` sur tous les fichiers modifiés : OK.
- Suite complète (`pytest`) : 531 passed, 13 skipped (contre 526/13 avant
  cette issue — 10 tests ajoutés, répartis entre les trois fichiers
  ci-dessus).

## Points douteux / choix de l'agent

- Le résultat mesuré au point 4 (218,1 s) dépasse l'estimation de l'issue
  (« une à deux minutes ») — signalé explicitement ci-dessus et dans le
  fichier de domaine, sans tentative de correction supplémentaire (hors
  périmètre explicite de cette issue).
- `afficher_rapport` (`comparer_niveaux_ia.py`) lit `fins.get(
  "pioche_vide_test", 0)` (plutôt que `fins["pioche_vide_test"]`) pour
  rester tolérant à un résumé synthétique construit sans cette clé (tests
  existants de `test_comparer_niveaux_ia_rapport.py` antérieurs à cette
  issue) — choix défensif mineur, sans effet sur le comportement réel de
  `comparer()`, qui pose toujours la clé.
- `_executer` (`calibrer_echelle.py`) transmet `empreinte[
  "fin_manche_pioche_vide_test"]` (la valeur FINALE après fusion avec un
  dossier existant) plutôt que `args.fin_manche_pioche_vide_test`
  directement — cohérent avec le traitement déjà existant de `donnes_visees
  = empreinte["donnes"]`, mais les deux valeurs sont en pratique toujours
  égales (la reprise avec une valeur différente est refusée avant
  d'atteindre ce point).

Non poussé (`git push`) — à vérifier et pousser par Alain.
