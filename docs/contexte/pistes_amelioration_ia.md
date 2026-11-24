# Pistes d'amélioration de l'IA à tester

## 13. Pistes d'amélioration de l'IA à tester (issue #195)

Idées formulées par Alain au fil des parties de calibrage contre Expert,
tirées de sa façon de jouer. **Aucune n'est implémentée** : ce sont des
pistes pour la future révision des niveaux de difficulté, à cocher une par
une au fur et à mesure que de futures issues les testent/implémentent.

- [ ] **Piste 1 — Réserve d'un coup (garder un coup pour le tour
  suivant)** : plutôt que de poser toutes les tuiles possibles en un tour,
  en garder une pour le tour suivant afin d'éviter de piocher (deux tours à
  une tuile plutôt qu'une pose de deux tuiles suivie d'une pioche).
  **Risque** : l'adversaire peut occuper la place laissée libre entre les
  deux tours. **Test** : nécessite d'évaluer un coup sur deux tours, pas un
  seul ; l'analyse des coups d'un joueur humain (§11, et la fiabilisation à
  venir de cette analyse) donnera les premières statistiques sur
  l'efficacité réelle de cette technique chez un humain avant d'envisager
  de l'implémenter côté IA.
- [ ] **Piste 2 — Éliminer en priorité les doublons de la main** : quand la
  main contient deux tuiles identiques (même valeur, même couleur), chercher
  à en poser une le plus vite possible, car deux tuiles identiques ne
  peuvent jamais entrer dans la même combinaison et sont donc plus
  difficiles à placer. Exemple d'Alain : main `1 rouge, 2 rouge, 2 rouge,
  3 rouge, 3 bleu, 3 noir` → jouer la suite 1-2-3 rouge plutôt que le groupe
  de 3, pour faire partir un des deux `2 rouge`. **Hypothèse** : à nombre de
  tuiles posées égal, préférer le coup qui laisse la main restante la plus
  facile à placer (moins de doublons, moins de tuiles isolées).
  **Test** : le départage actuel du solveur entre coups équivalents se fait
  par points puis par économie de jokers (§8bis) ; ajouter un critère
  d'évaluation de la main restante, puis comparer les deux versions avec
  `scripts/comparer_niveaux_ia.py` (§9, donnes jouées en miroir, plusieurs
  dizaines de donnes) pour voir si le taux de victoire change de façon
  significative.
- [ ] **Piste 3 — Plus de temps de réflexion pour Expert, ou un niveau
  au-dessus** : la force d'Expert dépend directement de son budget de temps
  (voir les mesures de #187 et #190, §8bis/§9). Un niveau supplémentaire qui
  réfléchirait plus longtemps, ou qui calculerait sur deux tours, pourrait
  se situer au-dessus du niveau de jeu d'un humain.
- [ ] **Piste 4 — Procédure commune d'évaluation d'une piste** : comparer
  deux versions de l'IA avec les parties jouées en miroir de
  `scripts/comparer_niveaux_ia.py` (§9), vérifier le nombre de parties et la
  marge d'erreur (IC 95 %) affichés par le script, et ne retenir une piste
  que si le gain est significatif ET que le temps de calcul par tour reste
  raisonnable.
- [ ] **Piste 5 — Rôle des points dans le départage** : le solveur
  départage aujourd'hui les coups équivalents en préférant celui qui pose
  le plus de points (§8bis). Dans une partie d'une seule manche (§3bis,
  configuration actuelle de l'application), ces points ne changent le
  vainqueur que si la partie se termine **bloquée** (pioche épuisée ET plus
  personne ne peut jouer un tour complet — vraie règle implémentée par
  #255, voir §3bis/§4 ; avant #255 cette description n'était qu'une
  hypothèse, la fin « pioche vide » étant alors immédiate quel que soit le
  coup) : gagne alors celui dont les tuiles restantes valent le moins.
  Sinon, la partie est gagnée par celui qui vide son chevalet en
  premier, et les points ne changent que la marge affichée en fin de
  partie. **Hypothèse** : le critère des points ne devrait passer en
  premier que si la pioche est vide ou presque, ou si plusieurs manches
  sont jouées (score cumulé) ; le reste du temps, il devrait laisser la
  place à l'évaluation de la main restante (piste 2). **Test** : comparaison
  par simulation, comme pour la piste 2.
- [ ] **Piste 6 — Se débarrasser en priorité des 1 et des 13** (idée d'Alain,
  #203) : les tuiles de valeur 1 et 13 entrent dans **moins de combinaisons**
  que les valeurs intermédiaires (un 1 ne peut prolonger une suite que par le
  haut, un 13 que par le bas ; comme toute valeur, chacune n'entre que dans un
  seul groupe de sa valeur) — elles sont donc plus difficiles à placer et
  plus coûteuses si elles restent en main à la fin d'une manche. **Hypothèse** :
  à nombre de tuiles posées égal, préférer le coup qui fait partir un 1 ou un
  13. Proche de la piste 2 (éliminer les doublons) : un critère d'évaluation
  de la main restante au départage du solveur. **Test** : comparer deux
  versions avec `scripts/comparer_niveaux_ia.py` (§9), en miroir.
- [ ] **Piste 7 — Tenir compte des points restants, mais seulement en
  plusieurs manches** (idée d'Alain, #203, précision de la piste 5) : depuis
  #203, un match peut compter plusieurs manches et les points restants
  s'accumulent au `score_cumul` — ils comptent alors réellement pour la
  suite, pas seulement pour la marge affichée. L'IA pourrait en tenir compte
  (se défausser des grosses tuiles, limiter la casse quand elle ne peut pas
  gagner la manche) **uniquement quand `nb_manches > 1`**. **Prudence
  explicite d'Alain** : ne pas accorder trop d'importance aux points au
  risque de **perdre des manches** qu'on aurait gagnées en vidant son
  chevalet — le premier objectif reste de finir la manche. En une seule
  manche, ce critère ne vaut que pour les parties bloquées (voir piste 5).
  **Test** : simulation en miroir avec `--manches N` (§9).
- [ ] **Constat — fiabilité du réglage « Nombre de manches » (corrigé par
  #203)** : ce réglage comparait jadis le numéro de tour au nombre de manches
  sans vrai compteur, si bien que plusieurs manches ne fonctionnaient pas
  (#192 l'avait alors masqué, §3bis). **#203 l'a corrigé** : vrai compteur
  `manche_numero`, scores cumulés, classement final au cumul — le réglage est
  de nouveau disponible (défaut 1 manche). La piste 5 ci-dessus reste donc
  valable telle quelle pour les parties d'une seule manche (où les points ne
  départagent que les parties bloquées) ; les pistes 6 et 7 en découlent.
  Entre joueurs humains, Alain n'a jamais observé de partie bloquée : les
  fins de partie bloquées vues en simulation (29 % au départ selon #184,
  environ 5 à 10 % avec le solveur d'Expert selon #186/#187, §9) sont un
  signe de faiblesse de l'IA plutôt qu'un phénomène normal du jeu, et leur
  proportion est un **indicateur de qualité à suivre** : elle doit baisser
  quand l'IA progresse.
- [x] **Traitée (#199) — simplicité du coup à nombre de tuiles posées
  égal** : observation d'Alain qui a motivé cette issue (voir §8bis pour le
  détail technique) — complexifier le plateau (défaire/recréer des
  combinaisons pour poser le même nombre de tuiles) n'a **aucun bénéfice
  stratégique démontré** : la campagne Avancé vs Expert avec et sans le
  critère de simplicité (§8bis, §9) ne montre aucune baisse du taux de
  victoire d'Expert en le préférant systématiquement, et sa perturbation
  moyenne du plateau par coup baisse nettement. La simplicité est donc
  désormais un critère MESURÉ (`mesurer_perturbation`, `moteur/solveur.py`)
  et appliqué par défaut, pas seulement une préférence de lisibilité pour
  le pas-à-pas — contrairement aux pistes 2 et 5 ci-dessus (évaluation de
  la main restante, rôle des points), désormais testées par #211 (voir
  l'entrée dédiée ci-dessous).
- [x] **Testée (#211) — évaluation de la main restante (pistes 2, 5, 6, 7)** :
  une **évaluation de la main restante** (doublons, tuiles de bord graduées
  1/13 > 2/12 > milieu, points restants pondérés par le nombre de manches) a
  été implémentée (`moteur/evaluation_main.py`) et intégrée au **modèle exact**
  comme objectif secondaire linéaire, JAMAIS avant le nombre de tuiles posées
  (`moteur/solveur_exact.py` : termes par ensemble pour bords/points, variable
  auxiliaire `d_i` par doublon). La tuile **isolée** est laissée de côté dans le
  solveur (non linéarisable simplement — elle dépend du reste de la main), et
  seulement calculée pour les tests/l'affichage. Deux ordres vs la simplicité
  ont été essayés (`apres_simplicite`, défaut ; `avant_simplicite`).

  **Mesure** (`scripts/comparer_niveaux_ia.py --eval-a off --eval-b <preset>`,
  30 donnes = 60 matchs en miroir, seed 42 ; marge d'erreur ±12,6 pt à 95 % ;
  camp A = Expert de référence `off`, camp B = variante) :

  | Variante (camp B)       | 1 manche : victoires B / score cumulé moyen B | 3 manches : victoires B / cumul B |
  |-------------------------|:--:|:--:|
  | doublons seuls          | 46,7 % / −0,4 | — |
  | bords seuls             | 48,3 % / −1,0 | — |
  | complet (d+b+p)         | 46,7 % / −1,6 | 48,3 % / −0,4 |
  | complet, ordre *avant*  | 48,3 % / −0,3 | — |
  | points nul              | — | 46,7 % / −2,2 |
  | points faible (poids 1) | 48,3 % / −0,4 | 45,0 % / −1,6 |
  | points moyen (poids 3)  | — | 46,7 % / −1,0 |
  | points fort (poids 8)   | — | 46,7 % / −1,1 |

  **Conclusion : aucun critère, à aucun poids ni dans aucun des deux ordres,
  n'apporte de gain significatif** — tous les taux de victoire restent à moins
  de 12,6 pt de 50/50, aussi bien en 1 manche qu'en 3 manches. Temps de calcul
  par tour inchangé en pratique (moyenne ≈ 180–215 ms, max sous le budget de
  1,5 s ; +10 % sur les positions typiques, +30 % sur les cas de référence les
  plus lourds, l'évaluation ajoutant une passe MIP sur le même petit modèle).
  Perturbation moyenne du plateau inchangée (≈ 1,76 tuile déplacée / coup).

  **« À partir de quel poids les points deviennent-ils contre-productifs ? »** :
  dans cet échantillon, **aucun seuil n'est atteint jusqu'au poids 8**. Le poids
  fort ne dégrade pas le taux de victoire (46,7 %, égal au poids nul) et réduit
  même légèrement le déficit de score cumulé (−2,2 à poids nul → −1,0/−1,1 à
  poids moyen/fort, en 3 manches) — l'effet reste sous le plancher de bruit à
  30 donnes. **Cause probable de l'absence de gain** : le modèle exact vide déjà
  les chevalets très vite (dans ces campagnes, **180/180 manches terminées
  chevalet vidé, 0 bloquée**) ; quand personne n'est bloqué, la qualité de la
  main restante départage rarement le vainqueur, qui est décidé par le premier
  chevalet vidé — ce que le critère primaire (nombre de tuiles posées) maximise
  déjà. L'exemple d'Alice (poser la suite 1-2-3 rouge plutôt que le groupe pour
  écouler un doublon `2r` + le bord `1`) est bien reproduit par l'évaluation
  (test `test_eval_depart_departage_exemple_alice`), mais ces départages n'ont
  pas d'effet mesurable sur l'issue des parties à cette échelle.

  **Adoption** : conformément au point 4 de l'issue, **l'évaluation est livrée
  DÉSACTIVÉE par défaut** (`moteur/ia.EVAL_MAIN_DEFAUT`, `active=False`). Tout le
  mécanisme reste en place et réglable en un seul endroit
  (`moteur/evaluation_main.py`) ; une campagne beaucoup plus large (plusieurs
  centaines de donnes) serait nécessaire pour résoudre un éventuel effet
  sous-bruit, en particulier dans les situations bloquées (rares ici). À
  réactiver seulement si un tel gain est un jour démontré.
- [ ] **Piste 8 — Ne pas libérer un joker pour rien** (idée d'Alain, #213,
  documentation seulement — non implémentée). Observé en jeu : Alain pouvait
  récupérer un joker du plateau en posant une tuile, mais n'avait aucune
  combinaison à former avec ce joker ; le replacer en bout de suite ou en 4e
  tuile d'un groupe l'aurait rendu **disponible à l'adversaire** au tour
  suivant. Il a préféré ne pas jouer. Un solveur qui n'optimise qu'UN tour (le
  modèle exact actuel) libérerait le joker et le reposerait quand même, offrant
  une ressource à l'adversaire sans gain pour soi. Deuxième cas, plus net :
  l'IA a elle-même LAISSÉ un joker en bout d'une suite (joker-6-7-8, joker en
  1re position), donc immédiatement reprenable par l'adversaire (poser le 5 de
  la couleur le remplace et libère le joker) ; elle aurait pu le placer
  autrement pour ne pas l'offrir. **Piste** : à nombre de tuiles posées égal,
  pénaliser un coup qui, dans le plateau résultant, laisse un joker en position
  **facilement reprenable** — que l'IA vienne de le replacer OU qu'il y était
  déjà et qu'elle aurait pu l'enfouir — c'est-à-dire un joker en **bout de
  suite** (valeur à une extrémité) ou en **4e tuile d'un groupe**. Plus fin :
  évaluer le coup sur deux tours. **Exception qui prime sur cette piste ET sur
  toutes les pistes de prudence** (réserve d'un coup, points restants, joker
  reprenable, rétention défensive) : **si le coup vide le chevalet, il gagne la
  partie** — il n'y a pas de tour suivant, donc aucun critère « pour plus tard »
  ne doit jamais empêcher ni dégrader un coup qui gagne immédiatement ; tout
  critère de prudence ne s'applique qu'aux coups laissant au moins une tuile en
  main. Ce garde-fou est **déjà appliqué** par l'échelle de #213 (un coup qui
  vide la main n'est jamais « oublié » ni bridé, voir §16 et
  `moteur/ia.jouer_niveau_bride`). Lien avec la piste 1 (réserve d'un coup,
  évaluation sur deux tours) et les critères de départage de l'évaluation de la
  main. **À tester une fois l'échelle des niveaux en place (faite par #213).**
- [ ] **Piste 9 — Rétention défensive de tuiles** (idée d'Alain, #213,
  documentation seulement — non implémentée). Observé : Alain a gardé en main
  une suite complète (p. ex. 2-3-4-5-6 d'une couleur) du début à la fin, au
  lieu de la poser, pour **priver l'adversaire** des tuiles qu'elle contient —
  risqué (grosse pénalité en cas de défaite) mais payant en une seule manche,
  où la pénalité ne change pas le résultat. Cas réel mesuré (journal d'une
  partie gagnée contre Expert) : Alain a gardé la suite 2-3-4-5-6 rouge pendant
  8 tours (5 tuiles), puis 4 tuiles pendant 3 tours, avant de tout poser au coup
  final — il a gagné (Expert resté à 3 tuiles). Un solveur qui pose le maximum
  à chaque tour ne fait jamais cela. **Nuance d'Alain** : la valeur des tuiles
  retenues doit entrer dans le calcul, d'autant plus en plusieurs manches.
  Retenir 2-3-4-5-6 (20 pts de risque) est acceptable ; retenir 9-10-11-12-13
  (55 pts) est bien plus risqué et, en multi-manches (où les points cumulés
  décident), probablement à éviter. En une seule manche, la valeur importe peu
  (la pénalité ne change que la marge, pas le résultat) ; en plusieurs manches,
  elle devient déterminante. La rétention doit donc **pondérer le gain défensif
  par la valeur des tuiles retenues et par le poids des points du mode de jeu**
  (lié à la piste 5/7). **Précision qui rend la piste CALCULABLE sans voir la
  main adverse** : l'IA connaît les 106 tuiles, les siennes et celles du tapis ;
  par soustraction, elle connaît l'ensemble exact des tuiles « ailleurs » (main
  adverse + pioche), la taille du sac, et peut estimer la taille de la main
  adverse à partir des parties déjà jouées (pondérée par la phase : souvent
  >10 tuiles au début, <5 en fin — statistique à tirer des journaux, par
  joueur). De là, pour une tuile donnée, elle estime la **probabilité** qu'elle
  soit dans la main adverse plutôt que dans le sac, donc la probabilité qu'une
  pièce retenue prive réellement l'adversaire. La stratégie : retenir une pièce
  (de préférence de faible valeur, surtout en multi-manches) quand la
  probabilité qu'elle serve à l'adversaire est élevée et que la garder ne
  compromet pas sa propre sortie. À relier à la piste 1 (réserve) et à
  l'évaluation sur deux tours. **Piste avancée, très difficile** (l'IA ne voit
  pas la main adverse) : à ne considérer que pour un niveau au-dessus
  d'Expert, aujourd'hui inexistant, et après les pistes plus simples.

> **Note #213 (historique).** La structure cible imaginée alors réservait les
> stratégies multi-tours des pistes 1, 8 et 9 ci-dessus à **Expert** (versions
> PARTIELLES, dosées) et à un niveau supplémentaire au-dessus, « Champion du
> Monde » (versions COMPLÈTES). Ce niveau a depuis été ajouté (#219 à #233)
> puis entièrement retiré, sa mesure n'ayant montré aucun effet net — voir
> l'archive en fin de cette section (§13). Les pistes 1, 8 et 9 restent
> valables telles quelles pour Expert seul, qui reste le niveau le plus fort
> de l'échelle (§16).

- [x] **Réalisée (#226) — mesure : où se décident les parties (trace par
  tour + analyse par phases).**

  Motivation : sur 600 matchs Expert/Champion du Monde (#221 + #225), aucune
  des deux stratégies de fin de partie n'a jamais changé un coup, et 58 % des
  tours de fin de partie sont des pioches. Avant de choisir les prochaines
  pistes de l'arbre ci-dessus (Ouverture, Tuiles vivantes, Modèle adverse,
  Course, Rétention), il fallait savoir OÙ se décident réellement les
  manches. **Issue de MESURE uniquement : ne modifie ni le jeu, ni les
  niveaux, ni le solveur, ni l'interface.**

  **Découpage en trois phases, JOUEUR PAR JOUEUR** (l'ouverture d'un joueur
  est indépendante de celle de l'autre — les phases ne sont PAS définies
  pour la manche entière) :
  1. **Prologue** : tous les tours d'un joueur avant sa propre ouverture (y
     compris le tour de l'ouverture elle-même, qui le clôt) — il ne peut ni
     toucher au tapis ni s'en servir, seul le contenu de sa main compte.
  2. **Développement** : après l'ouverture, tant que son chevalet compte
     PLUS de N tuiles au début du tour.
  3. **Fin** : chevalet de N tuiles ou moins au début du tour, après
     l'ouverture. N est réglable À L'ANALYSE (défaut 5, essayer aussi 6) —
     jamais figé dans la trace elle-même.

  **Trace par tour** (`scripts/comparer_niveaux_ia.py --export-trace
  FICHIER`, JSON Lines, option indépendante d'`--export-resultats` et
  **désactivée par défaut** — aucun changement sans elle) : une ligne par
  tour (donne, ordre des joueurs, manche, numéro de tour, camp, niveau,
  index du joueur, chevalet avant/après, "déjà ouvert" avant/après, action
  RÉELLEMENT exécutée — `pose`/`pioche`/`passe`, un coup rejeté retombant sur
  une pioche de secours est tracé comme une pioche —, tuiles posées, points
  posés, taille de la pioche avant, présence d'un joker en main avant) + une
  ligne de résultat par manche effectivement terminée (vainqueur, tuiles
  restantes du perdant, type de fin). Lit l'état complet de la partie à des
  fins de MESURE seulement (jamais une décision d'IA, jamais lu par le
  moteur ni par aucun niveau).

  **Script d'analyse** (`scripts/analyser_phases.py FICHIER --seuil N`,
  `--seuil` répétable, défaut 5) : pure lecture/regroupement par manche
  (indépendante d'une manche à l'autre, même au sein d'un match à plusieurs
  manches — redistribution complète à chaque `nouvelle_manche`). Rapporte,
  pour chaque phase et pour le gagnant/le perdant de la manche : durée
  moyenne en tours, tuiles posées par tour, fréquence des pioches ; plus le
  tour d'ouverture (moyenne/médiane/min/max), le nombre de pioches avant
  l'ouverture et la taille du chevalet à ce moment. **Question centrale** :
  l'écart de tuiles restantes en main entre les deux joueurs (a) à la FIN du
  prologue (quand le SECOND joueur à ouvrir vient d'ouvrir) et (b) à
  l'ENTRÉE en phase Fin de CHAQUE joueur (deux événements possibles par
  manche, regroupés dans le rapport) — et, à chacun de ces moments, le taux
  de victoire du joueur alors en avance (moins de tuiles en main ; égalités
  comptées à part, jamais mêlées au taux). Permet de voir, sans rejouer la
  moindre partie, à quelle phase l'écart se creuse vraiment — et de changer
  N pour vérifier si la réponse en dépend.

  **Vérifié** (`tests/test_export_trace.py`, `tests/test_analyser_phases.py`)
  sur une partie courte rejouée en vrai (Débutant contre Débutant) et sur de
  petits fichiers de trace fabriqués à la main, dont un cas où le seuil N
  change explicitement la classification d'un même tour (chevalet de 6
  tuiles, déjà ouvert : développement à N=5, fin à N=6) — aucune campagne
  longue rejouée par l'agent de cette issue, conformément à CONTEXTE.md §7.
  Un essai de 2 donnes (4 matchs) Expert contre Champion du Monde, au
  premier plan, a validé la chaîne complète trace → analyse sur du vrai
  jeu avant de remettre les commandes de campagne à Alain.

  **Pour mémoire — quelles pistes de l'arbre ci-dessus relèvent de quelle
  phase** (à affiner une fois une vraie campagne analysée) : Prologue →
  Ouverture (probabilité qu'une tuile d'ouverture soit encore disponible) ;
  Développement → Tuiles vivantes, Modèle adverse (Indices) ; Fin →
  vérification de finition (#221) et joker gardé (#225), dont la rareté
  d'activation a motivé cette issue. Rétention et Course dépendent des
  trois phases à la fois (évaluation de la main/estimation de qui finira
  le premier, quelle que soit la phase en cours).

### Hypothèses de stratégie issues de la recherche web (nov. 2026)

En novembre 2026, Alain et Claude (conversation de conception) ont cherché
sur internet ce que les joueurs et les éditeurs de Rummikub disent de la
stratégie, pour cesser de choisir les prochaines stratégies de l'IA à
l'intuition. La recherche a couvert l'anglais, le néerlandais, l'allemand,
le français, l'hébreu, le japonais, l'espagnol et le portugais. Les pays
les plus performants en compétition sont les Pays-Bas (quatre titres
mondiaux), le Japon (trois), le Brésil et l'Égypte (un chacun), Israël
(pays d'origine du jeu) n'en ayant gagné aucun (chiffres d'un article de
2018) : le néerlandais était donc la langue la plus utile, et c'est elle
qui a donné les meilleures sources. L'hébreu, le japonais et le portugais
n'ont presque rien donné.

**1. Méthode et règle de comptage**
- Les sites qui recopient le règlement officiel (par exemple
  `rulespal.com`, `scribd.com`, `rummikub.yolasite.com`) ne comptent que
  pour UNE source avec lui.
- Fiabilité : « solide » = règlement officiel, ou joueur de très haut
  niveau cité nommément ; « faible » = blog, site de conseils sans auteur,
  agrégateur, extrait sans source claire.
- Des sites générés automatiquement (par exemple `pop.killingthyme.net`,
  `db1.seeclickfix.com`) ont été écartés : ils contiennent des erreurs de
  règles (par exemple de prétendus points bonus par groupe).
- Littérature scientifique : le problème d'un SEUL tour (poser le maximum
  avec sa main et le tapis) est étudié et résolu (programmation linéaire
  en nombres entiers : den Hertog et Hulshof, The Computer Journal 49(6),
  2006 ; algorithme en temps polynomial : van Rijn et al., « The
  Complexity of Rummikub Problems », arXiv 1604.07553). Aucun travail
  publié n'a été trouvé sur la stratégie multi-tours de la partie
  complète.

**2. Tableau des hypothèses**
- **H1. Se retenir au début : ne pas tout poser, laisser les autres
  ouvrir la table.** 3 solides + 1 faible. Règlement officiel
  (Lemada/Hertzano) ; Matthijs Delvers, ex-champion du monde néerlandais
  (« ne pas poser chaque tuile tout de suite ») ; Rixt van Perlo,
  championne des Pays-Bas (garde longtemps toutes ses tuiles puis les pose
  d'un coup, ce qu'elle dit être habituel). Une page d'apprentissage en
  ligne (oboe.com), vague et faible, déconseille de se précipiter pour
  l'ouverture.
- **H1 inverse. Poser le plus tôt possible.** 2 faibles : un blog
  (mechanicsofmagic.com : cette stratégie semble préférée parce que le
  tapis change) et un article japonais (roomie.jp) qui dit que réussir
  tôt les 30 points pèse beaucoup sur le résultat (voir H8).
- **H2. Garder la 4e tuile d'un groupe ou d'une suite et n'en poser que
  trois pour avoir un coup au tour suivant au lieu de piocher.** 1 source
  (règlement officiel, éditions Pressman et Piatnik). Variante de
  l'édition Jumbo : ne poser qu'une tuile par tour pour ne pas avoir à
  piocher aux tours suivants.
- **H3. Garder le joker, idéalement jusqu'au dernier tour.** 3 sources +
  1 faible. Règlement officiel (avec le risque de 30 points) ; Delvers
  (une fois posé, le joker sert aussi aux adversaires, donc attendre si
  possible jusqu'au dernier tour) ; regles-du-jeu.net (« garder un joker
  pour le coup final est une tactique redoutable »), dont une autre page
  du MÊME site conseille au contraire de s'en débarrasser vite
  (contradiction interne) ; faible : tecnobits.com (réserver les jokers
  pour vider un gros groupe ou bloquer l'adversaire).
- **H4. Retenir les petits chiffres (par exemple les 3) pour empêcher les
  adversaires de former 1-2-3.** 1 source, très bonne : Delvers.
- **H5. Se demander à chaque coup si on aide l'adversaire.** 1 source :
  Delvers.
- **H6. Mémoire du tapis et de son chevalet, estimer ce que font les
  autres, bluffer un peu.** 1 source : Rixt van Perlo.
- **H7. Garder un équilibre : ne pas se débarrasser trop vite de toutes
  ses tuiles hautes ou basses.** 1 faible : tecnobits.com.
- **H8. Ouvrir vite (les 30 points tôt pèsent beaucoup).** 2 faibles :
  roomie.jp et un extrait d'agrégateur sans source claire.

Tensions à noter : H1 (se retenir) s'oppose à H8 (ouvrir vite) et à
l'hypothèse inverse de H1 ; regles-du-jeu.net se contredit lui-même sur
H3. Ces conseils sont des habitudes de joueurs humains, jamais mesurées.

**3. Liste des sources (avec adresses)**
- Règlement officiel (anglais) :
  `https://rummikub.com/wp-content/uploads/2019/12/2600-English.pdf` ;
  recopié par `https://rulespal.com/rummikub/rulebook` et
  `https://rulespal.com/rummikub-six-player/rulebook`.
