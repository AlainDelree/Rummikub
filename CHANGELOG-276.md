# Issue #276 — Nouveau script de tournoi à quatre IA (rotation des sièges, statistiques par niveau, reprise après interruption)

## Contexte

L'étude #275 avait établi que le moteur et `scripts/simulation_ia.py`
savent déjà faire jouer quatre IA de niveaux différents sans aucune
anomalie, mais qu'aucun outil n'organisait un tournoi : `comparer_niveaux_
ia.py`/`calibrer_echelle.py` restent câblés à deux camps (calibrage par
duels), et `simulation_ia.py` ne joue qu'un seul match sans rotation des
sièges ni statistiques par niveau. Cette issue crée l'outil manquant, en
complément des duels — elle ne modifie ni le moteur, ni l'IA, ni
`niveaux.py`, ni les réglages, ni l'interface, et ne lance aucune campagne
de tournoi réelle au-delà de l'essai de vérification court demandé.

## 1. `scripts/tournoi_niveaux.py` (nouveau)

Fait jouer 2 à 4 niveaux d'IA ENSEMBLE, à une même table, sur une
campagne de donnes avec rotation des sièges (autant de rotations que de
niveaux, chaque niveau occupant une fois chaque siège), statistiques par
niveau et reprise après interruption. Réutilise directement :

- la même boucle de tour et le même traitement des anomalies (coup
  invalide, tuiles disparues, exception IA, repli sur une pioche de
  secours) que `scripts/simulation_ia.py`, mais via `moteur.ia.
  jouer_niveau_bride` (plutôt que `jouer_ia`) pour transmettre un budget
  de temps du solveur explicite à chaque niveau ;
- `_limite_temps_ferme.lancer_avec_limite_ferme` pour la limite de temps
  FERME globale de la campagne (`--limite-temps`) ;
- `_verif_solveur_exact.exiger_solveur_exact_ou_quitter` (échec franc sans
  `highspy`/`numpy`, comme les autres outils de mesure) ;
- `_rapport_duels.entete_machine` pour l'en-tête machine/dépendances du
  rapport.

