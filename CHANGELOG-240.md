# Issue #240 — Outil de calibration de l'échelle : réglages par niveau en ligne de commande, quatre paires adjacentes, reprise après interruption, verdict 60 à 70 %

## Contexte
Après le retrait de Champion du Monde, l'échelle compte cinq niveaux ; Avancé
et Expert jouent aujourd'hui exactement de la même façon, et Facile n'est pas
plus fort que Débutant. Alain veut calibrer l'échelle PAR LA MESURE (paires
adjacentes jouées les unes contre les autres, réglage ajusté jusqu'à 60–70 %
de victoires pour le niveau du haut), sans modifier le jeu entre deux essais,
et en pouvant lancer la campagne sans surveillance sur un PC lent, avec
reprise après interruption.

## Modifications

- **`scripts/calibrer_echelle.py`** (nouveau) — outil de calibration par
  duels, réglages (perturbation/oubli) donnés en ligne de commande
  (`--reglage "Niveau=perturbation/oubli"`, répétable), **sans jamais
  modifier `moteur/niveaux.py`** (niveaux non précisés = valeurs du jeu).
  Réutilise directement `comparer()` de `comparer_niveaux_ia.py` (garde-fou
  solveur exact, export par partie, budget de temps du solveur), `_rapport_
  duels` et `_limite_temps_ferme` — aucune logique dupliquée.
  - Joue les quatre paires adjacentes par défaut, ou toute paire demandée
    (`--paire Avancé:Expert`, `--paire Débutant:Expert` pour l'étendue
    totale), même nombre de donnes chacune (miroir, graine commune).
  - Mode BALAYAGE (`--candidats "Avancé=inf/0.03,inf/0.06,inf/0.10" --contre
    Expert`) : plusieurs réglages candidats pour un niveau, tous joués contre
    un niveau fixe, tableau classé par proximité de la cible.
  - Reprise après interruption : relancer la même commande sur le même
    `--dossier` reprend à la dernière donne COMPLÈTE (une donne incomplète
    par coupure brutale est détectée et rejouée en entier, jamais de ligne
    JSON corrompue exploitée) ; augmenter `--donnes` prolonge la série sans
    la recommencer ; tout autre changement de réglage est REFUSÉ
    (`reglages.json` du dossier, empreinte comparée à chaque lancement).
  - Commande de statut (`--statut`) : affiche l'avancement sans rien jouer
    ni rien écrire.
  - `--budget-solveur` (budget de temps du solveur par coup, défaut : valeur
    du jeu) et `--processus` (1 ou 2, un `ProcessPoolExecutor` par paire/
    candidat) ; `--limite-temps` FERME (garde-fou externe par sous-processus,
    Linux et Windows, réutilisé de `_limite_temps_ferme.py`).
  - Rapport (`<dossier>/rapport.txt`, réécrit en continu et atomiquement) :
    victoires du niveau le plus fort/parties décidées, taux ± IC 95 %,
    verdict (« dans la cible » / « trop faible » / « trop fort », cible
    réglable via `--cible-basse`/`--cible-haute`), écart en Elo (formule
    habituelle, corrigée de continuité), et, en mode paires, distance Elo
    CUMULÉE de chaque niveau à Expert.

- **`scripts/valider_bas_echelle.py`** (retiré) — devenu redondant : c'était
  un cas particulier figé (Débutant/Facile et Facile/Intermédiaire
  uniquement, override d'un seul niveau, aucune reprise par dossier, aucun
  balayage, aucun calcul d'Elo) du nouvel outil générique, qui couvre
  strictement plus. `tests/test_valider_bas_echelle.py` retiré avec lui.
  Références mises à jour : `_rapport_duels.py`, `_limite_temps_ferme.py`,
  `_verif_solveur_exact.py`, `echelle_niveaux.py` (docstrings),
  `moteur/niveaux.py` (commentaire historique), `tests/
  test_garde_fou_scripts_tous.py` (inventaire des scripts qui font jouer
  l'IA : `valider_bas_echelle.py` retiré, `calibrer_echelle.py` ajouté).

- **`CONTEXTE.md`** (§16) :
  - Documentation de la méthode de calibration DESCENDANTE décidée par Alain
    (Expert fixe, puis Avancé contre Expert, puis Intermédiaire contre
    Avancé figé, etc. — chaque réglage ne dépend que du niveau juste au-
    dessus) et de la mesure préalable de l'étendue totale de l'échelle.
  - Documentation complète de `scripts/calibrer_echelle.py` : format des
    réglages, les trois modes d'usage (mesure, balayage, statut), reprise,
    parallélisme, rapport, avec des commandes prêtes à copier pour le PC fixe
    Windows (`C:\Tournois\venv`) et le ThinkPad (`/usr/bin/python3`).
  - Documentation du comportement EXACT du taux d'oubli (dépendance à la
    taille du chevalet via `taux_oubli_effectif`, coup gagnant jamais
    oublié) et de ses implications pour la calibration (la perturbation
    sépare mieux deux niveaux voisins que l'oubli, dont l'effet s'annule
    mécaniquement en fin de partie).

- **`tests/test_calibrer_echelle.py`** (nouveau) — tests rapides (budget du
  solveur et garde-fou de tours minuscules, au plus 2 donnes réelles) :
  lecture des réglages/candidats/paires valides et invalides, verdict et
  calcul d'Elo sur des chiffres fabriqués (dont la correction de continuité à
  0 %/100 %), distance Elo cumulée (chaîne adjacente, chaîne rompue, arête
  directe préférée), reprise sans rejouer une donne déjà complète, troncature
  d'une donne incomplète simulant une coupure brutale, refus de mélanger deux
  jeux de réglages dans un même dossier (fichier déjà écrit non modifié par
  la tentative refusée), prolongation de `--donnes` autorisée, rapport et
  statut lisibles sans rejouer, options CLI incompatibles.

## Commandes prêtes pour une campagne complète (hors agent)

```
# PC fixe Windows (venv dédié) :
C:\Tournois\venv\Scripts\python.exe scripts\calibrer_echelle.py ^
    --dossier C:\Tournois\calib_avance_240 --candidats "Avancé=inf/0.03,inf/0.06,inf/0.10" ^
    --contre Expert --donnes 60 --budget-solveur 3.0 --processus 2 --limite-temps 7200

# ThinkPad (interpréteur système) :
/usr/bin/python3 scripts/calibrer_echelle.py --dossier /tmp/calib_avance_240 \
    --candidats "Avancé=inf/0.03,inf/0.06,inf/0.10" --contre Expert \
    --donnes 60 --budget-solveur 1.5 --processus 2 --limite-temps 7200

# Statut (lecture seule, sur l'une ou l'autre machine) :
python scripts/calibrer_echelle.py --dossier <même dossier> --statut
```

## Vérifications
- `python3 -m py_compile` sur tous les fichiers Python ajoutés/modifiés : OK.
- Essai réel au premier plan (2 à 4 donnes, budget solveur 0,05–0,1 s,
  garde-fou 15–60 tours) : mode paires, mode balayage à 2 processus, reprise
  (prolongation de 2 à 4 donnes sans rejouer les 2 premières), refus de
  mélanger deux réglages, commande de statut — comportements tous vérifiés
  manuellement en plus des tests automatisés.
- Suite de tests complète (`pytest -q`) : voir le rapport de clôture de
  l'issue.
