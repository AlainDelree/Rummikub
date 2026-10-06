# Issue #67 — Réglages : « Vitesse de l'ordinateur » déplacée vers l'onglet Général

# Issue #130 — Tri automatique : correction du dysfonctionnement et mémorisation du choix

## Contexte
La case « Tri automatique » (issue #126) était censée insérer chaque tuile
piochée directement à sa place triée dans le chevalet. En test réel, l'effet
ne se produisait pas correctement, et l'état de la case n'était jamais
persisté : il repartait toujours décoché à chaque relance.

## Diagnostic
`insererTrie()` (jeu.js) recherchait la position d'insertion par un simple
balayage linéaire supposant le chevalet **déjà trié**. Or un chevalet n'est
trié que si le joueur a cliqué sur « Trier » : la distribution initiale (et
toute réorg manuelle ultérieure) le laisse dans un ordre quelconque. Sur un
chevalet non trié, le balayage s'arrête dès le premier élément « plus grand »
rencontré en partant du début — une position qui n'a souvent aucun rapport
avec la vraie place triée globale (ex. un 13 rouge pioché atterrissait avant
une tuile bleue placée tôt dans la main, au lieu de rejoindre les autres
tuiles rouges). D'où l'impression que la case n'avait aucun effet.
Par ailleurs, la case n'était reliée à aucun réglage persisté : `reglages.py`
ne connaissait pas de clé `tri_auto`, et `jeu.js` ne faisait que maintenir
une variable JS locale (`triAutoActif`), réinitialisée à `false` à chaque
chargement de l'écran de jeu.

## Corrections
- **Tri** (`jeu.js`, `insererTrie()`) : au lieu d'une recherche de position
  par balayage linéaire, la fonction ajoute la tuile piochée au chevalet
  local puis retrie l'ensemble via `comparerTuiles` (même comparateur que le
  bouton « Trier »). Résultat garanti correct quel que soit l'ordre courant
  du chevalet.
- **Persistance** :
  - `reglages.py` : nouvelle clé `tri_auto` (défaut `False`) dans `DEFAUTS`.
  - `ui/application.py` : `naviguer_vers_jeu()` et `reprendre_jeu()`
    reportent désormais `cfg.get("tri_auto", False)` dans
    `etat_jeu["config"]["tri_auto"]`, selon le même schéma déjà utilisé pour
    `mode_reorg`/`ia_auto`.
  - `jeu.js` :
    - `init()` restaure `triAutoActif` et l'état de la case `#chk-tri-auto`
      depuis `etat.config.tri_auto` au chargement de l'écran de jeu.
    - le gestionnaire `change` de la case appelle désormais
      `window.pywebview.api.sauvegarder_reglages({ tri_auto: ... })` pour
      persister le choix immédiatement dans `config.json`.

## Fichiers touchés
`src/rummikub/reglages.py`, `src/rummikub/ui/application.py`,
`src/rummikub/ui/web/jeu.js`.

## Tests
- `python3 -m pytest` : 25 tests, tous au vert (aucune régression).
- `node --check src/rummikub/ui/web/jeu.js` : OK.
- Script Node ad hoc reproduisant un chevalet non trié + pioche d'un 13
  rouge : confirme que l'ancienne logique plaçait mal la tuile, et que la
  nouvelle la place correctement (regroupée avec les autres tuiles rouges).

## Issue #129 — Suite #128 : pourtour coloré sur extension directe + masquage "Jouer" pendant le jeu auto de l'IA