- Manuel de l'édition Jumbo :
  `https://www.libble.eu/jumbo-rummikub/online-manual-365914/` ; version
  allemande de Piatnik :
  `https://www.piatnik.com/uploads/media/default/0001/03/4fcb17146c9070cfcdab35537f9134a3043281e3.pdf`.
- Matthijs Delvers, ex-champion du monde (Rodi, Haarlem, 10 septembre
  2026) :
  `https://www.rodi.nl/haarlem/nieuws/505808/rummikub-fans-opgelet-inschrijving-voor-het-nk-rummikub-in-haarlem-geopend`.
- Rixt van Perlo, championne des Pays-Bas (Vice Pays-Bas, 2009) :
  `https://www.vice.com/nl/article/rummikub/`.
- regles-du-jeu.net : `https://www.regles-du-jeu.net/?p=9594` et
  `https://www.regles-du-jeu.net/rummikub-peut-on-commencer-ou-finir-avec-un-joker/`.
- Blog : `https://mechanicsofmagic.com/?p=1749` ; Japonais :
  `https://www.roomie.jp/2021/11/772619/` ; Espagnol (faible) :
  `https://tecnobits.com/como-jugar-rummikub/` ; page d'apprentissage
  (faible) : `https://oboe.com/learn/mastering-rummikub-strategy-1t9ka02`.
