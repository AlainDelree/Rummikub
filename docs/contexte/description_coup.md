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

Deux tuiles d'aspect identique (même valeur/couleur, ou deux jokers) qui
échangent leur place — y compris en cycle entre deux combinaisons — ne
produisent ni étape ni changement compté (`_retrait_ajout_bruts`,
`_annuler_par_aspect` ; les cycles « update » entièrement invisibles sont
traités comme un seul bloc via les composantes fortement connexes du
graphe causal). Un repli d'urgence (`ui/api.py:jeu_ia_jouer`) sauvegarde
les deux plateaux dans `RACINE_DATA/erreurs_description/` en cas
d'exception résiduelle, sans jamais bloquer le tour de l'IA. Corrige un
`KeyError` réel (cas Bruno/Expert), couvert par un test de non-régression.
Voir CHANGELOG.md, issue #197.

### 12ter. Accords en français et suppression des pronoms genrés (issue #198)

« Suite » s'accorde au féminin selon la couleur (« suite noire », « suite
bleue » — jamais « groupe », masculin, qui reste invariable). Plus aucune
phrase du résumé (`decrire_coup_ia`) n'utilise de pronom « il »/« elle »
pour désigner le joueur : tournures nominales (« Création d'un groupe de
11. ») ou les tuiles elles-mêmes en sujet (« Le 3 bleu remplace le joker
dans le groupe de 3. »). Voir CHANGELOG.md, issue #198 ; voir aussi
coups_rates_bilan.md §11quater (même issue, filtre par date côté
`coups_rates.py`).

### 12quater. Pas-à-pas condensé, taille du coup, bascule Avant/Après (issue #207)

`etapes_coup_ia(..., mode="condense")` regroupe les gestes par combinaison
(une étape par combinaison créée/complétée, défaites invisibles) — **ce
mode n'est PLUS affiché par défaut depuis #214** (voir 12sexies, qui l'a
remplacé par le mode `"modification"`) ; il reste utilisé uniquement par
`coups_rates.py` pour la continuité des mesures (voir coups_rates_bilan.md
§11quater). `mesurer_coup_ia` calcule la taille d'un coup (petit/moyen/
grand, mêmes seuils que `coups_rates.py` : 1-2/3-5/6+ combinaisons
touchées) et alimente la ligne affichée en tête du pas-à-pas ; la bascule
Avant/Après (plateaux côte à côte, lecture seule) a été introduite ici
puis corrigée par 12sexies. Voir CHANGELOG.md, issue #207.

### 12quinquies. Surbrillance forte de la tuile active (issue #209)

La ou les tuiles concernées par l'étape courante du pas-à-pas portent un
contour magenta épais + halo pulsé (`.tuile-pas-active`), nettement plus
marqué que `.combi-modifiee`/`.combi-provisoire`, appliqué aussi bien sur
le plateau que dans le cadre « tuiles à placer » — y compris à l'écran
« Les jokers » (joker ET sa tuile de remplacement). Voir CHANGELOG.md,
issue #209.

### 12sexies. Découpage « une étape = une modification », repères d'origine, bascule Avant/Après corrigée (issue #214, suite de #207)

Le mode **affiché par défaut** du pas-à-pas est désormais `"modification"`
(`mode` ∈ {`"modification"` (défaut), `"detaille"`, `"condense"` — ce
dernier réservé à `coups_rates.py` et à la non-régression, voir 12quater} ;
l'ancien booléen `condense` reste accepté, `mode` prime) : chaque étape
porte sur UNE SEULE combinaison, avec une étape dédiée pour « défaire »
(toutes les tuiles réelles rejoignent le cadre d'un coup, puis la
combinaison disparaît). Des repères visuels (pastilles Départ/Arrivée de
même couleur) indiquent l'origine et la destination de chaque tuile
déplacée — **limite connue** : pas de vraie flèche reliant les deux points
(cadre et plateau sont deux zones séparées, re-rendues à chaque étape). La
bascule Avant/Après (12quater) est corrigée pour comparer les combinaisons
par CONTENU VISIBLE (aspect, identifiants ignorés) plutôt que par
identifiant, pour des liserés vert/orange plus visibles dans l'overlay, et
pour une légende illustrée par de vraies mini-tuiles. Voir CHANGELOG.md,
issue #214.
