# Issue #224 — Garde-fou « solveur exact requis » étendu à tous les scripts qui font jouer l'IA

Issue de **fiabilisation des outils de mesure uniquement** : aucun
comportement du jeu, du solveur, des niveaux ni de la vérification de
finition n'est modifié. Suite de #223, dont le garde-fou n'était câblé que
sur `comparer_niveaux_ia.py`, `valider_bas_echelle.py` et
`echelle_niveaux.py` — d'autres scripts qui font jouer Avancé/Expert/
Champion du Monde pouvaient encore retomber en silence sur un interpréteur
sans `highspy`/`numpy`.

## 1. Inventaire

Scripts examinés (critère : appel à `jouer_ia(`, `jouer_niveau_bride(`,
`jouer_niveau_expert(`, `creer_partie(`, ou import de `comparer_niveaux_ia`,
qui pilote lui-même des parties par ces fonctions) :

- **Déjà protégés par #223** : `comparer_niveaux_ia.py`,
  `valider_bas_echelle.py`, `echelle_niveaux.py` — aucun changement.
- **Protégés par #224** (aucune option `--sans-exact`, donc le solveur exact
  est toujours requis) : `simulation_ia.py`, `profil_joueur.py`,
  `calibrer_niveaux.py`, `verifier_simplicite_expert.py`,
  `generer_corpus_positions_222.py`, `match_solveurs.py`, `_campagne_186.py`
  (script historique du rapport de clôture #186).
- **Hors périmètre** (ne font jouer l'IA par aucun niveau, donc non
  concernés) : `analyser_coups_rates.py`, `analyser_partie.py`,
  `bilan_parties.py`, `verifier_cas_reference.py` (analyse de journaux déjà
  joués) ; `comparer_solveur_exact.py`, `verifier_solveur_exhaustif.py`
  (comparaisons de solveur indépendantes de highspy/numpy) ;
  `mesurer_volume_solveur_222.py` (mesure directe du solveur sur un corpus
  figé, rapporte déjà honnêtement un statut `indisponible` par position,
  en-tête machine/dépendances déjà présent via `_rapport_duels.
  entete_machine`) ; modules utilitaires internes (`_corpus_positions_222.py`,
  `_limite_temps_ferme.py`, `_mesure_volume_222.py`, `_rapport_duels.py`,
  `solveur_exact.py` l'adaptateur de bibliothèque).

## 2. Garde-fou câblé

- Les 7 scripts de la liste « protégés par #224 » importent désormais
  `exiger_solveur_exact_ou_quitter` de `_verif_solveur_exact.py` et
  l'appellent en tout début de `main()` (ou, pour `_campagne_186.py`, script
  historique sans fonction `main`, juste après l'analyse des arguments) —
  même message et même code de sortie non nul que #223.
- `verifier_simplicite_expert.py` avertissait jusqu'ici (texte sur stdout)
  sans s'arrêter quand `highspy`/`numpy` manquaient, puis continuait avec
  une approximation permanente (recherche arborescente) non signalée comme
  telle dans le résumé final : remplacé par l'arrêt franc. Le repli ponctuel
  de son juge sur la recherche arborescente en cas de budget dépassé POUR UN
  COUP (mécanisme distinct, légitime) reste inchangé.
- `match_solveurs.py` avait déjà un contrôle de disponibilité pour la
  bibliothèque EXTERNE `rummikub-solver` (#212) ; le nouveau garde-fou
  contrôle en plus le solveur exact MAISON (highspy/numpy) qu'utilise
  `jouer_niveau_expert`, les deux contrôles étant indépendants.

## 3. En-tête de rapport

- `simulation_ia.py`, `profil_joueur.py`, `calibrer_niveaux.py`,
  `verifier_simplicite_expert.py` et `match_solveurs.py` ajoutent désormais
  l'interpréteur Python et les versions de `highspy`/`numpy` en tête de leur
  rapport (console et/ou fichier), via `entete_dependances()`.
- `generer_corpus_positions_222.py` ajoute la même information (clé
  `dependances_generation`) dans le fichier JSON de corpus qu'il écrit.

## 4. Test anti-oubli

- Nouveau `tests/test_garde_fou_scripts_tous.py` : parcourt `scripts/*.py`,
  détecte par recherche de texte les scripts qui font jouer l'IA (même
  critère que l'inventaire ci-dessus) et échoue si l'un d'eux n'appelle pas
  le garde-fou et ne figure pas dans une liste d'exceptions explicitement
  justifiée (vide aujourd'hui : les 10 scripts détectés l'appellent tous).
  Un test de sanity-check fige l'inventaire détecté pour qu'un changement de
  liste soit visible en revue, pas silencieux.

## 5. Tests de comportement

- `tests/test_verif_solveur_exact.py` : un test par script modifié simule
  l'absence de `highspy`/`numpy` (`monkeypatch` de `solveur_exact.
  DISPONIBLE`) et vérifie un arrêt avec code de sortie non nul et un message
  qui nomme `sys.executable` — sans aucune simulation longue (paramètres
  minimaux, appel direct de `main()` ou, pour `_campagne_186.py`, chargement
  via `runpy`).

## 6. Documentation

- `CONTEXTE.md` (section #223) complété avec la liste des scripts étendus
  par #224, la liste des scripts hors périmètre et pourquoi, et un rappel
  de la commande de vérification de l'interpréteur.
