"""Déroulement d'une partie Rummikub : état, tours, pioche, fin de manche."""

import copy
import uuid

from rummikub import config
from rummikub.moteur.tuiles import (
    Tuile, creer_sac, distribuer, tuile_depuis_dict,
)
from rummikub.moteur.validation import valider_plateau, valider_combinaison
from rummikub.moteur.score import (
    calculer_scores_manche, trouver_gagnant_manche, trouver_gagnant_match,
    egalite_sommet_match,
)


# --------------------------------------------------------------------------- #
# Sérialisation Tuile <-> dict
# --------------------------------------------------------------------------- #
# ``tuile_depuis_dict`` est défini dans ``tuiles`` (foyer naturel de ``Tuile``)
# et ré-exporté ici pour compatibilité avec les imports existants.


def plateau_depuis_dict(plateau_dict: list) -> list[list[Tuile]]:
    """Reconstitue le plateau complet (liste de combinaisons de Tuiles)."""
    return [[tuile_depuis_dict(d) for d in combo] for combo in plateau_dict]


def _plateau_vers_dict(plateau: list[list[Tuile]]) -> list[list[dict]]:
    return [[t.as_dict() for t in combo] for combo in plateau]


# --------------------------------------------------------------------------- #
# Création de partie
# --------------------------------------------------------------------------- #

def creer_partie(config_joueurs: list[dict], config_regles: dict) -> dict:
    """
    config_joueurs = [{"nom": str, "est_ia": bool, "niveau": str|None,
                       "avatar_index": int|None}, ...]  # avatar_index optionnel
    Crée et retourne un état complet avec tuiles distribuées.
    """
    nb_joueurs = len(config_joueurs)
    distribution = distribuer(creer_sac(), nb_joueurs)

    # Nombre de manches du match (issue #203) : lu depuis les réglages, borné
    # à [1, 9], défaut 1 (une seule manche, comportement par défaut). Un
    # config.json ancien ou sans la clé retombe donc sur 1 sans erreur.
    try:
        nb_manches = int(config_regles.get("nb_manches", 1))
    except (TypeError, ValueError):
        nb_manches = 1
    nb_manches = max(1, min(9, nb_manches))

    joueurs = []
    for i, cj in enumerate(config_joueurs):
        joueurs.append({
            "nom": cj["nom"],
            "est_ia": cj.get("est_ia", False),
            "niveau": cj.get("niveau"),
            "avatar_index": cj.get("avatar_index"),
            "chevalet": [t.as_dict() for t in distribution["chevalets"][i]],
            "mise_initiale_faite": False,
            "score_manche": 0,
            "score_cumul": 0,
        })

    etat = {
        "id": uuid.uuid4().hex[:12],
        "phase": "jeu",
        "tour_numero": 1,
        "manche_numero": 1,
        "index_joueur_actuel": 0,
        "joueurs": joueurs,
        "pioche": [t.as_dict() for t in distribution["pioche"]],
        "plateau": [],
        "plateau_debut_tour": None,
        "chevalet_debut_tour": [],
        "index_debut_tour": 0,
        "tour_debut_tour": 1,
        "historique": [],
        "dernier_coup_ia": None,
        "manche_terminee": False,
        "gagnant_manche_index": None,
        "config": {
            # Nombre de manches du match (issue #203, suite de #192) : un vrai
            # compteur de manches (``manche_numero``) pilote désormais la fin
            # de partie — voir ``nouvelle_manche`` / ``est_fin_partie``.
            "nb_manches": nb_manches,
            "valeur_joker_penalite": config_regles.get(
                "valeur_joker_penalite", 30),
            "mise_initiale_min": config_regles.get(
                "mise_initiale_min", config.MISE_INITIALE_MIN),
            # Graine de l'affaiblissement des niveaux d'IA (issue #213) : fixe
            # le tirage « d'oubli » des niveaux bridés (Débutant → Intermédiaire)
            # pour des simulations reproductibles. ``None`` en jeu normal →
            # tirage non reproductible (voir moteur/ia._rng_oubli). Clé optionnelle.
            "graine_ia": config_regles.get("graine_ia"),
        },
    }
    return etat


