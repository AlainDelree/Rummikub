# Issue #67 — Réglages : « Vitesse de l'ordinateur » déplacée vers l'onglet Général

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