- **Pourtour du tour en cours (`.ce-tour`) peu visible sur une extension directe d'une combinaison du tapis.**
  Investigation approfondie (tests automatisés Playwright couvrant tous les chemins d'extension :
  zone début/fin/interne, avant/après mise initiale, plusieurs combinaisons) : la classe `.ce-tour`
  est en réalité déjà appliquée correctement par le JS (`jeu.js`) dans tous les cas, y compris
  l'extension directe — ce n'est donc pas un bug de logique. En revanche, une fois la mise initiale
  faite, la tuile du tapis reçoit *aussi* la classe `.tapis-manipulable` (contour pointillé bleu,
  2px, hors-bordure), qui écrase visuellement le pourtour vert de 1px de `.ce-tour` — exactement
  le cas de figure systématique lors d'une extension directe (impossible avant la mise initiale).
  Correction : `.tuile-jeu.ce-tour.tapis-manipulable` reprend désormais la couleur verte pour son
  contour au lieu du bleu, rendant le pourtour du tour en cours incontestable même combiné à l'état
  « manipulable » (`jeu.css`).
- **Bouton « Jouer » de l'IA masqué pendant le jeu automatique.** Quand le réglage "Jouer
  automatiquement le tour de l'ordinateur" (#126) est actif et que c'est au tour de l'IA, le bouton
  manuel `.btn-jouer-ia` n'est plus affiché le temps que le coup automatique se déroule — il
  réapparaît normalement dès que c'est de nouveau au tour d'un joueur humain ou que le réglage est
  désactivé (`jeu.js`, `rafraichirFichesJoueurs`). Supprime le risque de déclenchement concurrent
  identifié dans l'issue.

# Issue #128 — Bouton « Placer » par zone de pose + mise en évidence des tuiles du tour en cours sur le tapis

## Contexte
Jusqu'ici, les tuiles composées dans une zone de pose restaient dans un
espace totalement séparé du tapis jusqu'au clic sur « Jouer », qui les
transférait toutes d'un coup et validait le tour. Il était donc impossible
de combiner les tuiles d'une zone de pose avec celles déjà présentes sur le
tapis (ex. étendre une suite existante) avant la validation définitive.

## Ajouts / changements
- **Bouton « ⬆ Placer » par zone de pose** (`jeu.html`, `jeu.css`,
  `jeu.js` : fonction `placerRangee()`) : transfère immédiatement les tuiles
  de la zone sur le tapis (`plateauLocal`), sans valider le tour — rien n'est
  envoyé au serveur à ce stade, seul « Jouer » le fait. N'apparaît que si la
  zone n'est pas vide (même convention que « Vider »/« Trier »).
- **Pourtour coloré sur le tapis** : les tuiles posées ce tour (via « Placer »,
  une extension de combinaison ou une récupération de joker) portent déjà la
  classe `.ce-tour` (bordure verte) — ce rendu s'applique désormais aussi aux
  tuiles transférées par « Placer ».
