# IA — gestion du joker (Intermédiaire/Avancé/Expert, issues #253/#254)

> Ce document décrit l'état ACTUEL du code (#253 puis #254), pas
> l'historique. À lire avant de toucher à `moteur/ia.py` (section
> « Gestion du joker »), `moteur/niveaux.py` (`Bridage.eviter_don_joker`,
> `LIMITE_ECHANGE_DIFFERE`, `LIMITE_ECHANGE_DIFFERE_ADVERSAIRE_FAIBLE`,
> `SEUIL_TUILES_ADVERSAIRE_FAIBLE`, `CLE_ATTENTE_ECHANGE_DIFFERE`,
> `DEBARRAS_JOKER_FIN_MATCH_ACTIF`, `SEUIL_TUILES_ADVERSAIRE_FIN_MATCH`,
> `SEUIL_PIOCHE_FIN_MATCH`), ou aux options
> `--sans-don-joker-a`/`-b` de `scripts/comparer_niveaux_ia.py` (noms
> conservés de #252, gouvernent maintenant l'ensemble ci-dessous).

## 1. Constat qui a motivé #253

La mesure faite sous #252 (16 donnes, Avancé contre Expert, graine 42) a
montré que sa définition de « joker offert » était trop large : elle
comptait tout joker échangeable contre une tuile non encore vue, y compris
un joker au milieu d'une suite de 3 ou 4 tuiles, que personne ne peut
prendre sans poser une tuile ou recomposer le tapis. Sur 44 jokers
« offerts » relevés sans la règle (hors dernier coup), 40 étaient des
jokers de la MAIN posés par l'IA elle-même (plus de la moitié à
l'ouverture) — pas des jokers laissés accessibles sur le tapis. La règle de
#252 (pioche deux tours au plus) faisait donc perdre des tours (environ 9 %)
pour un résultat presque nul : les jokers restants étaient tous des coups
joués de force après l'attente.

Avec la définition d'Alain (§2 ci-dessous), ce problème ne se présente
quasiment pas : une campagne de mesure de 20 donnes (Expert contre Expert,
graine 42, **sans** aucune des règles ci-dessous) montre 1 coup sur 524
(0,2 %) qui laisse un NOUVEAU joker libre — proche de l'observation
d'Alain (« zéro cas sur 868 coups, même sans règle »). Le vrai problème que
#253 corrige est ailleurs : l'IA pose un joker de SA main sans que cela lui
serve, parce que le solveur compte le joker comme une tuile posée comme une
autre (l'économie de jokers n'étant qu'un tout dernier critère de
départage, voir §8bis de CONTEXTE.md). #254 corrige sept points où le code
ou le texte de #253 s'écartait encore des règles voulues par Alain (voir
§4 à §9bis ci-dessous) — aucune valeur de perturbation ni d'oubli n'est
modifiée.

## 2. Définitions : joker LIBRE, joker EN RÉSERVE

**Joker LIBRE** sur un plateau donné : N'IMPORTE QUI (adversaire ou l'IA
elle-même) peut le reprendre à son tour **sans poser aucune tuile ET sans
recomposer le tapis** — c'est-à-dire que le simple RETRAIT du joker, SANS
AUCUNE AUTRE MODIFICATION, laisse déjà les combinaisons restantes valides.
Trois voies, codées dans `jokers_libres_sur_plateau(plateau)`
(`moteur/ia.py`), toutes réutilisant une détection déjà codée pour l'IA
elle-même (§8 de CONTEXTE.md), SANS qu'aucune ne consomme de tuile du
chevalet — condition commune aux trois :

1. **bout de suite** (`_jokers_libres_par_bout_suite`) : joker à une
   extrémité d'une suite d'AU MOINS 4 tuiles, dont le retrait laisse une
   suite valide seule d'au moins 3 tuiles ;
2. **groupe de 4** (`_jokers_liberables_par_groupe4_sans_remplacement`) :
   joker d'un groupe de 4 tuiles (3 réelles de couleurs distinctes + le
   joker), dont le retrait laisse un groupe de 3 valide ;
3. **scission en milieu de suite** (`_jokers_liberables_par_scission_
   milieu`) : joker STRICTEMENT intérieur d'une suite d'AU MOINS 7 tuiles,
   dont le retrait scinde la suite en deux suites valides (au moins 3
   tuiles chacune).

Un joker au milieu d'une suite de 3 OU 4 tuiles (aucune des trois voies ne
s'applique — la suite est trop courte pour la scission, qui exige 7 tuiles
au moins, et il n'est pas en bout) n'est **pas** libre. Un joker dans un
groupe de 3 n'est **pas** libre (le groupe tomberait à 2 tuiles, sous le
minimum). `jokers_rendus_libres_par_coup(etat, idx, coup)` compare le
plateau AVANT et APRÈS un coup : laisser en place un joker déjà libre
AVANT n'est pas un cadeau fait PAR ce coup.

