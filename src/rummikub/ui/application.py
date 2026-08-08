import json
import subprocess
import sys
import webview
from pathlib import Path
from rummikub.ui.api import Api

_WEB = Path(__file__).parent / "web"


def _handler_fermeture_actualise():
    """À la fermeture de Rummikub, si Actualise a déposé un flag de mise à
    jour, retire le flag et lance le bat de mise à jour. Ne doit JAMAIS
    empêcher la fermeture de la fenêtre."""
    _flag = Path(sys.executable).parent / "actualise_update.flag"
    if _flag.exists():
        try:
            _data = json.loads(_flag.read_text(encoding="utf-8"))
            _flag.unlink(missing_ok=True)
            subprocess.Popen([_data["bat"]], shell=True)
        except Exception:
            pass


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

        # Handler de fermeture : déclenche la mise à jour Actualise si un flag
        # a été déposé pendant la session (voir _handler_fermeture_actualise).
        self._window.events.closing += _handler_fermeture_actualise

        def apres_demarrage():
            self._window.maximize()

        # Désactivation ciblée du cache WebKit SANS ouvrir la DevTools.
        # Le mode debug active `enable_developer_extras`, ce qui désactive le
        # cache mémoire/disque de WebKit2GTK — indispensable pour que les
        # modifications CSS/JS soient prises en compte sans vidage manuel.
        # Mais `debug=True` ouvre aussi l'inspecteur au démarrage, inacceptable
        # pour un jeu. On le supprime en forçant OPEN_DEVTOOLS_IN_DEBUG=False :
        # la DevTools n'est jamais affichée tout en gardant le cache désactivé
        # (cf. webview/platforms/gtk.py : `if settings['OPEN_DEVTOOLS_IN_DEBUG']:
        # self.webview.get_inspector().show()`).
        webview.settings['OPEN_DEVTOOLS_IN_DEBUG'] = False
        webview.start(apres_demarrage, debug=True)


def main():
    app = ApplicationRummikub()
    app.run()
