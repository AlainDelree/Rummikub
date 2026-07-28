import webview
from pathlib import Path
from rummikub.ui.api import Api

_WEB = Path(__file__).parent / "web"

class ApplicationRummikub:
    def __init__(self):
        self._window = None
        self._etat_jeu = None
        self._config_partie_en_attente = None

    def naviguer_vers_jeu(self, config):
        self._config_partie_en_attente = config
        self._window.load_url(str(_WEB / "jeu.html"))

    def reprendre_jeu(self, etat):
        self._etat_jeu = etat
        self._window.load_url(str(_WEB / "jeu.html"))

    def naviguer_vers_accueil(self):
        self._window.load_url(str(_WEB / "accueil.html"))

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
