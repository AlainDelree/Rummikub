# Changelog — issue #161

- doc(contexte) : ajout d'une section §7 « Vérification empirique d'un
  comportement front-end » à `CONTEXTE.md` — interdiction de lancer
  l'application pywebview réelle (`main.py`) ou un navigateur piloté sur
  l'application réelle pour vérifier un comportement front-end ; méthode
  imposée : charger `jeu.html`/`accueil.html` directement via Playwright
  avec un mock de `window.pywebview.api`, et un état de partie construit
  via le moteur réel (`creer_partie`, etc.) si besoin plutôt qu'un DOM vide.
