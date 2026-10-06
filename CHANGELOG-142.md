## Issue #142 — Remplacement d'un joker dans un groupe : vérifier la couleur de la tuile de remplacement

- `jeu.js` (`valeurJokerDansCombo`, `peutRemplacerJoker`) : pour un groupe, refuse désormais le remplacement d'un joker par une tuile dont la couleur est déjà présente parmi les autres tuiles du groupe (même garde-fou que pour une suite, qui vérifiait déjà la couleur). Avant ce correctif, un groupe 7-rouge / 7-bleu / joker pouvait voir son joker remplacé par un 7-rouge pris en main, créant un groupe invalide (couleur dupliquée).
