# IA — gestion du joker (Intermédiaire/Avancé/Expert, issue #253)

> REMPLACE la règle d'attente de #252 — tout ce document décrit l'état
> ACTUEL du code (#253), pas l'historique. À lire avant de toucher à
> `moteur/ia.py` (section « Gestion du joker (issue #253) »),
> `moteur/niveaux.py` (`Bridage.eviter_don_joker`,
> `LIMITE_ECHANGE_DIFFERE`, `LIMITE_ECHANGE_DIFFERE_ADVERSAIRE_FAIBLE`,
> `SEUIL_TUILES_ADVERSAIRE_FAIBLE`, `CLE_ATTENTE_ECHANGE_DIFFERE`), ou aux
> options `--sans-don-joker-a`/`-b` de `scripts/comparer_niveaux_ia.py`
> (noms conservés de #252, gouvernent maintenant l'ensemble ci-dessous).

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
départage, voir §8bis de CONTEXTE.md).

## 2. Définition d'un joker LIBRE (REMPLACE « joker offert » de #252)

Un joker est **libre** sur un plateau donné si N'IMPORTE QUI (adversaire ou
l'IA elle-même) peut le reprendre à son tour **sans poser aucune tuile ET
sans recomposer le tapis** — donc uniquement par une recombinaison du
plateau SEUL, immédiatement disponible. Trois voies, codées dans
`jokers_libres_sur_plateau(plateau)` (`moteur/ia.py`), toutes réutilisant
une détection déjà codée pour l'IA elle-même (§8 de CONTEXTE.md), SANS
qu'aucune ne consomme de tuile du chevalet — condition commune aux trois :

1. **bout de suite** (`_jokers_libres_par_bout_suite`, NOUVELLE fonction
   #253) : joker à une extrémité d'une suite d'AU MOINS 4 tuiles, dont le
   retrait laisse une suite valide seule d'au moins 3 tuiles ;
2. **groupe de 4** (`_jokers_liberables_par_groupe4_sans_remplacement`,
   réutilisée telle quelle de #183/#252) : joker d'un groupe de 4 tuiles (3
   réelles de couleurs distinctes + le joker), dont le retrait laisse un
   groupe de 3 valide ;
3. **scission en milieu de suite** (`_jokers_liberables_par_scission_
   milieu`, réutilisée telle quelle de #181/#252) : joker STRICTEMENT
   intérieur d'une suite d'AU MOINS 7 tuiles, dont le retrait scinde la
   suite en deux suites valides (au moins 3 tuiles chacune).

Un joker au milieu d'une suite de 3 OU 4 tuiles (aucune des trois voies ne
s'applique — la suite est trop courte pour la scission, qui exige 7 tuiles
au moins, et il n'est pas en bout) n'est **pas** libre. Un joker dans un
groupe de 3 n'est **pas** libre (le groupe tomberait à 2 tuiles, sous le
minimum). `jokers_rendus_libres_par_coup(etat, idx, coup)` compare le
plateau AVANT et APRÈS un coup : laisser en place un joker déjà libre
AVANT n'est pas un cadeau fait PAR ce coup (même nuance qu'en #252).

**Changements par rapport à #252** : l'ancienne notion de « joker offert »
incluait aussi l'échange direct (`_jokers_recuperables`) et le détachement
par extension (`_jokers_detachables_par_extension`) via un chevalet
HYPOTHÉTIQUE de tuiles non encore vues — ces deux voies exigent de JOUER
une tuile (la tuile de remplacement ou la tuile d'extension), donc ne
rendent PAS le joker libre au nouveau sens (nuance centrale d'Alain). Le
chevalet hypothétique et sa construction (`_exemplaires_vus`,
`_chevalet_hypothetique_inconnu`) sont donc **supprimés** : la nouvelle
définition ne dépend plus d'aucune tuile de main ou de pioche, seulement du
plateau.

**Point où la formulation laissait un doute (choix de l'agent) :** la
fonction `_jokers_detachables_par_extension` de #252 ne détectait QUE le cas
où une tuile d'extension est nécessaire (elle ne testait jamais si la
portion restante, SANS extension, était déjà valide seule) — ce cas
(bout de suite ≥ 4 tuiles) n'avait donc jamais été codé séparément avant
#253. `_jokers_libres_par_bout_suite` est une fonction NOUVELLE, écrite
pour #253, pas une réutilisation littérale malgré ce que la formulation de
l'issue (« le code actuel possède déjà ces détections ») pouvait suggérer.

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
   exception absolue du code (point 3 de l'issue, « l'ouverture comprise »
   n'est PAS une exception : l'ouverture passe par les étapes normales,
   voir §4).
3. **Si `applique_regle_joker` est faux** (niveau Débutant/Facile, ou
   `eviter_don_joker=False` forcé) → aucune des étapes a/b/c suivantes ne
   s'exécute ; passage direct à l'étape 4 (oubli). Le coup renvoyé n'a
   JAMAIS de clé `"joker"`.
4. **Si `applique_regle_joker` est vrai**, exactement DANS CET ORDRE :
   - **a. Joker en main utile** (`_appliquer_joker_utile`, §4) — peut
     REMPLACER `coup` par un coup sans aucun joker de main. Si le coup
     résultant n'est pas une action `"jouer"` (pioche/passe), il est
     renvoyé IMMÉDIATEMENT (annoté `"joker"`) — les étapes b et c ne
     s'exécutent PAS ;
   - **b. Échange différé** (`_appliquer_echange_differe`, §6) — peut
     REMPLACER `coup` par une alternative sans l'échange, ou par une
     pioche. Si le résultat n'est pas `"jouer"`, renvoyé IMMÉDIATEMENT
     (annoté). Si le résultat est un échange FORCÉ après expiration du
     délai (`info["force"] = True`), l'étape c suivante est SAUTÉE (voir
     §6, dernier point — choix de l'agent, pas une conséquence automatique
     du texte de l'issue) ;
   - **c. Joker libre évité** (`_appliquer_joker_libre`, §5) — seulement
     si b n'a pas forcé. Peut REMPLACER `coup` par une alternative sans
     nouveau joker libre, ou par une pioche. Si le résultat n'est pas
     `"jouer"`, renvoyé IMMÉDIATEMENT (annoté).
5. **Oubli** (inchangé depuis #213/#252) : seulement si l'étape 4 a laissé
   un coup `"jouer"` (ou si l'étape 3 s'est appliquée) — avec probabilité
   `taux_oubli_effectif`, remplacé par une pioche/passe (jamais annoté
   `"joker"`, cette clé n'existe que si l'étape 4 s'est exécutée).

Un coup renvoyé porte la clé `"joker"` **si et seulement si**
`applique_regle_joker` est vrai ET le coup initial n'était ni « aucun coup
posable » ni gagnant — jamais pour Débutant/Facile, jamais pour un coup
gagnant, jamais pour `eviter_don_joker=False`.

## 4. Point 3 — joker en main UTILE (`_appliquer_joker_utile`)

**Le code fait exactement ceci** : si `coup` ne joue AUCUN joker de la main
(`ids_tuiles ∩ jokers_de_la_main == ∅`), rien à faire (le reste de la
fonction ne s'exécute pas). Sinon, calcule `coup_sans` : le meilleur coup
du MÊME niveau avec un chevalet totalement PRIVÉ de tous les jokers de la
main (pas seulement le ou les jokers joués par `coup` — TOUS, qu'ils
soient joués ou non par `coup`). `reel_avec` = nombre de tuiles RÉELLES
(jokers exclus) dans `ids_tuiles` de `coup`. `reel_sans` = nombre de
tuiles dans `ids_tuiles` de `coup_sans` SI son action est `"jouer"`, sinon
0. Si `reel_avec > reel_sans` (STRICTEMENT, l'égalité ne compte PAS comme
utile) → `coup` est renvoyé tel quel. Sinon → `coup_sans` est renvoyé s'il
est `"jouer"`, sinon une pioche/passe.

**Exemples** :
- *S'applique, utile* : main `joker, rouge_7, rouge_8, bleu_5, bleu_6,
  bleu_7, noir_2`. Avec joker : rouge7-8-(joker=9) + bleu5-6-7 = 5 tuiles
  réelles. Sans aucun joker : seule bleu5-6-7 est jouable = 3 réelles.
  5 > 3 : joué tel quel (test
  `test_joker_en_main_utile_est_joue`).
- *S'applique, pas utile* : main `joker, rouge_7, rouge_8, rouge_9,
  noir_2`. Avec joker : rouge7-8-9-(joker=10), 3 réelles (le joker n'ajoute
  QUE lui-même). Sans aucun joker : rouge7-8-9 seule, 3 réelles aussi.
  3 == 3 (égalité) : PAS utile, le joker est gardé, seule la suite de 3
  est jouée (test `test_joker_en_main_non_utile_est_garde`).
- *Cas limite — ouverture non faite* : mise initiale non faite, main
  `joker, rouge_11, rouge_12, noir_2`. Avec joker : rouge11-12-(joker=13) =
  36 points (≥ 30), 2 réelles. Sans aucun joker : rouge11-12 seules
  n'atteignent aucune mise initiale, 0 réelle jouée. 2 > 0 : utile — le
  joker REND l'ouverture possible, et c'est joué (test
  `test_joker_rend_l_ouverture_possible_est_joue`). Il n'y a pas de
  branche séparée « ouverture » dans le code : la comparaison
  `reel_avec > reel_sans` couvre ce cas automatiquement (`coup_sans` sans
  mise initiale atteignable est une pioche, donc `reel_sans = 0`).
- *Ne s'applique pas* : aucun joker dans `ids_tuiles` de `coup` →
  `evalue=False`, `coup` inchangé — par exemple un joker SUR LE PLATEAU
  (jamais concerné par cette règle, qui ne porte que sur la main).
- *Cas limite — ne s'applique JAMAIS à un coup gagnant* : un coup qui vide
  le chevalet est intercepté par l'exception absolue (§3, étape 2) AVANT
  d'atteindre cette fonction, même s'il contient un ou deux jokers de
  main — tests `test_coup_gagnant_avec_joker_toujours_joue` et
  `test_coup_gagnant_sans_joker_toujours_joue`.
- *Deux jokers* : la comparaison est faite sur l'ENSEMBLE des jokers de la
  main à la fois (chevalet SANS AUCUN joker, pas « sans ce seul joker
  joué ») — **point de doute, choix de l'agent** : la formulation
  d'Alain parle du joker au singulier ; avec deux jokers en main, le code
  ne teste pas séparément l'utilité de chacun, seulement l'utilité du jeu
  AVEC accès aux jokers (0, 1 ou 2, au choix du solveur) contre SANS aucun.
  Alain confirmera si une main à deux jokers où un seul serait utile doit
  être traitée différemment (aucun test dédié : à écrire si la réponse est
  oui).

## 5. Point 4 — joker LIBRE évité (`_appliquer_joker_libre`)

**Le code fait exactement ceci** : si `coup` ne rend libre AUCUN nouveau
joker (`jokers_rendus_libres_par_coup` vide), rien à faire. Sinon, cherche
une alternative (`_chercher_coup_sans_joker_libre`) en essayant, DANS CET
ORDRE, et en s'arrêtant au PREMIER trouvé qui n'en laisse aucun libre (pas
nécessairement le plus riche en tuiles) :
1. le coup SANS réarrangement du plateau (`_coup_sans_rearrangement`) ;
2. pour chaque tuile jouée par `coup` (les jokers joués D'ABORD, puis les
   autres dans l'ordre d'origine), le meilleur coup du même niveau obtenu
   en RETIRANT cette seule tuile de la main.

Si une alternative est trouvée, elle est jouée (quitte à poser moins de
tuiles). **Si aucune des alternatives essayées n'en évite — le seul coup
que la recherche trouve laisse un joker libre —**, l'IA pioche plutôt que
de jouer, **SANS compteur ni limite** (contrairement à l'attente bornée à
2 tours de #252, entièrement supprimée : pas de contrainte sur le nombre
de tours consécutifs de pioche).

**Point où la formulation laissait un doute (choix de l'agent)** : l'issue
parle du « seul coup possible » ; la recherche ci-dessus n'est PAS
exhaustive (bornée par `deadline`, comme #252) — « aucune alternative
trouvée par cette recherche bornée » est traité comme équivalent à « seul
coup possible », pas une preuve d'unicité absolue.

**Exemples** :
- *S'applique, alternative trouvée* : plateau `rouge_7, rouge_8,
  (joker=9)` (pas libre, 2 tuiles restantes). Main `rouge_6, bleu_5,
  bleu_6, bleu_7, noir_2`. Le coup le plus riche étendrait avec rouge_6 →
  `rouge_6,7,8,(joker=9)`, 4 tuiles, joker maintenant en bout avec 3 tuiles
  restantes : LIBRE. Alternative (retirer rouge_6) : bleu5-6-7 seule, pas
  de joker touché — jouée à la place, une tuile en moins (test
  `test_evite_le_coup_qui_rend_un_joker_libre_en_posant_moins_de_tuiles`).
- *S'applique, aucune alternative* : même plateau, main `rouge_6, noir_2`
  SEULEMENT (noir_2 injouable isolément). Retirer rouge_6 ne laisse plus
  rien à jouer → pioche, répétée IDENTIQUEMENT au tour suivant sur le même
  état (aucun compteur) — test
  `test_pioche_sans_compteur_ni_limite_si_seul_coup_laisse_un_joker_libre`.
- *Ne s'applique pas* : `coup` ne rend libre aucun joker (cas le plus
  fréquent, 99,8 % des coups joués mesurés sans AUCUNE règle sur 20
  donnes, §9) → `coup` inchangé.
- *Cas limite — deux jokers* : si `coup` rend libres DEUX jokers à la fois,
  `jokers_rendus_libres_par_coup` renvoie les deux ids ; la recherche
  s'arrête au premier candidat qui n'en laisse PLUS AUCUN (les deux
  évités ensemble, pas un à la fois) — aucun test dédié à ce cas précis.
- *Cas limite — pioche vide* : si la pioche est vide, `_piocher_ou_passer`
  renvoie une action `"passer"` à la place de `"piocher"` — même
  mécanisme, pas de code spécifique à cette règle.

## 6. Point 5 — joker repris camouflé ; échange facultatif

Le code NE contient PAS de fonction séparée « camouflage » : le
camouflage (choisir une position non libre pour un joker repris) est un
EFFET du point 4 ci-dessus (§5), appliqué de façon générique à N'IMPORTE
QUEL coup, qu'il vienne ou non d'une reprise de joker — `jokers_rendus_
libres_par_coup` ne distingue pas l'ORIGINE du joker devenu libre. Quand
le seul moyen de replacer un joker repris est une position libre et
qu'aucune alternative (même coup sans cette reprise, ou avec moins de
tuiles) n'y échappe, le point 4 pioche à sa place — ce qui réalise
exactement « elle ne le reprend pas » du point 5 de l'issue, SAUF que le
code ne décide pas spécifiquement de « ne pas reprendre » : il pioche
simplement parce qu'aucune alternative n'évite le joker libre, quelle
qu'en soit la cause.

**Limite assumée (scope, à confirmer par Alain)** : le texte de l'issue
demande aussi, PARMI plusieurs placements non libres possibles pour un
MÊME joker repris, de préférer celui dont la reprise exige la
recombinaison la plus profonde (mesure de perturbation). **Cette
préférence n'est PAS implémentée.** Deux raisons : (1) analyse structurelle
— un placement par pure extension (sans tuile de main) d'un joker repris
est TOUJOURS libre par construction (la combinaison existante qu'il
prolonge était déjà valide seule, donc son retrait la laisse valide — la
définition même de « libre », §2) ; un placement NON libre exige donc
presque toujours de combiner le joker avec au moins une tuile de la MAIN
(ce qui bascule le cas dans « elle peut l'utiliser avec sa main », hors du
périmètre du camouflage) — les scénarios où un placement purement
structurel (sans tuile de main) ET non libre coexistent avec un AUTRE
placement libre pour le MÊME joker sont donc rares et n'ont pas pu être
isolés de façon fiable dans le temps imparti ; (2) le solveur exact
(`solveur_exact.py`) décide seul, en une passe ILP, OÙ atterrit un joker
repris — choisir PARMI plusieurs placements à tuiles égales demanderait de
modifier son objectif lexicographique interne, risqué pour la garantie de
validité/conservation exigée par l'issue, donc explicitement écarté dans
le temps de cette tâche. Un futur suivi pourra re-essayer un placement
alternatif (comme `_chercher_coup_sans_joker_libre` le fait déjà pour
« éviter »), classé par perturbation (`mesurer_perturbation`, déjà
disponible), SI Alain confirme que le cas se produit assez souvent pour
justifier l'effort.

**Échange facultatif** (`_jokers_recuperables`, §8 CONTEXTE.md — l'IA
détient la tuile EXACTE de remplacement d'un joker du plateau) : le point
4 (§5) couvre naturellement les trois cas demandés, puisqu'un échange
facultatif qui expose un nouveau joker libre est traité comme n'importe
quel autre coup qui en expose un :
- *repris et camouflé* (placement non libre existe) : test
  `test_echange_facultatif_repris_et_camoufle_en_position_non_libre` — le
  joker libéré est placé avec des tuiles de main (noir_2+jaune_2, groupe
  de 3, pas libre) ;
- *non repris* (seul placement est libre, et ne gagne pas) : test
  `test_echange_facultatif_non_repris_si_seul_endroit_est_libre` — pioche ;
- *repris quand ça gagne* : test
  `test_echange_facultatif_repris_si_le_coup_fait_gagner` — l'exception
  absolue du coup gagnant (§3, étape 2) s'applique, AVANT même d'atteindre
  cette logique.

## 7. Point 6 — échange différé (`_appliquer_echange_differe`)

**Le code fait exactement ceci**, pour le PREMIER échange direct facultatif
(parmi `_jokers_recuperables` calculés sur le plateau et la main AVANT ce
tour) effectivement joué par `coup` qui remplit TOUTES les conditions
suivantes (un « ET » non exclusif : toutes doivent être vraies à la fois) :

- la tuile de remplacement de cet échange est dans `ids_tuiles` de
  `coup` ;
- le joker récupéré est toujours présent (ailleurs) dans le plateau
  résultant (repositionné par ce même coup) ;
- le joker récupéré N'EST PAS utilisé avec le reste de la main
  (`_joker_repris_utilise_avec_main` : AUCUNE tuile de la main jouée ce
  tour, autre que la tuile de remplacement elle-même, ne partage la
  combinaison finale du joker) ;
- le joker récupéré est EN RÉSERVE (`_joker_en_reserve`, voir ci-dessous).

Si ces conditions sont réunies, SEUL le PREMIER échange facultatif
rencontré dans cet ordre est traité (s'il y en a plusieurs sur le même
coup, les autres sont ignorés CE tour — point de doute, choix de l'agent :
l'issue ne précise pas le cas de plusieurs échanges différables
simultanément ; aucun test dédié).

- si le compteur d'attente de CE joker (propre à chaque id de joker,
  `dict` `{id_joker: n}`, jamais un compteur global du joueur) est
  STRICTEMENT inférieur à la limite (3, `LIMITE_ECHANGE_DIFFERE` ; réduite
  à 2, `LIMITE_ECHANGE_DIFFERE_ADVERSAIRE_FAIBLE`, si au moins un AUTRE
  joueur a STRICTEMENT moins de 5 tuiles en main — nombre de tuiles
  seulement, jamais le contenu d'une main) : cherche le meilleur coup SANS
  jouer la tuile de remplacement (`_coup_sans_tuile_main`) ;
  - si ce coup existe (action `"jouer"`) : il est joué À LA PLACE de
    `coup` (l'échange est différé), le compteur de CE joker est incrémenté
    de 1 ;
  - sinon (aucun coup sans la tuile de remplacement n'est possible — « le
    seul coup possible du tour ») : pioche À LA PLACE, le compteur n'est
    PAS incrémenté (ce tour de pioche ne compte pas comme un tour
    d'attente) ;
- sinon (compteur ≥ limite) : `coup` est joué TEL QUEL (l'échange est
  fait), le compteur de CE joker est retiré du `dict` (remis à 0). Dans ce
  cas précis, **le point 4 (§5, joker libre évité) n'est PAS appliqué
  ensuite à ce même tour** — voir « point de doute » ci-dessous.

**Joker en réserve** (`_joker_en_reserve(plateau, rec)`) : vrai si et
seulement si (un « ET » non exclusif) le nombre d'exemplaires de la tuile
de remplacement visibles sur le plateau (jokers exclus) est EXACTEMENT
`NB_SERIES - 1` (1, puisque `NB_SERIES = 2`) ET ce joker n'est pas déjà
libre (`jokers_libres_sur_plateau`). La première condition signifie :
l'autre exemplaire est sur le plateau — PERSONNE d'autre (adversaire ou
pioche) ne peut en détenir un. La seconde : aucune recombinaison du
plateau SEUL (sans la main de quiconque) ne libère déjà ce joker.

**Après chaque appel**, indépendamment du traitement ci-dessus : tout
joker dont le compteur existe mais qui N'EST PLUS en réserve (p. ex. le
plateau a été recomposé par l'adversaire) voit son compteur RETIRÉ du
`dict` — même si ce joker n'était pas concerné par `coup` ce tour-ci. C'est
la mise en œuvre de « remis à zéro... quand la réserve cesse ».

**Point où la formulation laissait un doute (choix de l'agent)** : l'issue
dit « passé ce délai, elle fait l'échange, sous les règles du point 5 ».
Appliquer LITTÉRALEMENT les règles du point 5 à ce moment referait
exactement la recherche d'alternative que le délai vient d'épuiser (le
point 4 chercherait l'alternative SANS l'échange, qui existe presque
toujours puisque l'échange est par définition facultatif) — annulant
systématiquement la décision « forcer » de ce point 6. L'agent a choisi de
rendre cette décision FINALE pour le tour en cours (le point 4 n'est pas
réappliqué à CE coup précis) : une fois le délai de réserve épuisé, le
risque est accepté sans retour en arrière. **Alain confirmera** si cette
lecture correspond à son intention, ou si « sous les règles du point 5 »
signifiait plutôt que l'échange forcé devrait, lui aussi, décliner si son
seul placement est libre (ce qui, par construction algorithmique actuelle,
reviendrait à ne JAMAIS pouvoir forcer l'échange après un délai expiré tant
qu'une alternative existe — comportement jugé incohérent avec l'intention
du délai, donc non retenu sans confirmation).

**Exemples** (voir `tests/test_ia_anti_don_joker.py`, section « Point 6 ») :
- *différé jusqu'à 3 tours puis fait* :
  `test_echange_differe_jusqu_a_trois_tours_puis_fait` — 3 appels
  consécutifs sur le même état différent (compteur 1, 2, 3), le 4e force
  l'échange (compteur remis à 0) ;
- *limite à 2 si adversaire faible* :
  `test_echange_differe_limite_a_deux_tours_si_adversaire_faible` — même
  scénario, adversaire à 3 tuiles (< 5), limite atteinte au 3e appel ;
- *fait aussitôt si utilisable avec la main* :
  `test_echange_fait_aussitot_si_joker_utilisable_avec_la_main` — réserve
  présente, mais le joker rejoint un groupe avec deux tuiles de main :
  jamais différé ;
- *fait aussitôt si pas en réserve* :
  `test_echange_fait_aussitot_si_pas_en_reserve` — aucun second exemplaire
  visible, le point 6 ne s'applique pas du tout, le point 4 (général)
  décide seul ;
- *fait aussitôt si le coup gagne* :
  `test_echange_facultatif_repris_si_le_coup_fait_gagner` — l'exception
  absolue du coup gagnant (§3) s'applique avant même le point 6 ;
- *compteur retiré quand la réserve cesse* :
  `test_compteur_differe_retire_quand_la_reserve_cesse` — compteur posé à
  2 manuellement, plateau recomposé (plus de second exemplaire visible),
  retiré au tour suivant ;
- *pas de tour passé, sauf coup unique* :
  `test_echange_differe_ne_passe_pas_le_tour_sauf_coup_unique` — pendant le
  différé, l'IA joue un AUTRE coup normalement (pas un tour passé) ; si
  l'échange est le SEUL coup possible, elle pioche.

**Cas limite — deux jokers en réserve simultanément** : seul le PREMIER
rencontré dans l'itération de `_jokers_recuperables` est traité par appel ;
aucun test dédié à deux réserves simultanées (voir point de doute
ci-dessus, §7).

## 8. Paramètres et désactivation

Activée (`Bridage.eviter_don_joker=True`, nom du champ CONSERVÉ de #252)
pour **Intermédiaire, Avancé et Expert** ; **Débutant et Facile** restent à
`False` (comportement d'avant #252/#253 inchangé). `jouer_niveau_bride(...,
eviter_don_joker=None|True|False)` force l'activation/désactivation
indépendamment du niveau — utilisé par `scripts/comparer_niveaux_ia.py
--sans-don-joker-a`/`-b` (noms de drapeau CONSERVÉS) pour comparer, à
seed et donnes identiques, une campagne AVEC et SANS l'ensemble de la
règle (y compris A et B au même niveau).

Paramètres réglables (`moteur/niveaux.py`) :
- `LIMITE_ECHANGE_DIFFERE = 3` (tours de différé au plus) ;
- `LIMITE_ECHANGE_DIFFERE_ADVERSAIRE_FAIBLE = 2` (si un adversaire a moins
  de `SEUIL_TUILES_ADVERSAIRE_FAIBLE` tuiles) ;
- `SEUIL_TUILES_ADVERSAIRE_FAIBLE = 5`.

La règle ne limite JAMAIS les tactiques de récupération de joker de l'IA
elle-même (§8 de CONTEXTE.md, inchangées) — elle gouverne seulement : quel
joker de main jouer (point 3), où le camoufler s'il est repris (point 5),
si différer un échange facultatif (point 6), et quel coup choisir pour ne
pas laisser de joker libre (point 4).

## 9. Mesure (`scripts/comparer_niveaux_ia.py`)

Le rapport affiche, **par CAMP** : le nombre de coups joués (hors coup qui
vide le chevalet) qui rendent NOUVEAU libre un joker, sur le total de ces
coups (taux) ; le nombre de tours de pioche dus à un joker libre sans
alternative (doivent rester quasi nuls) ; le nombre de jokers de main
gardés plutôt que joués ; le nombre d'échanges facultatifs différés, et
parmi eux ceux ayant forcé une pioche.

Essai de 20 donnes, premier plan, graine 42, Expert contre Expert :

```
# AVANT (règle désactivée des deux côtés — référence) :
python scripts/comparer_niveaux_ia.py --niveau-a Expert --niveau-b Expert \
    --donnes 20 --seed 42 --sans-don-joker-a --sans-don-joker-b
# → 1/524 coup(s) (0,2 %) laissent un joker libre ; 0 pioche forcée ;
#   0 joker de main gardé ; 0 échange différé.
#   Temps de calcul Expert : moyenne 78,3 ms, max 1496,0 ms (2610 tours).

# APRÈS (règle activée des deux côtés) :
python scripts/comparer_niveaux_ia.py --niveau-a Expert --niveau-b Expert \
    --donnes 20 --seed 42
# → 0/531 coup(s) (0,0 %) laissent un joker libre ; 2 pioches forcées ;
#   5 jokers de main gardés ; 1 échange différé (ayant forcé 1 pioche).
#   Temps de calcul Expert : moyenne 91,5 ms, max 1462,1 ms (2642 tours).
```

Effet mesuré : le taux de jokers libres restants passe de 0,2 % à 0,0 % (déjà
quasi nul sans règle, confirmant l'observation d'Alain — le problème que
#253 corrige est surtout les 5 jokers de main gardés, invisibles dans
cette mesure sous #252). Temps de calcul : +13,2 ms en moyenne (~+17 %),
le maximum NE SE DÉGRADE PAS (la recherche d'alternative n'est invoquée
que sur les rares coups concernés) — bien plus léger que #252 (qui
doublait le temps moyen sur les tours concernés).

### Campagnes appariées (à lancer par Alain — voir CONTEXTE.md §19)

Voir CONTEXTE.md §19 pour les commandes complètes (≥ 300 donnes, premier
plan, limite de temps ferme) : Expert avec/sans la règle, et Intermédiaire
contre Avancé avec/sans la règle des deux côtés. Chaque rapport affiche,
par camp, le taux de victoire (IC 95 %) et les compteurs de ce §9 — à
comparer entre AVEC et SANS pour juger l'effet réel. Seul le point 6
(échange différé) profite à l'IA elle-même quel que soit l'adversaire :
c'est le seul sous-point que ces duels IA-contre-IA mesurent vraiment (les
points 4/5 ne sont validés que par les compteurs et les tests fixes — voir
CONTEXTE.md §19).