- Résultats des championnats du monde (2018) :
  `https://www.pressreader.com/israel/jerusalem-post/20181025/281668255962433`.

**4. Correspondance avec l'arbre de stratégies et le découpage en phases**
- H1 et H2 : phase « développement » ; piste « réserve d'un coup » de
  l'arbre ; elles visent à éviter les pioches (58 % des tours simulés
  sont des pioches).
- H3 : stratégie du joker en main (#225), dont la rareté a été mesurée
  (le troisième candidat n'a jamais été choisi sur 600 matchs entre
  Expert et Champion du Monde).
- H4 : piste « Rétention » ; hypothèse propre à Claude, non issue d'une
  source : garder de petits chiffres coûte peu de points si l'on perd et
  pourrait bloquer l'adversaire.
- H8 et H1 pour l'ouverture : phase « prologue » ; piste « Ouverture ».
- H6 : brique « Inconnues » (#219).

**5. Protocole d'expérience prévu**
Les traces de #226 (Expert contre Champion du Monde, Avancé contre
Intermédiaire) diront d'abord dans quelle phase l'écart entre gagnant et
perdant se creuse. Ensuite, une variante de Champion du Monde qui se
retient au début (H1 et H2), puis une autre qui garde les petits chiffres
(H4), chacune derrière un réglage propre à Champion du Monde, comparée à
Expert en duels appariés (même graine, mêmes donnes). Méthode : ajouter
les stratégies une à une (chaque version comparée à la précédente), puis,
à la fin, comparer le Champion complet à lui-même privé d'une stratégie à
la fois. On juge d'abord au mécanisme (combien de fois la stratégie change
un coup, et le résultat des seules parties qui divergent), jamais au seul
taux de victoire global.

