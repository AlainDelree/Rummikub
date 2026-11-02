# Relance une série de scripts/matrice_strategies.py après une coupure de
# courant, un Ctrl+C ou un redémarrage de la machine (issue #228, point 5).
#
# Ne rejoue RIEN de déjà écrit : matrice_strategies.py reprend tout seul à
# la dernière donne complète déjà écrite (voir CONTEXTE.md §13) — ce
# lanceur se contente de relancer EXACTEMENT la même commande sur le MÊME
# --dossier. Il peut donc être appelé sans risque autant de fois que
# nécessaire (manuellement, ou via une tâche planifiée au démarrage de
# Windows — voir CONTEXTE.md §13 pour la commande schtasks, à mettre en
# place par Alain avec Claude, PAS par cet agent).
#
# Installation :
#   1. Copier ce fichier à un emplacement fixe, p. ex. :
#        C:\rummikub\lancer_matrice.ps1
#   2. Renseigner les deux variables ci-dessous (dépôt du jeu, dossier de
#      la série — HORS du dépôt).
#   3. Adapter la ligne de commande à la série réellement lancée (mêmes
#      --niveau-a/--niveau-b/--donnes/--seed/--plan/--budget-solveur que la
#      première fois : matrice_strategies.py refuse de mélanger deux
#      définitions de série dans le même --dossier).
#
# Usage manuel :
#   powershell -ExecutionPolicy Bypass -File C:\rummikub\lancer_matrice.ps1

$Depot   = "C:\chemin\vers\Rummikub"
$Dossier = "D:\mesures\matrice_strategies_228"

Set-Location $Depot
& python scripts\matrice_strategies.py `
    --dossier $Dossier `
    --niveau-a "Expert" --niveau-b "Champion du Monde" `
    --donnes 300 --seed 7 --plan ablation `
    --budget-solveur 4.0

exit $LASTEXITCODE