# --------------------------------------------------------------------------- #
# Backup / annulation de tour
# --------------------------------------------------------------------------- #

def backup_debut_tour(etat: dict) -> None:
    """Deep-copy de plateau + chevalet du joueur actuel dans les champs backup.

    Mémorise aussi l'index du joueur et le numéro de tour au début du tour, afin
    que ``annuler_tour`` restaure le bon joueur même si le tour a déjà avancé
    (ex. après une pioche qui appelle ``_terminer_tour``).
    """
    idx = etat["index_joueur_actuel"]
    etat["plateau_debut_tour"] = copy.deepcopy(etat["plateau"])
    etat["index_debut_tour"] = idx
    etat["tour_debut_tour"] = etat["tour_numero"]
    etat["chevalet_debut_tour"] = copy.deepcopy(etat["joueurs"][idx]["chevalet"])


def annuler_tour(etat: dict) -> None:
    """Restaure plateau, chevalet, joueur actif et numéro de tour depuis backup."""
    if etat["plateau_debut_tour"] is not None:
        etat["plateau"] = copy.deepcopy(etat["plateau_debut_tour"])
    idx = etat.get("index_debut_tour", etat["index_joueur_actuel"])
    etat["index_joueur_actuel"] = idx
    etat["tour_numero"] = etat.get("tour_debut_tour", etat["tour_numero"])
    etat["joueurs"][idx]["chevalet"] = copy.deepcopy(etat["chevalet_debut_tour"])


# --------------------------------------------------------------------------- #
# Valeur effective des tuiles d'une combinaison (pour la mise initiale)
# --------------------------------------------------------------------------- #

def _valeurs_par_tuile(combo: list[Tuile]) -> dict:
    """Retourne {id_tuile: valeur_effective} pour une combinaison valide."""
    r = valider_combinaison(combo)
    if not r["valide"]:
        return {}
    valeurs: dict = {}
    if r["type"] == "suite":
        # Valeur de base ancrée sur la première tuile réelle.
        i0, t0 = next((i, t) for i, t in enumerate(combo) if not t.est_joker)
        base = t0.valeur - i0
        for i, t in enumerate(combo):
            valeurs[t.id] = base + i
    else:  # groupe
        valeur = next(t.valeur for t in combo if not t.est_joker)
        for t in combo:
            valeurs[t.id] = valeur
    return valeurs


def _points_tuiles_posees(plateau: list[list[Tuile]], ids_posees: set) -> int:
    """Somme des valeurs effectives des tuiles posées ce tour (issues du chevalet)."""
    total = 0
    for combo in plateau:
        valeurs = _valeurs_par_tuile(combo)
        for t in combo:
            if t.id in ids_posees:
                total += valeurs.get(t.id, 0)
    return total


# --------------------------------------------------------------------------- #
# Tours de jeu
# --------------------------------------------------------------------------- #

