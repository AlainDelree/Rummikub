# Issue #136 — Distinguer tuiles main/tapis + messages d'erreur précis sur une combinaison invalide

## Contexte
En formant un groupe de trois 7 mêlant une tuile de la main et deux tuiles déjà posées ailleurs
sur le tapis, les 3 tuiles recevaient le même pourtour vert (`.ce-tour`, issue #128), sans
distinguer l'origine réelle de chacune. Par ailleurs, un plateau invalide affichait un message
générique ("Combinaison 9 : ni suite ni groupe valide") sans indiquer la raison précise, et la
combinaison fautive n'était pas repérable visuellement sur le tapis.

## Correctif

### 1. Distinction visuelle main vs tapis déplacé (`jeu.js`, `commun.css`)
- Nouvelle classe CSS `.deplacee-tapis` (pourtour bleu `#3b82f6`), appliquée à la place de
  `.ce-tour` (vert) sur les tuiles déjà présentes sur le tapis avant ce tour mais
  déplacées/réorganisées pendant celui-ci — déduit de `tuilesOrigineTapis`, déjà suivi par le
  code existant (issue #103/#133) mais jusqu'ici non reflété visuellement.
- Appliqué à la fois sur le tapis (`rafraichirPlateau`) et dans les zones de pose
  (`rafraichirZoneTravail`).
- Aucune nouvelle règle n'était nécessaire pour l'état « tapis-manipulable » : son contour par
  défaut est déjà bleu, cohérent avec la nouvelle couleur.

### 2. Messages d'erreur précis (`validation.py`)
- `valider_suite`/`valider_groupe` retournent désormais un champ `"raison"` (texte explicite :
  couleurs différentes, jokers adjacents, valeurs hors limites, tuiles non consécutives, couleurs
  en double, plus d'un joker, etc.) en plus de `"valide"`/`"points"`.
- `valider_combinaison` déduit, via `_raison_combinaison_invalide`, la raison la plus pertinente
  selon que les tuiles réelles partagent une couleur commune (tentative de suite), une valeur
  commune (tentative de groupe), les deux (ambigu) ou ni l'une ni l'autre (incompatibles).
- `valider_plateau` utilise cette raison dans chaque entrée de `"erreurs"` au lieu du message
  générique, et renvoie en plus `"combos_invalides"` : la liste des ids de tuiles de chaque
  combinaison fautive (tapis ET zones de pose), pour permettre son repérage visuel côté JS.

### 3. Surlignage de la combinaison fautive (`partie.py`, `api.py`, `jeu.js`, `jeu.css`)
- `jouer_tour` (plateau invalide) et `jeu_verifier_plateau` propagent désormais
  `combos_invalides` au front.
- `jeu.js` convertit ces listes d'ids en signatures (`id1|id2|...`) comparées au contenu courant
  de chaque combinaison du tapis/des zones de pose (`signatureCombo`) : la combinaison fautive
  reçoit la classe `.combi-invalide` (déjà utilisée pour les combinaisons <3 tuiles, bordure rouge
  pulsante) — et perd automatiquement ce surlignage dès que son contenu change (plus besoin de le
  nettoyer explicitement à chaque manipulation).
- Nouvelle règle CSS `.rangee-travail.combi-invalide` (même traitement que sur le tapis) pour les
  combinaisons encore en zone de pose au moment du contrôle.

## Tests
- `pytest` (25 tests, moteur + IA) : tous passent, aucune régression — les appelants existants de
  `valider_suite/valider_groupe/valider_combinaison/valider_plateau` (IA notamment) n'utilisaient
  que les clés `valide`/`points`/`type`, inchangées.
- `node --check jeu.js` et `python -m py_compile` : OK.
