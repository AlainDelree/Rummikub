"""Détection des « coups ratés » de l'IA à partir des journaux de parties
(issue #188, suite de #185).

Un coup raté est une décision de piocher ou de passer alors que le solveur
d'Expert (``moteur/solveur.py``), interrogé après coup avec un budget de
temps généreux sur l'état exact qu'affrontait l'IA (chevalets, plateau,
pioche reconstitués depuis le journal), trouve un réarrangement qui pose au
moins une tuile du chevalet (et, avant la mise initiale, qui atteint le
minimum requis).

Ce module est pur (aucune I/O autre que la manipulation des dictionnaires
passés en argument — la lecture des fichiers reste dans ``bilan.py``) afin
d'être testable facilement. Il ne dépend jamais de pywebview.

AVERTISSEMENT — à répéter dans tout affichage qui utilise ce module : le
solveur gèle certaines combinaisons déjà posées sur le plateau pour limiter
la combinatoire (voir la docstring de ``moteur/solveur.py``,
``_separer_combos_figees``). Un coup non trouvé ne prouve donc PAS qu'aucun
coup n'existe : les coups ratés détectés ici sont une BORNE BASSE, jamais une
liste exhaustive.

Reconstitution de l'état avant une décision (voir ``extraire_decisions_ia``) :
l'état avant la décision enregistrée à l'index ``i`` de ``actions`` est
l'état enregistré PAR l'action précédente (``actions[i-1]`` : chevalets,
plateau). La toute première action d'un journal ne peut donc jamais être
reconstituée et est ignorée. La mise initiale d'un joueur est considérée
faite s'il a déjà posé au moins une tuile (``action: "pose"``,
``nb_tuiles_posees > 0``) plus tôt dans le même journal — en jeu réel, il est
impossible de poser quoi que ce soit avant d'avoir atteint le minimum de
mise initiale en une seule fois, donc toute pose antérieure l'atteste.

Limite documentée : le journal ne conserve pas la configuration de la partie
(``mise_initiale_min``...) — ``config.MISE_INITIALE_MIN`` (valeur par défaut
du jeu) est utilisée pour toutes les parties rejouées, ce qui est inexact si
une partie a été jouée avec des réglages personnalisés.
"""

from rummikub import config
from rummikub.moteur.ia import BUDGET_TEMPS_EXPERT
from rummikub.moteur.partie import plateau_depuis_dict, _points_tuiles_posees
from rummikub.moteur.solveur import resoudre_coup, BudgetDepasse
from rummikub.persistance.bilan import _joueurs_normalises

# Actions qui représentent une décision de piocher ou de passer (on exclut
# "pose" et "annulation", sans intérêt pour cette analyse).
_DECISIONS_SANS_POSE = {"pioche", "passe"}


# --------------------------------------------------------------------------- #
# Reconstitution des décisions analysables depuis un journal brut.
# --------------------------------------------------------------------------- #

def extraire_decisions_ia(data: dict) -> list:
    """Décisions de piocher/passer d'une IA, avec l'état reconstitué juste
    avant chacune, prêtes pour :func:`analyser_decision`.

    Tolère les formats anciens/corrompus (retourne une liste vide plutôt que
    de lever une exception) : actions absentes/invalides, en-tête ``joueurs``
    absent, champs ``plateau``/``mains_joueurs`` manquants sur l'état
    précédent (journal écrit avant #185).
    """
    if not isinstance(data, dict):
        return []
    actions = data.get("actions")
    if not isinstance(actions, list):
        return []
    actions = [a for a in actions if isinstance(a, dict)]
    if len(actions) < 2:
        # La toute première action ne peut jamais être reconstituée (pas
        # d'état précédent) : il faut au moins une action avant elle.
        return []

    joueurs = _joueurs_normalises(data.get("joueurs"))
    if not joueurs:
        return []

    decisions = []
    for i in range(1, len(actions)):
        actuelle = actions[i]
        precedente = actions[i - 1]
        if actuelle.get("action") not in _DECISIONS_SANS_POSE:
            continue

        idx = actuelle.get("auteur_index")
        if not isinstance(idx, int) or not (0 <= idx < len(joueurs)):
            continue
        joueur = joueurs[idx]
        if joueur.get("est_ia") is not True:
            continue
        niveau = joueur.get("niveau")
        if not niveau:
            continue

        plateau_dict = precedente.get("plateau")
        mains = precedente.get("mains_joueurs")
        if not isinstance(plateau_dict, list) or not isinstance(mains, list):
            continue
        if not (0 <= idx < len(mains)) or not isinstance(mains[idx], dict):
            continue
        chevalet_dict = mains[idx].get("tuiles")
        if not isinstance(chevalet_dict, list):
            continue

        mise_initiale_faite = any(
            a.get("action") == "pose" and a.get("auteur_index") == idx
            and (a.get("nb_tuiles_posees") or 0) > 0
            for a in actions[:i]
        )

        joueurs_etat = [{"chevalet": [], "mise_initiale_faite": True}
                        for _ in joueurs]
        joueurs_etat[idx] = {"chevalet": chevalet_dict,
                             "mise_initiale_faite": mise_initiale_faite}

        decisions.append({
            "tour": actuelle.get("tour"),
            "niveau": niveau,
            "nom": joueur.get("nom"),
            "action": actuelle.get("action"),
            "moment": "apres_mise" if mise_initiale_faite else "avant_mise",
            "idx": idx,
            "etat": {
                "joueurs": joueurs_etat,
                "plateau": plateau_dict,
                "config": {"mise_initiale_min": config.MISE_INITIALE_MIN},
            },
        })
    return decisions


