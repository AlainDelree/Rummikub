# Solveur de réarrangement global du plateau — niveau Expert

## 8bis. Solveur de réarrangement global du plateau — niveau Expert (#186, #206)

> **Depuis #206, Expert joue avec un MODÈLE EXACT** (programmation linéaire
> en nombres entiers, `moteur/solveur_exact.py`, voir §8ter ci-dessous). La
> recherche arborescente décrite dans cette section (`moteur/solveur.py`)
> reste en place comme **repli** (import de `highspy`/`numpy` impossible,
> budget dépassé sans solution, ou erreur) et n'est PAS modifiée. Elle reste
> donc le comportement de secours exact décrit ici.

Depuis #186, Expert ne joue plus la chaîne de tactiques ci-dessus : il
appelle `moteur/solveur.py::resoudre_coup(etat, idx, budget_temps)`, qui
reconstruit librement tout le plateau (toutes les tuiles déjà posées
peuvent changer de combinaison, aucune ne peut disparaître) pour y poser le
plus grand nombre possible de tuiles du chevalet, jokers compris.

- **Principe** : on raisonne sur des compteurs par emplacement
  `(couleur, valeur)` (0 à 2 tuiles réelles possibles) et sur les 2 jokers
  du jeu, chacun marqué « obligatoire » s'il vient du plateau (doit
  impérativement finir dans une combinaison valide) ou « optionnel » s'il
  vient du chevalet (peut rester en main). Une recherche récursive
  mémoïsée choisit, à chaque étape, une combinaison (groupe ou suite)
  consommant un emplacement obligatoire restant — si aucune n'existe, la
  branche échoue, aucune tuile du plateau ne doit disparaître — puis, une
  fois tous les emplacements obligatoires traités, tente d'y ajouter le
  plus de tuiles optionnelles (chevalet) possible.
- **Départage** (plusieurs réarrangements posant le même nombre de
  tuiles) : d'abord le plus de points posés (valeur des tuiles du
  chevalet effectivement jouées), puis, à égalité, celui qui utilise le
  moins de jokers du chevalet — un joker reste une ressource précieuse
  même quand il ne change pas le nombre de tuiles posées ce tour-ci.
- **Mise initiale pas faite** : la RECHERCHE ignore alors le plateau (une
  règle du jeu interdit d'y toucher avant la mise initiale) et cherche la
  meilleure combinaison formable depuis la seule main, sous la contrainte
  des points posés ≥ `mise_initiale_min` — avec un repli en 2 passes documenté
  dans `solveur.py` quand le réarrangement qui pose le plus de tuiles
  n'atteint pas ce minimum (limite documentée : pas nécessairement
  l'optimum exact sous cette contrainte, voir docstring de
  `_meilleur_rearrangement`). **Le plateau existant (posé par d'autres
  joueurs) est intégralement gelé et reconduit tel quel dans le résultat**
  — bug corrigé par #187 : avant ce correctif, `resoudre_coup` l'omettait
  purement et simplement du plateau renvoyé, ce qui faisait disparaître ses
  tuiles (constaté en jeu : un groupe de 12 déjà posé effacé par Expert à
  sa première pose). Voir §4 (règle « le plateau ne perd jamais de tuile »)
  et les tests `test_expert_conserve_le_plateau_quand_la_mise_initiale_n_
  est_pas_faite` / `test_expert_conserve_plusieurs_combinaisons_du_
  plateau_sans_mise_initiale` (`tests/test_ia.py`).
- **Combinaisons gelées** (`_separer_combos_figees`) : une combinaison du
  plateau qui ne partage aucune couleur/valeur avec la main et ne contient
  aucun joker est reconduite telle quelle, hors recherche — borne
  nécessaire pour la combinatoire (principal facteur de ralentissement en
  milieu/fin de partie), au prix de réarrangements à travers une chaîne de
  combinaisons toutes étrangères à la main courante (cas non rencontré par
  les scénarios couverts par les tests).
- **Dégradation progressive sous budget de temps** (`BudgetDepasse`,
  `_resoudre`) : au-delà d'une dizaine de combinaisons pertinentes pour la
  main courante, l'arbre de recherche dépasse largement ce qu'un budget
  d'1 à 2 secondes permet de parcourir en entier (voir le rapport de
  clôture #186 pour l'analyse). Deux mesures en atténuent l'effet : les
  candidats de chaque emplacement sont essayés en priorité dans l'ordre
  décroissant de tuiles de main consommées (atteint le plafond optimiste,
  donc la coupure de branche, plus vite) ; et si le budget s'épuise EN
  COURS d'exploration, la meilleure branche déjà trouvée à ce niveau est
  conservée (réarrangement valide, pas nécessairement optimal) plutôt que
  tout perdre. `BudgetDepasse` n'est donc levée, et `jouer_niveau_expert`
  ne se replie sur le comportement d'Avancé (joker_tactiques.md §8) pour ce tour, que si
  RIEN n'a été trouvé nulle part dans l'arbre avant expiration du budget
  (`BUDGET_TEMPS_EXPERT`, 1.5s par défaut, `moteur/ia.py`) — idem si le
  solveur conclut lui-même qu'aucun coup n'existe (filet de sécurité,
  coût négligeable).
