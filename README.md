# Rummikub

Un Rummikub à jouer seul contre l'ordinateur, avec une interface web affichée
dans une fenêtre native via [pywebview](https://pywebview.flowrl.com/).
Fonctionne sous Windows et sous Linux.

## Ce que le jeu propose

- De 1 à 3 adversaires contrôlés par l'ordinateur dans une même partie.
- Cinq niveaux de difficulté, du plus faible au plus fort : **Débutant**,
  **Facile**, **Intermédiaire**, **Avancé**, **Expert**.
- Le nombre de manches du match est réglable avant de lancer la partie (de 1
  à 9).
- Tous les niveaux calculent leur coup par programmation linéaire en nombres
  entiers résolue par HiGHS ; la difficulté est réglée par des limites
  (réarrangements permis, coups oubliés). Repli automatique sur une recherche
  arborescente si ce solveur est indisponible.
- Les parties en cours sont sauvegardées et peuvent être reprises depuis
  l'écran d'accueil.

## Jouer

**Sous Windows**, le plus simple est de télécharger l'installeur de la
dernière version depuis la page
[Releases](https://github.com/AlainDelree/Rummikub/releases) du dépôt, puis
de l'exécuter.

**Depuis les sources** (Windows ou Linux), avec Python 3.12 installé :

```
pip install -r requirements.txt
python main.py
```

## Développer

Le dépôt est organisé ainsi :

- `src/rummikub/` — le code de l'application :
  - `moteur/` — logique de jeu pure (règles, IA, solveurs) ;
  - `persistance/` — sauvegarde des parties et journal ;
  - `ui/` — fenêtre pywebview, API exposée au front-end web.
- `tests/` — suite de tests pytest.
- `scripts/` — outils de mesure et d'analyse (IA, solveurs, parties).
- `installeur/` — script Inno Setup de l'installeur Windows.
- `build/` — script de reconstruction complète du binaire Windows.

Installer les dépendances (versions épinglées dans `requirements.txt`) puis
lancer le jeu :

```
pip install -r requirements.txt
python main.py
```

Lancer la suite de tests (environ 2 minutes) :

```
python -m pytest tests/ -q
```

## Construire l'installeur Windows

Le script `build/rebuild_rummikub.bat` reconstruit l'exécutable avec
PyInstaller puis l'installeur avec Inno Setup. Voir `CONTEXTE.md` pour le
détail des étapes.

## Données personnelles

Les réglages et les parties du joueur restent sur sa machine : `config.json`
(à la racine du dépôt en développement, dans `%APPDATA%\Rummikub` pour le jeu
installé sous Windows), `data/parties.db` et `data/logs_parties/`. Ces fichiers ne sont
pas versionnés dans le dépôt.

## Documentation technique

- `CONTEXTE.md` — architecture, règles du jeu, solveurs.
- `CHANGELOG.md` — historique des modifications.
