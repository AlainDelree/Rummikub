# Rendre lisible un coup complexe de l'IA (pas-à-pas)

## 12. Rendre lisible un coup complexe de l'IA (issue #189, puis #191)

Depuis le solveur de réarrangement global (#186), un coup de l'IA peut
défaire et recomposer plusieurs combinaisons du plateau en un seul tour. Le
rejeu animé existant (tuile par tuile, #144/#149) reste le comportement PAR
DÉFAUT du bouton « ▶ Dernier coup joué par... », inchangé pour tous les
coups — les aides ci-dessous sont des options accessibles à côté de ce
bouton, jamais imposées, et ne modifient jamais l'état de la partie.

L'issue #191 a entièrement revu le moteur `description_coup.py` introduit par
#189 : le classement par simple comparaison avant/après donnait des étapes
incohérentes (une même tuile visible deux fois à la fois, des phrases avec
des tournures de message automatique). Le nouveau moteur suit **chaque
tuile individuellement, par son identifiant**, de sa position d'avant à sa
position d'après.

- **Moteur commun** (`_construire_operations`, privé, partagé par les deux
  fonctions publiques) : pour chaque combinaison d'avant, la destination
  d'après qui reçoit une **majorité stricte** (`> moitié`) de ses tuiles est
  sa continuation ("update" : elle garde son identité, peut à la fois perdre
  et gagner des tuiles en un seul changement, ex. joker remplacé par une
  tuile réelle). Sans majorité claire, elle se dissout et chacune de ses
  tuiles est libérée par une opération **"retrait"** distincte, regroupée
  par destination (jamais tout d'un coup si plusieurs destinations se
  partagent ses tuiles — c'est ce qui permet d'afficher un état
  "provisoire" entre deux retraits). Une combinaison d'après sans
  continuation est "create" (entièrement recomposée depuis le cadre). Les
  opérations sont ensuite triées par un **tri topologique causal** (une
  tuile doit être libérée avant d'être réutilisée) qui **privilégie les
  échanges de jokers dès qu'ils sont possibles** (issue #191, point 3bis) —
  priorité aux opérations qui libèrent/consomment un joker, puis
  update > create > retrait, puis ordre stable. Deux combinaisons
  distinctes qui porteraient le même nom (ex. deux « groupe de 11 » à des
  moments différents du coup) sont désambiguïsées en listant leurs couleurs
  (`_desc_fabrique`, en comptant les identités distinctes — pas les simples
  libellés — pour ne pas confondre une combinaison avec sa propre
  continuation).
- **Résumé écrit** (`decrire_coup_ia(plateau_avant, plateau_apres, nom=None)`)
  : renvoie `{"texte", "tuiles_posees", "nb_combinaisons_defaites",
  "nb_combinaisons_creees", "nb_combinaisons_modifiees", "jokers_deplaces"}`.
  `nom` (le nom du joueur IA, passé par `api.py`) permet de commencer par
  « <Nom> a posé... » plutôt que par « A posé... » (sujet omis). Depuis
  #198 (voir §12ter), AUCUNE phrase du résumé n'utilise de pronom
  « il »/« elle » pour désigner le joueur. Un coup simple
  (une seule combinaison touchée, aucun joker déplacé) reste **une seule
  phrase** ; au-delà, plusieurs phrases courtes en français naturel, avec
  contractions (« du groupe de 3 », « au groupe de 11 » — jamais « de le »/
  « à le », cf. `_contracter`).
- **Rejeu pas-à-pas** (`etapes_coup_ia`, PRIORITÉ de l'issue) : une suite
  d'états où chaque tuile n'est qu'à un seul endroit à la fois — sur le
  plateau (`"plateau"`, même format qu'avant) ou dans le cadre **« tuiles à
  placer »** (`"cadre"` : `[{"tuile": dict, "origine": "main"|"plateau"}]`).
  Structure : un écran **« Départ »** (titre dédié, plateau d'avant, cadre
  rempli des tuiles de la main) ; si des jokers changent de combinaison, un
  écran **« Les jokers »** juste après (vue d'ensemble : d'où chaque joker
  vient, par quelle tuile il est remplacé et d'où elle vient, où il finit —
  ne change rien à l'écran, titre dédié) ; puis une étape par opération
  (titre vide), chacune avec `"provisoires"` (index dans `"plateau"` des
  combinaisons mi-démantelées, temporairement invalides) et `"surbrillance"`
  (ids des tuiles juste posées/libérées à cette étape, pour réutiliser la
  surbrillance existante côté front). La toute dernière étape correspond
  exactement au plateau d'après, cadre vide. `etapes_coup_ia([], [])` (ou
  tout coup sans la moindre tuile posée) renvoie `[]`.
- **Seuil d'affichage du bouton** : ce n'est PLUS `coup.etapes.length >= 2`
  (les écrans "Départ"/"Les jokers" existent même pour un coup simple) mais
  le nombre d'étapes à **titre vide** (changements réels) — voir
  `nbChangementsPasAPas()` côté JS, dupliquant la même logique que `simple`
  côté Python dans `decrire_coup_ia`.
- **Calcul unique côté `api.py`** : `jeu_ia_jouer` appelle les deux fonctions
  ci-dessus immédiatement après une pose (avec `nom=etat["joueurs"][idx]
  ["nom"]`) et stocke `resume`/`etapes` dans `etat["dernier_coup_ia"]` —
  aucun aller-retour JS → Python supplémentaire.
- **Front-end** (`jeu.js`/`jeu.html`/`jeu.css`) :
  - `#resume-coup-ia` affiche `coup.resume` tel quel (inchangé depuis #189).
  - `#zone-cadre-pas-a-pas`/`#cadre-tuiles-pas-a-pas` (NOUVEAU, au-dessus de
    l'aperçu du plateau dans `#overlay-pas-a-pas`) : rendu par
    `rendreCadrePasAPas`, une tuile par entrée de `etape.cadre`, pourtour
    **vert `.ce-tour`** (tuile de la main) ou **orange `.deplacee-tapis`**
    (tuile libérée du plateau) — mêmes classes que la légende existante
    (`#legende-couleurs`), aucune nouvelle couleur introduite. Cadre vide
    affiché comme tel (`.cadre-vide`, texte "vide").
  - `#soustitre-etape-pas-a-pas` affiche `etape.titre` ("Départ"/"Les
    jokers"/vide pour un changement normal).
  - `rendreApercuPlateauPasAPas` ajoute `.combi-provisoire` (liseré ambre
    pointillé + mention, visuellement distinct de `.combi-invalide` qui
    reste réservée aux vraies erreurs du joueur sur le vrai tapis) sur les
    combinaisons listées dans `etape.provisoires`, et la **surbrillance forte**
    `.tuile-pas-active` (issue #209, voir §12quinquies — remplace l'ancien
    `.tuile-ia-highlight` discret, désormais réservé au rejeu animé) sur les
    tuiles listées dans `etape.surbrillance`. `rendreCadrePasAPas` applique la
    même `.tuile-pas-active` aux tuiles du cadre nommées par l'étape.
  - `#btn-pas-a-pas-coup-ia` démasqué par `rafraichirBoutonRejouerIA()` —
    critère revu par #207 (`coupMeriteePasAPas`, voir §12quater), qui remplace
    l'ancien `nbChangementsPasAPas(coup.etapes) >= 2`.
  - `#overlay-pas-a-pas` reste une carte modale en LECTURE SEULE, totalement
    indépendante de `rejouerDernierCoupIA` (bouton de rejeu animé,
    inchangé) ; navigation Suivant/Précédent par index local
    (`indexEtapePasAPas`), « Quitter » referme sans effet sur la partie.
  - **Bascule Avant/Après (point 2 de l'issue #189) : réalisée par #207**
    (voir §12quater), de même que le pas-à-pas condensé et la ligne de taille.
- Tests : `tests/test_description_coup.py` — contractions (`_contracter`,
  du/au/des/aux, groupe/suite) ; coups simples (extension de suite, groupe
  créé depuis la main, aucun changement) ; joker récupéré puis rejoué dans
  un nouveau groupe (avec vérification explicite que le joker transite par
  le cadre AVANT d'être repris) ; démantèlement complet d'un groupe en 3
  nouvelles combinaisons (désambiguïsation par couleurs, état provisoire
  visible) ; le cas Bruno (3 bleu/11 bleu/11 noir) décrit dans l'issue, texte
  du résumé comparé mot pour mot à l'exemple de l'issue ; le coup en chaîne
  Bruno/Expert à 5 combinaisons d'avant (jokers + double suite coupée en
  deux), avec vérification tuile par tuile de l'ordre causal (le 11 jaune
  sort de la suite jaune avant de remplacer le joker, etc.) et que le 11
  jaune est bien présenté comme venant du plateau, jamais de la main. Un
  helper `_verifier_invariants` commun vérifie sur chaque scénario : aucune
  tuile à deux endroits à aucune étape, pas d'étape sans changement visible,
  cadre vide et plateau identique à `plateau_apres` à la toute dernière
  étape. `tests/test_playwright_pas_a_pas.py` (nécessite `pip install
  playwright` + `playwright install chromium`, absent de requirements.txt
  — sauté proprement sinon) : charge `jeu.html` directement (jamais la
  vraie app pywebview), injecte un `dernier_coup_ia` fictif et pilote les
  boutons réels ; vérifie le cadre qui se vide progressivement avec les
  bonnes couleurs de pourtour, l'absence de tuile commune cadre/plateau à
  chaque étape, et que « Quitter » ne modifie rien.

### 12bis. Tuiles identiques interchangeables (issue #197)

Le jeu contient deux exemplaires de chaque tuile (même valeur/couleur). Le
suivi tuile-par-tuile de `description_coup.py` (§12), qui identifie chaque
tuile par son identifiant individuel, prenait littéralement « la tuile A
sort, la tuile B entre » comme un changement réel même quand A et B sont
visuellement indiscernables — bruit supplémentaire dans le pas-à-pas, et
**plantage réel en jeu** (`KeyError` sur `del cadre[...]`, une tuile libérée
par un échange annulé n'étant jamais déposée dans le cadre avant d'être
consommée ailleurs).

- **Séparation bookkeeping/affichage** (`_retrait_ajout_bruts` +
  `_annuler_par_aspect`, dans `_construire_operations`) : pour chaque
  continuation ("update"), les tuiles RÉELLEMENT parties/arrivées
  (`retirees`/`ajoutees`, par identifiant — toujours utilisées pour le
  cadre et le graphe de dépendances, donc JAMAIS d'exception) sont
  distinctes des tuiles À AFFICHER (`retirees_vues`/`ajoutees_vues` —
  réduites en annulant deux à deux une tuile partie et une tuile arrivée de
  même aspect, `_aspect()` : même valeur/couleur, ou n'importe quel joker).
  Une opération dont les deux listes "vues" sont vides est ajoutée au
  cadre/plateau comme d'habitude mais n'affiche AUCUNE étape
  (`etapes_coup_ia`) et ne compte dans aucun total (`decrire_coup_ia`,
  `_desc_fabrique`, `_jokers_deplaces`) — couvre l'échange dans une même
  combinaison (point 1), une tuile de la main identique à une tuile du
  plateau qui se déplace (point 2 : les deux « tuiles » s'annulent au sein
  d'une même opération), et deux jokers qui se remplacent dans une même
  combinaison (point 3, premier cas — `_jokers_deplaces` ne considère un
  joker comme déplacé que s'il figure dans `retirees_vues` de sa propre
  opération, jamais via `libere` brut).
- **Échange cyclique entre deux combinaisons** (`_composantes_fortement_
  connexes` — Tarjan, puis `_detecter_blocs_silencieux`) : quand deux
  combinaisons s'échangent leurs tuiles (chacune a besoin d'une tuile
  libérée par l'autre), le graphe de dépendances causales a un cycle
  strict, impossible à sérialiser normalement — **c'est le cas réel qui
  faisait planter le jeu**. Un cycle où TOUTES les opérations impliquées
  sont des "update" entièrement invisibles est traité comme un seul
  **bloc** : le tri topologique le place comme une unité, et
  `etapes_coup_ia` applique en un seul geste toutes les tuiles libérées du
  bloc au cadre, PUIS toutes les tuiles consommées du bloc, sans jamais
  dépendre de l'ordre interne entre ses membres. Un cycle qui ne qualifie
  pas (un "retrait"/"create" dedans, ou une "update" partiellement
  visible) reste sur le repli pré-existant (ordre arbitraire) — cas
  extrême resté hors de portée, jamais rencontré avec un coup réellement
  joué.
- **Repli d'urgence déjà en place côté `ui/api.py`** (`jeu_ia_jouer`,
  issue #196) : si malgré tout `decrire_coup_ia`/`etapes_coup_ia` levaient
  une exception, le tour de l'IA n'est jamais bloqué — résumé/étapes vides,
  et les deux plateaux sont sauvegardés dans
  `RACINE_DATA/erreurs_description/<horodatage>.json`
  (`{"erreur", "plateau_avant", "plateau_apres"}`) pour reproduire le cas.
  `tests/donnees/erreur_description_20261027_115033.json` est un exemple
  réel ainsi capturé (le `KeyError: 'jaune_3_a'` ci-dessus), rejoué dans
  `tests/test_description_coup.py` comme test de non-régression.
- **Complexité des coups ratés** (`persistance/coups_rates.py`,
  `_complexite_coup`) : réutilise tel quel `decrire_coup_ia`/
  `etapes_coup_ia` corrigés — un échange de tuiles identiques n'est donc
  plus compté dans `nb_combinaisons_touchees` ni `nb_etapes`, sans
  changement de code dans `coups_rates.py` lui-même.
- **Tests** (`tests/test_description_coup.py`) : échange main/plateau dans
  une même combinaison, échange cyclique entre deux combinaisons (sans
  autre changement), régression bout en bout sur le cas réel ayant
  planté, deux jokers (un remplacé par l'autre dans une même combinaison —
  pas un déplacement — et un second qui change réellement de combinaison
  — reste un déplacement). `tests/test_coups_rates_description.py` : un
  échange de tuiles identiques, seul changement d'un coup, est classé
  "simple" (0 combinaison touchée, 0 étape). Les cas déjà couverts avant
  #197 (chaîne Bruno/Expert, échange de joker, démantèlement de groupe)
  gardent EXACTEMENT le même nombre d'étapes qu'avant (pas de régression).

### 12ter. Accords en français et suppression des pronoms genrés (issue #198)

Deux défauts grammaticaux relevés sur de vraies descriptions produites par
#189/#191/#197 ci-dessus, corrigés dans `moteur/description_coup.py` SANS
toucher au moteur tuile-à-tuile (`_construire_operations`) ni à la logique
de complexité (§11quater) :

- **Accord de la couleur avec « suite »** (`_couleur_suite`, table
  `_COULEURS_FEMININES = {"noir": "noire", "bleu": "bleue"}`) : « suite »
  est féminin, donc « suite noire », « suite bleue » (« rouge »/« jaune »
  sont déjà identiques au féminin, inchangés). Appliqué partout où une
  couleur qualifie « suite » : `_decrire_combo` (résumé, étapes, écran
  « Les jokers ») et `_label_combo` (désambiguïsation par couleurs,
  §12 point `_desc_fabrique`). **Jamais appliqué à « groupe »** (masculin,
  ou simple liste de couleurs par tuile, ex. « groupe de 11 bleu, jaune et
  noir ») : accord uniquement sur le mot « suite » lui-même, jamais sur la
  liste de couleurs d'un groupe.
- **Suppression des pronoms « il »/« elle »** : plus aucune phrase du
  résumé (`decrire_coup_ia`) ne présuppose le genre du joueur. La branche
  « coup complexe » (plusieurs phrases) utilisait `"Il a créé..."`,
  `"Il a complété..."`, `"Il a retiré..."` quel que soit `nom` — corrigé en
  tournures impersonnelles : une création devient nominale (`"Création
  d'un groupe de 11."`, avec élision « de » → « d' » devant voyelle, voir
  extension de `_contracter` ci-dessous), les autres changements d'une
  combinaison reprennent les TUILES comme sujet de la phrase (`"Le 3 bleu
  remplace le joker dans le groupe de 3."`), exactement comme le fait déjà
  le pas-à-pas (`etapes_coup_ia`) depuis #191. Les deux fonctions
  partagent désormais le même texte pour un changement « update »
  (nouveau helper privé `_texte_update(op, desc)`, extrait de la logique
  dupliquée) — pur regroupement de code, aucun changement de comportement
  côté pas-à-pas. `_contracter` gère en plus l'élision de « de » devant un
  article indéfini à initiale vocalique (« un »/« une » → « d'un »/« d'une »,
  jamais pour « à », qui ne s'élide pas en français).
- **Non concerné** : l'écran « Les jokers » et les phrases sur les
  combinaisons défaites (`_phrase_sujet`) n'utilisaient déjà aucun pronom
  (sujet = les tuiles ou « le joker ») — aucun changement nécessaire
  au-delà de l'accord de couleur ci-dessus.
- Tests (`tests/test_description_coup.py`) : accord de « suite » avec
  chacune des quatre couleurs (texte ET étiquette courte `_label_combo`) ;
  « groupe » reste invariable avec les quatre couleurs (jamais de « e »
  final ajouté). Mise à jour nécessaire de deux tests existants devenus
  obsolètes par construction (texte comparé mot pour mot) : la contraction
  de référence attendait `"suite noir"` (désormais `"suite noire"`), et le
  cas Bruno (#191) attendait `"Il a créé..."`/`"Il a complété..."`
  (désormais `"Création d'un groupe de 11."`/`"Le 3 bleu remplace le
  joker dans le groupe de 3."`) — même contenu, formulation différente.

### 12quater. Pas-à-pas condensé, taille du coup, bascule Avant/Après (issue #207)

Depuis l'Expert exact (#206), un coup peut déplacer beaucoup de tuiles : le
pas-à-pas tuile-par-tuile (#191) devenait très long (30 étapes pour un vrai
coup de Clara). L'issue #207 condense le découpage, annonce l'ampleur du coup,
ajoute un mode détaillé optionnel et la bascule Avant/Après, et corrige deux
défauts d'affichage. **Aucun changement au moteur, à l'IA ni à la sauvegarde.**

- **Pas-à-pas condensé par défaut** (`etapes_coup_ia(avant, apres,
  condense=True)`, défaut) : regroupe les gestes par combinaison. Les tuiles
  libérées d'une combinaison défaite transitent par le cadre **sans étape
  dédiée** (la combinaison rétrécie reste « provisoire ») ; **une étape par
  combinaison créée ou complétée** ; départ, écran « Les jokers », cadre,
  provisoires, surbrillances et dernière étape (plateau d'après exact, cadre
  vide) inchangés. Résultat : le coup de Clara passe de 30 à **10 étapes**
  (< 12), celui de Bruno #57 de 27 à < 11. Un coup court donne le même
  découpage qu'en détaillé. Implémentation : en mode condensé, les opérations
  « retrait » et les « update » invisibles mettent à jour working/cadre mais
  **n'émettent pas d'étape** (le suivi causal reste exact) ; un filet ajoute
  une dernière étape « plateau d'après » dédoublonnée par
  `_sans_etapes_sans_effet`.
- **Mode détaillé** : `etapes_coup_ia(..., condense=False)` conserve le
  découpage tuile-par-tuile de #191. `api.py` calcule et stocke les DEUX
  (`etat["dernier_coup_ia"]["etapes"]` = condensé, `["etapes_detaillees"]` =
  détaillé). Front : bouton `#btn-pas-a-pas-detailler` (« Détailler » ↔
  « Condenser »), condensé à chaque ouverture. **Note importante** : la
  relabellisation des tuiles indiscernables (ci-dessous) n'est PAS appliquée à
  `etapes_coup_ia` (elle casse le suivi causal d'un très gros coup : le repli
  à 2 étapes s'y substituerait) — seulement au résumé et à la mesure.
- **Mesure / taille du coup** (`mesurer_coup_ia(avant, apres)` →
  `{"nb_tuiles_posees", "nb_tuiles_plateau_deplacees",
  "nb_combinaisons_modifiees", "nb_combinaisons_creees", "taille"}`), stockée
  dans `etat["dernier_coup_ia"]["mesure"]`. `nb_combinaisons_modifiees` =
  combinaisons DÉFAITES ou MODIFIÉES (hors créations pures). `taille` =
  « petit »/« moyen »/« grand » selon les combinaisons TOUCHÉES
  (défaites+créées+modifiées), **mêmes seuils que `coups_rates.py`** (1-2 /
  3-5 / 6+, `_taille_mot` recopie ces bornes pour ne pas dépendre de la
  persistance). `nb_tuiles_plateau_deplacees` = même définition que
  `trouverTuilesDeplacees` de `jeu.js`. Affichée en tête du pas-à-pas par
  `majLigneTaillePasAPas` : « Coup de grande taille : 14 tuiles du plateau
  déplacées, 6 combinaisons modifiées, 4 tuiles posées depuis la main. »
- **Bascule Avant/Après** (point 2 de #189, enfin réalisé) : bouton
  `#btn-pas-a-pas-comparaison` ; `#vue-comparaison-pas-a-pas` montre les deux
  plateaux côte à côte en LECTURE SEULE, combinaisons modifiées/créées en
  évidence (`.combi-modifiee`), tuiles distinguées par origine (`.ce-tour`
  main, `.deplacee-tapis` déplacée), avec légende `#legende-pas-a-pas`.
  Ne modifie jamais la partie.
- **Défaut 1 corrigé (résumé)** : `decrire_coup_ia` (et `mesurer_coup_ia`)
  passent d'abord par `_relabeler_tuiles_indiscernables` (remontée depuis
  `coups_rates.py`, enrichie d'un **appariement bijectif global** + garde-fou
  itératif contre la duplication d'id — notamment d'un joker resté dans un
  autre groupe). Deux tuiles de même aspect qui échangent leurs places dans
  une même combinaison ou entre combinaisons ne produisent plus de phrase
  « X remplace Y » ; une combinaison identique avant/après n'est ni modifiée
  ni défaite.
- **Défaut 2 corrigé (seuil du bouton)** : le bouton « Pas à pas » apparaît
  dès que le coup **déplace ≥ 1 tuile du plateau OU modifie ≥ 2 combinaisons**
  (`coupMeriteePasAPas`, à partir de `coup.mesure`), plus seulement « ≥ 2
  étapes nettoyées ». Un coup qui n'ajoute que des tuiles de la main à une
  seule combinaison, ou en crée, reste sans bouton. Repli sur l'ancien
  critère pour les parties d'avant #207.
- Tests : `tests/test_description_coup.py` (condensé < 12 étapes pour Clara,
  invariants condensés, position fabriquée, coup court inchangé, mesure,
  défaut 1) ; `tests/test_condense_solveur.py` (coups réels du modèle exact,
  dont Bruno #57 < 11 — sauté sans `rummikub-solver`) ;
  `tests/test_playwright_pas_a_pas.py` (bouton présent pour Clara, absent pour
  une création pure, ligne de taille, bouton « Détailler », bascule
  Avant/Après).

### 12quinquies. Surbrillance forte de la tuile active (issue #209)

Dans le pas-à-pas condensé (#207), chaque étape décrit un geste précis (« Le
2 bleu, le 2 noir et le joker forment un groupe de 2 ») mais la ou les tuiles
concernées n'avaient qu'un liseré discret (`.tuile-ia-highlight`), noyé sous le
cadre « provisoire » et le liseré de la combinaison modifiée. #209 rend la
tuile active **repérable d'un coup d'œil, sans lire la phrase**.
**Front-end uniquement** (`jeu.css`/`jeu.js`), plus un ajustement de la liste
`surbrillance` côté `description_coup.py` pour l'écran « Les jokers » ; aucun
changement au moteur de jeu, à l'IA, à la sauvegarde ni au texte/découpage.

- **Nouvelle classe `.tuile-pas-active`** (`jeu.css`) : contour épais magenta
  (3 px), double halo pulsé, léger agrandissement (`scale(1.1)`) et fond
  légèrement teinté (voile `::after` glissé SOUS le chiffre via
  `.tuile-pas-active > * { z-index:1 }`, pour ne jamais masquer la valeur ni la
  couleur). **Intensité volontairement supérieure** à `.combi-modifiee`
  (liseré bleu 2 px) et à `.combi-provisoire` (liseré ambre pointillé) → la
  hiérarchie saute aux yeux : d'abord la tuile active, puis la combinaison
  touchée, puis le reste. Le magenta est absent des couleurs de tuile
  (rouge/bleu/jaune/noir) et des deux liserés, donc aucune confusion ; visible
  sur le fond vert du plateau comme sur le fond clair du cadre.
- **Remplacement de `.tuile-ia-highlight`** dans `rendreApercuPlateauPasAPas`
  par `.tuile-pas-active`. `.tuile-ia-highlight` reste utilisée UNIQUEMENT par
  le rejeu animé (`animerPoseTuiles`), inchangé.
- **Surbrillance aussi dans le cadre** : `rendreCadrePasAPas(conteneur, cadre,
  surbrillance)` applique `.tuile-pas-active` aux tuiles du cadre « tuiles à
  placer » nommées par l'étape (par-dessus leur pourtour de provenance
  vert/orange) — écran « Départ » (tuiles de la main prêtes à poser) et toute
  tuile qui vient de rejoindre le cadre.
- **Cohérence texte ↔ surbrillance** : les tuiles mises en avant à une étape
  sont EXACTEMENT celles de `etape.surbrillance`, plateau et cadre confondus.
  Correctif associé dans `description_coup.py` : la `surbrillance` de l'écran
  « Les jokers » inclut désormais le joker ET, s'il est remplacé, sa ou ses
  tuiles de remplacement (auparavant le seul id du joker), pour correspondre
  mot pour mot à la phrase « Le joker … est remplacé par … ».
- Tests : `tests/test_description_coup.py`
  (`test_joker_recupere_puis_rejoue_ailleurs` vérifie la `surbrillance`
  joker+remplaçant ; `test_surbrillance_jokers_libere_sans_remplacant` qu'un
  joker simplement libéré ne met en avant que lui) ;
  `tests/test_playwright_pas_a_pas.py`
  (`test_surbrillance_forte_suit_exactement_les_tuiles_de_chaque_etape` : à
  chaque étape du coup de Clara, les tuiles `.tuile-pas-active`
  plateau+cadre == `etape.surbrillance`, au moins une par étape ;
  `test_surbrillance_forte_joker_et_remplacant_plateau_et_cadre` : écran
  « Les jokers » du cas Bruno, joker sur le plateau + remplaçant dans le cadre
  tous deux mis en avant).

### 12sexies. Découpage « une étape = une modification », repères d'origine, bascule Avant/Après corrigée (issue #214, suite de #207)

Sur un gros coup d'Expert (Léo), ni le condensé (#207, trop fusionné : plusieurs
modifications dans une même étape) ni le détaillé (une tuile à la fois, trop
fin) ne se lisaient bien, et la bascule Avant/Après (#207) avait trois défauts.
L'issue #214 ajoute un **troisième découpage, devenu le mode par défaut**, et
corrige la bascule. **Aucun changement au moteur de jeu, à l'IA ni à la
sauvegarde.**

- **Nouveau découpage « une modification »** (`etapes_coup_ia(avant, apres,
  mode="modification")`, **défaut** — remplace le condensé comme mode affiché) :
  chaque étape = UN geste compréhensible portant sur UNE SEULE combinaison, et
  dit toujours CE qui bouge et D'OÙ ça vient / vers où.
  - **Défaire une combinaison** = UNE étape : toutes ses tuiles réelles (joker
    compris) rejoignent le cadre d'un coup, puis la combinaison disparaît
    (`_texte_defaite` : « Le groupe de 9 est défait : le 9 bleu, le 9 jaune et
    le 9 noir rejoignent les tuiles à placer. »). C'est le point clé qui
    distingue ce mode du condensé (où la défaite était invisible) et du
    détaillé (une étape par destination de tuile). Libérer toutes les tuiles
    d'une combinaison dès son premier « retrait » reste causalement sûr (une
    tuile consommée plus loin était de toute façon ordonnée après).
  - **Créer** / **compléter** une combinaison = UNE étape chacune (comme le
    condensé). Quand une combinaison ne fait que PERDRE une tuile
    (continuation « update »), le texte précise qu'elle rejoint le cadre
    (`_texte_update_modif` : « Le 11 rouge sort de la suite rouge (8 à 11) et
    rejoint les tuiles à placer. »).
  - Ordre causal, cadre « tuiles à placer », écran « Départ », écran « Les
    jokers », dernière étape (plateau d'après exact, cadre vide) et surbrillance
    forte `.tuile-pas-active` (#209) : tous **inchangés**. Résultat : coup de
    Clara tour 45 = 16 étapes (condensé 10, détaillé 30), entre les deux ;
    chaque étape ne touche qu'une combinaison (vérifié PAR ASPECT, une
    relabellisation invisible de tuiles indiscernables ne comptant pas). Borne
    testée : `nb_combinaisons_modifiees + nb_combinaisons_creees + 3`.
- **`mode`** ∈ {`"modification"` (défaut), `"detaille"` (= ancien
  `condense=False`, bouton « Détailler »), `"condense"` (= ancien
  `condense=True`, conservé pour `coups_rates.py` et la non-régression)}.
  L'ancien booléen `condense` reste accepté (`True`→condensé, `False`→détaillé)
  ; `mode` prime. `api.py` stocke désormais `etapes` = `"modification"` et
  `etapes_detaillees` = `"detaille"`. `coups_rates.py` est épinglé à
  `"condense"` (base historique de `nb_etapes`/`categorie`, inchangée).
- **Repères d'origine (front-end, `jeu.js`/`jeu.css`)** : à chaque étape, pour
  chaque tuile nommée qui vient de changer de place (cadre→plateau quand une
  combinaison se forme/complète, plateau→cadre quand une combinaison est
  défaite), un **couple de pastilles de même couleur** — un bandeau « Départ »
  dans la zone quittée (`.bandeau-departs`/`.chip-depart`) et une pastille
  « arrivée » en coin de la tuile à sa nouvelle place (`.pastille-arrivee`).
  Calculés en JS par diff avec l'étape précédente (`calculerReperesOrigine`).
  **Limite connue (signalée comme prévu par l'issue)** : une vraie flèche
  reliant les deux points n'est pas réalisable proprement dans la mise en page
  actuelle (cadre et plateau sont deux zones séparées, re-rendues à chaque
  étape), d'où le repli par pastilles explicitement prévu.
- **Bascule Avant/Après corrigée** (`rendreComparaisonPasAPas`) :
  - **5a — combinaison inchangée** : comparaison par CONTENU VISIBLE (multiset
    d'aspects, identifiants ignorés — `signatureAspectCombo` /
    `indexCombinaisonsModifiees`, même principe que
    `_relabeler_tuiles_indiscernables`) plutôt que par ids. Une combinaison
    identique avant/après n'est plus entourée de bleu. Les repères de tuile
    (vert/orange) ne sont posés que DANS une combinaison mise en évidence.
  - **5b — vert/orange plus visibles** : dans l'overlay les tuiles ne portent
    pas `.tapis-manipulable`, donc les liserés du vrai tapis ne s'appliquaient
    pas (repères quasi invisibles). Règles dédiées `.carte-pas-a-pas .tuile-jeu.
    ce-tour`/`.deplacee-tapis` : contour épais + halo + voile teinté (inset),
    lisibles sur n'importe quelle couleur de tuile et sur les deux thèmes.
  - **5c — légende illustrée** (`construireLegendePasAPas`) : un vrai exemple
    DANS chaque repère — UNE mini-tuile dans le repère vert et orange, TROIS
    côte à côte dans le repère bleu (`.legende-combi-illustree`), pour que la
    forme (une tuile vs une combinaison) se comprenne sans lire le texte.
- **Tests** : `tests/test_description_coup.py` (section « une modification » :
  défaite en une étape, sortie explicite vers le cadre, Clara entre condensé et
  détaillé, invariants sur les gros coups réels, coup court inchangé,
  rétrocompat `condense`) ; `tests/test_playwright_pas_a_pas.py` (repères
  d'origine départ/arrivée présents quand une tuile bouge et absents au
  « Départ », combinaison inchangée non surlignée, légende illustrée) ;
  `tests/test_condense_solveur.py` et `coups_rates` épinglés à `mode="condense"`
  (comportement inchangé).