- **Règle supprimée** (#186, suite de #184) : Expert ne refuse plus de
  poser quand un adversaire a ≤ 3 tuiles (ancien comportement, retiré —
  la campagne de #184 n'a montré aucun avantage mesurable à la prudence).
- **Recherche rendue « progressive » (#190, suite de #187)** : sur un
  plateau chargé (≈ 70 tuiles, ~19 combinaisons), la quasi-totalité des
  combinaisons se retrouvait « flexible » (`_separer_combos_figees` ne
  gèle que celles ne partageant AUCUNE couleur/valeur avec la main — avec
  seulement 4 couleurs, une main de 2-3 couleurs distinctes suffit à
  déflexibiliser presque tout le plateau), forçant ~45 emplacements
  obligatoires avec une quarantaine de candidats chacun. Dans cet arbre,
  le premier chemin DFS (candidats triés pour maximiser l'usage de la
  main, voir `_score_rapide`) tombait régulièrement sur une impasse
  (emplacement obligatoire sans aucun candidat compatible avec l'état
  réduit), forçant un retour en arrière coûteux — avant qu'AUCUN
  réarrangement complet n'ait jamais été trouvé nulle part dans l'arbre,
  le budget de production (1.5s) s'épuisait : repli systématique sur
  Avancé, perte de l'essentiel de la force d'Expert en milieu/fin de
  partie (mesuré sur `tests/donnees/cas_expert_budget_tour81.json`, avec
  le solveur d'avant #190 : `BudgetDepasse` toujours levée jusqu'à 2.5s de
  budget ; premier coup trouvé (3 tuiles) entre 2.5s et 3.0s — la mention
  « 3 tuiles en 20s » du cas de test d'origine (#187) ne reflétait qu'une
  marge large choisie pour le test à gros budget, pas le temps minimal
  réellement nécessaire). Cause : la plupart des emplacements obligatoires ne touchent
  en rien la main (aucun gain possible à les restructurer), mais la
  recherche les traitait comme n'importe quel autre, essayant toutes les
  régularisations possibles avant celle, triviale, qui reconduit la
  combinaison déjà posée. Correctif : chaque candidat généré
  (`_candidats_groupe`, `_candidats_suite`, et leurs variantes « joker »)
  porte désormais une signature `(type, couleur/valeur, taille)`
  (`_signatures_originales`) ; parmi les candidats ex-aequo sur
  `_score_rapide` (typiquement ceux qui n'utilisent aucune tuile de la
  main), celui qui reproduit une combinaison déjà posée avant ce tour est
  tenté EN PREMIER — réduit radicalement les impasses/retours en arrière
  sur les zones du plateau non concernées par la main, et donc le temps
  nécessaire pour trouver un premier réarrangement complet valide. Sur le
  cas de test ci-dessus, le solveur retrouve désormais le coup de 3
  tuiles (11 noir, 11 noir, 7 rouge) dès 56 ms de budget, et le confirme
  toujours au budget de production de 1.5s (aucun autre coup meilleur
  trouvé en continuant à chercher jusqu'à expiration — voir « anytime »
  ci-dessous) — au lieu de `BudgetDepasse` sans rien trouver jusqu'à 2.5s
  avant #190. Soit environ 45 à 50× plus vite pour atteindre un premier
  coup valide, pour une qualité de résultat au moins égale (mêmes 3
  tuiles). La recherche continue ensuite d'essayer de faire mieux jusqu'à
  expiration du budget (comportement « anytime » déjà en place via
  `BudgetDepasse`, désormais effectif dès les tout premiers appels plutôt
  qu'après plusieurs secondes — ce qui, sur un plateau chargé, consomme
  maintenant systématiquement tout le budget restant même après avoir
  trouvé un premier coup, puisque la recherche ne s'arrête que sur borne
  prouvée ou budget épuisé). Ne change jamais le résultat OPTIMAL trouvé
  avec un budget suffisant pour explorer exhaustivement, seulement la
  vitesse pour l'atteindre (et, en cas d'égalité stricte de la valeur de
  départage entre plusieurs réarrangements équivalents, lequel des deux
  est renvoyé). **Important, voir CHANGELOG-190 pour le détail** : ce gain
  ciblé ne se traduit PAS par une amélioration visible sur une campagne
  Avancé vs Expert avec des plateaux tirés au hasard (taux de repli
  d'Expert sur Avancé et temps moyen par tour, mesurés avant/après,
  inchangés ou légèrement dégradés à cette taille d'échantillon) : le
  correctif n'accélère que les nœuds à candidats ex-aequo sur
  `_score_rapide` (plateaux structurellement proches du cas visé —
  beaucoup de combinaisons non pertinentes pour la main), pas l'ensemble
  des situations ; et le comportement « anytime » fait désormais consommer
  tout le budget restant après un premier succès, ce qui tend à augmenter
  le temps moyen par tour plutôt qu'à le réduire.
- **Performance** : rapide en début de partie (plateau simple, < quelques
  ms) ; sur un plateau chargé, trouve désormais un premier coup jouable
  en quelques dizaines de ms (voir ci-dessus), puis continue de chercher
  mieux jusqu'à expiration du budget — le repli total sur Avancé par
  manque de temps, fréquent avant #190, devient rare — voir le rapport
  de clôture #190 (et #186 pour les mesures d'origine, temps moyen/
  maximal par tour).
- **Tests** : `tests/test_ia.py` — le solveur retrouve au moins aussi bien
  chaque scénario déjà couvert par Avancé (échange direct, détachement en
  bout, libérations combinées, groupe de 4, scission en milieu de suite,
  groupe de 4 avec joker retiré), plus le démantèlement complet (#175),
  un scénario de mise initiale, un scénario sans aucun coup possible, et
  le repli sur budget de temps dépassé. Un ancien test spécifique à Expert
  (`test_expert_ne_detache_pas_un_joker_en_bout_de_suite_par_scission`) a
  été remplacé : le solveur y trouve légitimement un meilleur coup qu'« 
  aucun » (voir `test_expert_trouve_un_groupe_pour_le_joker_en_bout_de_
  suite`).
- **Nouvelle stratégie de recherche (#194, suite de #190)** : #190
  n'accélérait que les nœuds à candidats ex-aequo sur `_score_rapide` — ne
  réglait pas le cas où le coup optimal exige d'enchaîner plusieurs
  échanges de jokers à travers des zones différentes du plateau. Cas réel
  (tour 57 de Bruno, `tests/donnees/cas_expert_bruno_tour57.json`) : Expert
  n'avait posé qu'UNE tuile en partie, alors que le solveur en trouve 3
  (joker d'un groupe de 4 remplacé par la tuile d'une suite voisine) — mais
  seulement avec 10s de budget ; rien à 1.5s/3s/6s. Deux changements,
  combinés (voir la docstring de `moteur/solveur.py` pour le détail
  technique) :
  1. **Recherche par paliers croissants** (`_meilleur_rearrangement`,
     `_Contexte.objectif`, `_seuil_atteint`) : au lieu de viser l'optimum
     en une seule passe, le solveur cherche d'abord « au moins 1 tuile
     posable », puis si trouvé « au moins 2 », etc. Chaque palier coupe la
     recherche dès qu'il est atteint n'importe où dans l'arbre — prouver
     un petit palier est beaucoup moins coûteux que prouver l'optimum
     exact d'un coup. Le dernier palier PROUVÉ atteignable avant expiration
     du budget est renvoyé (comportement anytime déjà présent depuis #186,
     affiné ici par palier plutôt que par nœud).
  2. **Ordre de visite des emplacements par VALEUR** (`_ordre_slot`) plutôt
     que par couleur : visiter toutes les valeurs d'une seule couleur avant
     de passer à la suivante forçait la recherche à épuiser un bloc de
     couleur combinatoire avant d'atteindre un groupe utile à la main d'une
     tout autre couleur ; visiter par valeur croissante atteint ce groupe
     dès que sa valeur revient, et le palier correspondant coupe alors la
     recherche immédiatement.

  Ni l'un ni l'autre ne change le résultat optimal trouvé avec un budget
  suffisant pour explorer exhaustivement — seulement la vitesse pour
  l'atteindre. Les pistes « zones indépendantes du plateau » et
  « élagage anticipé sur une borne globale » évoquées par l'issue n'ont
  **pas** été retenues : la mémoïsation par nœud (déjà en place depuis
  #186) et le découpage en combinaisons gelées/flexibles
  (`_separer_combos_figees`, #190) couvraient déjà l'essentiel de ce
  gain pour un coût d'implémentation moindre — voir le rapport de clôture
  #194 pour la mesure avant/après sur les deux cas de référence
  (`cas_expert_budget_tour81.json` et `cas_expert_bruno_tour57.json`) et sur
  des parties réelles.
  Budget de production (`BUDGET_TEMPS_EXPERT`) **inchangé à 1.5s** : les
  deux cas de référence sont désormais résolus dans ce budget.
  Tests ajoutés : `test_solveur_cascade_joker_trouve_trois_tuiles_avec_
  gros_budget` et `test_solveur_cascade_joker_trouve_un_coup_avec_budget_
  de_production` (`tests/test_ia.py`), sur le nouveau cas de référence
  `cas_expert_bruno_tour57.json`.
- **Préférer le coup le plus simple à nombre de tuiles posées égal (#199,
  suite de #194)** : aucun des critères de départage ci-dessus ne tenait
  compte de la PERTURBATION du plateau — parmi toutes les solutions posant
  le même nombre de tuiles, le solveur pouvait renvoyer n'importe laquelle,
  y compris une qui défait et recrée plusieurs combinaisons pour ne poser,
  au final, qu'une seule tuile de la main. Cas réel (David, tour 31,
  `tests/donnees/cas_expert_coup_simple_david_tour31.json`) : un 1 noir à
  poser, qu'il suffisait d'ajouter au groupe de 1 (rouge, bleu, jaune) déjà
  posé pour en faire un groupe de 4 couleurs en un seul geste — Expert
  avait pourtant joué un coup en 12 étapes de pas-à-pas, fragmentant ce
  groupe pour reformer une suite jaune ailleurs. Réglage `preferer_simple`
  (`solveur.PREFERER_SIMPLICITE`, activé par défaut, exposé en paramètre de
  `resoudre_coup`/`jouer_niveau_expert` pour comparer les deux versions par
  simulation) :
  - **Mesure de perturbation** `(tuiles_déplacées, combinaisons_modifiées)` :
    nulle si un candidat n'utilise aucune tuile du plateau, ou si les
    tuiles du plateau qu'il utilise reproduisent EXACTEMENT une combinaison
    déjà posée avant ce tour (il ne fait qu'ajouter des tuiles de la main à
    cette combinaison, ou la reconduire à l'identique) ; non nulle sinon
    (fragmente ou fusionne des combinaisons existantes). Deux tuiles de
    même aspect (même valeur, même couleur, ou deux jokers quelconques)
    sont interchangeables, comme pour le pas-à-pas (#197,
    `description_coup.py::_aspect`) — calculée directement sur les
    compteurs par emplacement de la recherche (`_perturbation_candidat`),
    sans jamais reconstruire le plateau concret. `mesurer_perturbation`
    (API publique de `solveur.py`) calcule la même mesure, mais sur un
    plateau avant/après concret — utilisée par les tests et par
    `scripts/comparer_niveaux_ia.py`, pas par la recherche elle-même.
  - **Nouvel ordre de départage** : nombre de tuiles posées, puis
    perturbation minimale, puis points posés, puis économie de jokers
    (`_meilleur_rearrangement`, `ctx.cle`).
  - **Tri des candidats** (`_resoudre`) : la perturbation REMPLACE, plutôt
    que compléter, le critère de signature d'origine (#190) — la signature
    (forme + taille seulement, pas la composition exacte) aurait sinon pu
    faire gagner, par coïncidence de forme, un candidat qui FRAGMENTE une
    combinaison d'origine sur celui qui l'ÉTEND proprement, exactement le
    bug observé. Mesuré sur un cas déjà difficile pour la recherche
    (`cas_expert_ia_261026172338_tour61.json`, cascade de jokers à travers
    tout le plateau, #194) : AJOUTER la perturbation en plus de la
    signature (sans même réordonner les deux) suffisait déjà à faire
    manquer, à budget identique, le palier que trouvait de justesse
    l'ancien comportement — ce cas est nativement sans la moindre marge
    pour un coût supplémentaire par nœud de recherche ; REMPLACER la
    signature (plutôt que l'additionner) évite ce coût.
  - **Limite documentée** : un candidat qui ne reconstitue qu'une FRACTION
    d'une combinaison d'origine (celle-ci ayant été fragmentée entre
    plusieurs candidats) compte sa propre perturbation indépendamment de
    l'autre fragment — peut compter deux combinaisons modifiées là où un
    œil humain n'en verrait qu'une scindée en deux, sans jamais fausser la
    distinction nulle/non-nulle qui est l'essentiel de ce critère.
  - **Tests** (`tests/test_ia.py`) : le cas de David (coup trouvé touchant
    au plus une combinaison, zéro tuile déplacée) ; un petit plateau
    fabriqué où deux solutions posent la même seule tuile et où la plus
    simple est retenue (démarche de réduction du cas réel documentée dans
    le rapport de clôture #199) ; non-régression sur tous les cas de
    référence existants (`cas_expert_budget_tour81.json`,
    `cas_expert_bruno_tour57.json`, `cas_expert_humain_*`,
    `cas_expert_ia_*`) — au budget de production pour tous sauf
    `cas_expert_ia_261026172338_tour61.json`, structurellement instable à
    ce budget (le solveur y trouve souvent RIEN en 1.5s, avec ou sans le
    nouveau critère, bien avant #199 déjà) et donc testé séparément à
    budget large (12s).
  - **Mesure** (campagne Avancé vs Expert, 10 donnes x 2 miroir, seed 42,
    voir rapport de clôture #199 pour le détail) : taux de victoire
    d'Expert 95.0 % ± 9.6 pt AVEC le critère contre 80.0 % ± 17.5 pt SANS
    (IC qui se recoupent largement, écart non démontrable à cet
    échantillon — comme pour #190/#194, aucune baisse, donc le critère
    reste activé par défaut) ; perturbation moyenne par coup d'Expert
    2.43 tuiles déplacées / 2.19 combinaisons modifiées AVEC, contre
    3.00 / 2.63 SANS (baisse mesurée, conforme à l'objectif) ; temps moyen
    par tour d'Expert comparable (204 ms AVEC contre 221 ms SANS, maximum
    ~1.5 s dans les deux cas) ; replis sur Avancé par dépassement de budget
    légèrement MOINDRES avec le critère (0.6 % contre 1.5 % des tours
    d'Expert) — aucune dégradation observée.

### 8ter. Modèle EXACT d'Expert — programmation linéaire en nombres entiers (issue #206, suite de #204)

Depuis #206, Expert joue avec un **modèle exact** (`moteur/solveur_exact.py`)
qui trouve TOUJOURS le coup posant le plus grand nombre de tuiles, y compris
les victoires immédiates et les recombinaisons multi-zones que la recherche
arborescente de §8bis ratait (vérifié par le solveur exact de #204 : Bruno
tour 57 — 4 tuiles au lieu de 3, en coupant une suite rouge ; Ines tour 85 —
victoire immédiate de 2 tuiles manquée). La recherche de §8bis reste le
**repli** (voir plus bas), inchangée.

- **Méthode** : programmation linéaire en nombres entiers (den Hertog &
  Hulshof, *The Computer Journal*, 2006), résolue par **HiGHS** via `highspy`
  (licence MIT) + `numpy` (BSD) — **sans** `cvxpy` ni `scipy` (la « voie (b) »
  du rapport de #204, ≈3× plus légère : ~+55 Mo et ~+65 ms au démarrage, au
  lieu de ~+150-200 Mo et ~+0,8 s). On énumère une fois pour toutes tous les
  ensembles valides possibles (suites de longueur 3 à 5, groupes de 3-4,
  jokers en remplacement ; ~1170 ensembles — les suites plus longues sont
  recomposées par le modèle à partir des courtes, borne reprise de la
  bibliothèque de #204). Une variable entière `x_s ∈ {0,1,2}` par ensemble ;
  pour chaque type de tuile `i`, contrainte de conservation
  `t_i ≤ Σ a_{s,i} x_s ≤ t_i + r_i` (toutes les tuiles du plateau restent
  posées, on n'utilise pas plus de tuiles qu'on n'en a).
- **Critères de départage** (lexicographiques, par passes successives figeant
  l'optimum entier de la précédente ; le nombre de tuiles posées reste
  TOUJOURS le premier critère) : (1) tuiles posées, (2) perturbation minimale
  du plateau (#199 : tuiles déplacées puis combinaisons modifiées, via des
  variables d'affectation `cover`), (3) points posés, (4) économie de jokers
  de la main. Le cas de David tour 31 reste joué en un seul geste (extension
  d'un groupe, 0 tuile déplacée).
- **Mise initiale pas faite** : le plateau est GELÉ (reconduit à l'identique),
  les ensembles ne sont formés que depuis la main, avec la contrainte
  `Σ points_s x_s ≥ mise_initiale_min`. Contrairement à la bibliothèque de
  #204 (qui réarrange le plateau au second temps), le modèle maison respecte
  la règle ; un test le vérifie.
- **Reproductibilité & budget** : HiGHS en `threads=1`, `random_seed=0`,
  sortie muette, limite de temps ferme = budget de production d'Expert
  (`BUDGET_TEMPS_EXPERT`, 1,5 s). Toute combinaison renvoyée est remise dans
  l'ordre (suites, jokers aux bons endroits) puis **revalidée par
  `valider_combinaison`**, et la conservation des tuiles du plateau est
  contrôlée (comme l'adaptateur de #204) — un résultat qui échouerait n'est
  jamais joué.
- **Repli, sans jamais bloquer le jeu ni lever** : `jouer_niveau_expert`
  tente le modèle exact ; en cas d'absence de `highspy`/`numpy`
  (`SolveurExactIndisponible`), de budget dépassé sans solution
  (`BudgetExactDepasse`) ou d'erreur, il se replie sur la recherche de §8bis
  (`solveur.py`, conservée telle quelle), puis sur Avancé. `UTILISER_SOLVEUR_
  EXACT` (dans `ia.py`) ou `jouer_niveau_expert(..., utiliser_exact=False)`
  fige Expert sur l'ancienne recherche (campagne « avant / après »,
  `scripts/comparer_niveaux_ia.py --sans-exact`).
- **Chiffres (#206)** : sur les 10 cas de référence, le modèle exact atteint
  `attendu_exact_tuiles` sur **10/10** (écart nul avec l'optimum), en **406 ms
  en moyenne, 916 ms au plus** (budget 1,5 s). Campagne Avancé vs Expert
  (20 donnes × 2 miroir, graine 206) : voir le rapport de clôture #206 pour
  les chiffres avant/après (taux de victoire, replis, temps par tour,
  perturbation, démarrage). Tests : `tests/test_solveur_exact_maison.py`
  (optimum sur tous les cas, accord avec `verif_solveur` et avec la
  bibliothèque de #204 si installée, mise initiale, départage, replis).

### 8quater. Autotest de l'exécutable `--autotest` (issue #208, suite de #206)

Depuis #206, l'exécutable embarque `highspy` + `numpy` (modèle exact d'Expert,
§8ter). Si PyInstaller collecte mal ces paquets natifs, Expert retombe
**silencieusement** sur la recherche arborescente (§8bis) : rien, sans ouvrir
la fenêtre, ne permettait de le détecter. L'option `--autotest` (issue #208)
répond à ce risque.

- **Point d'entrée** : `main.py` détecte `--autotest` dans `sys.argv` **avant**
  tout import de `rummikub.ui.application` → ni `pywebview` ni le moteur de
  fenêtre ne sont chargés, aucune fenêtre ne s'ouvre. La logique vit dans un
  module dédié, embarqué et testable : **`src/rummikub/autotest.py`**
  (`executer_autotest(argv)`).
- **Ce qu'il vérifie et affiche** (quelques lignes lisibles) : version de
  Python, mode (sources / exécutable gelé), versions de `numpy` et `highspy`,
  présence des ressources web (`RACINE_WEB/accueil.html` + `jeu.html`), puis
  résout une **petite position intégrée** (plateau vide + suite 5-6-7 + groupe
  de 10, 6 tuiles attendues) avec `solveur_exact.resoudre_exact` et affiche le
  nombre de tuiles posées et la durée. **Code 0** si tout fonctionne, **1**
  sinon avec la cause. Ne lit/écrit **aucune donnée utilisateur** (ni SQLite ni
  `config.json`).
- **Rapport fichier** : l'exe Windows est fenêtré (`console=False`), sa sortie
  standard est perdue ; `--autotest <chemin>` écrit donc le même compte rendu
  dans ce fichier. Le script de build le récupère (`type`).
- **Script de build** (`build/rebuild_rummikub.bat`, Windows) : nouvelle
  sous-étape **5bis** — lance `dist\Rummikub\Rummikub.exe --autotest <log>`
  après PyInstaller, reprend le log dans le compte rendu, et **refuse le build**
  (exit 1) si le code de sortie n'est pas 0. Garde-fous de taille **élargis**
  pour numpy+highspy (valeurs provisoires, à confirmer au 1ᵉʳ build Windows) :
  dossier non compressé **20-120 Mo** (étape 5), installeur et zip compressés
  **5-50 Mo** (étapes 6/7).
- **`rummikub.spec`** : `excludes` ajoutés (issue #208) pour ne pas embarquer
  d'inutile — `scipy`, `matplotlib`, `pandas`, `tkinter`, Qt/PySide, et les
  sous-paquets de dev/compilation/tests de numpy (`f2py`, `distutils`,
  `testing`, `tests`, `array_api`). ⚠️ `numpy.libs/libscipy_openblas64_*.so`
  (~27 Mo) est l'**OpenBLAS vendu par numpy**, PAS le paquet `scipy` : il est
  **requis** et ne doit jamais être exclu.
- **Essai Linux (issue #208)** : build PyInstaller onedir validé hors dépôt
  (venv `.venv-exact`, gitignoré) → `--autotest` renvoie 0 (6 tuiles, HiGHS),
  dossier **~74 Mo** (numpy.libs 27 Mo + numpy 14 Mo + highspy 6 Mo + runtime).
  Aucun paquet exclu n'est entraîné. Un essai Linux ne remplace PAS le build
  Windows : il ne sert qu'à détecter tôt une erreur de collecte.
- **Tests** : `tests/test_autotest.py` (succès, dépendances absentes simulées,
  ressources manquantes, écriture du rapport, et garantie que `--autotest`
  n'importe jamais `pywebview`/l'UI).

### 8bis-bis. Coups de grande envergure et bug de mesure côté humain (issue #200, suite de #194)

- **Contexte** : `scripts/analyser_coups_rates.py --joueur "Alain" --budget 10`
  (#193) signalait 10 tours où le joueur humain aurait posé plus de tuiles
  que le solveur n'en trouve même à budget généreux, dont deux écarts
  énormes (+11, +15 tuiles) enregistrés comme cas de référence
  (`tests/donnees/cas_expert_humain_*.json`, clé `attendu_min_tuiles`).
  L'hypothèse de départ était une incomplétude du solveur sur les grandes
  mains (plusieurs dizaines de tuiles posées d'un coup, chevalet presque
  plein).
- **Diagnostic (voir le rapport de clôture #200 pour le détail des mesures
  par budget 1.5/10/30/60/120s)** : sur les 3 cas enregistrés, le chevalet
  réellement capturé ne contenait que 7, 3 et 3 tuiles — `attendu_min_tuiles`
  (18, 7, 18) dépassait donc la taille du chevalet lui-même, une cible
  **physiquement impossible** pour n'importe quel solveur (on ne peut jamais
  poser plus de tuiles que n'en contient la main). Le solveur trouvait déjà,
  en quelques centaines de ms à ~2s, le maximum réel (= la main entière) sur
  les 3 cas : aucune incomplétude démontrée, la limite était dans la MESURE,
  pas dans l'algorithme.
- **Cause réelle** : `analyser_decision_complete`
  (`persistance/coups_rates.py`) comparait le solveur au champ
  `nb_tuiles_posees` du journal (`"nb_tuiles_jouees"` une fois extrait), lui-
  même `len(data["ids_tuiles"])` côté `ui/api.py::jeu_jouer_coup` — la
  longueur BRUTE de la liste d'ids envoyée par le client JS pour une pose
  humaine (`tuilesCeTour`, `ui/web/jeu.js`), qui peut dépasser la taille
  réelle du chevalet d'avant-coup (mécanisme exact non élucidé côté JS —
  pas nécessaire pour la correction : il suffit de ne plus se fier à ce
  compteur). `jouer_tour` lui-même n'est jamais en cause : il ne retire du
  chevalet que les ids qui y figurent réellement (`set()`), donc aucune
  tuile n'a jamais été dupliquée ou perdue en jeu réel. Le module calculait
  pourtant déjà, juste à côté, une mesure fiable et bornée par construction
  (`ids_tuiles_reelles`, différence entre le chevalet d'avant et celui
  d'après la pose — déjà utilisée par `detecter_reserves_joueur`) sans
  jamais s'en servir pour `nb_tuiles_reel`. **Corrigé** : `nb_tuiles_reel`
  utilise désormais `len(ids_tuiles_reelles)` pour une pose, plus jamais le
  champ brut — corrige à la source le calcul de `joueur_bat_solveur`/
  `pose_sous_optimale` et tout ce qui en dépend (résumé, enregistrement des
  cas de référence). Les 3 `attendu_min_tuiles` corrigés (7, 3, 3,
  désormais égaux à la taille du chevalet) ; les 3 fichiers restent des
  tests de non-régression légers (plus des cas « grande envergure »).
- **Les 3 cas `cas_expert_ia_*.json` (IA Expert d'avant #194, jugée par le
  solveur actuel), eux, étaient authentiques dès l'origine** (chevalet et
  `attendu_min_tuiles` cohérents) : `tour37` déjà trouvé au budget de
  production (1.5s) ; `tour59` manquait sa dernière tuile (6/7) ; `tour61`
  (cascade de jokers à travers 13 combinaisons, déjà documentée #194 comme
  à la limite du budget) ne trouvait souvent RIEN en 1.5s, jusqu'à 10s
  nécessaires pour les 4 tuiles attendues.
- **Optimisation appliquée (profilage `cProfile` sur ces deux cas)** :
  `_candidats_suite` dominait le temps (jusqu'à 40% du temps total) en
  reconstruisant l'intégralité des tokens de l'intervalle `[v1, v2]` depuis
  zéro pour CHAQUE largeur testée (coût quadratique dans la largeur de la
  fenêtre `_FENETRE_SUITE`, pour chaque ancre). Réécrit pour construire les
  tokens une seule fois par `v1`, en étendant `v2` d'une position à la fois
  (le nombre de jokers ne pouvant que croître avec la fenêtre, un
  dépassement du nombre de jokers disponibles ou deux jokers consécutifs le
  reste pour toute extension ultérieure — on arrête alors d'étendre ce `v1`
  au lieu de continuer à générer des candidats rejetés). Équivalence avec
  l'ancienne version vérifiée par comparaison exhaustive sur 20000 états
  aléatoires et par la suite de tests complète (187 tests, aucune
  régression) — ce n'est qu'une accélération, jamais un changement de
  résultat, donc valable à tous les niveaux et toutes tailles de main (les
  petites mains, déjà rapides, ne sont pas pénalisées).
- **Résultat mesuré** : `tour59` passe de ~3s à ~2s pour sa dernière tuile
  (reste juste AU-DESSUS du budget de production strict de 1.5s : parfois
  atteint de justesse, parfois non selon la charge machine — fiable à
  partir de ~2s) ; `tour61` passe de ~10s à ~5s (reste nettement hors de
  portée du budget de production). Le budget de production n'a PAS été
  augmenté (dernier recours, non justifié pour un gain qui resterait de
  toute façon loin de la cible pour `tour61`, et marginal pour `tour59`) —
  ces deux cas restent documentés comme hors de portée du budget de
  production de 1.5s, pas corrigés plus avant dans cette issue.
- **Pas de piste « grande main » retenue parmi celles envisagées** : sur
  les cas réels disponibles, geler moins de combinaisons pour une main
  large n'aurait rien changé (une main qui touche déjà les 4 couleurs gèle
  déjà 0 combinaison, voir `_separer_combos_figees` — c'est automatique, pas
  un réglage à ajuster) ; faire monter les paliers plus vite (bonds de 2+
  plutôt que +1) a été écarté : si le palier visé n'est pas atteignable, la
  recherche dégénère vers l'ancien comportement pré-#194 (preuve exhaustive,
  justement ce que #194 avait corrigé) ; chercher d'abord en partant du
  haut (toute la main, puis main-1...) a été écarté pour la même raison (le
  plafond optimiste est une borne, pas une garantie d'atteignabilité).
  Aucun cas réel de « grande main » authentiquement bloquée par le solveur
  n'a été trouvé pour justifier ces pistes plus risquées — voir le rapport
  de clôture #200 si un nouveau cas apparaît.
- **Tests** (`tests/test_ia.py`) : un test à gros budget (10s) et un test
  au budget de production (tolérance ×6, comme #190/#194) par cas de
  référence pour les 5 cas désormais atteints
  (`cas_expert_humain_261026172338_tour66.json`,
  `cas_expert_humain_261026174101_tour81.json`,
  `cas_expert_humain_261026213723_tour65.json`,
  `cas_expert_ia_261026172338_tour37.json`,
  `cas_expert_ia_261026172338_tour59.json`) ; un test à gros budget (12s)
  seul pour `cas_expert_ia_261026172338_tour61.json` (volontairement pas de
  test au budget de production pour ce cas, qui serait soit flaky soit
  trompeur avec une tolérance large).

## 17. Vérifier qu'Expert ne décompose jamais le plateau inutilement (issue #215, suite de #199)

Le profil d'Expert (§16, `scripts/profil_joueur.py`) montre qu'environ deux
tiers de ses poses sont « grandes » (elles **touchent** 3 combinaisons du
plateau ou plus). Question d'Alain : ces grosses recompositions sont-elles
toutes NÉCESSAIRES, ou l'IA décompose-t-elle parfois le plateau pour rien ? Le
critère de simplicité de #199 (« à nombre de tuiles posées égal, préférer le
coup qui perturbe le moins le plateau » — `moteur/solveur.mesurer_perturbation`
pour la MESURE, départage par variables `cover` dans
`moteur/solveur_exact.py`) est censé l'empêcher. #215 le vérifie
**systématiquement** (et non sur quelques cas isolés) et fournit à Alain des
exemples lisibles.

**`scripts/verifier_simplicite_expert.py`** (script d'analyse SEUL — aucune
modification du moteur/IA/solveur). Pour chaque pose d'Expert :

1. mesure la perturbation du coup RÉELLEMENT joué (`mesurer_perturbation` #199 :
   `(tuiles du plateau déplacées, combinaisons modifiées)`) ;
2. interroge INDÉPENDAMMENT le solveur (modèle exact `solveur_exact` si
   `highspy`/`numpy` dispo, sinon recherche `solveur`) avec un budget GÉNÉREUX
   (`--budget-juge`, 5 s par défaut > 1,5 s de production) pour obtenir « le
   coup le plus simple posant le plus de tuiles » (max tuiles, puis
   perturbation minimale) ;
3. quand les deux posent le MÊME nombre de tuiles (cas normal, Expert maximise
   toujours), compare les perturbations → écart de simplicité. Un coup qui pose
   MOINS que l'optimum (budget/coup raté, cf. §11) est compté à part, hors sujet.

Deux sources : **journaux** (`--journaux DIR`, poses d'Expert reliées comme #202
via `persistance/parties_liees`) ou, à défaut, **simulation** d'Expert contre
lui-même. Le script affiche la distribution, l'écart moyen/maximal, et la
proportion de GROS coups qui sont des décompositions nécessaires.

Il produit aussi, dans un **dossier de SORTIE** (`--sortie`, hors du dépôt — par
défaut un sous-dossier du répertoire temporaire ; `_sortie_locale/` et
`exemples_simplicite_expert.txt` sont gitignorés), le fichier
**`exemples_simplicite_expert.txt`** : une dizaine de cas variés (petits, moyens,
grands ; au moins un où Expert décompose beaucoup), chacun décrit en français
clair SANS jargon — plateau de départ ENTIER, main complète, nombre de tuiles
posables, coup joué étape par étape (réutilise `moteur/description_coup.py`),
plateau d'arrivée ENTIER, le coup plus simple s'il existe (plateau d'arrivée
entier aussi), et une ligne « décomposition nécessaire / évitable ».

Résultat de la campagne (simulation Expert, 12 parties, 323 poses, budget-juge
5 s) : **100 % des poses sont au minimum de perturbation, 0 décomposition
évitable** — dont 208 « gros » coups (3+ combinaisons touchées, soit ~64 %,
cohérent avec le ~68 % du profil) **tous nécessaires**. Nuance importante :
« toucher 3 combinaisons » (métrique du profil) n'est PAS « déplacer des
tuiles » — beaucoup de gros coups prolongent/reforment des combinaisons sans
déplacer la moindre tuile (perturbation nulle). Le critère de #199 tient donc
ses promesses sur cet échantillon. Si un écart non nul apparaissait, le script
le SIGNALE (sans corriger le solveur : correction = issue dédiée).

Commande pour Alain (sur ses propres parties) :

```
PYTHONPATH=src python3 scripts/verifier_simplicite_expert.py \
    --journaux data/logs_parties --sortie /tmp/simplicite_expert
# ou, sans journaux, par simulation :
PYTHONPATH=src python3 scripts/verifier_simplicite_expert.py --donnes 20
```

### Tests

`tests/test_verifier_simplicite_expert.py` : description française d'une
combinaison (groupe, suite, suite avec joker) ; un coup déjà minimal → écart nul
(« nécessaire ») ; un coup artificiellement SUR-DÉCOMPOSÉ (combinaison éclatée en
deux) → écart bien détecté (« évitable ») ; un coup posant moins que l'optimum
exclu du calcul ; le juge indépendant et l'enchaînement complet
(`analyser_coup`/`rediger_exemple`) sur un état jouable. Tournent sans
dépendance externe (le juge se replie sur la recherche arborescente).

