"""API pywebview : méthodes appelables depuis JS via window.pywebview.api.*"""
import json
from rummikub import reglages as Reglages
from rummikub.persistance import stockage as Stockage

class Api:
    def __init__(self, app):
        self._app = app   # référence à ApplicationRummikub

    # --- Accueil ---
    def charger_accueil(self):
        return {"reglages": Reglages.charger(), "parties": Stockage.charger_parties()}

    def sauvegarder_reglages(self, data):
        return Reglages.sauvegarder(data)

    def supprimer_partie(self, pid):
        Stockage.supprimer_partie(pid); return {"ok": True}

    def lancer_nouvelle_partie(self, config):
        # config = {joueurs:[{nom,est_ia,niveau},...], regles:{...}}
        # Crée la partie, navigue vers jeu.html
        # Sera complété issue 2 quand le moteur sera dispo
        self._app.naviguer_vers_jeu(config)
        return {"ok": True}

    def reprendre_partie(self, pid):
        etat = Stockage.charger_partie(pid)
        if not etat:
            return {"ok": False, "erreur": "Partie introuvable"}
        self._app.reprendre_jeu(etat)
        return {"ok": True}

    # --- Jeu (stubs, complétés issues 2 et 3) ---
    def jeu_get_etat(self):            return {}
    def jeu_jouer_coup(self, data):    return {"ok": False, "erreur": "non implémenté"}
    def jeu_piocher(self):             return {"ok": False}
    def jeu_passer(self):              return {"ok": False}
    def jeu_annuler(self):             return {"ok": False}
    def jeu_retour_accueil(self):
        self._app.naviguer_vers_accueil(); return {"ok": True}
