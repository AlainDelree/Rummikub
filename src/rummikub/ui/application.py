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
        from rummikub import reglages as Reglages
        self.etat_jeu = creer_partie(config["joueurs"], config["regles"])
        # Mémorise la vitesse IA (utile côté JS, non gérée par le moteur).
        self.etat_jeu["config"]["vitesse_ia"] = \
            config.get("regles", {}).get("vitesse_ia", "Normale")
        # Mode de réorganisation du chevalet (préférence UI, lue depuis config.json).
        self.etat_jeu["config"]["mode_reorg"] = \
            Reglages.charger().get("mode_reorg", "clic")
        backup_debut_tour(self.etat_jeu)
        self._window.load_url(str(_WEB / "jeu.html"))

    def reprendre_jeu(self, etat):
        from rummikub.moteur.partie import backup_debut_tour
        from rummikub import reglages as Reglages
        self.etat_jeu = etat
        # Reflète toujours la préférence UI courante, même sur partie reprise.
        self.etat_jeu.setdefault("config", {})["mode_reorg"] = \
            Reglages.charger().get("mode_reorg", "clic")
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

        def apres_demarrage():
            self._window.maximize()

        # debug=True désactive le cache disque persistant de WebKit : sans cela,
        # les modifications CSS/JS ne sont pas prises en compte au relancement
        # (pywebview sert les fichiers via HTTP local, mis en cache par WebKit).
        webview.start(apres_demarrage, debug=True)


def main():
    app = ApplicationRummikub()
    app.run()
