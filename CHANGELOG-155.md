# Issue #155 — Suite #140 : le dé-zoom auto écrase un choix manuel à chaque tour, et se déclenche trop tôt

## Contexte
Après la fusion de #140 (qui avait corrigé la pollution de `localStorage` faisant démarrer une
nouvelle partie déjà dézoomée, et un chevauchement visuel sur petite fenêtre), Alain a constaté
deux problèmes persistants à l'intérieur d'une MÊME partie, une fois le tapis arrivé à plusieurs
lignes :

1. `autoZoomSiTapisDeborde()` est réévaluée à chaque tour et force systématiquement le dé-zoom dès
   que le tapis déborde à 100%, même après un clic manuel sur "100%" au tour précédent — ce choix
   ne « tenait » qu'un seul tour avant d'être écrasé par l'automatisme au tour suivant.
2. Le seuil de déclenchement restait trop précoce : le dé-zoom se déclenchait alors qu'il restait
   encore visiblement environ la moitié de l'espace du tapis libre à l'écran.

## Correctifs (`jeu.js`)

### 1. Choix manuel = main définitivement laissée au joueur pour la partie en cours
Nouvelle variable `zoomModifieManuellementCettePartie` (propre à la partie en cours, PAS un
réglage persisté comme `dezoomAutoActif`/#135 — une simple variable JS, naturellement remise à
`false` à chaque chargement de `jeu.html`, donc à chaque nouvelle partie ou reprise, mais qui
survit à un changement de manche au sein de la même partie puisque `onNouvelleManche` ne recharge
pas la page). Elle passe à `true` dès le premier clic du joueur sur un bouton de zoom
(`brancherZoomTapis`) — la restauration du niveau mémorisé au chargement de la page ne compte pas
comme un clic manuel. `autoZoomSiTapisDeborde()` retourne immédiatement sans rien modifier dès que
ce drapeau est à `true`, quel que soit l'état de débordement des tours suivants.

Tant que le joueur n'a jamais touché au zoom lui-même, le comportement d'avant cette issue est
inchangé : l'automatisme continue de s'appliquer normalement à chaque tour (y compris une
progression 100% → 75% → 50% sur plusieurs tours successifs si le tapis continue de déborder).

### 2. Marge de tolérance avant de considérer que le tapis « déborde »
`autoZoomSiTapisDeborde()` comparait `scroll.scrollHeight` à `scroll.clientHeight` sans aucune
marge : un dépassement d'un seul pixel déclenchait un cran complet de dé-zoom. Ajout d'une marge
verticale de tolérance avant de déclencher : `MARGE_VERTICALE_PX = 66 * zoomActuel` (≈ hauteur
d'une tuile à l'échelle courante, 56px, + l'écart de 10px entre lignes posé par `jeu.css`), soit
environ une ligne de tuiles entière de battement. Le dé-zoom ne se déclenche donc plus au premier
pixel de dépassement, mais seulement quand il ne reste plus la place d'une ligne de tuiles
complète — ce qui correspond à l'espace « effectivement insuffisant » visé par la demande.

Aucune valeur numérique exacte n'était fournie par la demande (point confirmé explicitement lors
de la relance : « volontaire, Alain n'a pas de valeur précise à donner »). Le choix d'une ligne de
tuiles complète comme marge est un compromis raisonnable : assez généreux pour ne plus déclencher
alors qu'il reste nettement de la place, sans pour autant laisser déborder plusieurs lignes avant
de réagir. La marge ne s'applique qu'à la hauteur : un débordement horizontal, même minime, coupe
réellement des tuiles au bord du cadre et doit continuer à être corrigé sans délai.

## Vérification
- `node --check jeu.js` : syntaxe valide.
- `pytest` (suite existante, moteur non touché) : 33 passés.
- Playwright sur `jeu.html` chargé directement (état minimal mocké, pas la vraie application —
  conformément à la consigne de la relance qui écarte pywebview/navigateur réel dans cet
  environnement headless), en simulant le débordement par insertion de blocs de la hauteur d'une
  tuile dans `#zone-plateau` et des appels directs à `autoZoomSiTapisDeborde()` :
  - un débordement de 16px (moins d'une ligne) ne déclenche rien (confirme la marge du point 2) ;
  - un gros débordement déclenche 100% → 75%, puis 75% → 50% au tour suivant tant que le joueur
    n'a pas touché au zoom (confirme que l'automatisme n'est pas « figé » après un premier
    dé-zoom, cf. point 1 côté comportement par défaut) ;
  - après un clic manuel sur le bouton "100%", un nouveau tour avec un tapis toujours très
    débordant ne change plus rien : le zoom reste à 100% (confirme le cœur du correctif du
    point 1).
