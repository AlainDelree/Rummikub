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
        self._app.naviguer_vers_jeu(config)
        return {"ok": True}

    def reprendre_partie(self, pid):
        etat = Stockage.charger_partie(pid)
        if not etat:
            return {"ok": False, "erreur": "Partie introuvable"}
        self._app.reprendre_jeu(etat)
        return {"ok": True}

    # --- Jeu ---
    def jeu_get_etat(self):
        return self._app.etat_jeu_serialise()   # dict JSON

    def jeu_jouer_coup(self, data):
        # data = {"ids_tuiles": [...], "nouveau_plateau": [[dict_tuile,...], ...]}
        from rummikub.moteur.partie import jouer_tour, backup_debut_tour
        etat = self._app.etat_jeu
        res = jouer_tour(etat, data["ids_tuiles"], data["nouveau_plateau"])
        if res["ok"]:
            self._app.etat_jeu = res["etat"]
            backup_debut_tour(self._app.etat_jeu)
            from rummikub.persistance.stockage import sauvegarder_partie
            sauvegarder_partie(self._app.etat_jeu)
        return res

    def jeu_piocher(self):
        from rummikub.moteur.partie import piocher, backup_debut_tour
        res = piocher(self._app.etat_jeu)
        self._app.etat_jeu = res["etat"]
        backup_debut_tour(self._app.etat_jeu)
        from rummikub.persistance.stockage import sauvegarder_partie
        sauvegarder_partie(self._app.etat_jeu)
        return res

    def jeu_passer(self):
        from rummikub.moteur.partie import passer_tour, backup_debut_tour
        res = passer_tour(self._app.etat_jeu)
        self._app.etat_jeu = res["etat"]
        backup_debut_tour(self._app.etat_jeu)
        from rummikub.persistance.stockage import sauvegarder_partie
        sauvegarder_partie(self._app.etat_jeu)
        return res

    def jeu_annuler(self):
        from rummikub.moteur.partie import annuler_tour
        annuler_tour(self._app.etat_jeu)
        return {"ok": True, "etat": self._app.etat_jeu}

    def jeu_verifier_plateau(self, plateau):
        # plateau = [[dict_tuile, ...], ...] — valide chaque combinaison.
        from rummikub.moteur.partie import plateau_depuis_dict
        from rummikub.moteur.validation import valider_plateau, valider_combinaison
        combos = plateau_depuis_dict(plateau or [])
        res = valider_plateau(combos)
        points_total = 0
        for combo in combos:
            r = valider_combinaison(combo)
            if r["valide"]:
                points_total += r["points"]
        return {"valide": res["valide"], "erreurs": res["erreurs"],
                "points_total": points_total}

    def jeu_verifier_combinaison(self, tuiles):
        # tuiles = [dict_tuile, ...]
        from rummikub.moteur.partie import tuile_depuis_dict
        from rummikub.moteur.validation import valider_combinaison
        combo = [tuile_depuis_dict(t) for t in (tuiles or [])]
        return valider_combinaison(combo)

    def jeu_nouvelle_manche(self):
        from rummikub.moteur.partie import nouvelle_manche
        self._app.etat_jeu = nouvelle_manche(self._app.etat_jeu)
        from rummikub.persistance.stockage import sauvegarder_partie
        sauvegarder_partie(self._app.etat_jeu)
        return {"ok": True, "etat": self._app.etat_jeu}

    def jeu_ia_jouer(self):
        from rummikub.moteur.ia import jouer_ia
        from rummikub.moteur.partie import (jouer_tour, piocher, passer_tour,
                                            backup_debut_tour, annuler_tour)
        from rummikub.persistance.stockage import sauvegarder_partie
        etat = self._app.etat_jeu
        if not etat:
            return {"ok": False, "erreur": "Aucune partie en cours"}
        idx = etat["index_joueur_actuel"]
        if not etat["joueurs"][idx]["est_ia"]:
            return {"ok": False, "erreur": "Pas le tour d'une IA"}
        backup_debut_tour(etat)
        res_ia = jouer_ia(etat, idx)
        if res_ia["action"] == "jouer":
            res = jouer_tour(etat, res_ia["ids_tuiles"],
                             res_ia["nouveau_plateau"])
            if not res["ok"]:
                # L'IA a proposé un coup invalide → pioche de secours.
                annuler_tour(etat)
                res = piocher(etat)
        elif res_ia["action"] == "piocher":
            res = piocher(etat)
        else:
            res = passer_tour(etat)
        self._app.etat_jeu = res["etat"]
        backup_debut_tour(self._app.etat_jeu)
        sauvegarder_partie(self._app.etat_jeu)
        return {"ok": True, "etat": self._app.etat_jeu}

    def jeu_retour_accueil(self):
        self._app.naviguer_vers_accueil(); return {"ok": True}
