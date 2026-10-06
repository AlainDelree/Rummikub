# Issue #143 — Suite #137 : l'échange tuile/joker ne se produisait pas — la tuile se posait à côté du joker qui restait en place

## Contexte
#137 avait modifié `tenterRecupererJoker` pour que le joker libéré par un échange devienne la
tuile sélectionnée (attachée au curseur) plutôt que simplement désélectionné. Mais le test réel
d'Alain montrait que l'échange ne se déclenchait jamais : la tuile posée sur le joker s'insérait
À CÔTÉ de lui (insertion normale), et le joker restait en place. L'issue soupçonnait un défaut
de détection de correspondance pour les jokers ambigus entre plusieurs couleurs restantes (même
défaut que #142 avait corrigé côté blocage d'un remplacement invalide).

## Investigation
La fonction `peutRemplacerJoker`/`valeurJokerDansCombo` (jeu.js) s'est révélée correcte même pour
le cas à deux couleurs manquantes : vérifié par un test Node isolant ces deux fonctions pures sur
le scénario exact de l'issue (groupe 8-noir/8-jaune/joker, tuile 8-bleu ou 8-rouge en main) — les
deux couleurs sont acceptées, un doublon (8-noir) est refusé (#142). La piste de l'issue n'était
donc pas la cause réelle.

**Cause réelle : branche morte dans le dispatcheur de clic de `rafraichirPlateau`.** La
récupération de joker (issue #12, bien avant #137) est déclenchée par une branche
`else if (d.est_joker && tuileSelectionnee !== null && ...)` tout en bas d'une chaîne
`if/else if`. L'issue #47 (« insertion ciblée ») a depuis inséré AVANT cette branche un cas
`else if (modeCible)` qui, sur la combinaison active, attache systématiquement un clic vers
`insererTuileTapis` (insertion à côté) à CHAQUE tuile — y compris un joker — sans jamais vérifier
si la tuile sélectionnée pourrait l'échanger. Or `modeCible` est vrai exactement quand
`tapisManipulable() && une tuile est sélectionnée` — c'est-à-dire précisément la condition
requise pour atteindre la branche de récupération de joker plus bas. Résultat : cette dernière
branche ne pouvait plus jamais s'exécuter pendant le tour du joueur (elle ne devenait accessible
que si `tapisManipulable()` était faux, ce qui exige de ne PAS être son tour — un état où aucun
clic ne devrait de toute façon produire d'effet). Le correctif de #137 avait donc modifié une
fonction (`tenterRecupererJoker`) que le dispatcheur de clic n'appelait plus jamais en pratique
depuis l'ajout de #47 — bug resté invisible car vérifié uniquement par relecture de code et
`node -e`, sans clic réel dans la page.

## Correctif (src/rummikub/ui/web/jeu.js)
Dans la branche `modeCible` / `estActive` de `rafraichirPlateau` : avant d'attacher le clic de
chaque tuile de la combinaison ciblée, on calcule si la tuile cliquée est un joker que la tuile
actuellement sélectionnée (si elle vient bien de la main, via `chevaletLocal`) peut remplacer
(`peutRemplacerJoker(tuileSelDict, valeurJokerDansCombo(combo, idxTuile))`). Si oui, le clic
appelle `tenterRecupererJoker` (échange réel : retrait du joker, insertion de la tuile à sa
place, joker libéré attaché au curseur) au lieu de `insererTuileTapis` (insertion à côté). La
classe CSS `joker-recuperable` (surlignage orange pulsé, déjà définie dans jeu.css depuis #12)
est réutilisée pour signaler visuellement ce joker échangeable.

L'ancienne branche `else if (d.est_joker && ...)`, désormais prouvée inatteignable pendant le
tour du joueur, a été supprimée — elle induisait en erreur sur l'endroit où la logique
s'exécutait réellement (cause de la confusion ayant mené à la clôture erronée de #137).

## Vérification
- `node --check` sur jeu.js : syntaxe OK.
- Script Node isolant `valeurJokerDansCombo`/`peutRemplacerJoker` sur le scénario exact de
  l'issue (groupe de 3 avec joker ambigu entre 2 couleurs) : comportement correct confirmé,
  ce n'était pas la cause.
- `pytest` (suite existante, côté Python, non concernée par ce changement JS) : 25 passés,
  aucune régression.
- Pas de test Playwright/navigateur disponible dans ce worktree pour rejouer le clic réel ;
  la correction a été tracée pas à pas dans le dispatcheur de clic (ordre des branches
  `if/else if`, conditions exactes de `modeCible` vs `tapisManipulable()`) jusqu'à confirmer
  que la nouvelle branche est bien atteinte et appelle `tenterRecupererJoker` dans le scénario
  décrit par Alain.
