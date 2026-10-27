# Issue #200 — Suite #194 : Solveur Expert, coups de grande envergure et bug de mesure côté humain

Diagnostic des 3 cas humains enregistrés comme référence (#193,
`tests/donnees/cas_expert_humain_*.json`) : le chevalet réellement capturé
ne contenait que 7, 3 et 3 tuiles, alors que `attendu_min_tuiles` (18, 7,
18) en exigeait davantage — une cible physiquement impossible (on ne peut
jamais poser plus de tuiles que n'en contient la main). Le solveur
trouvait déjà, en quelques centaines de ms à ~2s, le maximum réel (= la
main entière) sur les 3 cas : aucune incomplétude du solveur sur ces cas,
contrairement à l'hypothèse de départ de l'issue.

Cause réelle, localisée dans `persistance/coups_rates.py` :
`analyser_decision_complete` comparait le solveur au champ brut
`nb_tuiles_posees` du journal (`len(data["ids_tuiles"])` côté
`ui/api.py::jeu_jouer_coup`, la longueur de la liste d'ids envoyée par le
client JS), qui peut dépasser la taille réelle du chevalet d'avant-coup,
plutôt qu'à `ids_tuiles_reelles` — déjà calculé juste à côté (différence
entre le chevalet d'avant et celui d'après la pose), fiable et borné par
construction par la taille du chevalet. `jouer_tour` lui-même n'a jamais
été en cause (aucune tuile n'a jamais disparu ni été dupliquée en jeu
réel) : le bug était seulement dans la MESURE utilisée par l'outil
d'analyse, pas dans le moteur de jeu.

**Corrections :**

1. `persistance/coups_rates.py::analyser_decision_complete` : `nb_reel`
   utilise désormais `len(ids_tuiles_reelles)` pour une pose, plus jamais
   `nb_tuiles_jouees` (le compteur brut) — corrige à la source le calcul
   de `joueur_bat_solveur`/`pose_sous_optimale` et tout ce qui en dépend
   (résumé par joueur, enregistrement des cas de référence).
2. `tests/donnees/cas_expert_humain_*.json` (3 fichiers) : `attendu_min_tuiles`
   corrigé à la taille réelle du chevalet (7, 3, 3) — ces cas restent des
   tests de non-régression légers, mais ne sont plus des cas « grande
   envergure » manqués par le solveur.
3. `moteur/solveur.py::_candidats_suite` : optimisation pure (même
   résultat, plus rapide) — construit désormais les tokens d'un intervalle
   de suite une seule fois par borne gauche `v1`, en étendant la borne
   droite `v2` d'une position à la fois, au lieu de reconstruire tout
   l'intervalle `[v1, v2]` depuis zéro pour chaque largeur testée (coût
   quadratique identifié au profilage `cProfile` comme le principal poste
   de temps de la recherche, jusqu'à 40 % du temps total sur les cas les
   plus durs). Équivalence vérifiée par comparaison exhaustive sur 20000
   états aléatoires et par la suite de tests complète (187 tests, aucune
   régression).

**Mesures avant/après** (3 cas de référence authentiques,
`tests/donnees/cas_expert_ia_*.json`, IA Expert d'avant #194 jugée par le
solveur actuel) :
- `tour37` (attendu 6) : déjà trouvé au budget de production (1.5s), AVANT
  comme APRÈS.
- `tour59` (attendu 7) : AVANT, 6/7 à 1.5s, ~3s nécessaires pour la 7e
  tuile. APRÈS, ~2s nécessaires (toujours juste au-dessus du budget de
  production strict, parfois atteint de justesse selon la charge machine).
- `tour61` (attendu 4, cascade de jokers à travers 13 combinaisons du
  plateau, déjà documentée #194 comme à la limite du budget) : AVANT,
  souvent RIEN à 1.5s, jusqu'à 10s nécessaires pour les 4 tuiles. APRÈS,
  ~5s nécessaires (reste nettement hors de portée du budget de
  production).

Le budget de production (1.5s) n'a **pas** été augmenté (dernier recours,
non justifié pour un gain qui resterait de toute façon loin de la cible
sur `tour61`, et marginal sur `tour59`) — ces deux cas restent documentés
comme hors de portée du budget de production, pas forcés plus avant dans
cette issue plutôt que de risquer une régression ailleurs pour les
atteindre.

Aucune piste de changement structurel de la stratégie par paliers
(montée plus rapide, relâchement du gel de combinaisons pour une main
large, recherche en partant du haut de la main) n'a été retenue : sur les
cas réels disponibles, geler moins de combinaisons pour une main large
n'aurait rien changé (une main qui touche déjà les 4 couleurs gèle déjà 0
combinaison — automatique, pas un réglage) et les deux autres pistes
risquaient de faire dégénérer la recherche vers l'ancien comportement
pré-#194 (preuve exhaustive) sur un palier non atteignable, sans qu'aucun
cas réel de « grande main » authentiquement bloquée n'ait été trouvé pour
les justifier.

**Tests ajoutés** (`tests/test_ia.py`) : pour chacun des 5 cas désormais
atteints (3 `cas_expert_humain_*`, `cas_expert_ia_*_tour37`,
`cas_expert_ia_*_tour59`), un test à gros budget (10s) et un test au
budget de production (tolérance ×6, comme #190/#194). Pour
`cas_expert_ia_*_tour61`, un test à gros budget (12s) seul — volontairement
pas de test au budget de production pour ce cas, qui serait soit flaky
soit trompeur avec une tolérance large.

**Campagne de mesure** : voir le rapport de clôture de l'issue pour la
campagne Avancé vs Expert (10 donnes, replis/temps moyen/taux de victoire)
et les limites rencontrées pour la comparaison avant/après sur les
journaux de parties réelles (non disponibles dans ce worktree isolé).
