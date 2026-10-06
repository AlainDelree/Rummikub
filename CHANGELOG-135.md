# Issue #135 — Seuil de dé-zoom automatique du tapis + réglage pour l'activer/désactiver

## Investigation : #128 a-t-il avancé le seuil de dé-zoom ?
Mesure réelle (Playwright, chargement direct de `jeu.html`/`jeu.css`, remplissage du tapis par
combinaisons de 3 tuiles jusqu'à détection du débordement `scrollHeight > clientHeight` de
`#zone-plateau-scroll`) comparant l'état juste avant #128 (commit `9c0f9b5`) et l'état actuel,
sur toutes les tailles de fenêtre autorisées par l'appli (`min_size=(900,600)` à la taille par
défaut `1100x750`, plus un format laptop `1366x768`) :

| Fenêtre    | Seuil AVANT #128 | Seuil APRÈS #128 |
|------------|:---:|:---:|
| 900×600 (taille mini)  | 7 combos  | 10 combos |
| 1024×600   | 9 combos  | 13 combos |
| 1100×650   | 11 combos | 16 combos |
| 1100×750 (défaut)      | 11 combos | 16 combos |
| 1366×768   | 13 combos | 19 combos |

Dans **toutes** les configurations testées, le seuil de débordement est plus **haut** après #128,
pas plus bas : le passage de `max-height: 260px` à `330px` sur `#zone-plateau-scroll` (plus
d'espace rendu au tapis) l'emporte largement sur la réduction de la zone de pose (4→2 rangées, qui
libère elle aussi de la place). Conclusion : **les changements de hauteur de #128 n'ont pas
dégradé le seuil — ils l'ont amélioré d'environ 30-45 %.** Aucune régression à corriger de ce
côté ; aucun changement de CSS/seuil n'a donc été apporté.

L'explication la plus probable de la perception d'Alain est documentée dans le code depuis #128 :
le bouton « Placer » permet désormais de transférer une zone de pose sur le tapis **avant**
validation du tour (combinaison visible immédiatement, pourtour vert), alors qu'avant #128 ces
tuiles restaient invisibles sur le tapis jusqu'au clic sur « Jouer ». Le tapis peut donc sembler
se remplir — et donc dézoomer — plus vite **au fil d'un même tour**, même si le seuil en pixels
qui déclenche le dé-zoom (évalué uniquement après « Jouer » ou un tour IA, `autoZoomSiTapisDeborde`
n'étant pas appelée depuis `placerRangee`) n'a lui pas changé. Une taille d'écran/fenêtre plus
petite que la machine de référence reste par ailleurs un facteur à part entière (voir tableau
ci-dessus : le seuil absolu chute fortement entre 1366×768 et 900×600, indépendamment de #128).

## Réglage ajouté : dé-zoom automatique activable/désactivable
- `reglages.py` : nouvelle clé persistée `dezoom_auto` (défaut `True`, comportement historique
  inchangé par défaut).
- `accueil.html`/`accueil.js` : nouvelle case dans l'onglet *Général* des réglages, « Dé-zoomer
  automatiquement le tapis quand il déborde », lue/sauvegardée comme les réglages existants
  (`ia_auto`, `mode_reorg`, etc.).
- `application.py` : la préférence est propagée dans `etat_jeu["config"]["dezoom_auto"]` au
  lancement d'une partie et à la reprise d'une partie existante (même mécanisme que `tri_auto`,
  issue #130).
- `jeu.js` : `autoZoomSiTapisDeborde()` ne fait plus rien si le réglage est désactivé
  (`dezoomAutoActif`, initialisé depuis `etat.config.dezoom_auto` à l'ouverture de la partie ;
  absent sur une vieille partie reprise ⇒ traité comme activé, pour ne pas changer le
  comportement des parties en cours).
