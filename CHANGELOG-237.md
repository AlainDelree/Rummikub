# Issue #237 — Déclaration d'audit : ajouter « donnees_personnelles » à .audit.json

## Contexte
Le dépôt étant public, les fichiers contenant des noms de joueurs ou des
réglages personnels (constatés par Diagnostique_Programme) doivent être
déclarés dans `.audit.json` pour l'outil d'audit. Les trois sont déjà
ignorés par git.

## Modifications
- **`.audit.json`** : ajout de la clé `donnees_personnelles` avec les trois
  entrées `config.json`, `data/parties.db`, `data/logs_parties`. Les clés
  `cas` et `roles` restent inchangées.