Options : `--niveaux` (2 à 4 niveaux séparés par des virgules, défaut
« Expert,Avancé,Intermédiaire,Facile », noms sans accent acceptés — ex.
« Avance », « Intermediaire » — refus avec la liste des noms valides pour
un nom inconnu, et refus d'un niveau répété), `--donnes` (défaut 50),
`--seed` (graine de base, la donne i utilise `seed + i`), `--max-tours`
(défaut 300), `--budget-solveur` (défaut : valeur du jeu, 1,5 s),
`--dossier` (requis), `--processus` (1 ou 2, comme `calibrer_echelle.py`),
`--limite-temps`, `--statut` (lecture seule), `-v`.

**Reprise.** Un enregistrement JSON Lines par MANCHE
(`<dossier>/resultats_<worker>.jsonl`) ; une donne est complète quand ses
`len(niveaux)` rotations sont toutes présentes, où qu'elles soient dans le
fichier. Relancer exactement la même commande sur le même `--dossier`
reprend à la première donne manquante sans rejouer ni dupliquer une donne
déjà complète ; `--donnes` peut augmenter pour prolonger la campagne ;
tout autre changement de réglage (niveaux, graine, max_tours, budget,
`--processus`) est refusé (`reglages.json` verrouillé). `--processus`
partitionne les numéros de donne entre fichiers (`(d-1) % nb_processus`),
d'où son verrouillage : le changer entre deux lancements casserait la
correspondance donne → fichier.

**Rapport** (`rapport.txt`, régénéré en continu, lisible à tout moment y
compris sur une campagne partielle) : par niveau, manches décidées
(chevalet vidé ou manche bloquée — une manche arrêtée par le garde-fou
`--max-tours` est comptée séparément et exclue des statistiques de
victoire/place/score), part de victoires avec intervalle de confiance de
WILSON (nouveau dans ce script — plus fiable sur petit échantillon que
l'approximation de Wald déjà utilisée par `comparer_niveaux_ia.
intervalle_confiance_95`), place moyenne (égalités partagées en
« fractional ranking »), score moyen avec son intervalle de confiance ;
une matrice « qui bat qui » (part des manches où chaque niveau a un
meilleur score qu'un autre, égalité = 0,5 part chacun) ; les victoires par
siège (contrôle de l'absence de biais de position) ; la répartition des
fins de manche (chevalet vide / manche bloquée / limite de tours) ; le
nombre moyen de tours par manche ; le temps par tour moyen et maximum par
niveau ; le nombre d'anomalies ; la graine, le budget, les niveaux et
leurs réglages réels (lus dans `niveaux.py`, jamais modifiés), le commit
git si disponible, et l'état de la campagne (partielle ou terminée).

## 2. `tests/test_tournoi_niveaux.py` (nouveau)

25 tests rapides et déterministes : résolution des noms de niveaux sans
accent et refus d'un nom inconnu (liste des noms valides) ou d'un
doublon ; la rotation couvre bien les quatre sièges sur quatre rotations
consécutives d'une même donne ; le classement (`places_depuis_scores`)
est correct et stable, égalités partagées ; l'agrégation des statistiques
(`stats_par_niveau`, `matrice_qui_bat_qui`, `victoires_par_siege`,
`repartition_fins`) sur un petit jeu de données fabriqué à la main donne
exactement les valeurs attendues (calculées à la main) ; l'intervalle de
Wilson reste dans [0, 1] et est symétrique à 50 % ; la purge d'une donne
incomplète (coupure brutale simulée) et la reprise ne rejouent ni ne
dupliquent une donne terminée ; un essai de bout en bout très court (une
donne, cinq tours maximum) fonctionne ; refus de mélanger deux campagnes
aux réglages différents dans un même dossier.

Les niveaux réels utilisés dans ces tests (Débutant/Facile) ont leur
réglage remplacé par un réglage RAPIDE (`perturbation_max=0`, jamais de
recours au solveur exact) via `monkeypatch.setitem(niveaux.BRIDAGES, ...)`
— restauré automatiquement par le filet de sécurité autouse
`_bridages_restaures` de `tests/conftest.py` — jamais de vrai niveau lent
en boucle, conformément à la règle de #268 (voir docs/contexte/
niveaux_ia_calibrage.md).

## 2bis. `tests/test_garde_fou_scripts_tous.py` (modifié)

Ajouté `"tournoi_niveaux.py"` à l'inventaire figé `attendu` de
`test_inventaire_connu` (issue #224) : ce script est correctement détecté
comme faisant jouer l'IA (il appelle `jouer_niveau_bride`) ET appelle bien
le garde-fou `exiger_solveur_exact_ou_quitter` — mise à jour consciente
demandée par le test lui-même, aucun autre changement.

## 3. Documentation

- `docs/contexte/scripts_simulation.md` : nouvelle section 10 (but,
  usage, rotations, métriques du rapport, lecture, limites — complément
  des duels, aucune cible de taux de victoire, jamais utilisé pour
  recalibrer `niveaux.BRIDAGES`).
- `docs/contexte/niveaux_ia_calibrage.md` : ligne de renvoi vers cette
  nouvelle section, en fin de fichier.

## 4. Vérifications effectuées

- Compilation (`py_compile`) du script et du fichier de tests : OK.
- Essai réel court (vrais niveaux Expert/Avancé/Intermédiaire/Facile, 2
  donnes = 8 manches, un seul processus, budget solveur par défaut,
  `timeout 300`, sortie dans un fichier) : **TERMINÉ en 136,2 s**
  (`real 2m16,760s`), 0 anomalie, 8/8 manches décidées (toutes par
  chevalet vidé), ordre de force dans l'exemple : Expert 62,5 % de
  victoires, Avancé 37,5 %, Intermédiaire et Facile 0 % — échantillon bien
  trop petit pour une conclusion (la matrice « qui bat qui » le rappelle
  dans ses propres limites). Dossier de l'essai supprimé à la fin.
- `ruff --select S` sur `main.py` et `src` : **aucune anomalie**
  (`All checks passed!`) — inchangé par cette issue (aucun fichier de
  `src`/`main.py` touché). `ruff --select S` sur le nouveau script et le
  nouveau fichier de tests également propre (S101 dans les tests est la
  convention acceptée du projet, voir `docs/contexte/
  linter_securite.md`).
- Suite de tests complète (`pytest tests/`, au premier plan, `timeout
  900`, sortie dans un fichier) : **585 passed, 13 skipped** (190,3 s),
  **aucune baisse** du nombre de tests réussis. Un premier passage avait
  révélé une anomalie ATTENDUE (`test_garde_fou_scripts_tous.py::
  test_inventaire_connu`, un inventaire figé des scripts qui font jouer
  l'IA, qui doit être mis à jour consciemment à chaque nouveau script —
  corrigé en y ajoutant `tournoi_niveaux.py`) et un échec isolé,
  non reproductible hors charge machine (`test_ia.py::
  test_solveur_cascade_joker_61_trouve_attendu_avec_gros_budget`, budget de
  temps sensible à la charge CPU, documenté dans `docs/contexte/
  tests_frontend.md` §6 — repassé seul avec succès, aucun rapport avec
  cette issue). Troisième passage complet, propre : 585 passed, 13
  skipped, 0 failed.

## 5. Commandes types

```
# petit lot d'essai (10 donnes = 40 manches à 4 niveaux)
python scripts/tournoi_niveaux.py --dossier /tmp/tournoi_276 --donnes 10

# campagne complète (100 donnes = 400 manches), reprenable après coupure
python scripts/tournoi_niveaux.py --dossier /tmp/tournoi_276 --donnes 100
```

Sous Windows (PC fixe, venv dédié de calibration, même convention que
`calibrer_echelle.py` — voir `docs/contexte/niveaux_ia_calibrage.md`) :

```
C:\Tournois\venv\Scripts\python.exe scripts\tournoi_niveaux.py --dossier C:\Tournois\tournoi_276 --donnes 10
C:\Tournois\venv\Scripts\python.exe scripts\tournoi_niveaux.py --dossier C:\Tournois\tournoi_276 --donnes 100
```