**Joker EN RÉSERVE** (notion DISTINCTE, utilisée seulement pour différer un
échange facultatif — §7) : un joker du tapis est en réserve quand **aucune
recombinaison du plateau SEUL — fût-elle complexe, pas seulement les trois
voies ci-dessus — ne peut, sans aucune tuile de main (de quiconque),
NI le rendre libre NI rendre sa tuile de remplacement disponible
ailleurs** (par exemple en déplaçant l'autre exemplaire visible de cette
tuile). « Libre » exige une disponibilité IMMÉDIATE (retrait seul, zéro
recombinaison) ; « en réserve » exige l'ABSENCE de toute recombinaison,
même en plusieurs étapes, qui y conduirait — l'un est un sous-cas qui
EXCLUT l'autre : un joker déjà libre n'est par construction jamais en
réserve. Voir §7 pour le test complet (`_joker_en_reserve`, #254 point 1).

**Changements par rapport à #252** : l'ancienne notion de « joker offert »
incluait aussi l'échange direct (`_jokers_recuperables`) et le détachement
par extension (`_jokers_detachables_par_extension`) via un chevalet
HYPOTHÉTIQUE de tuiles non encore vues — ces deux voies exigent de JOUER
une tuile (la tuile de remplacement ou la tuile d'extension), donc ne
rendent PAS le joker libre au sens ci-dessus (nuance centrale d'Alain). Le
chevalet hypothétique et sa construction (`_exemplaires_vus`,
`_chevalet_hypothetique_inconnu`) sont donc **supprimés** : la définition
de « libre » ne dépend plus d'aucune tuile de main ou de pioche, seulement
du plateau.

## 3. Arbre de décision complet (`jouer_niveau_bride`, `moteur/ia.py`)

Dans l'ordre EXACT où le code évalue les étapes, pour un coup `coup` déjà
choisi par le niveau (le meilleur coup que son `perturbation_max` laisse
voir) :

1. **Aucun coup posable** (`coup["action"] != "jouer"`) → le coup
   pioche/passe déjà décidé par le moteur est renvoyé TEL QUEL. Aucune des
   étapes suivantes ne s'applique.
2. **Coup gagnant** (le nombre de tuiles jouées rend le chevalet vide,
   `taille_main - len(ids_tuiles) <= 0`) → renvoyé TEL QUEL,
   IMMÉDIATEMENT, avant toute autre étape — ni oubli, ni aucune des règles
   ci-dessous ne s'applique JAMAIS à un coup gagnant. C'est la SEULE
   exception absolue du code.
3. **Si `applique_regle_joker` est faux** (niveau Débutant/Facile, ou
   `eviter_don_joker=False` forcé) → aucune des étapes a/b/c suivantes ne
   s'exécute ; passage direct à l'étape 5 (oubli). Le coup renvoyé n'a
   JAMAIS de clé `"joker"`.
4. **Si `applique_regle_joker` est vrai**, exactement DANS CET ORDRE :
   - **a. Joker en main utile, évalué JOKER PAR JOKER**
     (`_appliquer_joker_utile`, §4) — peut REMPLACER `coup` par un coup
     sans les jokers de main jugés non utiles (chacun évalué
     séparément, §4), SAUF en fin de match à plusieurs manches où un
     joker non utile mais déjà placé dans `coup` est quand même posé
     pour éviter sa pénalité (§8bis). Si le coup résultant n'est pas une
     action `"jouer"`, il est renvoyé IMMÉDIATEMENT (annoté `"joker"`) —
     les étapes b et c ne s'exécutent PAS ;
   - **b. Échange différé** (`_appliquer_echange_differe`, §7) — peut
     REMPLACER `coup` par une alternative sans l'échange, ou par une
     pioche (qui compte désormais dans le délai, §7). Si le résultat
     n'est pas `"jouer"`, renvoyé IMMÉDIATEMENT (annoté). Si le résultat
     est un échange FORCÉ parce que la pioche était vide (compteur
     retiré directement par cette étape), l'étape c suivante est SAUTÉE
     — seul ce sous-cas précis, voir §7 dernier point ;
   - **c. Joker LIBRE évité** (`_appliquer_joker_libre`, §5) — seulement
     si b n'a pas forcé pour pioche vide. **SAUTÉE AUSSI** si l'étape a
     a débarrassé l'IA d'un joker inutile en fin de match (§8bis) — un
     tel coup n'est jamais reconsidéré par cette étape. Sinon, peut
     REMPLACER `coup` par une alternative sans nouveau joker libre, ou
     par une pioche — SAUF si la pioche est vide, auquel cas elle joue
     malgré tout le meilleur coup disponible (§5, #254 point 5). Si le
     résultat n'est pas `"jouer"`, renvoyé IMMÉDIATEMENT (annoté).
5. **Oubli** (inchangé depuis #213/#252) : seulement si l'étape 4 a laissé
   un coup `"jouer"` (ou si l'étape 3 s'est appliquée) — avec probabilité
   `taux_oubli_effectif`, remplacé par une pioche/passe (jamais annoté
   `"joker"`, cette clé n'existe que si l'étape 4 s'est exécutée).

Un coup renvoyé porte la clé `"joker"` **si et seulement si**
`applique_regle_joker` est vrai ET le coup initial n'était ni « aucun coup
posable » ni gagnant — jamais pour Débutant/Facile, jamais pour un coup
gagnant, jamais pour `eviter_don_joker=False`.

## 4. Point « joker en main UTILE », évalué séparément pour chaque joker (#253 ; #254 point 4)

**Le code fait exactement ceci** (`_appliquer_joker_utile`) : si `coup` ne
joue AUCUN joker de la main (`ids_tuiles ∩ jokers_de_la_main == ∅`), rien à
faire (le reste de la fonction ne s'exécute pas). Sinon, pour CHAQUE joker
de la main joué par `coup`, SÉQUENTIELLEMENT (pas « tous les jokers à la
fois » comme sous #253) :

* `reel_avec` = nombre de tuiles RÉELLES (jokers exclus) du meilleur coup
  avec l'ENSEMBLE des jokers encore jugés utiles à ce stade (tous au
  premier passage) ;
* `reel_sans_j` = nombre de tuiles RÉELLES du meilleur coup avec ce même
  ensemble PRIVÉ de ce seul joker `j` (`_coup_avec_chevalet` ; un coup
  `"piocher"`/`"passer"` y compte pour 0, ce qui couvre aussi l'ouverture
  rendue possible par le joker) ;
* si `reel_avec > reel_sans_j` (STRICTEMENT) → `j` est UTILE : il reste
  disponible pour le test du joker suivant, `reel_avec` ne change pas ;
* sinon → `j` est NON utile (sauf fin de match, voir §8bis) : il est
  RETIRÉ de l'ensemble disponible, et `reel_avec` est remis à jour sur
  `reel_sans_j` pour le test du joker suivant.

**Pourquoi évaluer SÉQUENTIELLEMENT et pas chaque joker indépendamment
contre l'ensemble complet** (point où la formulation de l'issue —
« l'autre joker étant évalué de la même façon » — laissait un choix à
l'agent) : les deux jokers de la main sont INTERCHANGEABLES pour le
solveur. S'il n'existe qu'UN SEUL emplacement qui a réellement besoin d'un
joker, le retirer INDÉPENDAMMENT (en laissant chaque fois l'AUTRE
disponible) montrerait, pour CHACUN des deux, « l'autre suffit » — donc
AUCUN des deux ne paraîtrait utile, alors qu'ENSEMBLE, les retirer TOUS LES
DEUX ferait perdre cet unique emplacement. Retirer chaque joker confirmé
non utile de l'ensemble disponible AVANT de juger le suivant évite ce
piège : exactement un joker reste alors jugé utile pour un unique
emplacement qui en a besoin, quel que soit celui des deux qui s'y trouve
assigné par le solveur (les deux objets « joker » sont interchangeables :
aucun test ne peut donc fixer LEQUEL des deux id est joué dans ce cas,
seulement COMBIEN).

Le coup final rejoue le meilleur coup avec {tuiles réelles} ∪ {jokers
utiles, ou débarrassés en fin de match, voir §8bis} UNIQUEMENT — un joker
jugé non utile (et non débarrassé) reste en main même si L'AUTRE est posé.

**Exemples** :
- *Utile, main à un seul joker* : main `joker, rouge_7, rouge_8, bleu_5,
  bleu_6, bleu_7, noir_2`. Avec joker : rouge7-8-(joker=9) + bleu5-6-7 = 5
  tuiles réelles. Sans aucun joker : seule bleu5-6-7 est jouable = 3
  réelles. 5 > 3 : joué tel quel
  (`test_joker_en_main_utile_est_joue`) ;
- *Pas utile, main à un seul joker* : main `joker, rouge_7, rouge_8,
  rouge_9, noir_2`. Avec joker : rouge7-8-9-(joker=10), 3 réelles (le
  joker n'ajoute QUE lui-même). Sans aucun joker : rouge7-8-9 seule, 3
  réelles aussi. 3 == 3 (égalité) : PAS utile, le joker est gardé, seule
  la suite de 3 est jouée (`test_joker_en_main_non_utile_est_garde`) ;
- *Ouverture rendue possible* : mise initiale non faite, main `joker,
  rouge_11, rouge_12, noir_2`. Avec joker : 36 points (≥ 30), 2 réelles.
  Sans aucun joker : 0 réelle jouée (mise inatteignable). 2 > 0 : utile
  (`test_joker_rend_l_ouverture_possible_est_joue`) ;
- *Deux jokers, un seul utile* (#254, point 4, NOUVEAU — sous #253 les deux
  auraient été jugés utiles ENSEMBLE et le second posé pour rien) : main
  `joker_1, joker_2, rouge_7, rouge_8, noir_5, noir_6, noir_7, bleu_2`.
  rouge_7-8 ne forme rien sans AUCUN joker (0 réelle) : UN joker y est
  utile (2 réelles). noir_5-6-7 est DÉJÀ une suite valide à 3 réelles sans
  AUCUN joker : y ajouter le second (en bout, 4e tuile) n'apporte RIEN de
  plus (3 == 3) : NON utile. Exactement un joker posé, l'autre gardé
  (`test_deux_jokers_en_main_un_seul_utile_est_joue`) ;
- *Deux jokers, tous deux utiles* (voisin) : même main sans `noir_7` —
  noir_5-6 NE forme plus rien sans joker non plus (2 tuiles seulement) :
  les DEUX paires ont chacune besoin d'UN joker, retirer l'un OU l'autre
  fait perdre une paire entière (2 réelles de moins) : les deux sont jugés
  utiles et posés (`test_deux_jokers_en_main_tous_deux_utiles_sont_joues`) ;
- *Ne s'applique jamais à un coup gagnant* : intercepté par l'exception
  absolue (§3, étape 2) AVANT d'atteindre cette fonction
  (`test_coup_gagnant_avec_joker_toujours_joue`) ;
- *Ne s'applique pas* : aucun joker dans `ids_tuiles` de `coup` (y compris
  un joker SUR LE PLATEAU, jamais concerné par cette règle).

## 5. Point « joker LIBRE évité » (#253 ; #254 point 5 — pioche vide)

**Le code fait exactement ceci** (`_appliquer_joker_libre`) : si `coup` ne
rend libre AUCUN nouveau joker (`jokers_rendus_libres_par_coup` vide), rien
à faire. Sinon, cherche une alternative (`_chercher_coup_sans_joker_libre`)
en essayant, DANS CET ORDRE, et en s'arrêtant au PREMIER trouvé qui n'en
laisse aucun libre (pas nécessairement le plus riche en tuiles) :
1. le coup SANS réarrangement du plateau (`_coup_sans_rearrangement`) ;
2. pour chaque tuile jouée par `coup` (les jokers joués D'ABORD, puis les
   autres dans l'ordre d'origine), le meilleur coup du même niveau obtenu
   en RETIRANT cette seule tuile de la main.

Si une alternative est trouvée, elle est jouée (quitte à poser moins de
tuiles). Si AUCUNE des alternatives essayées n'en évite :

* **la pioche n'est PAS vide** → l'IA pioche plutôt que de jouer, SANS
  compteur ni limite (inchangé depuis #253) ;
* **la pioche EST vide** (#254, point 5 — REMPLACE, dans ce seul cas, la
  règle ci-dessus) → `_meilleur_candidat_si_pioche_impossible` choisit,
  parmi `coup` et les MÊMES candidats que la recherche d'alternative, celui
  qui laisse le MOINS de nouveaux jokers libres (camouflage BEST-EFFORT,
  §6), puis le plus riche en tuiles — et ce coup est JOUÉ, pas remplacé par
  une pioche impossible.

**Comment la pioche vide est détectée** : `not etat.get("pioche")` — un
test visible de tous, jamais le contenu d'une main. **Mise à jour #255
(remplace la remarque d'avant #255, devenue fausse)** : avant #255, le
moteur de partie (`moteur/partie._terminer_tour`) terminait la manche
IMMÉDIATEMENT dès que la pioche était vide à la fin d'UN tour, quelle que
soit l'action jouée ce tour-là — ce qui rendait ce chemin de code
INATTEIGNABLE en jeu réel tour par tour (la pioche ne pouvait jamais être
observée vide au DÉBUT d'une décision, la manche ayant déjà pris fin au
tour précédent) : il n'était exercé que par les tests unitaires (état
construit directement avec `pioche: []`). **#255 implémente la vraie
règle** : la pioche vide ne termine plus la manche à elle seule — elle
termine seulement de piocher (`moteur/partie.piocher` ne tire alors plus
aucune tuile) ; un joueur qui ne peut pas jouer PASSE (`passer_tour`), et
la manche ne se termine que par un chevalet vidé ou par un **blocage**
(pioche vide ET tous les joueurs ont passé un tour complet de suite sans
qu'aucun coup ne soit joué entre-temps, voir CONTEXTE.md §3bis). **Ce
chemin de code (pioche vide au début d'une décision de l'IA) est donc
désormais un cas FRÉQUENT en jeu réel** (en fin de manche, surtout à
plusieurs joueurs), pas seulement un filet de robustesse pour les tests
unitaires ou le replay — toutes les règles ci-dessus (§5, §6, §7ter/
7quater) qui distinguent « pioche vide » de « pioche non vide » sont
donc désormais exercées en jeu normal, pas seulement par leurs tests
dédiés.

**Exemples** :
- *Alternative trouvée* : plateau `rouge_7, rouge_8, (joker=9)` (pas
  libre). Main `rouge_6, bleu_5, bleu_6, bleu_7, noir_2`. Étendre avec
  rouge_6 rendrait le joker libre ; bleu5-6-7 (sans toucher au plateau) ne
  touche pas le joker — jouée à la place, une tuile en moins
  (`test_evite_le_coup_qui_rend_un_joker_libre_en_posant_moins_de_tuiles`) ;
- *Aucune alternative, pioche NON vide* : même plateau, main `rouge_6,
  noir_2` SEULEMENT. Pioche : non vide. Pioche, répétée IDENTIQUEMENT au
  tour suivant (`test_pioche_sans_compteur_ni_limite_si_seul_coup_laisse_
  un_joker_libre`) ;
- *Aucune alternative, pioche VIDE* (#254, point 5, voisin immédiat du
  précédent) : même plateau/main, mais `etat["pioche"] = []` : l'IA JOUE
  `rouge_6` malgré le joker libre qui en résulte, plutôt que de passer
  (`test_joue_malgre_joker_libre_si_pioche_vide`, voisin
  `test_pioche_encore_si_pioche_non_vide_meme_scenario`) ;
- *Ne s'applique pas* : `coup` ne rend libre aucun joker (cas le plus
  fréquent, 99,8 % des coups joués mesurés sans AUCUNE règle sur 20
  donnes, §9).

## 6. Camouflage du joker repris du tapis ; échange facultatif (#253 ; #254 point 6)

Le code NE contient PAS de fonction séparée « camouflage » pour le cas
GÉNÉRAL : le camouflage (choisir une position non libre pour un joker
repris) est un EFFET du §5 ci-dessus, appliqué de façon générique à
N'IMPORTE QUEL coup — `jokers_rendus_libres_par_coup` ne distingue pas
l'ORIGINE du joker devenu libre. **Le camouflage ne concerne, dans les
FAITS, QUE le joker repris du TAPIS, jamais un joker de la MAIN** : un
joker de main n'est joué QUE s'il est utile (§4) — son placement n'est
jamais choisi pour « camoufler » une reprise, cette notion n'ayant de sens
que pour un joker qui ÉTAIT déjà sur le plateau avant le coup.

Quand l'IA n'a pas le choix (soit le seul placement trouvé laisse un
joker libre, §5 ; soit la pioche est vide et aucune alternative
n'existe, #254 point 5), le code essaie de limiter les dégâts :

* **Cas général (§5, pioche non vide)** : si aucune alternative n'évite
  TOTALEMENT le joker libre, l'IA pioche — elle ne pose donc RIEN, le
  camouflage ne s'applique pas puisqu'aucun coup n'est joué ;
* **Cas pioche vide (#254, point 5)** : `_meilleur_candidat_si_pioche_
  impossible` essaie RÉELLEMENT de camoufler, parmi `coup` et les
  candidats déjà calculés par la recherche d'alternative : il choisit celui
  qui laisse le MOINS de nouveaux jokers libres (minimiser le risque),
  puis le plus riche en tuiles.

**Limite assumée, NON levée par #254 (comme annoncé possible par
l'issue — « sinon la signaler comme limite connue »)** : le texte de
l'issue demande aussi, PARMI PLUSIEURS placements NON libres possibles
pour un MÊME joker repris, de préférer celui dont la reprise exige la
recombinaison la plus profonde (nombre de tuiles à déplacer). **Cette
préférence n'est PAS implémentée**, y compris pour le cas spécifique de la
pioche vide (#254 point 5) :
1. analyse structurelle inchangée depuis #253 : un placement par pure
   extension d'un joker repris (sans tuile de main) est TOUJOURS libre par
   construction (la combinaison qu'il prolonge était déjà valide seule) ;
   un placement NON libre exige donc presque toujours de combiner le
   joker avec au moins une tuile de la MAIN, ce qui bascule le cas hors du
   périmètre du camouflage (« elle peut l'utiliser avec sa main ») — les
   scénarios où PLUSIEURS placements non libres coexistent pour le MÊME
   joker repris restent rares et n'ont pas pu être isolés de façon fiable ;
2. le solveur exact décide seul, en une passe, OÙ atterrit un joker
   repris — choisir PARMI plusieurs placements à tuiles égales demanderait
   de modifier son objectif interne, risqué pour la garantie de
   validité/conservation du plateau, donc explicitement écarté. La
   minimisation du NOMBRE de nouveaux jokers libres (#254, point 5,
   ci-dessus) est une approximation DIFFÉRENTE (plus grossière, mais sans
   risque pour le solveur) — PAS la préférence de recombinaison la plus
   profonde demandée par l'issue.

**Échange facultatif** (`_jokers_recuperables` — l'IA détient la tuile
EXACTE de remplacement d'un joker du plateau) : le §5 couvre naturellement
les trois cas demandés, puisqu'un échange facultatif qui expose un nouveau
joker libre est traité comme n'importe quel autre coup qui en expose un :
- *repris et camouflé* (placement non libre existe, via la main) :
  `test_echange_facultatif_repris_et_camoufle_en_position_non_libre` ;
- *non repris* (seul placement est libre, et ne gagne pas) :
  `test_echange_facultatif_non_repris_si_seul_endroit_est_libre` — pioche ;
- *repris quand ça gagne* : l'exception absolue du coup gagnant (§3,
  étape 2) s'applique, AVANT même d'atteindre cette logique
  (`test_echange_facultatif_repris_si_le_coup_fait_gagner`).

## 7. Échange différé d'un échange facultatif « en réserve » (#253 ; #254 points 1, 2, 3)

**Le code fait exactement ceci** (`_appliquer_echange_differe`), pour le
PREMIER échange direct facultatif (parmi `_jokers_recuperables` calculés
sur le plateau et la main AVANT ce tour) effectivement joué par `coup` qui
remplit TOUTES les conditions suivantes (un « ET » non exclusif) :

- la tuile de remplacement de cet échange est dans `ids_tuiles` de
  `coup` ;
- le joker récupéré est toujours présent (ailleurs) dans le plateau
  résultant (repositionné par ce même coup) ;
- le joker récupéré N'EST PAS utilisé avec le reste de la main
  (`_joker_repris_utilise_avec_main`) ;
- le joker récupéré est EN RÉSERVE (`_joker_en_reserve`, voir §7bis).

### 7bis. Joker « en réserve » : test COMPLET (#254, point 1)

`_joker_en_reserve(plateau, rec)` est vrai si et seulement si TROIS
conditions cumulatives tiennent :

1. **`vus_sur_plateau == NB_SERIES - 1`** (1, puisque `NB_SERIES = 2`) :
   le nombre d'exemplaires de la tuile de remplacement visibles sur le
   plateau (jokers exclus). Avec `rec["remplacement"]` dans la main de
   l'IA (c'est de là qu'il vient, par construction de
   `_jokers_recuperables`), cela comptabilise la TOTALITÉ des
   `NB_SERIES` exemplaires (1 en main de l'IA + `NB_SERIES - 1` visibles
   sur le plateau) : AUCUN exemplaire ne peut donc se trouver ailleurs —
   ni dans la main d'un adversaire, ni dans la pioche, **ni dans un AUTRE
   emplacement de la main de l'IA elle-même** (point explicitement vérifié
   par #254 : avec `NB_SERIES=2`, les 2 seuls exemplaires existants sont
   déjà intégralement comptés par cette égalité — 1 en main + 1 visible —
   la main de l'IA ne peut structurellement PAS en détenir un second ; la
   réserve n'en est donc que PLUS sûre, jamais remise en cause par ce
   cas) ;
2. le joker n'est pas déjà libre (`jokers_libres_sur_plateau`, §2) ;
3. **NOUVEAU (#254, point 1 — #253 ne vérifiait pas ce cas)** : aucune
   libération SANS tuile de main n'existe pour ce joker au sens LARGE de
   `_liberations_possibles(plateau, [])` (chevalet VIDE, donc seules les
   libérations GRATUITES — zéro tuile de main — peuvent y apparaître, par
   construction de cette fonction, réutilisée telle quelle). Ceci couvre,
   EN PLUS des trois voies du §2 (« libre »), la réduction d'un groupe de 4
   DÉJÀ COMPLET (`_jokers_liberables_par_reduction_groupe4`, cas
   `len(groupe) == 4`) : une tuile réelle qu'elle libère peut directement
   remplacer CE joker (ou tout autre), rendant la tuile de remplacement
   « disponible » par simple déplacement de l'autre exemplaire visible —
   exactement l'exemple donné par l'issue — SANS qu'aucune des trois voies
   « libre » du §2 ne s'applique à CE joker directement.

Exemple (`test_joker_en_reserve_dechu_par_groupe4_deja_complet`) : suite
rouge `3-4-(joker_1=5)` (pas libre, bout de suite de 3 seulement) ; un
groupe `rouge_5/bleu_5/noir_5/jaune_5` DÉJÀ COMPLET ailleurs sur le
plateau peut perdre `rouge_5` (groupe de 3 valide restant) — ce `rouge_5`
correspond EXACTEMENT à `joker_1` : PAS en réserve, bien que la condition 1
soit remplie (un seul `rouge_5` visible) et que la condition 2 le soit
aussi (pas déjà libre). Voisin immédiat
(`test_joker_en_reserve_tient_si_le_groupe_n_est_pas_deja_a_4`) : le
groupe n'a que 3 tuiles (pas 4) — aucun candidat de réduction sans tuile de
main n'existe (chevalet vide passé à `_liberations_possibles`) : toujours
en réserve.

### 7ter. Décision de différer, compter, forcer

- si le compteur d'attente de CE joker (propre à chaque id de joker,
  `dict` `{id_joker: n}`, jamais un compteur global du joueur) est
  STRICTEMENT inférieur à la limite (3, `LIMITE_ECHANGE_DIFFERE` ; réduite
  à 2, `LIMITE_ECHANGE_DIFFERE_ADVERSAIRE_FAIBLE`, si au moins un AUTRE
  joueur a STRICTEMENT moins de 5 tuiles en main,
  `SEUIL_TUILES_ADVERSAIRE_FAIBLE`) : cherche le meilleur coup SANS jouer
  la tuile de remplacement (`_coup_sans_tuile_main`) ;
  - si ce coup existe (action `"jouer"`) : il est joué À LA PLACE de
    `coup` (l'échange est différé), le compteur de CE joker est incrémenté
    de 1 ;
  - sinon (aucun coup sans la tuile de remplacement n'est possible — « le
    seul coup possible du tour ») : **le compteur de CE joker est QUAND
    MÊME incrémenté de 1** (#254, point 3 — CORRIGE #253, qui ne comptait
    PAS ce tour comme un tour d'attente, permettant une attente SANS
    LIMITE) ; puis :
    - si la pioche n'est pas vide → pioche À LA PLACE ;
    - **si la pioche EST vide** (#254, point 5, appliqué ICI aussi) →
      l'échange est fait MALGRÉ TOUT (`coup` joué tel quel), compteur de
      CE joker retiré (l'échange est fait) ; passer n'aurait servi à rien
      de plus, la pioche restant vide au tour suivant ;
- sinon (compteur ≥ limite) : `coup` est joué TEL QUEL (l'échange est
  fait), le compteur de CE joker est retiré du `dict` (remis à 0). **Ce cas
  est désormais SOUMIS normalement à la règle du joker libre du §5
  (#254, point 2 — CORRIGE #253)** : voir §7quater.

Un joker qui n'est plus en réserve (ses conditions ne tiennent plus, p.
ex. le plateau a été recomposé par un adversaire) voit son compteur
retiré du `dict`, qu'il ait été concerné par `coup` ou non.

### 7quater. Point 2 (#254) : l'échange forcé par le délai est soumis au §5

#253 exemptait l'échange forcé (délai expiré) de la règle du joker libre
du §5, par crainte que celle-ci ne trouve SYSTÉMATIQUEMENT l'alternative
sans l'échange — exactement celle que le délai venait d'épuiser — et
n'annule ainsi la décision de forcer. **#254 corrige cette justification**
(fausse en général) : le §5 ne se déclenche QUE si `coup` rend RÉELLEMENT
un NOUVEAU joker libre, ce qui n'est pas automatique — un joker récupéré
peut très bien retomber dans une position non libre (camouflage via la
main, §6). Le §5 s'applique donc désormais à TOUT coup, y compris un
échange forcé :

* si l'échange forcé laisse réellement un joker libre ET qu'une
  alternative sans nouveau joker libre existe → l'alternative est prise
  (le joker reste en réserve sur le tapis, ce qui ne coûte rien, puisque
  PAR DÉFINITION personne d'autre ne peut le prendre) ;
* si AUCUNE alternative n'existe et que la pioche n'est pas vide → §5
  pioche (générique, SANS compteur ni limite — ce n'est PAS une réouverture
  du délai propre à ce point 7 : le compteur de CE joker reste remis à 0,
  seul le filet de sécurité générique du §5 s'applique, comme pour
  n'importe quel autre coup) ;
* si la pioche est vide → §5 force la pose du meilleur coup (point 5).

**Conséquence observée sur le test de référence** (plateau où la seule
reposition possible du joker libéré est TOUJOURS libre, par construction —
voir §6, point 1) : l'échange forcé par le délai est repris par le §5, qui
trouve l'alternative sans l'échange (le joker reste en réserve sur le
tapis) — l'échange proprement dit n'est donc PAS joué ce tour-là non plus
(`test_echange_differe_jusqu_a_trois_tours_puis_fait`, 4e appel). Un test
séparé (`test_echange_differe_force_et_joue_si_pioche_vide_et_aucune_
alternative`) couvre le cas où aucune autre tuile n'est disponible en
main : les 3 tours de délai sont consommés par la pioche COMPTÉE (point 3),
puis, si la pioche est vide au moment de forcer, l'échange est RÉELLEMENT
joué (point 5) ; si elle ne l'est pas, le §5 générique pioche encore, sans
jouer l'échange (« mieux vaut le laisser sur le tapis »).

**Exemples** (voir `tests/test_ia_anti_don_joker.py`) :
- *différé 3 tours, tous par pioche comptée, puis joué si pioche vide* :
  `test_echange_differe_force_et_joue_si_pioche_vide_et_aucune_alternative` ;
- *limite à 2 si adversaire faible* :
  `test_echange_differe_limite_a_deux_tours_si_adversaire_faible` — même
  scénario, adversaire à 3 tuiles (< 5), limite atteinte au 3e appel (le
  §5 reprend l'échange forcé, comme au 4e appel du test à 3 tours) ;
- *fait aussitôt si utilisable avec la main* :
  `test_echange_fait_aussitot_si_joker_utilisable_avec_la_main` ;
- *fait aussitôt si pas en réserve* :
  `test_echange_fait_aussitot_si_pas_en_reserve` ;
- *fait aussitôt si le coup gagne* :
  `test_echange_facultatif_repris_si_le_coup_fait_gagner` ;
- *compteur retiré quand la réserve cesse* :
  `test_compteur_differe_retire_quand_la_reserve_cesse` ;
- *pas de tour passé, sauf coup unique — compteur avance quand même* :
  `test_echange_differe_ne_passe_pas_le_tour_sauf_coup_unique` (#254,
  point 3 : le compteur passe à 1 même quand ce tour se solde par une
  pioche faute d'alternative — cohérence vérifiée dans les trois cas :
  autre coup joué (compteur avance), pioche faute d'alternative (compteur
  avance aussi depuis #254), tour de l'adversaire entre deux décisions de
  l'IA (compteur inchangé, persistant sur `etat["joueurs"][idx]`)).

**Cas limite — deux jokers en réserve simultanément** : seul le PREMIER
rencontré dans l'itération de `_jokers_recuperables` est traité par appel ;
aucun test dédié à deux réserves simultanées (point de doute hérité de
#253, non résolu par #254 — hors périmètre de cette issue).

## 8. Paramètres et désactivation

Activée (`Bridage.eviter_don_joker=True`) pour **Intermédiaire, Avancé et
Expert** ; **Débutant et Facile** restent à `False` (comportement d'avant
#252/#253 inchangé). `jouer_niveau_bride(..., eviter_don_joker=None|True
|False)` force l'activation/désactivation indépendamment du niveau —
utilisé par `scripts/comparer_niveaux_ia.py --sans-don-joker-a`/`-b`.

Paramètres réglables (`moteur/niveaux.py`) :
- `LIMITE_ECHANGE_DIFFERE = 3` (tours de différé au plus — compte
  désormais aussi les tours de pioche faute d'alternative, #254 point 3) ;
- `LIMITE_ECHANGE_DIFFERE_ADVERSAIRE_FAIBLE = 2` (si un adversaire a moins
  de `SEUIL_TUILES_ADVERSAIRE_FAIBLE` tuiles) ;
- `SEUIL_TUILES_ADVERSAIRE_FAIBLE = 5`.

## 8bis. Fin de match à plusieurs manches : débarras du joker inutile (#254, point 7)

Lecture préalable nécessaire (faite par l'agent) : `moteur/partie.py`
(`creer_partie` pose `etat["config"]["nb_manches"]`, borné à `[1, 9]`,
défaut 1 — TOUJOURS disponible, TOUJOURS distingue un match à une seule
manche d'un match à plusieurs manches : aucun cas où cette distinction
serait indisponible) et `moteur/score.calculer_scores_manche` (la
pénalité d'un joker en main, `valeur_joker_penalite`, défaut 30, est
soustraite du `score_manche` du perdant, qui s'ACCUMULE ensuite dans
`score_cumul` au fil des manches, `moteur/partie.nouvelle_manche` — voir
§3bis de CONTEXTE.md pour le détail des manches).

**Conséquence** : à une seule manche, perdre avec ou sans joker en main ne
change RIEN (le score cumulé ne va pas au-delà de cette manche) — la règle
qui garde un joker inutile en main (§4) ne change donc PAS pour ce cas. À
PLUSIEURS manches, un joker encore en main à la fin d'une manche PERDUE
AJOUTE sa pénalité au score cumulé du MATCH, alors qu'une manche future
pourrait rattraper le score — mieux vaut donc s'en débarrasser s'il ne
sert plus à rien, PLUTÔT QUE de le garder par précaution jusqu'à la toute
fin.

**Conditions (`_fin_de_match_proche_pour_debarras`, toutes les trois
requises, nombres visibles de tous, JAMAIS le contenu d'une main)** :
1. `etat["config"]["nb_manches"] > 1` (match à PLUSIEURS manches) ;
2. au moins un AUTRE joueur a AU PLUS `SEUIL_TUILES_ADVERSAIRE_FIN_MATCH`
   (2) tuiles en main (`_adversaire_a_au_plus`) ;
3. la pioche contient STRICTEMENT MOINS de `SEUIL_PIOCHE_FIN_MATCH` (30)
   tuiles.

Désactivable en bloc par `DEBARRAS_JOKER_FIN_MATCH_ACTIF = False` (lu à
l'appel, comme `ia.UTILISER_SOLVEUR_EXACT`), pour les scripts de
simulation qui veulent isoler l'effet des autres règles.

**Effet** (`_appliquer_joker_utile`, §4) : un joker jugé NON utile par le
test séquentiel du §4, pour lequel `coup` (le coup de base, chevalet
complet) prévoyait DÉJÀ une place (même sans gain réel — jamais une
recherche SUPPLÉMENTAIRE pour lui en trouver une), est quand même posé.
S'il n'avait AUCUNE place dans `coup`, il reste en main (rien ne change :
le point 7 ne force jamais une pose qui n'existait pas déjà).

**Interaction avec le §5 (joker libre évité) — point douteux, choix de
l'agent** : un joker ainsi « débarrassé » N'EST PAS resoumis au §5 — ce
dernier chercherait sinon systématiquement l'alternative SANS ce joker
(le garder en main), ce qui annulerait TOUJOURS la décision de ce point 7
(tout placement « gratuit » d'un joker — pure extension d'une combinaison
déjà valide seule — étant quasi systématiquement libre par construction,
§6 point 1). L'issue ne précise pas cette interaction ; l'agent a choisi de
faire primer le débarras, le risque d'un joker libre étant jugé secondaire
face à la pénalité CERTAINE dans un match qui se termine. Ce comportement
ne s'applique QU'AUX niveaux où `eviter_don_joker` est actif (Intermédiaire,
Avancé, Expert) — Débutant/Facile restent inchangés (§3, étape 3).

**Exemples** (`tests/test_ia_anti_don_joker.py`) :
- *Toutes les conditions réunies* : match à 2 manches, adversaire à 2
  tuiles (au plus 2), pioche à 10 tuiles (moins de 30) : le joker normalement
  gardé (voir l'exemple « pas utile » du §4) est posé quand même
  (`test_joker_inutile_debarrasse_en_fin_de_match_multi_manches`) ;
- *Voisin — une seule manche* : `nb_manches=1` (défaut), sinon identique :
  règle jamais appliquée, joker gardé
  (`test_joker_garde_si_match_a_une_seule_manche`) ;
- *Voisin — valeur limite adversaire* : adversaire à 3 tuiles (strictement
  AU-DESSUS du seuil « au plus 2 ») : joker gardé
  (`test_joker_garde_si_aucun_adversaire_a_au_plus_deux_tuiles`) ;
- *Voisin — valeur limite pioche* : pioche à EXACTEMENT 30 tuiles (pas
  « strictement moins de 30 ») : joker gardé
  (`test_joker_garde_si_pioche_a_trente_tuiles_exactement`) ; à 29, posé
  (`test_joker_debarrasse_si_pioche_a_vingt_neuf_tuiles`) ;
- *Désactivation en simulation* :
  `test_regle_fin_de_match_desactivable_en_simulation`.

## 9. Mesure (`scripts/comparer_niveaux_ia.py`)

Le rapport affiche, **par CAMP** : le nombre de coups joués (hors coup qui
vide le chevalet) qui rendent NOUVEAU libre un joker, sur le total de ces
coups (taux) ; le nombre de tours de pioche dus à un joker libre sans
alternative ; le nombre de jokers de main gardés plutôt que joués
(désormais compté joker par joker, §4) ; le nombre d'échanges facultatifs
différés, et parmi eux ceux ayant forcé une pioche ; et, NOUVEAU (#254,
point 7), le nombre de jokers inutiles posés pour s'en débarrasser en fin
de match.

Essai de 20 donnes, premier plan, graine 42, Expert contre Expert, limite
de temps ferme (`timeout 900`, bien au-delà du temps réel observé) :

```
# AVANT (règle désactivée des deux côtés — référence, INCHANGÉ depuis #253,
# cette campagne ne mesure aucune des 7 corrections de #254 puisque la
# règle entière est coupée) :
python scripts/comparer_niveaux_ia.py --niveau-a Expert --niveau-b Expert \
    --donnes 20 --seed 42 --sans-don-joker-a --sans-don-joker-b
# → 1/524 coup(s) (0,2 %) laissent un joker libre ; 0 pioche forcée ;
#   0 joker de main gardé ; 0 échange différé ; 0 débarras fin de match.
#   Temps de calcul Expert : moyenne 74,7 ms, max 1259,8 ms (2610 tours).

# APRÈS (règle activée des deux côtés, #254 appliqué) :
python scripts/comparer_niveaux_ia.py --niveau-a Expert --niveau-b Expert \
    --donnes 20 --seed 42
# → 0/531 coup(s) (0,0 %) laissent un joker libre ; 2 pioches forcées ;
#   5 jokers de main gardés ; 1 échange différé (ayant forcé 1 pioche) ;
#   0 débarras de fin de match (nb_manches=1, condition 1 du point 7
#   jamais remplie — voir ci-dessous).
#   Temps de calcul Expert : moyenne 78,2 ms, max 1386,9 ms (2642 tours).
```

Effet mesuré : les compteurs sont IDENTIQUES à ceux déjà publiés par #253
(même graine, mêmes donnes) — attendu, puisqu'aucune des 7 corrections de
#254 ne change le comportement pour les coups effectivement rencontrés
sur CETTE campagne précise à une seule manche et sans situation de pioche
vide ni de double-joker non utile : le point 1 (test complet de réserve)
ne change rien tant qu'aucune recombinaison « groupe de 4 déjà complet »
ne coexiste avec l'échange rencontré ; le point 2 (soumission au §5) ne
change rien tant que l'échange forcé ne laisse pas réellement de nouveau
joker libre ; le point 3 (compteur pendant une pioche) ne change rien tant
que le délai n'est pas atteint par cette voie ; le point 4 (jokers
évalués séparément) ne change rien tant que l'IA n'a pas deux jokers en
main simultanément ; le point 5 (pioche vide) ne se déclenche jamais en
jeu réel tour par tour (voir §5 — vrai SEULEMENT pour cette campagne,
jouée avant #255 ; depuis #255, la pioche vide persiste sur plusieurs
tours réels, voir la mise à jour de §5) ; le point 7 (fin de match) exige
`nb_manches > 1`, absent de cette campagne à 1 manche. Ces 7 points
restent chacun couverts par un test unitaire DÉDIÉ (§4 à §8bis) qui les
exerce directement, indépendamment de cette mesure globale. Le match étant
à UNE SEULE manche par défaut, le point 7 (débarras en fin de match) ne
peut se déclencher dans CETTE campagne (`nb_manches=1`) — il est propre
aux campagnes à plusieurs manches (voir CONTEXTE.md §19 pour les commandes
appariées, inchangées par #254).

### Campagnes appariées (à lancer par Alain — voir CONTEXTE.md §19)

Voir CONTEXTE.md §19 pour les commandes complètes (≥ 300 donnes, premier
plan, limite de temps ferme) : Expert avec/sans la règle, et Intermédiaire
contre Avancé avec/sans la règle des deux côtés. Chaque rapport affiche,
par camp, le taux de victoire (IC 95 %) et les compteurs de ce §9 — à
comparer entre AVEC et SANS pour juger l'effet réel. Le point 7 (#254)
n'est mesurable que sur une campagne à plusieurs manches (`--manches N`,
N > 1) : aucune commande appariée de ce type n'existait avant #254 ; à
ajouter par Alain si une mesure spécifique de ce point est souhaitée.