# --------------------------------------------------------------------------- #
# Interrogation du solveur sur une décision.
# --------------------------------------------------------------------------- #

def analyser_decision(decision: dict, budget_genereux: float = 10.0,
                       budget_production: float = BUDGET_TEMPS_EXPERT) -> dict:
    """Interroge le solveur sur l'état précédant une décision de piocher/
    passer et qualifie cette décision.

    Pour le niveau Expert, interroge en plus le solveur avec le budget de
    production (celui réellement utilisé en jeu, voir ``moteur/ia.py``) afin
    de distinguer un coup raté par faiblesse de l'algorithme (le budget de
    production l'aurait trouvé aussi) d'un coup raté par manque de temps de
    calcul (seul le budget généreux le trouve) — champ ``budget_limite``.

    Retourne un dict ``{tour, niveau, nom, action, moment, coup_rate,
    nb_tuiles, points_ouverture, budget_limite, inconclusif}``. ``coup_rate``
    est ``True`` si le solveur (budget généreux) a trouvé un coup posant au
    moins une tuile. ``inconclusif`` est ``True`` si le budget généreux s'est
    épuisé sans qu'AUCUNE branche n'ait abouti nulle part (voir
    ``BudgetDepasse``) : dans ce cas ``coup_rate`` vaut ``False`` par prudence
    (absence de preuve, pas preuve d'absence — voir avertissement du module).
    """
    def _essayer(budget):
        try:
            return resoudre_coup(decision["etat"], decision["idx"],
                                  budget_temps=budget)
        except BudgetDepasse:
            return "budget_depasse"

    resultat = _essayer(budget_genereux)
    inconclusif = resultat == "budget_depasse"
    coup = None if inconclusif or resultat is None else resultat

    nb_tuiles = len(coup["ids_tuiles"]) if coup else None
    points_ouverture = None
    if coup and decision["moment"] == "avant_mise":
        plateau_res = plateau_depuis_dict(coup["nouveau_plateau"])
        points_ouverture = _points_tuiles_posees(plateau_res, set(coup["ids_tuiles"]))

    budget_limite = None
    if decision["niveau"] == "Expert" and coup is not None:
        resultat_prod = _essayer(budget_production)
        coup_prod = None if resultat_prod in (None, "budget_depasse") else resultat_prod
        budget_limite = coup_prod is None

    return {
        "tour": decision["tour"],
        "niveau": decision["niveau"],
        "nom": decision["nom"],
        "action": decision["action"],
        "moment": decision["moment"],
        "coup_rate": coup is not None,
        "nb_tuiles": nb_tuiles,
        "points_ouverture": points_ouverture,
        "budget_limite": budget_limite,
        "inconclusif": inconclusif,
    }


def analyser_journal(data: dict, budget_genereux: float = 10.0,
                      budget_production: float = BUDGET_TEMPS_EXPERT,
                      on_resultat=None) -> list:
    """Analyse toutes les décisions de piocher/passer d'une IA dans un
    journal brut. ``on_resultat``, si fourni, est appelé après chaque
    décision analysée (callback de progression — le solveur peut prendre
    jusqu'à ``budget_genereux`` secondes par décision)."""
    resultats = []
    for decision in extraire_decisions_ia(data):
        resultat = analyser_decision(decision, budget_genereux=budget_genereux,
                                     budget_production=budget_production)
        resultats.append(resultat)
        if on_resultat is not None:
            on_resultat(resultat)
    return resultats


# --------------------------------------------------------------------------- #
# Résumé par niveau d'IA et par phase (avant/après mise initiale).
# --------------------------------------------------------------------------- #

def calculer_resume(resultats: list) -> dict:
    """Retourne ``{niveau: {moment: {decisions, coups_rates, pct_rates,
    budget_limite, inconclusifs}}}`` — ``moment`` vaut ``"avant_mise"`` ou
    ``"apres_mise"``. ``budget_limite`` ne compte que les coups ratés
    d'Expert pour lesquels le budget de production n'aurait rien trouvé (voir
    :func:`analyser_decision`)."""
    out: dict = {}
    for r in resultats:
        bucket = out.setdefault(r["niveau"], {}).setdefault(r["moment"], {
            "decisions": 0, "coups_rates": 0, "budget_limite": 0,
            "inconclusifs": 0,
        })
        bucket["decisions"] += 1
        if r["inconclusif"]:
            bucket["inconclusifs"] += 1
        if r["coup_rate"]:
            bucket["coups_rates"] += 1
            if r.get("budget_limite"):
                bucket["budget_limite"] += 1

    for par_moment in out.values():
        for stats in par_moment.values():
            stats["pct_rates"] = (
                stats["coups_rates"] / stats["decisions"] if stats["decisions"] else None)
    return out


def top_coups_rates(resultats: list, n: int = 5) -> list:
    """Les ``n`` coups ratés qui posaient le plus de tuiles, triés
    décroissant (pour examen manuel)."""
    rates = [r for r in resultats if r["coup_rate"]]
    rates.sort(key=lambda r: r["nb_tuiles"] or 0, reverse=True)
    return rates[:n]
