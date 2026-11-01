# Issue #223 — Campagnes de comparaison : échec franc sans solveur exact, chemin de production du jeu, compteurs de finition lisibles

Issue de **fiabilisation des outils de mesure uniquement** : aucun
comportement du jeu, des niveaux, du solveur ni de la vérification de
finition n'est modifié — seulement les scripts de campagne, leurs
compteurs et le journal. Motivée par un incident réel : une campagne Avancé
contre Expert (lancée pour mesurer #221) a tourné à vide, le terminal
utilisé pointant par défaut vers un autre interpréteur Python sans
`highspy`/`numpy` — Expert s'est replié sur Avancé à chaque tour (766/766)
sans que rien ne le signale, et le rapport a même étiqueté ces replis
« coup légitimement impossible, aucun rapport avec la vitesse », ce qui
était faux.

## 1. Échec franc sans solveur exact

- Nouveau module `scripts/_verif_solveur_exact.py` : `exiger_solveur_exact_
  ou_quitter(sans_exact=False)` arrête le script (code de sortie 1, message
  sur stderr nommant `sys.executable` et le(s) paquet(s) manquant(s)) si
  `highspy`/`numpy` ne sont pas importables — sauf `--sans-exact`
  (désactivation volontaire et assumée, jamais concernée). `entete_
  dependances()` fournit les lignes d'en-tête (interpréteur + versions de
  `highspy`/`numpy`, ou leur absence volontaire) réutilisées par tous les
  rapports.
- Câblé dans `main()` de `scripts/comparer_niveaux_ia.py`,
  `scripts/valider_bas_echelle.py` et `scripts/echelle_niveaux.py` (ces deux
  derniers n'ayant pas de `--sans-exact`, le solveur exact y est toujours
  requis — Facile et Intermédiaire le consultent aussi pour leur candidat
  « complet »).
- `scripts/_rapport_duels.py` (`entete_machine`, partagé par
  `echelle_niveaux.py`/`valider_bas_echelle.py`) inclut désormais
  l'interpréteur et les versions de `highspy`/`numpy`. L'en-tête de
  `comparer_niveaux_ia.py` fait de même.

## 2. Replis d'Expert honnêtement étiquetés

- Dans `scripts/comparer_niveaux_ia.py`, les replis d'Expert sur la
  recherche arborescente sont désormais comptés par **trois causes
  séparées** (dict `replis_expert`) : `budget_depasse` (dépassement réel du
  budget de temps), `deps_absentes` (solveur exact indisponible — vérifié
  directement via `solveur_exact.DISPONIBLE` au moment de l'appel, jamais
  deviné depuis le seul booléen `timeout`), `autre` (anomalie : résultat
  non valide ou exception). Un avertissement visible (`!!!`) apparaît en
  tête de rapport si des replis par indisponibilité ont eu lieu PENDANT la
  campagne.
- Le cas légitime « aucun coup possible » (le modèle exact PROUVE qu'il n'y
  a rien à jouer) est désormais compté SÉPARÉMENT (`aucun_coup_expert`, via
  le nouveau point d'observation `on_aucun` de `ia.jouer_niveau_expert`) —
  ce n'est PAS un repli, Expert reste décidé par le modèle exact.
- L'étiquette inexacte « coup légitimement impossible (aucun rapport avec
  la vitesse) » est retirée : elle décrivait en réalité, selon les
  circonstances, une absence de dépendances ou une anomalie — jamais le cas
  légitime, qui ne passait de toute façon jamais par ce compteur.

## 3. Chemin de production

- `ia.jouer_niveau_bride` et `ia.jouer_niveau_expert` acceptent désormais
  deux paramètres optionnels supplémentaires (`preferer_simple`,
  `eval_config` déjà existant sur `jouer_niveau_expert`, et le nouveau
  `on_aucun`) — tous `None` par défaut, comportement de production
  strictement inchangé pour `jouer_ia` et tout appelant existant.
- `scripts/comparer_niveaux_ia.py` fait désormais jouer Expert via
  `ia.jouer_niveau_bride(etat, idx, "Expert", on_repli=..., on_aucun=...,
  preferer_simple=..., eval_config=...)` — le MÊME chemin que `jouer_ia`
  (qui résout le niveau puis délègue à cette fonction), au lieu d'appeler
  `jouer_niveau_expert` directement puis d'appliquer manuellement la
  vérification de finition avec une échéance propre au script. L'échéance
  du coup ET de la vérification est désormais intégralement PARTAGÉE,
  calculée par le moteur lui-même, comme en jeu réel. Champion du Monde
  passait déjà par ce chemin (`jouer_ia` générique).
