# Issue #220 — Outils de tournoi : critère par duels uniquement, arrêt propre à la limite de temps, résultats partiels lisibles

Trois défauts constatés en #216/#217 sur `scripts/valider_bas_echelle.py` et
`scripts/echelle_niveaux.py` sont corrigés.

## 1. Critère de force : duels uniquement

Retrait du relevé des **tuiles restantes en défaite** (miroir d'un niveau
contre lui-même) et de l'option `--donnes-profil` des deux scripts, avec tout
ce qui en dépendait (`mesurer_tuiles_restantes`, `jouer_profils`,
`NIVEAUX_PROFIL`, affichage dédié, textes d'aide). Ce critère mesurait surtout
la longueur des parties (non comparable à un humain), ne terminait plus
naturellement dès que `perturbation_max >= 1`, et avait consommé tout le
temps imparti des tournois de #216/#217 sans que les duels ne soient jamais
joués. Le seul critère retenu est désormais le **duel entre niveaux voisins**
(même donne jouée deux fois, mains échangées), avec un écart « net » visé
**entre 60 et 75 %** (resserré de 60–80 % dans `echelle_niveaux.py`, constante
partagée `scripts/_rapport_duels.SEUIL_NET_HAUT`).

`scripts/calibrer_niveaux.py` et le relevé de `scripts/profil_joueur.py`
reposent ENCORE sur le critère des tuiles restantes en défaite : ils ne sont
PAS modifiés par cette issue (hors périmètre), signalé dans `CONTEXTE.md` §16.

## 2. Limite de temps réellement ferme

Nouveau module `scripts/_limite_temps_ferme.py` : les deux scripts se relancent
eux-mêmes dans un sous-processus (argument interne `--_worker`) surveillé par
le processus parent. Le sous-processus continue de s'arrêter proprement de
lui-même dès que `--limite-temps` est dépassée (aucune nouvelle donne
lancée) ; si cela ne suffit pas (donne déjà en cours anormalement longue), le
parent **termine** le sous-processus — et l'arbre de processus qu'il aurait
créé — une fois `limite_temps + 10 s` dépassée, sur Linux (groupe de
processus POSIX, `SIGTERM` puis `SIGKILL`) comme sous Windows (`taskkill /PID
<pid> /T /F`, jamais `/IM` par motif de nom). Code de sortie : `0` terminé
normalement, `3` arrêté sur la limite de temps, `1` erreur.

## 3. Résultats partiels toujours lisibles

Chaque paire du fichier `--sortie` affiche, dès que des parties sont
terminées : victoires du niveau le plus fort / parties jouées, taux ± marge,
et donnes terminées / prévues, avec la mention `[partiel]` tant que la paire
n'est pas finie. La fin du fichier indique si le tournoi est allé au bout
(« TERMINÉ NORMALEMENT ») ou s'est arrêté sur la limite de temps (« ARRÊTÉ SUR
LA LIMITE DE TEMPS »), avec la liste des paires incomplètes. L'en-tête indique
le nom de la machine et la version de Python (`scripts/_rapport_duels.
entete_machine`), pour comparer des tournois lancés sur des machines
différentes. `scripts/echelle_niveaux.py` gagne une option `--sortie`
(absente jusqu'ici).

## 4. Vérifications et portée Windows

Le mécanisme de sous-processus (`subprocess.Popen` + `sys.executable`) et
l'arrêt d'arbre de processus sont codés pour les DEUX plateformes dès
l'origine (branches `sys.platform == "win32"` dédiées : groupe de processus +
`taskkill /PID … /T /F` sous Windows, `start_new_session` + `os.killpg` sous
Linux) — aucune partie de ce nouveau code n'est propre à Linux. Rien d'autre,
dans les deux scripts modifiés, ne dépend de l'OS (chemins via `pathlib`,
aucun appel système direct).

## Tests

`tests/test_limite_temps_ferme.py` (nouveau) : relais normal/erreur, relais du
code « limite de temps » déjà atteint, et scénario pathologique (tâche qui ne
se termine jamais) terminée dans un délai borné sans processus résiduel.
`tests/test_rapport_duels.py` (nouveau) : en-tête machine/Python, verdicts
d'écart. `tests/test_valider_bas_echelle.py` et `tests/test_echelle_niveaux.py`
(nouveaux) : `--donnes-profil` n'est plus accepté (code 2), tournoi complet
rapide terminé normalement, limite de temps courte sur un tournoi factice
arrêtée avec résultats partiels lisibles (`[partiel]`, paire incomplète), code
de sortie distinguant terminé/limite de temps, test d'intégration marqué
`@pytest.mark.lent` lançant le script réel en sous-processus. Suite complète
existante (354 tests + 13 sautés, inchangés) toujours au vert.

## Documentation

`CONTEXTE.md` §16 : nouvelle sous-section « Critère de force depuis #220 »
expliquant l'abandon du relevé en auto-partie et le nouveau critère par
duels ; cibles en tuiles restantes de #216 (Débutant ≈ 9, Facile ≈ 7,
Intermédiaire ≈ 4,5) et #217 (Facile 6,0–6,3) marquées OBSOLÈTES sans être
effacées de l'historique ; rappel que `calibrer_niveaux.py` et le relevé de
`profil_joueur.py` reposent encore sur ce critère, et que le profil humain en
tuiles restantes reste seulement indicatif.

## Fichiers touchés

- `scripts/valider_bas_echelle.py`, `scripts/echelle_niveaux.py` — réécrits.
- `scripts/_limite_temps_ferme.py`, `scripts/_rapport_duels.py` — nouveaux
  modules partagés.
- `tests/test_limite_temps_ferme.py`, `tests/test_rapport_duels.py`,
  `tests/test_valider_bas_echelle.py`, `tests/test_echelle_niveaux.py` —
  nouveaux.
- `CONTEXTE.md` §16 — mise à jour.

Ni le solveur, ni `moteur/niveaux.py`, ni le comportement des IA, ni
l'interface n'ont été touchés. La signification de l'option de budget du
solveur (`--budget-solveur`) est inchangée.
