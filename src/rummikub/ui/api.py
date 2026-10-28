"""API pywebview : méthodes appelables depuis JS via window.pywebview.api.*"""
import json
import threading
from rummikub import reglages as Reglages
from rummikub.persistance import stockage as Stockage


class Api:
    # Délai (s) avant une navigation load_url : laisse pywebview livrer la
    # valeur de retour de l'appel API courant AVANT de changer de page.
    _DELAI_NAVIGATION = 0.05

    def __init__(self, app):
        self._app = app   # référence à ApplicationRummikub

    def _tour_est_humain(self, etat):
        """Vrai si c'est le tour du joueur humain dans `etat` (#146) : une
        action de jeu (pioche, pose, passe, annulation) déclenchée côté client
        pendant le tour de l'IA — bouton cliqué dans la fenêtre de latence
        avant son coup auto, ou tout autre décalage client/serveur — doit être
        ignorée ici, pas seulement masquée côté JS, sous peine de faire
        avancer `index_joueur_actuel` deux fois (une fois pour cette action,
        une fois pour le coup IA programmé) et de désynchroniser durablement
        le client, qui ne revoit alors plus jamais la main."""
        idx = etat["index_joueur_actuel"]
        return not etat["joueurs"][idx]["est_ia"]

    def _differer_navigation(self, fn):
        """Exécute une navigation (load_url) hors du thread de l'appel API.

        pywebview livre la valeur de retour d'une méthode via un callback JS
        (window.pywebview._returnValuesCallbacks[...]). Si load_url est appelé
        dans le même thread synchrone, la nouvelle page détruit le contexte JS
        avant que ce callback ne soit invoqué → JavascriptException en boucle.
        On diffère donc la navigation sur un thread minuteur : la méthode API
        retourne d'abord, le callback est livré, puis la page change.
        """
        threading.Timer(self._DELAI_NAVIGATION, fn).start()

    # --- Accueil ---
    def charger_accueil(self):
        return {"reglages": Reglages.charger(), "parties": Stockage.charger_parties()}

    def sauvegarder_reglages(self, data):
        return Reglages.sauvegarder(data)

    def nom_ia_aleatoire(self, exclure=None):
        # exclure = liste de prénoms déjà pris (humain + IA existantes)
        from rummikub.ui.noms_ordinateur import choisir
        return {"nom": choisir(exclure or [])}

    def supprimer_partie(self, pid):
        Stockage.supprimer_partie(pid); return {"ok": True}

    def lancer_nouvelle_partie(self, config):
        # config = {joueurs:[{nom,est_ia,niveau},...], regles:{...}}
        self._differer_navigation(lambda: self._app.naviguer_vers_jeu(config))
        return {"ok": True}

    def reprendre_partie(self, pid):
        etat = Stockage.charger_partie(pid)
        if not etat:
            return {"ok": False, "erreur": "Partie introuvable"}
        self._differer_navigation(lambda: self._app.reprendre_jeu(etat))
        return {"ok": True}

    # --- Jeu ---
    def jeu_get_etat(self):
        return self._app.etat_jeu_serialise()   # dict JSON

    def jeu_jouer_coup(self, data):
        # data = {"ids_tuiles": [...], "nouveau_plateau": [[dict_tuile,...], ...]}
        from rummikub.moteur.partie import jouer_tour, backup_debut_tour
        etat = self._app.etat_jeu
        if not self._tour_est_humain(etat):
            return {"ok": False, "erreur": "Pas votre tour"}
        idx = etat["index_joueur_actuel"]
        # ``data["ids_tuiles"]`` (= ``tuilesCeTour`` côté JS) mélange les
        # tuiles venues de la main ET celles du plateau déplacées ce tour
        # (voir jeu.js:prendreTuileTapis) : capturer la main AVANT le coup
        # (jouer_tour la mute en place) permet de les distinguer dans le
        # journal (issue #201) sans changer le comportement du jeu.
        ids_main_avant = {t["id"] for t in etat["joueurs"][idx]["chevalet"]}
        res = jouer_tour(etat, data["ids_tuiles"], data["nouveau_plateau"])
        if res["ok"]:
            self._app.etat_jeu = res["etat"]
            backup_debut_tour(self._app.etat_jeu)
            from rummikub.persistance.stockage import sauvegarder_partie
            sauvegarder_partie(self._app.etat_jeu)
            from rummikub.persistance.journal import logger_action
            ids_tuiles = set(data["ids_tuiles"])
            nb_posees = len(ids_tuiles & ids_main_avant)
            logger_action(self._app.etat_jeu, "pose", auteur_index=idx,
                         nb_tuiles_posees=nb_posees,
                         nb_tuiles_deplacees=len(ids_tuiles) - nb_posees)
        return res

    def jeu_piocher(self):
        from rummikub.moteur.partie import piocher, backup_debut_tour
        etat = self._app.etat_jeu
        if not self._tour_est_humain(etat):
            return {"ok": False, "erreur": "Pas votre tour"}
        idx = etat["index_joueur_actuel"]
        res = piocher(etat)
        self._app.etat_jeu = res["etat"]
        backup_debut_tour(self._app.etat_jeu)
        from rummikub.persistance.stockage import sauvegarder_partie
        sauvegarder_partie(self._app.etat_jeu)
        from rummikub.persistance.journal import logger_action
        logger_action(self._app.etat_jeu, "pioche", auteur_index=idx)
        return res

    def jeu_passer(self):
        from rummikub.moteur.partie import passer_tour, backup_debut_tour
        etat = self._app.etat_jeu
        if not self._tour_est_humain(etat):
            return {"ok": False, "erreur": "Pas votre tour"}
        idx = etat["index_joueur_actuel"]
        res = passer_tour(etat)
        self._app.etat_jeu = res["etat"]
        backup_debut_tour(self._app.etat_jeu)
        from rummikub.persistance.stockage import sauvegarder_partie
        sauvegarder_partie(self._app.etat_jeu)
        from rummikub.persistance.journal import logger_action
        logger_action(self._app.etat_jeu, "passe", auteur_index=idx)
        return res

    def jeu_annuler(self):
        from rummikub.moteur.partie import annuler_tour
        etat = self._app.etat_jeu
        if not self._tour_est_humain(etat):
            return {"ok": False, "erreur": "Pas votre tour"}
        idx = etat["index_joueur_actuel"]
        annuler_tour(etat)
        from rummikub.persistance.journal import logger_action
        logger_action(etat, "annulation", auteur_index=idx)
        return {"ok": True, "etat": self._app.etat_jeu}

    def jeu_verifier_plateau(self, plateau, ids_ce_tour=None):
        # plateau = [[dict_tuile, ...], ...] — valide chaque combinaison.
        # ids_ce_tour (optionnel) = ids des tuiles posées PENDANT CE TOUR
        # (issue #173) : permet de distinguer, dans points_ce_tour, les
        # points des combinaisons nouvellement posées de ceux du reste du
        # plateau (tours précédents).
        from rummikub.moteur.partie import plateau_depuis_dict
        from rummikub.moteur.validation import valider_plateau, valider_combinaison
        combos = plateau_depuis_dict(plateau or [])
        res = valider_plateau(combos)
        ids_ce_tour = set(ids_ce_tour or [])
        points_total = 0
        points_ce_tour = 0
        for combo in combos:
            r = valider_combinaison(combo)
            if r["valide"]:
                points_total += r["points"]
                if any(t.id in ids_ce_tour for t in combo):
                    points_ce_tour += r["points"]
        return {"valide": res["valide"], "erreurs": res["erreurs"],
                "combos_invalides": res["combos_invalides"],
                "points_total": points_total,
                "points_ce_tour": points_ce_tour}

    def jeu_verifier_combinaison(self, tuiles):
        # tuiles = [dict_tuile, ...]
        from rummikub.moteur.partie import tuile_depuis_dict
        from rummikub.moteur.validation import valider_combinaison
        combo = [tuile_depuis_dict(t) for t in (tuiles or [])]
        return valider_combinaison(combo)

    def jeu_nouvelle_manche(self):
        from rummikub.moteur.partie import nouvelle_manche, backup_debut_tour
        self._app.etat_jeu = nouvelle_manche(self._app.etat_jeu)
        # Point de retour arrière du 1er tour de la nouvelle manche (convention
        # projet, comme jeu_jouer_coup / jeu_piocher / jeu_passer).
        backup_debut_tour(self._app.etat_jeu)
        from rummikub.persistance.stockage import sauvegarder_partie
        sauvegarder_partie(self._app.etat_jeu)
        return {"ok": True, "etat": self._app.etat_jeu}

    def jeu_ia_jouer(self):
        import copy
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
        plateau_avant = copy.deepcopy(etat["plateau"])
        res_ia = jouer_ia(etat, idx)
        coup_joue = False
        type_reel = res_ia["action"]
        if res_ia["action"] == "jouer":
            res = jouer_tour(etat, res_ia["ids_tuiles"],
                             res_ia["nouveau_plateau"])
            if res["ok"]:
                coup_joue = True
                type_reel = "pose"
            else:
                # L'IA a proposé un coup invalide → pioche de secours.
                annuler_tour(etat)
                res = piocher(etat)
                type_reel = "piocher"
        elif res_ia["action"] == "piocher":
            res = piocher(etat)
        else:
            res = passer_tour(etat)
        # Mémorise le TOUT DERNIER coup de l'IA (pose, pioche ou passe) pour
        # permettre son rejeu/affichage à la demande (issue #144, corrigé en
        # #157 : avant ce correctif, seule une pose écrasait ce champ, si bien
        # qu'une pioche/passe laissait figé un ancien rejeu de pose périmé).
        plateau_apres = copy.deepcopy(etat["plateau"])
        etat["dernier_coup_ia"] = {
            "type": type_reel,
            "joueur_index": idx,
            "nom": etat["joueurs"][idx]["nom"],
            "plateau_avant": plateau_avant,
            "plateau_apres": plateau_apres,
        }
        if type_reel == "pose":
            # Résumé écrit + étapes du rejeu pas-à-pas (issue #189, suite de
            # #144/#149) : calculés une seule fois ici, à partir du plateau
            # avant/après déjà disponible, puis simplement affichés côté JS.
            try:
                from rummikub.moteur.description_coup import (
                    decrire_coup_ia, etapes_coup_ia, mesurer_coup_ia)
                resume = decrire_coup_ia(plateau_avant, plateau_apres,
                                          nom=etat["joueurs"][idx]["nom"])
                etat["dernier_coup_ia"]["resume"] = resume["texte"]
                # Pas-à-pas CONDENSÉ par défaut (issue #207) + découpage
                # DÉTAILLÉ (bouton « Détailler »), calculés une seule fois ici.
                etat["dernier_coup_ia"]["etapes"] = etapes_coup_ia(
                    plateau_avant, plateau_apres, condense=True)
                etat["dernier_coup_ia"]["etapes_detaillees"] = etapes_coup_ia(
                    plateau_avant, plateau_apres, condense=False)
                # Mesure d'ampleur du coup : ligne de titre du pas-à-pas et
                # critère d'affichage du bouton « Pas à pas ».
                etat["dernier_coup_ia"]["mesure"] = mesurer_coup_ia(
                    plateau_avant, plateau_apres)
            except Exception as exc:
                # La description du coup est un simple confort d'affichage :
                # une erreur ici ne doit JAMAIS bloquer le tour de l'IA.
                # On garde les deux plateaux pour pouvoir reproduire le cas.
                import json, time
                from rummikub import config
                try:
                    dossier = config.RACINE_DATA / "erreurs_description"
                    dossier.mkdir(parents=True, exist_ok=True)
                    nom_fichier = time.strftime("%Y%m%d_%H%M%S") + ".json"
                    with open(dossier / nom_fichier, "w", encoding="utf-8") as f:
                        json.dump({"erreur": repr(exc),
                                   "plateau_avant": plateau_avant,
                                   "plateau_apres": plateau_apres},
                                  f, ensure_ascii=False)
                except Exception:
                    pass
                etat["dernier_coup_ia"]["resume"] = ""
                etat["dernier_coup_ia"]["etapes"] = []
                etat["dernier_coup_ia"]["etapes_detaillees"] = []
                etat["dernier_coup_ia"]["mesure"] = None
        self._app.etat_jeu = res["etat"]
        backup_debut_tour(self._app.etat_jeu)
        sauvegarder_partie(self._app.etat_jeu)
        from rummikub.persistance.journal import logger_action
        # Canonise le libellé pour qu'il rejoigne celui des coups humains
        # (pose/pioche/passe), nécessaire au bilan par niveau d'IA (#185) :
        # ``type_reel`` reprend ici les libellés internes de l'IA ("piocher",
        # "passer") plutôt que ceux du journal.
        action_journal = {"piocher": "pioche", "passer": "passe"}.get(
            type_reel, type_reel)
        nb_posees = len(res_ia.get("ids_tuiles") or []) if coup_joue else 0
        logger_action(self._app.etat_jeu, action_journal, auteur_index=idx,
                     nb_tuiles_posees=nb_posees)
        return {"ok": True, "etat": self._app.etat_jeu}

    def jeu_retour_accueil(self):
        self._differer_navigation(lambda: self._app.naviguer_vers_accueil())
        return {"ok": True}
