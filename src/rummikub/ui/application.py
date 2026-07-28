import webview
from pathlib import Path
from rummikub.ui.api import Api

_WEB = Path(__file__).parent / "web"


class ApplicationRummikub:
    def __init__(self):
        self._window = None
        self._etat_jeu = None   # dict JSON-sérialisable de la partie en cours

    @property
    def etat_jeu(self):
        return self._etat_jeu

    @etat_jeu.setter
    def etat_jeu(self, val):
        self._etat_jeu = val

    def naviguer_vers_jeu(self, config):
        from rummikub.moteur.partie import creer_partie, backup_debut_tour
        self.etat_jeu = creer_partie(config["joueurs"], config["regles"])
        # Mémorise la vitesse IA (utile côté JS, non gérée par le moteur).
        self.etat_jeu["config"]["vitesse_ia"] = \
            config.get("regles", {}).get("vitesse_ia", "Normale")
        backup_debut_tour(self.etat_jeu)
        self._window.load_url(str(_WEB / "jeu.html"))

    def reprendre_jeu(self, etat):
        from rummikub.moteur.partie import backup_debut_tour
        self.etat_jeu = etat
        backup_debut_tour(self.etat_jeu)
        self._window.load_url(str(_WEB / "jeu.html"))

    def naviguer_vers_accueil(self):
        self._window.load_url(str(_WEB / "accueil.html"))

    def etat_jeu_serialise(self):
        return self.etat_jeu   # déjà dict JSON-sérialisable

    def run(self):
        api = Api(self)
        self._window = webview.create_window(
            "Rummikub",
            str(_WEB / "accueil.html"),
            js_api=api,
            width=1100, height=750,
            min_size=(900, 600),
        )
        webview.start(debug=False)


def main():
    app = ApplicationRummikub()
    app.run()