- Les statistiques de campagne (replis, perturbation du plateau, temps par
  tour, appels supplémentaires au solveur de vérification) restent
  disponibles, recueillies par les points d'observation du moteur
  (`on_repli`, `on_aucun`, monkeypatch de `verification_finition.
  resoudre_exact` pour le comptage d'appels) plutôt qu'en dupliquant sa
  logique de décision.

## 4. Statuts de finition plus fins

`moteur/verification_finition.py` distingue désormais SEPT statuts (clé
`verif_finition` de l'action, journalisée comme avant) au lieu de quatre :

- `non_applicable` : chevalet trop grand ;
- `pas_de_coup_a_comparer` : pas de coup « jouer » à comparer (pioche/passe)
  — nouveau : auparavant non tracé du tout pour Expert/Champion du Monde ;
- `solveur_non_exact` : coup du tour pas décidé par le modèle exact
  (dépendances absentes, ou repli déjà survenu faute de budget) — distingué
  de `budget_epuise` ;
- `budget_epuise` : budget de temps RÉELLEMENT épuisé pendant la
  vérification elle-même ;
- `appliquee_meilleur_suffit` : le meilleur coup du solveur permettait déjà
  de finir au tour suivant ;
- `appliquee_aucun_candidat` : aucun candidat ne permet de finir — avant
  cette issue, confondu avec le statut précédent sous
  `appliquee_sans_changement`, masquant deux situations très différentes ;
- `appliquee_autre_coup` : inchangé (un autre candidat permet de finir).

La DÉCISION de jeu (quel coup est effectivement joué) reste strictement
identique à avant cette issue — seuls les statuts journalisés sont affinés.
Le rapport de `comparer_niveaux_ia.py` affiche la répartition des sept
statuts séparément.

## 5. Tests

- `tests/test_verification_finition.py` : 3 nouveaux tests — une vraie fin
  de partie via `jouer_ia` (solveur exact requis) qui ne retourne jamais
  `BUDGET_EPUISE` et produit un statut d'application ; `PAS_DE_COUP_A_
  COMPARER` via `jouer_ia` sans aucun coup posable ; `on_aucun` appelé
  quand le modèle exact prouve l'absence de coup (jamais confondu avec
  `on_repli`). Les tests existants sont mis à jour pour les statuts
  renommés/scindés (`appliquee_sans_changement` → `appliquee_meilleur_
  suffit` / `appliquee_aucun_candidat` selon le cas ; repli sans
  dépendances → `solveur_non_exact`).
- Nouveau `tests/test_verif_solveur_exact.py` : garde-fou de dépendances
  (arrêt franc, message nommant l'interpréteur, `--sans-exact` l'ignore),
  en-tête de dépendances, relais dans `comparer_niveaux_ia.main`.
- Nouveau `tests/test_comparer_niveaux_ia_rapport.py` : séparation des
  trois causes de repli dans le rapport, avertissement si dépendances
  absentes, compteur « aucun coup possible », affichage séparé des sept
  statuts de finition, fréquence d'activation qui exclut les statuts non
  exécutés.
- `tests/test_rapport_duels.py` mis à jour pour l'en-tête de dépendances
  ajoutée à `entete_machine()`.
- Suite complète : 410 tests passés, 14 sautés (dépendances optionnelles),
  0 échec.

## 6. Essai de deux donnes (vérification manuelle, premier plan)

`python scripts/comparer_niveaux_ia.py --niveau-a Avancé --niveau-b Expert
--donnes 2 --seed 0` : en-tête avec interpréteur + versions highspy/numpy,
0 repli (toute cause confondue) sur 108 tours d'Expert, 62 tours « aucun
coup possible » (cas légitime), répartition des sept statuts de
vérification de finition affichée séparément (32 non applicable, 62 pas de
coup à comparer, 12 appliquée : aucun candidat, 0 pour les autres statuts
sur cette petite campagne).

## Limites assumées

- Le garde-fou de dépendances n'est câblé que sur les trois scripts
  explicitement nommés par l'issue (`comparer_niveaux_ia.py`,
  `valider_bas_echelle.py`, `echelle_niveaux.py`). D'autres scripts qui
  font jouer Avancé/Expert/Champion du Monde (`verifier_simplicite_
  expert.py`, `profil_joueur.py`, `match_solveurs.py`, `simulation_ia.py`,
  `calibrer_niveaux.py`) ne sont PAS concernés par ce garde-fou — hors du
  minimum demandé, à traiter dans une issue ultérieure si besoin.