def jouer_tour(etat: dict,
               ids_tuiles_posees: list[str],
               nouveau_plateau: list[list[dict]]) -> dict:
    """
    ids_tuiles_posees : ids des tuiles du chevalet jouées.
    nouveau_plateau : plateau proposé (dict-sérialisé).
    """
    # 1. Convertir le plateau proposé.
    plateau = plateau_depuis_dict(nouveau_plateau)

    # 2. Valider le plateau.
    validation = valider_plateau(plateau)
    if not validation["valide"]:
        return {"ok": False, "erreur": "Plateau invalide : "
                + " ; ".join(validation["erreurs"]),
                "combos_invalides": validation["combos_invalides"]}

    # 2bis. Garde-fou (#187) : aucune tuile déjà posée sur le plateau en
    # début de tour ne peut disparaître (elle peut changer de combinaison,
    # jamais être perdue) — contrôle central, valable pour un coup humain
    # comme pour n'importe quel niveau d'IA, présent ou futur.
    ids_avant = {t["id"] for combo in etat.get("plateau", []) for t in combo}
    ids_apres = {t.id for combo in plateau for t in combo}
    ids_disparues = ids_avant - ids_apres
    if ids_disparues:
        return {"ok": False, "erreur":
                "Coup refusé : des tuiles du plateau ont disparu ("
                + ", ".join(sorted(ids_disparues)) + ")",
                "tuiles_disparues": sorted(ids_disparues)}

    joueur = etat["joueurs"][etat["index_joueur_actuel"]]
    ids_posees = set(ids_tuiles_posees)

    # 3. Mise initiale : les tuiles posées issues du chevalet doivent
    #    totaliser >= mise_initiale_min.
    points_poses = _points_tuiles_posees(plateau, ids_posees)
    if not joueur["mise_initiale_faite"]:
        mini = etat["config"]["mise_initiale_min"]
        if points_poses < mini:
            return {"ok": False, "erreur":
                    f"Mise initiale insuffisante ({points_poses} < {mini})"}

    # 4. Retirer les tuiles posées du chevalet.
    joueur["chevalet"] = [t for t in joueur["chevalet"]
                          if t["id"] not in ids_posees]

    # 5. Remplacer le plateau.
    etat["plateau"] = _plateau_vers_dict(plateau)

    # 6. Marquer la mise initiale comme faite.
    joueur["mise_initiale_faite"] = True

    # 7. Historique.
    description = f"{joueur['nom']} a posé {len(ids_posees)} tuile(s)"
    _ajouter_historique(etat, etat["index_joueur_actuel"],
                        description, points_poses)

    # 8. Terminer le tour.
    _terminer_tour(etat)

    return {"ok": True, "etat": etat}


def piocher(etat: dict, nb: int = 1) -> dict:
    """
    Pioche nb tuiles (ou moins si pioche vide), les ajoute au chevalet.
    Appelle _terminer_tour.
    """
    joueur = etat["joueurs"][etat["index_joueur_actuel"]]
    piochees: list[dict] = []
    for _ in range(nb):
        if not etat["pioche"]:
            break
        tuile = etat["pioche"].pop(0)
        joueur["chevalet"].append(tuile)
        piochees.append(tuile)

    _ajouter_historique(etat, etat["index_joueur_actuel"],
                        f"{joueur['nom']} a pioché {len(piochees)} tuile(s)", 0)
    _terminer_tour(etat)

    return {"ok": True, "tuiles_piochees": piochees, "etat": etat}


def passer_tour(etat: dict) -> dict:
    """Appelle _terminer_tour directement."""
    _ajouter_historique(etat, etat["index_joueur_actuel"],
                        f"{etat['joueurs'][etat['index_joueur_actuel']]['nom']} "
                        f"a passé son tour", 0)
    _terminer_tour(etat)
    return {"ok": True, "etat": etat}


def _terminer_tour(etat: dict) -> None:
    """
    Vérifie fin de manche (chevalet vide OU pioche vide).
    Si fin : calculer_scores_manche, marquer manche_terminee.
    Sinon : passer au joueur suivant, incrémenter tour_numero.
    """
    joueur = etat["joueurs"][etat["index_joueur_actuel"]]
    chevalet_vide = len(joueur["chevalet"]) == 0
    pioche_vide = len(etat["pioche"]) == 0

    # Simplification : la manche se termine si un chevalet est vide, ou si la
    # pioche est épuisée (approximation de « tous bloqués »).
    if chevalet_vide or pioche_vide:
        calculer_scores_manche(etat["joueurs"],
                               etat["config"]["valeur_joker_penalite"])
        etat["manche_terminee"] = True
        etat["gagnant_manche_index"] = trouver_gagnant_manche(etat["joueurs"])
        if est_fin_partie(etat):
            # Dernière manche : le match est terminé. Le vainqueur du MATCH est
            # le joueur au plus haut score cumulé (issue #203) — il coïncide
            # avec le vainqueur de la manche quand il n'y a qu'une seule manche.
            etat["phase"] = "fin"
            etat["terminee"] = True
            etat["gagnant_match_index"] = trouver_gagnant_match(etat["joueurs"])
            etat["egalite_match"] = egalite_sommet_match(etat["joueurs"])
        return

    nb = len(etat["joueurs"])
    etat["index_joueur_actuel"] = (etat["index_joueur_actuel"] + 1) % nb
    etat["tour_numero"] += 1


