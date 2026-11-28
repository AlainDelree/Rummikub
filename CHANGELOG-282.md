## Issue #282 — Installeur Windows : droit users-modify sur le dossier du jeu et sur C:\Actualise

Alignement de `installeur/rummikub.iss` sur le modèle de Scrabble (son issue
#471) : un compte Windows standard doit pouvoir mettre le jeu à jour par
Actualise, pas seulement un compte administrateur.

- Section `[Dirs]` : ajout du dossier d'installation (`{app}`) avec
  `Permissions: users-modify`, et ajout de la même permission à l'entrée
  existante de `C:\Actualise`. Ajout pur : aucun droit existant n'est retiré
  ni réinitialisé. Commentaire ajouté expliquant pourquoi (mise à jour par
  Actualise depuis un compte standard), pourquoi l'ordre de création compte
  (dossiers créés avant la copie des fichiers, qui héritent ainsi du droit),
  et que `C:\Actualise` reste partagé avec Scrabble (droits jamais retirés).
- Commentaire de `PrivilegesRequired=admin` (section `[Setup]`) corrigé : ne
  prétend plus que `C:\Actualise` reste « protégée en écriture pour les
  utilisateurs standards » après l'installation — c'est désormais faux,
  précisément le but du changement. Explique que l'élévation reste requise
  pour créer le dossier à la racine du disque système et y poser les
  permissions, et qu'une fois l'installation faite en administrateur, un
  compte standard peut ensuite écrire dans `{app}` et `C:\Actualise`.
- Aucune autre section touchée : `PrivilegesRequired` reste `admin`, la
  logique de suppression/nettoyage de `C:\Actualise` (partagé, jamais
  supprimé par la désinstallation de Rummikub) est inchangée, le numéro de
  build et la version ne sont pas modifiés ici.

**Point d'attention signalé, non corrigé** : dans le fichier, la section
`[Files]` apparaît textuellement AVANT la section `[Dirs]` (c'était déjà le
cas avant cette issue). Le modèle attendu, d'après l'issue, place les
dossiers avant la copie des fichiers. Inno Setup traite en principe la
création des dossiers du `[Dirs]` avant l'extraction des fichiers du
`[Files]` selon un ordre d'exécution interne indépendant de l'ordre textuel
des sections dans le script — mais ceci n'a pas pu être vérifié par
compilation/exécution réelle (impossible sous Linux). Signalé ici comme
demandé plutôt que réordonné, à confirmer par CCW au build du candidat v15
(vérifier concrètement qu'un compte standard peut bien écrire dans `{app}`
et `C:\Actualise` après une installation réelle).

**Non compilé sous Linux** : Inno Setup (`ISCC.exe`) ne peut pas tourner sur
cette machine Linux. La syntaxe (guillemets, points-virgules, ordre des
paramètres `Name:`/`Permissions:`) a été relue avec soin et suit la forme
déjà utilisée ailleurs dans ce même fichier (`Name: "..."; Permissions:
users-modify`, cohérente avec `Name: "..."; Filename: "..."; ...` des
sections `[Icons]`/`[Files]`). Le dépôt Scrabble (modèle cité par l'issue)
est hors périmètre de cette tâche (lecture seule, hors du worktree) et n'a
donc pas pu être consulté directement pour comparer la syntaxe exacte. La
vérification réelle se fera au build du candidat v15 par CCW.

**Documentation** : `docs/contexte/architecture.md`, `README.md` et
`CONTEXTE.md` ne décrivent à aucun endroit les droits de l'installeur ni la
mise à jour en compte standard — aucune modification nécessaire dans ces
fichiers. `BUILD_WINDOWS_CCW.md` est hors du périmètre strict de ce
worktree (fichier du dépôt bridge_agent, pas de ce dépôt) : il n'a pas pu
être lu ni modifié ici ; à mettre à jour séparément si besoin, par un agent
ayant ce fichier dans son périmètre.

Aucun fichier Python modifié.
