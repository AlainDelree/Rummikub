## Issue #131 — Double-clic sur une tuile du tapis → zone de pose active (déjà implémenté)

## Contexte
L'issue #131 demande qu'un double-clic sur une tuile du tapis l'envoie
directement dans la dernière zone de pose sélectionnée, sans clic
intermédiaire, sans toucher au simple clic ni au double-clic déjà existant
sur les tuiles du chevalet/zones de pose.

## Constat
Cette fonctionnalité est déjà intégralement implémentée depuis le commit
`a1fac21` (« Issue #103 : double-clic sur une tuile du tapis → la placer
dans la zone de pose active », 2026-08-10), toujours présent dans
`src/rummikub/ui/web/jeu.js` :

- Détection manuelle du double-clic sur une tuile du tapis (`dernierClicTapis`,
  ligne ~20, listener ligne ~336-348), posée avant tout autre handler de clic
  sur la tuile — même mécanisme que pour le chevalet (`dernierClicChevalet`).
- Au second clic (< 350 ms), `prendreTuileTapis(idxCombo, idxTuile)` (ligne
  ~940) retire la tuile de sa combinaison et la pousse directement dans
  `travail[rangeeActive]`, c'est-à-dire la zone de pose actuellement (ou
  dernièrement) activée via `activerRangee()`.
- Le comportement couvre aussi bien les combinaisons jouées lors de tours
  précédents que les tuiles posées pendant le tour en cours (extension
  issue #128), et n'altère ni le simple clic (toujours fonctionnel en dehors
  de la fenêtre de 350 ms) ni le double-clic du chevalet
  (`poserTuileDirectement`, mécanisme indépendant).

## Conclusion
Aucune modification de code nécessaire : le résultat attendu par l'issue
#131 est déjà couvert par l'implémentation de l'issue #103. Aucun fichier
touché.