def _ajouter_historique(etat: dict, joueur_index: int,
                        description: str, points: int) -> None:
    etat["historique"].append({
        "joueur_index": joueur_index,
        "description": description,
        "points": points,
        "tour": etat["tour_numero"],
    })


def nouvelle_manche(etat: dict) -> dict:
    """
    Démarre la manche suivante en conservant score_cumul (issue #203).
    Incrémente ``manche_numero``, redistribue 106 tuiles, remet à zéro le
    plateau, les chevalets, la mise initiale et le score de manche de chacun.

    Qui commence la manche : rotation documentée — la manche N (1-based)
    commence par le joueur d'index ``(N - 1) % nb_joueurs`` (manche 1 : joueur
    0, manche 2 : joueur 1, etc.). Chacun ouvre ainsi à tour de rôle au fil
    des manches du match.
    """
    nb_joueurs = len(etat["joueurs"])
    distribution = distribuer(creer_sac(), nb_joueurs)

    for i, joueur in enumerate(etat["joueurs"]):
        joueur["chevalet"] = [t.as_dict()
                              for t in distribution["chevalets"][i]]
        joueur["mise_initiale_faite"] = False
        joueur["score_manche"] = 0
        # score_cumul est volontairement conservé.

    etat["pioche"] = [t.as_dict() for t in distribution["pioche"]]
    etat["plateau"] = []
    etat["plateau_debut_tour"] = None
    etat["chevalet_debut_tour"] = []
    etat["historique"] = []
    etat["dernier_coup_ia"] = None
    etat["manche_terminee"] = False
    etat["gagnant_manche_index"] = None
    etat["manche_numero"] = etat.get("manche_numero", 1) + 1
    etat["index_joueur_actuel"] = (etat["manche_numero"] - 1) % nb_joueurs
    etat["tour_numero"] = 1
    etat["phase"] = "jeu"
    etat["terminee"] = False

    backup_debut_tour(etat)
    return etat


def normaliser_etat_reprise(etat: dict) -> dict:
    """Normalise un état rechargé depuis la sauvegarde avant de le reprendre
    (issue #203). Une partie enregistrée AVANT que les manches multiples ne
    fonctionnent n'a pas de compteur de manches (``manche_numero`` absent de
    l'état) : une telle partie, même sauvegardée avec ``nb_manches > 1``, est
    reprise comme une partie d'UNE SEULE manche (aucun point de départ fiable
    pour un décompte). Une partie créée depuis #203 porte toujours
    ``manche_numero`` et conserve donc son vrai nombre de manches à la reprise
    (y compris au milieu d'un match)."""
    etat.setdefault("config", {})
    if "manche_numero" not in etat:
        etat["config"]["nb_manches"] = 1
        etat["manche_numero"] = 1
    return etat


def est_fin_partie(etat: dict) -> bool:
    """Vrai quand la manche courante est terminée ET que c'est la dernière
    manche du match (issue #203) : un vrai compteur de manches
    (``manche_numero``) remplace l'ancienne comparaison fondée sur le numéro
    de tour (§3bis). Avec ``nb_manches == 1`` (défaut), équivaut à
    ``manche_terminee`` — comportement d'une partie d'une seule manche."""
    if not etat.get("manche_terminee"):
        return False
    return etat.get("manche_numero", 1) >= etat["config"]["nb_manches"]
