# Issue #209 — Pas à pas : mettre nettement en avant la ou les tuiles concernées par l'étape en cours (suite de #207)

Dans le pas-à-pas condensé (#207), chaque étape décrit un geste précis
(« Le 11 rouge remplace le 11 jaune dans le groupe de 11 rouge, bleu et
noir »), mais la tuile dont parle la phrase n'avait qu'un liseré discret
(`.tuile-ia-highlight`) : elle se perdait sous le cadre « provisoire » et le
liseré de la combinaison modifiée, qui ressortaient davantage. Le joueur
devait lire la phrase puis chercher la tuile. #209 rend la ou les tuiles
actives **repérables d'un coup d'œil**, nettement plus que le reste.

**Front-end uniquement** (`ui/web/jeu.css`, `ui/web/jeu.js`), plus un petit
correctif de la liste `surbrillance` de l'écran « Les jokers » dans
`moteur/description_coup.py`. **Aucun changement au moteur de jeu, à l'IA, à la
sauvegarde**, ni au texte des étapes, au découpage condensé, au mode
« Détailler », à la bascule Avant / Après ou aux blocs « provisoire ».

## Changements

- **Surbrillance forte `.tuile-pas-active`** (`jeu.css`) : contour épais
  magenta (3 px), double halo pulsé, léger agrandissement (`scale(1.1)`) et
  fond légèrement teinté. Le voile de fond (`::after`) est glissé **sous** le
  chiffre (`.tuile-pas-active > * { z-index: 1 }`), donc la valeur et la
  couleur de la tuile restent parfaitement lisibles, quelle que soit sa
  couleur. L'intensité est **volontairement supérieure** à celle du liseré de
  la combinaison modifiée (`.combi-modifiee`, bleu 2 px) et du cadre
  « provisoire » (`.combi-provisoire`, ambre pointillé) : la hiérarchie saute
  aux yeux — d'abord la tuile active, puis la combinaison touchée, puis le
  reste. Le magenta est absent des couleurs de tuile (rouge/bleu/jaune/noir) et
  des deux liserés, et reste bien visible sur le fond vert du plateau comme sur
  le fond clair du cadre.
- **Aperçu du plateau** (`rendreApercuPlateauPasAPas`, `jeu.js`) : les tuiles
  de `etape.surbrillance` reçoivent `.tuile-pas-active` au lieu de l'ancien
  `.tuile-ia-highlight` discret. `.tuile-ia-highlight` reste utilisée
  uniquement par le rejeu animé (`animerPoseTuiles`), inchangé.
- **Cadre « tuiles à placer »** (`rendreCadrePasAPas`, `jeu.js`) : reçoit
  désormais la liste `surbrillance` et applique la **même** surbrillance forte
  aux tuiles du cadre nommées par l'étape (par-dessus leur pourtour de
  provenance vert/orange) — écran « Départ » (tuiles de la main prêtes à poser)
  et toute tuile qui vient de rejoindre le cadre.
- **Cohérence texte ↔ surbrillance** : à chaque étape, les tuiles mises en
  avant sont exactement celles de `etape.surbrillance` (plateau et cadre
  confondus), ni plus ni moins. Correctif associé dans `description_coup.py` :
  la `surbrillance` de l'écran « Les jokers » inclut maintenant le joker **et**,
  s'il est remplacé, sa ou ses tuiles de remplacement (auparavant seul l'id du
  joker), pour correspondre mot pour mot à la phrase « Le joker … est remplacé
  par … ». Un joker simplement libéré ne met en avant que lui.

## Vérification

- `tests/test_description_coup.py` : `test_joker_recupere_puis_rejoue_ailleurs`
  vérifie la `surbrillance` joker + remplaçant ;
  `test_surbrillance_jokers_libere_sans_remplacant` qu'un joker simplement
  libéré ne met en avant que lui.
- `tests/test_playwright_pas_a_pas.py` (chargé sur `jeu.html`, jamais la vraie
  app pywebview) :
  `test_surbrillance_forte_suit_exactement_les_tuiles_de_chaque_etape` — sur le
  coup de Clara au tour 45 (`tests/donnees/pas_a_pas_clara_tour45.json`), à
  chaque étape les tuiles portant `.tuile-pas-active` (plateau + cadre) sont
  exactement celles de `etape.surbrillance`, et il y en a au moins une ;
  `test_surbrillance_forte_joker_et_remplacant_plateau_et_cadre` — écran
  « Les jokers » du cas Bruno : le joker (sur le plateau) et sa tuile de
  remplacement (dans le cadre) sont tous deux mis en avant.
- Vérifié visuellement par capture Playwright sur `jeu.html` : la tuile active
  ressort nettement, la valeur reste lisible, la hiérarchie tuile > combinaison
  > reste est claire.

`CONTEXTE.md` §12 et nouvelle sous-section §12quinquies mis à jour.
