# Issue #140 — Suite #135 : seuil de dé-zoom revérifié dans la page réelle complète

## Contexte
#135 avait mesuré le seuil de débordement du tapis (`#zone-plateau-scroll`) en chargeant
`jeu.html` isolément dans Playwright, et conclu qu'il n'y avait pas de régression. En jeu réel
(fenêtre pywebview maximisée, page complète avec en-tête, chevalet, zones de pose), Alain
observait un dé-zoom (100%→75%) toujours trop précoce, alors qu'il restait visiblement de la
place à l'écran.

## Investigation (Playwright, page réelle complète via un état de partie généré par le vrai
moteur — joueurs, chevalet, historique peuplés comme dans l'appli, pas un harnais minimal)

**Deux causes distinctes trouvées, indépendantes de la CSS mesurée par #135 :**

1. **`#zone-plateau-scroll` avait une hauteur figée (`max-height: 330px`, #128) au lieu d'utiliser
   l'espace réellement disponible.** Sur une fenêtre pywebview maximisée (ex. laptop 1366×768),
   la bande sous le tapis (zone de pose + résultat) ne prend qu'environ 120px, laissant ~400px
   disponibles à `#zone-plateau-wrap` — mais la hauteur figée à 330px plafonnait artificiellement
   le tapis bien en-dessous, gaspillant ~90-115px d'espace pourtant visible et vide à l'écran
   (exactement ce qu'Alain rapportait). À l'inverse, sur une petite fenêtre (ex. 900×600), le
   budget réellement disponible pouvait descendre sous 330px : comme `#zone-plateau-wrap` est
   compressible (`flex-shrink`) mais que `#zone-plateau-scroll` gardait son `max-height` fixe
   indépendant de son parent compressé, le tapis pouvait effectivement s'afficher sur 330px alors
   que son conteneur n'en avait que ~255 de libres — chevauchant visuellement la zone de pose
   juste en-dessous (vérifié par capture d'écran, voir rapport).

2. **Le niveau de zoom déclenché AUTOMATIQUEMENT par débordement était mémorisé dans le même
   `localStorage` que le choix manuel de l'utilisateur**, et relu comme point de départ à chaque
   chargement de `jeu.html`. Comme ce stockage persiste réellement entre les parties dans l'appli
   pywebview (contrairement à un test Playwright isolé, qui repart toujours d'un stockage vide à
   chaque exécution), un dé-zoom automatique survenu une seule fois dans une partie passée restait
   collé indéfiniment : **toute nouvelle partie démarrait déjà zoomée à 75%, dès la toute première
   tuile posée**, donnant l'impression d'un dé-zoom systématiquement prématuré — un effet que la
   méthodologie de #135 (page isolée, stockage toujours vierge) ne pouvait structurellement pas
   révéler.

Mesure du seuil (nombre de combinaisons de 3 tuiles posées avant le premier dé-zoom 100%→75%),
avec un état de partie réaliste (3 joueurs, chevalet de 14 tuiles, historique) sur les tailles de
fenêtre couvertes par l'appli :

| Fenêtre                    | Seuil AVANT (page réelle) | Seuil APRÈS |
|-----------------------------|:---:|:---:|
| 900×600 (taille mini)       | 7  | 5\* |
| 1024×600                    | 10 | 7\* |
| 1100×650                    | 10 | 10  |
| 1100×750 (défaut)           | 10 | 13  |
| 1366×768 (laptop courant)   | 13 | 17  |

\* Sur les deux plus petites tailles, le seuil mesuré baisse légèrement — mais le seuil « avant »
était artificiellement gonflé par le chevauchement décrit au point 1 (le tapis débordait déjà
visuellement sur la zone de pose avant même que `scrollHeight > clientHeight` ne soit détecté).
Le nouveau seuil, plus bas mais honnête, correspond à l'espace réellement disponible sans
chevauchement. Sur les tailles réalistes (1100×750 et plus, dont le format laptop 1366×768 visé
par la tâche), le seuil progresse de +30 à +45 %.

## Correctifs

- `jeu.css` (`#zone-plateau-wrap`, `#zone-plateau-scroll`) : remplace la hauteur figée
  (`max-height: 330px`) par `flex: 1 1 auto` + `height: 100%`, pour que le tapis occupe tout
  l'espace vertical réellement laissé libre par le reste de la mise en page, quelle que soit la
  taille de fenêtre — au lieu d'une constante choisie sans rapport avec la fenêtre réelle de
  l'appli. Supprime au passage le chevauchement visuel avec la zone de pose sur petite fenêtre.
- `jeu.js` (`autoZoomSiTapisDeborde`) : le dé-zoom déclenché automatiquement n'est plus écrit dans
  `localStorage` (seul un clic manuel sur un bouton de zoom reste mémorisé comme préférence
  durable). Le niveau automatique continue de s'appliquer visuellement pour la partie en cours,
  mais ne contamine plus le point de départ des parties futures.
- `jeu.js` (`init`) : à chaque chargement de `jeu.html`, si le tapis est vide (nouvelle partie, ou
  reprise avant la première pose), le zoom est explicitement remis à 100% (et la mémoire nettoyée),
  même si une ancienne valeur dézoomée traînait en `localStorage` — ce qui corrige aussi
  immédiatement les parties déjà affectées par le problème, sans attendre un clic manuel de
  l'utilisateur. Dans tous les autres cas (reprise d'une partie avec un tapis déjà rempli), le
  débordement réel est réévalué immédiatement après le premier rendu (`autoZoomSiTapisDeborde()`
  appelé en fin d'`init()`), pour retrouver le bon niveau de zoom dès l'affichage plutôt que
  d'attendre la pose suivante.

## Vérification
Suite pytest existante (25 tests, logique moteur non touchée) : OK. `node --check jeu.js` : OK.
Revérification par Playwright sur la page réelle complète (état de partie généré par le vrai
moteur, pas un harnais minimal) : seuils mesurés ci-dessus, chevauchement visuel disparu (capture
avant/après), et confirmation qu'une nouvelle partie démarre bien à 100% même avec un ancien
`localStorage` pollué à 0.75 par une exécution précédente.
