# Issue #239 — Déclaration d'audit : ajouter l'exception ARC-002 (api.py) à .audit.json

## Contexte
Le projet Diagnostique_Programme a signalé un accès à la persistance depuis
`src/rummikub/ui/api.py`, qui enfreint en apparence la règle ARC-002 (aucun
accès aux données dans la couche interface). Ce fichier est le pont `js_api`
de pywebview : il joue le rôle de contrôleur et accède volontairement à la
persistance. C'est accepté tant qu'il reste le seul fichier de
`src/rummikub/ui` à le faire.

## Modifications
- **`.audit.json`** : ajout de la clé `exceptions` (liste) avec une entrée
  `{ "regle": "ARC-002", "raison": "..." }` justifiant le cas d'`api.py`.
  Les clés `cas`, `roles` et `donnees_personnelles` restent inchangées.
