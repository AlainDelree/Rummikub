# assets/

Ressources statiques du projet Rummikub utilisées au moment du *build*.

## Icône de l'application

Pour donner une icône personnalisée à l'exécutable généré par PyInstaller,
placez ici un fichier :

    assets/rummikub.ico

- Format **`.ico`** (Windows accepte plusieurs résolutions dans un même
  fichier : 16, 32, 48, 256 px).
- `rummikub.spec` détecte automatiquement ce fichier : s'il est présent, il
  est passé au paramètre `icon` de l'`EXE` ; s'il est absent, le build se
  fait sans icône personnalisée (aucune erreur).

Aucune icône n'est fournie par défaut : le dépôt reste léger et le build
fonctionne tel quel.