- **Réarrangement unifié** (`rafraichirPlateau()`) : une fois la mise initiale
  faite, une tuile du tour en cours se manipule avec EXACTEMENT le même
  mécanisme que les tuiles des tours précédents (clic pour la prendre,
  double-clic, insertion ciblée) — y compris en la combinant avec d'autres
  tuiles du tour en cours ou déjà présentes. Avant la mise initiale (où ce
  mécanisme de réarrangement n'existe pas encore), le comportement précédent
  (reprise directe vers la main) est conservé à l'identique.
- **« Jouer »** reste inchangé : il valide l'ensemble du tapis
  (`plateauLocal` + zones de pose encore non placées), fige les combinaisons
  et retire le pourtour coloré (`tuilesCeTour` est vidé par `reinitTour()`
  après succès).
- **« Annuler »** : vérifié sans changement nécessaire — comme les tuiles
  « Placées » ne vivent que dans l'état local (`plateauLocal`/`travail`)
  jusqu'à « Jouer », `onAnnuler()` les efface déjà intégralement en
  réinitialisant `plateauLocal` depuis l'état serveur (`reinitTour()`).
- **2 zones de pose au lieu de 4** (`jeu.html`, `jeu.css`) : la grille passe
  d'un agencement 2×2 à une seule ligne de 2 colonnes. La hauteur libérée est
  réattribuée au tapis : `#zone-plateau-scroll` passe de 260px à 330px de
  hauteur maximale.

## Validation
- `node --check src/rummikub/ui/web/jeu.js` : OK.
- `python3 -m pytest` : 25 tests, tous au vert (aucune régression — ce
  changement est entièrement côté client, aucun fichier Python modifié).
- Relecture manuelle du flux complet : chevalet → zone de pose → « Placer »
  (tuiles sur le tapis avec pourtour vert) → réarrangement sur le tapis avec
  le mécanisme existant (prise, insertion, combinaison avec d'autres tuiles
  du tour) → « Jouer » (validation, pourtour retiré) ou « Annuler » (retour
  complet à l'état de début de tour, y compris les tuiles déjà « Placées »).

# Issue #127 — Réorganisation des tuiles dans une zone de pose, comme sur le tapis

## Contexte
Le mécanisme d'insertion d'une tuile entre deux tuiles déjà placées existait
déjà dans le code des zones de pose (ajouté aux issues #27 et #31, zones
`.zone-ext-interne` + `insererTuileRangee`), au même titre que sur le tapis.
Mais `selectionnerTuile()` — appelée au clic sur une tuile du chevalet —
rafraîchissait le chevalet et le tapis, sans jamais rafraîchir la zone de
travail. Les zones d'insertion internes des rangées de pose (et les
gestionnaires de clic associés) restaient donc figés dans l'état « aucune
tuile sélectionnée », rendant l'insertion interne invisible et inopérante :
seul un clic sur le fond de la rangée (= ajout systématique en fin) restait
disponible.

## Correction
`src/rummikub/ui/web/jeu.js` — `selectionnerTuile()` appelle désormais aussi
`rafraichirZoneTravail()`, au même titre que `rafraichirChevalet()` et
`rafraichirPlateau()`. Les zones d'insertion (avant la première tuile, entre
deux tuiles, après la dernière) apparaissent donc correctement dès qu'une
tuile du chevalet est sélectionnée, avec le même comportement que sur le
tapis.

## Validation
- `node --check src/rummikub/ui/web/jeu.js` : OK.
- `python3 -m pytest` : 25 tests, tous au vert (aucune régression).
- Relecture manuelle du flux : sélection d'une tuile du chevalet → zones
  `.zone-ext-interne` recréées dans chaque rangée de travail non vide, avec
  les bons gestionnaires de clic (`insererTuileRangee` au lieu de l'ancien
  `reprendreTuileRangee` figé).

# Issue #126 — Ergonomie : jeu automatique de l'IA, tri automatique au pioché, suppression d'un texte inutile

## Contexte
Trois petites améliorations d'ergonomie identifiées en jouant, indépendantes
les unes des autres.

## Ajouts / changements
- **Jeu automatique de l'IA** : nouveau réglage « Jouer automatiquement le
  tour de l'ordinateur » (onglet Général des réglages, clé `ia_auto` dans
  `config.json`). Quand il est actif, dès que c'est le tour d'une IA, son
  coup se déclenche seul après une latence d'environ 1 seconde (pour ne pas
  paraître brusque), sans qu'il faille cliquer sur le bouton « Jouer » de sa
  fiche. Ce bouton manuel reste affiché et fonctionnel (clic possible pendant
  la latence, ou si le réglage est désactivé).
- **Tri automatique à la pioche** : nouvelle case à cocher « Tri automatique »
  à côté du bouton « Trier » du chevalet. Quand elle est active, chaque tuile
  piochée est insérée directement à sa place triée (couleur puis valeur,
  jokers en fin) plutôt qu'ajoutée en fin de chevalet. Le bouton « Trier »
  existant est inchangé et reste utilisable indépendamment de la case.
- **Suppression du texte « Mes tuiles — cliquez, réarrangez »** affiché
  au-dessus du chevalet du joueur : n'apportait rien à l'utilisateur.

## Fichiers touchés
`src/rummikub/reglages.py`, `src/rummikub/ui/application.py`,
`src/rummikub/ui/web/{accueil.html,accueil.js,jeu.html,jeu.css,jeu.js}`.