### Archive : stratégies multi-tours de Champion du Monde (nov. 2026)

**Contexte.** Entre #219 et #233, un sixième niveau « Champion du Monde », au-dessus
d'Expert, a porté des versions COMPLÈTES de plusieurs stratégies multi-tours
(Expert n'en gardant que des versions partielles, dosées). #235 a retiré ce
niveau et tout le code propre à ces stratégies, faute d'effet mesuré (voir
plus bas) — cette section archive ce qui a été essayé.

**a. Ce qui a été essayé** (une phrase par stratégie — l'idée, pas le détail
d'implémentation) :
- `verif_finition` (#221) — en fin de partie (chevalet ≤ 5 tuiles), vérifier
  si un autre coup équivalent permettrait de finir au tour suivant plutôt que
  le meilleur coup brut du solveur. Restée active pour Expert après #235
  (qui n'avait retiré que la variante « garder un joker » ci-dessous) ;
  **retirée à son tour par #236**, jamais un coup changé — voir le point g
  ci-dessous pour le détail chiffré.
- `garde_joker` (#225, Champion du Monde seul) — garder un joker en main en
  fin de partie plutôt que le jouer tout de suite, pour le garder jusqu'au
  coup qui vide le chevalet d'un coup.
- `reserve_tuile` (#229, hypothèse H2) — après le coup du solveur, garder une
  tuile qu'il aurait posée (p. ex. la 4e tuile d'un groupe) pour avoir un coup
  garanti au tour suivant plutôt que de risquer une pioche.
- `retenue_debut` (#229, hypothèse H1) — dans les tours qui suivent sa propre
  ouverture, plafonner le nombre de tuiles posées par tour plutôt que de tout
  poser d'un coup, pour ne pas dégarnir sa main trop vite.
- `petits_chiffres` (#230, hypothèse H4) — garder en main les tuiles de
  petite valeur (≤ 3) pour priver l'adversaire de combinaisons basses
  (1-2-3…), peu coûteux en points en cas de défaite.
- `chances_prochain_tour` (#231, anciennement « tuiles vivantes ») — à
  nombre de tuiles posées égal, préférer le chevalet restant qui a
  statistiquement le plus de chances de permettre de jouer au tour suivant
  (probabilités de pioche, brique « Inconnues », #219).
- `placement_joker` (#232, corrigée par #233) — à nombre de tuiles posées
  égal, placer un joker à l'endroit où l'adversaire a le moins de chances de
  le reprendre (le moins de types de tuile de remplacement encore inconnus).

Toutes dépendaient de la brique de lecture `moteur/inconnues.py` (#219 :
probabilités de pioche calculées à partir des 106 tuiles, de sa propre main
et des TAILLES — jamais le contenu — des mains adverses) et étaient pilotées
par un registre générique (`niveaux.STRATEGIES`, #228), une option de
campagne unique (`--strategies-champion` de `comparer_niveaux_ia.py`) et un
outil de matrice (`scripts/matrice_strategies.py`) pour enchaîner des séries
de mesure sans surveillance sur plusieurs jours.

**b. Méthode de test.** Duels appariés (même graine, mêmes donnes, Expert
contre Champion du Monde) ; mesure par ablation : chaque stratégie SEULE
contre le témoin, puis Champion du Monde complet privé d'une stratégie à la
fois (`scripts/matrice_strategies.py`, plan `ablation`) ; comparaison des
seules parties dont le vainqueur diverge entre deux campagnes à la même
graine (jamais le seul taux de victoire global, noyé dans les parties non
concernées).

**c. Résultats chiffrés.** 12 configurations de 1 000 parties, Expert contre
Champion du Monde : taux de victoire de Champion du Monde entre 49,8 % et
52,1 % pour TOUTES les configurations (marge ±3,1 pt) — aucun écart
significatif, quelle que soit la combinaison de stratégies. Par stratégie
seule contre le témoin, sur les seules parties dont le vainqueur diffère
(effet net en points de score, test des signes) :

| Stratégie | Parties divergentes | Effet net (points) | p |
|---|---:|---:|---:|
| reserve_tuile | 242 | +0,6 | 0,75 |
| retenue_debut | 114 | −0,2 | 0,93 |
| petits_chiffres | 20 | +0,2 | 0,82 |
| chances_prochain_tour | 137 | +1,3 | 0,31 |
| placement_joker | 30 | −0,2 | 0,86 |
| Champion du Monde complet | 321 | +1,9 | 0,32 |

**d. Conclusion.** Aucun effet mesurable : les stratégies changent bel et
bien des parties (jusqu'à 321 sur la configuration la plus concernée), mais
les gains et les pertes qu'elles provoquent se compensent — aucune ne penche
significativement d'un côté ni de l'autre, à aucune échelle testée. Le
niveau « Champion du Monde » et tout le code propre à ces stratégies ont
donc été retirés (#235) ; l'échelle compte de nouveau cinq niveaux, Expert
restant le niveau le plus fort.

**e. Intuition d'Alain, non vérifiée.** Ces stratégies pourraient être utiles
si l'on savait les appliquer au bon moment selon la main et le jeu en cours
(par exemple seulement quand le tapis est pauvre, ou seulement en fin de
manche serrée) — mais aucune règle de ce genre n'existe aujourd'hui, et rien
dans les mesures ci-dessus ne permet de la deviner.

**f. Retrouver le code archivé.** Tout le code retiré par #235 reste
accessible au tag git `archive-strategies-champion` :

```
git show archive-strategies-champion:<chemin>
git checkout archive-strategies-champion -- <chemin>
```

Fichiers SUPPRIMÉS (récupérables uniquement via ce tag) :
`src/rummikub/moteur/sorties.py`, `src/rummikub/moteur/inconnues.py`,
`scripts/matrice_strategies.py`, `scripts/lancer_matrice_windows.ps1`, et les
tests dédiés (`tests/test_sorties.py`, `tests/test_inconnues.py`,
`tests/test_ia_reserve_tuile.py`, `tests/test_ia_retenue_debut.py`,
`tests/test_ia_petits_chiffres.py`, `tests/test_ia_chances_prochain_tour.py`,
`tests/test_ia_placement_joker.py`, `tests/test_registre_strategies.py`,
`tests/test_matrice_strategies.py`, `tests/test_option_strategies_champion.py`).
Fichiers encore présents mais NETTOYÉS (seuls les champs et fonctions propres
à Champion du Monde en ont disparu — le tag donne la version complète
d'AVANT nettoyage) : `src/rummikub/moteur/niveaux.py`,
`src/rummikub/moteur/ia.py`, `src/rummikub/moteur/solveur_exact.py`.
`src/rummikub/moteur/verification_finition.py` existait encore tel quel au
commit visé par ce tag (seule la partie « garder un joker », #225, en avait
été retirée) ; **il a depuis été supprimé à son tour par #236** — récupérable
au MÊME tag, qui le contient dans son état antérieur à ce retrait.

**g. Vérification de finition (#221), retirée par #236.** Contrairement aux
stratégies ci-dessus (toutes évaluées et retirées ensemble par #235), la
vérification de finition n'évaluait qu'UN coup alternatif en fin de partie
(chevalet ≤ 5 tuiles) et était restée active pour Expert après #235. Mesures
qui ont motivé son retrait : sur la série de tests des stratégies (#235, 12
configurations de 1 000 parties), elle a été déclenchée 4 534 fois dans la
configuration témoin **sans changer le coup une seule fois** ; dans les
campagnes précédentes (#221, #226), 5 180 tours de fin de partie examinés,
**aucun coup changé**, dont 881 tours sur 901 où aucun candidat ne permettait
de finir au tour suivant. Coût : un ou deux appels supplémentaires au solveur
exact sur environ un tour sur sept, pour aucun effet. Code retiré plutôt que
désactivé (même décision que pour #235) : `moteur/verification_finition.py`
supprimé, son appel dans `moteur/ia.py` et les champs dédiés de
`moteur/niveaux.py` (`Bridage.verif_finition`,
`SEUIL_FIN_PARTIE_VERIF_FINITION`) retirés, annotation `verif_finition` du
journal de partie (`persistance/journal.py`, `ui/api.py`) retirée. Expert et
Avancé sont de nouveau STRICTEMENT IDENTIQUES (même solveur exact complet,
aucune étape additionnelle) — voir §16. Récupérable au tag
`archive-strategies-champion` (le commit visé contient encore le module,
avant ce retrait).

