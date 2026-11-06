# Issue #242 — Écriture d'un README pour le dépôt public

## Contexte

Le dépôt est public mais n'avait pas de README. L'audit de
Diagnostique_Programme le signalait comme un confort, pas comme un défaut de
règle. Cette issue ajoute un `README.md` court destiné à deux lecteurs :
quelqu'un qui veut seulement jouer, et quelqu'un qui veut lire ou modifier le
code.

## Modifications

- **`README.md`** (nouveau, à la racine) — présentation du jeu, fonctionnalités
  vérifiées dans le code (adversaires, niveaux, réglage du nombre de manches,
  solveur Expert HiGHS, sauvegarde des parties), instructions pour jouer
  (installeur Windows via la page Releases, lancement depuis les sources),
  instructions pour développer (dépendances épinglées, lancement des tests,
  organisation du dépôt), construction de l'installeur Windows (renvoi vers
  `CONTEXTE.md`), confidentialité des données locales du joueur, et renvois
  vers `CONTEXTE.md` / `CHANGELOG.md`.
- Aucune mention de licence, aucune capture d'écran, aucun lien externe hors
  des adresses du dépôt, aucune donnée personnelle de l'auteur, aucun badge —
  conformément à la demande.

## Points volontairement laissés de côté

- Les prérequis système Linux pour pywebview (bibliothèque GTK/Qt) ne sont
  documentés nulle part dans le dépôt : non mentionnés, faute de pouvoir les
  vérifier.
- Le journal JSON optionnel des parties (`persistance/journal.py`,
  `data/logs_parties/`) existe mais est un outil de débogage désactivé par
  défaut (`LOG_PARTIES = False`) : seule la sauvegarde des parties (visible et
  active par défaut) est présentée comme fonctionnalité du jeu ; le journal
  est mentionné uniquement dans la section « Données personnelles » (chemin
  non versionné), pas comme fonctionnalité.
- Aucune version minimale/maximale de Python autre que 3.12 n'est affirmée :
  le dépôt (`CONTEXTE.md`) ne documente que « Python 3.12 », sans bornes.