# Issue #125 — Script headless de simulation de parties IA vs IA

## Contexte
Le moteur de jeu est pur Python, découplé de l'UI pywebview, mais il n'existait
aucun moyen de vérifier qu'une partie complète se déroule sans erreur sans
passer par l'interface (lancement manuel, clics répétés sur « tour IA »).

## Ajout
`scripts/simulation_ia.py` (nouveau) : script headless qui fait s'affronter
2 à 4 IA entre elles sur une ou plusieurs manches complètes, en pilotant
directement `rummikub.moteur` (sans pywebview). La boucle de tour reproduit
exactement la logique de `Api.jeu_ia_jouer` (même traitement du cas « coup IA
invalide » : annulation + pioche de secours), afin que la simulation couvre le
même chemin de code que le jeu réel.

- Options CLI : `--joueurs` (2-4, défaut 4), `--niveaux` (liste explicite par
  joueur, sinon répartition cyclique sur les 5 niveaux), `--manches` (défaut
  1), `--max-tours` (garde-fou anti-blocage par manche, défaut 500), `--seed`
  (reproductibilité), `-v/--verbose` (log de chaque tour).
- Toute exception levée par l'IA, tout coup invalide proposé, toute action IA
  inconnue ou tout blocage (dépassement de `--max-tours` sans fin de manche)
  est journalisé (`logging`) et compté comme anomalie.
- Résumé final sur stdout : manches/tours joués, durée, scores cumulés,
  liste des anomalies. Code de sortie 0 si la partie est saine, 1 sinon.

## Validation
- `python3 -m pytest` : 25 tests, tous au vert (aucune régression).
- Exécutions manuelles de confirmation : 60 parties simulées (2/3/4 joueurs,
  5 niveaux mélangés, seeds 100 à 119, 2 manches chacune) + plusieurs runs
  ciblés (4 IA de niveaux différents, 3 joueurs sur 3 manches, 2 IA Expert
  face à face, mode verbeux) — **aucune anomalie détectée dans tous les cas**.
  Exemple de résumé obtenu :
  ```
  RÉSUMÉ : 3/3 manche(s) jouée(s), 268 tour(s) au total, 0.17s.
  Scores cumulés finaux : {'IA-1 (Débutant)': -387, 'IA-2 (Facile)': -159, 'IA-3 (Intermédiaire)': -286}
  Aucune anomalie détectée.
  ```

# Issue #104 — Zoom automatique quand le tapis déborde après une pose

## Contexte
Quand une combinaison posée dépassait la zone visible du tapis, le joueur ne
s'en rendait pas compte (combinaison hors écran) et devait dézoomer manuellement.

## Modification
`src/rummikub/ui/web/jeu.js` :

- Nouvelle fonction `autoZoomSiTapisDeborde()` (placée après `brancherZoomTapis`).
  Elle mesure le débordement de la zone visible du tapis (`#zone-plateau-scroll` :
  `scrollHeight > clientHeight` ou `scrollWidth > clientWidth`). En cas de
  débordement, elle réduit le zoom d'UN cran en réutilisant la fonction de zoom
  existante `appliquerZoomTapis()` (100 % → 75 % → 50 %), et mémorise le niveau
  dans `localStorage` comme le font les boutons manuels.
  - Les niveaux sont lus depuis les boutons `#zoom-tapis .btn-zoom` (aucune valeur
    codée en dur), donc restent synchronisés avec le HTML.
  - Ne descend jamais sous le niveau minimal (dernier bouton).
  - Ne fait rien si le contenu est déjà entièrement visible.
  - Un seul cran par pose : le joueur garde la main et peut rezoomer librement ;
    l'automatisme ne se redéclenche qu'à la pose suivante.

