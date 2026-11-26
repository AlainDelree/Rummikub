# Issue #271 — Suppression entière du système de notification ntfy

## Contexte

Le projet notifiait Alain (fin de tâche, build, publication) via un message
envoyé sur un topic public d'un service de notification externe. Ce système
était totalement abandonné côté Alain et constituait la dernière faille
ouverte d'un audit de sécurité : le nom du topic était écrit en clair dans
`installeur/rummikub.iss`, fichier versionné d'un dépôt public, donc lisible
de tous. Décision : supprimer le système plutôt que de changer de topic.

## Recensement

Recherche exhaustive dans tout le dépôt (code Python de `src`, `scripts`,
`tests`, `main.py` ; scripts de build/publication `build/rebuild_rummikub.bat` ;
`installeur/rummikub.iss` ; fichiers de configuration ; `README.md` ;
`docs/contexte/` ; `CONTEXTE.md`) : aucune trace de code Python, de script de
build/publication ni de documentation de domaine n'utilisait ce système. La
seule trace trouvée dans l'ensemble du dépôt était une valeur de topic écrite
en clair dans `installeur/rummikub.iss`, dans le champ `topic_ntfy` du JSON
`config_rummikub.json` généré par l'installeur (section `[Code]`, procédure
`CreerConfigRummikub`). Rien d'autre dans le dépôt n'exploitait ce champ — pas
de code Rummikub qui l'aurait lu ou utilisé (sa consommation, si elle
existait, se faisait entièrement hors de ce dépôt).

Les deux seules autres occurrences du mot « notification »/« notifi » dans le
dépôt (`docs/contexte/solveur_verification_exacte.md`, ligne sur la commande
manuelle de mesure, et `THIRD_PARTY_LICENSES.txt`) sont sans rapport : la
première décrit l'usage de l'utilitaire de bureau Linux `notify-send` pour
prévenir Alain localement à la fin d'une commande manuelle (aucun topic,
aucun service externe) ; la seconde est un terme de licence tiers. Les deux
laissées en place.

## 1. `installeur/rummikub.iss`

Retiré le champ `topic_ntfy` du JSON `config_rummikub.json` généré par
`CreerConfigRummikub` (ligne contenant l'ancien topic en clair), et la
virgule devenue superflue sur le champ `icone` précédent. Aucun autre
changement : le reste du fichier (génération de l'installeur, Actualise,
désinstallation) est inchangé.

## Points laissés pour décision

Aucun. Le recensement n'a trouvé aucune autre trace à retirer, partagée ou
non avec un autre usage.

## Documentation

`docs/contexte/architecture.md`, `docs/contexte/linter_securite.md` et
`docs/contexte/tests_frontend.md` ne mentionnaient déjà nulle part ce
système : rien à mettre à jour. `CONTEXTE.md` ne le mentionnait pas non
plus : non modifié.

## Vérifications

- Recherche finale (`grep -ri ntfy`) sur tout le dépôt hors `CHANGELOG*.md` :
  aucune occurrence.
- `ruff check --select S main.py src` : tous les contrôles passent.
- Suite de tests complète (`pytest`, premier plan, `timeout 900`) :
  **547 passed, 13 skipped** en 130,6 s. Aucun test ne portait sur ce
  système de notification : aucun test retiré, aucune baisse du nombre de
  tests réussis.

## Rappel pour Alain

L'ancien topic reste visible dans l'historique git public de ce dépôt
(commits antérieurs à cette issue). Le système étant abandonné, il n'y a
rien de plus à faire côté Rummikub — sauf si ce topic est encore utilisé
ailleurs (Bridge_Agent, Actualise), ce qui est hors du périmètre de cette
issue.
