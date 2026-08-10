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