- Appel de `autoZoomSiTapisDeborde()` après le rafraîchissement du plateau aux
  deux seuls points de pose réelle de tuiles :
  - `onJouer()` (pose humaine validée), après `rafraichirTout()`.
  - `jouerIA()` (pose de l'IA), après le `rafraichirTout()` final. Les cas
    « pioche » / « passe » de l'IA sortent avant ce point (aucune tuile ajoutée),
    donc n'y déclenchent pas de zoom.

## Résultat
- Après une pose faisant déborder le tapis, le zoom se réduit d'un cran.
- Le joueur ajuste ensuite librement ; l'auto-zoom ne se réimpose qu'à la pose
  suivante.
- Le zoom minimal n'est jamais dépassé.
- Tests existants : 25 passés. Syntaxe JS vérifiée (`node --check`).

# CHANGELOG — Issue #113

## Correction rebuild_rummikub.bat : chemin Z:\CCW\rummikub à l'étape 8

- `build/rebuild_rummikub.bat` (étape 8, hors mode `--publier`) : la commande
  `git -C Z:\CCW\rummikub reset --hard origin/master` référençait le lecteur
  réseau `Z:` qui n'existe plus sur le PC fixe physique (échec silencieux).
  Remplacement du chemin par `C:\CCW_Share\CCW\rummikub` (même correctif que
  `rebuild_scrabble.bat`, issue #410).
- Correction également du commentaire stale ligne 349
  (`%ORIGDIR% = Z:\CCW\rummikub` → `%ORIGDIR% = C:\CCW_Share\CCW\rummikub`)
  afin qu'il ne subsiste plus aucune référence à `Z:\CCW` dans le fichier.

## Contexte
Retours de tests sur machine réelle (public âgé) : le terme « IA » est anxiogène.

## Modifications
- `src/rummikub/ui/web/accueil.html` : le paramètre « Vitesse de l'IA » (bloc
  `<select id="rgl-vitesse">`) est déplacé de l'onglet « Règles du jeu »
  (`#panneau-regles`) vers l'onglet « Général » (`#panneau-general`), et son
  label affiché est renommé en « Vitesse de l'ordinateur ».
- `src/rummikub/ui/web/jeu.js` : commentaire mis à jour pour refléter le
  nouveau libellé (« Vitesse de l'ordinateur »).

## Points d'attention
- Les identifiants techniques internes sont conservés inchangés :
  `id="rgl-vitesse"` (DOM) et la clé `vitesse_ia` (config.json, `reglages.py`,
  `application.py`, `accueil.js`, `jeu.js`). Seul le libellé affiché change,
  conformément à la demande.
- Aucun fichier Python modifié : la logique de lecture/écriture du réglage
  (par `id`) reste valide après le déplacement du bloc.

---

# CHANGELOG — Issue #61

## Mise à jour TACHES.md — icône et intégration Actualise

- Déplacé « Icône application (assets/rummikub.ico) » de « À faire » vers
  « Fonctionnalités implémentées » (le fichier existe déjà dans le dépôt).
- Ajouté une note « Intégration Actualise (Issue #59, #60) » dans les
  fonctionnalités implémentées : `rummikub.iss` et `rebuild_rummikub.bat`
  embarquent l'updater autonome, raccourcis pointant vers `Actualise.exe`,
  génération automatique de `config.json`, production de `rummikub.zip`,
  suppression de la section [Run].
- Conservé « Build Windows via CCW » dans « À faire » avec la précision que
  le pipeline d'installation est désormais prêt.
# Issue #93 — Lancement d'Actualise au démarrage de Rummikub

## Contexte
Même refonte architecturale que Scrabble — symétrique. Au démarrage, Rummikub
doit lancer Actualise en arrière-plan s'il est présent sur la machine.

## Modifications
- `main.py` : nouvelle fonction `_lancer_actualise_au_demarrage()`.
  - Si `C:\Actualise\Actualise.exe` existe → le lance en subprocess
    non-bloquant (`subprocess.Popen`) avec l'argument `--config rummikub`.
  - Si absent → retour immédiat, aucun effet.
  - Si le lancement échoue → exception avalée, simple log discret sur
    `stderr`, jamais d'exception propagée.
  - Appelée dans `__main__`, avant `_lancer_actualise_ui_si_flag()` et avant
    l'ouverture de la fenêtre.

## Points d'attention
- Le check `actualise_update.flag` existant (`_lancer_actualise_ui_si_flag()`)
  reste **inchangé** : les deux mécanismes coexistent.
- Chemin Windows codé en dur (`C:\Actualise\Actualise.exe`) conforme à la
  demande de l'issue ; sur Linux le fichier n'existe pas → `return` silencieux,
  le jeu démarre normalement.
- Non-bloquant : `Popen` n'attend pas la fin du processus, le démarrage du jeu
  n'est ni bloqué ni retardé.

---

# Issue #75 — Mode `--publier` dans `rebuild_rummikub.bat` (SHA-256 + version.json automatiques)

## Contexte
Automatiser la publication d'une nouvelle version pour éviter les erreurs
manuelles (numéro de build, calcul du SHA-256, rédaction de `version.json`).
La référence mentionnée (`build/rebuild_actualise.bat` du dépôt
`AlainDelree/Bridge_Agent`, issue #365) n'était pas accessible au moment du
traitement (HTTP 404 : chemin absent de l'arbre `master`) ; l'implémentation
s'appuie donc sur la spécification détaillée de l'issue.

## Modifications
- `build/rebuild_rummikub.bat` :
  - **Analyse d'arguments** (nouveau bloc après `setlocal`) : `--publier`
    (active la publication) et `--build N` (force le numéro de build). Sans
    argument, le comportement historique est strictement inchangé.
  - **Étape 8bis (`--publier` uniquement)**, insérée après l'étape 8 (une fois
    `rummikub.zip` généré) :
    - lecture du build courant depuis `%ORIGDIR%\version.json` via PowerShell
      (`ConvertFrom-Json`), puis `build + 1` ; surchargé par `--build N` ;
    - réécriture de `manifest.json` avec le nouveau numéro et régénération de
      `rummikub.zip` (`Compress-Archive` de `dist\Rummikub\*` + `manifest.json`),
      recopié vers le partage ;
    - calcul du **SHA-256** du zip via `Get-FileHash` (PowerShell), en
      minuscules ;
    - écriture de `version.json` à la racine du clone partagé (`%ORIGDIR%`,
      soit `Z:\CCW\rummikub`) au format `{"build": N, "sha256": "..."}` ;
    - **commit local** de `version.json` (`git -C "%ORIGDIR%" commit -- version.json`).
  - **Étape 9** : en mode `--publier`, le `git reset --hard origin/master` du
    clone partagé est **désactivé** afin de préserver le commit `version.json`
    fraîchement créé (il serait sinon effacé). Comportement normal inchangé
    hors `--publier`.
  - **Fin de script** : en mode `--publier`, rappel explicite des étapes
    restées **manuelles** — `git push` puis création de la Release GitHub (tag
    `vN`) avec `Rummikub-Setup.exe` et `rummikub.zip` en pièces jointes.

## Points d'attention
- **Jamais de `git push` ni de `gh release create`** dans le script,
  conformément à l'issue et aux consignes du bridge : seul un commit local est
  réalisé.
- Le `reset --hard` de l'étape 9 aurait supprimé le commit `version.json` en
  mode publication : il est donc explicitement contourné dans ce mode. En mode
  normal (sans `--publier`), aucun commit n'est fait et le reset garde son
  rôle de nettoyage habituel.
- `--build N` fixe le build à **N** exactement (pas `N+1`) ; sans lui, le build
  vaut `version.json.build + 1`.
- Script Windows (`.bat`) : non exécutable/validable sous Linux ; revue
  statique de la syntaxe batch effectuée (labels, blocs `if`/parenthèses,
  échappements `^( ^)`, expansion différée `!VAR!`).
