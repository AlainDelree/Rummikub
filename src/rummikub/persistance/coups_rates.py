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

import copy

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


# =========================================================================== #
# Issue #193 (suite de #188) : poses sous-optimales, budget nécessaire,
# analyse d'un joueur humain, technique de la « réserve ».
# =========================================================================== #
#
# Les fonctions ci-dessus (``extraire_decisions_ia``, ``analyser_decision``,
# ``calculer_resume``, ``top_coups_rates``) ne regardent que les décisions de
# piocher/passer d'une IA et restent INCHANGÉES (tests #188 toujours valables
# tels quels). Les fonctions ci-dessous généralisent la même approche :
#   1. aux POSES (une IA qui pose moins de tuiles que le solveur n'en trouve,
#      pas seulement une pioche/passe alors qu'un coup existait) ;
#   2. à N'IMPORTE QUEL joueur, humain compris (``extraire_decisions_joueur``,
#      utilisé par ``--joueur`` du script) ;
#   3. à la mesure du budget de temps minimal nécessaire pour qu'un coup raté
#      soit retrouvé (``budget_necessaire``) ;
#   4. à la détection de la technique de la « réserve » d'un joueur humain
#      (``detecter_reserves_joueur``) — à ne jamais compter comme un coup raté
#      ni comme un cas où le solveur est battu.

# Série de budgets par défaut pour mesurer le budget nécessaire à un coup
# raté/une pose sous-optimale (point 2 de l'issue).
BUDGETS_SERIE_DEFAUT = (1.5, 3.0, 6.0, 10.0, 20.0, 30.0)


# --------------------------------------------------------------------------- #
# Extraction généralisée (poses comprises, joueur quelconque).
# --------------------------------------------------------------------------- #

def extraire_toutes_decisions(data: dict, predicat_joueur) -> list:
    """Généralise ``extraire_decisions_ia`` aux poses et à un joueur
    quelconque sélectionné par ``predicat_joueur(joueur_normalise, idx) ->
    bool``.

    Comme ``extraire_decisions_ia``, l'état AVANT chaque décision est celui
    enregistré par l'action PRÉCÉDENTE du journal — y compris une
    ``"annulation"``, qui porte elle aussi un instantané complet (voir
    ``journal.py``), ce qui permet de reconstituer correctement l'état même
    après une pose annulée puis rejouée. Une décision annulée puis rejouée
    réutilise le même numéro de ``tour`` (comme dans ``bilan.py``) : seule la
    DERNIÈRE occurrence par ``(tour, idx)`` est conservée — l'annulation
    elle-même n'apparaît jamais comme décision (ce n'en est pas une).

    Pour une ``"pose"``, ``ids_tuiles_reelles`` (ids effectivement posés) est
    calculé par différence entre le chevalet d'avant et celui enregistré par
    l'action elle-même (état APRÈS la pose) — nécessaire à
    :func:`detecter_reserves_joueur`.
    """
    if not isinstance(data, dict):
        return []
    actions = data.get("actions")
    if not isinstance(actions, list):
        return []
    actions = [a for a in actions if isinstance(a, dict)]
    if len(actions) < 2:
        return []

    joueurs = _joueurs_normalises(data.get("joueurs"))
    if not joueurs:
        return []

    brutes: dict = {}
    for i in range(1, len(actions)):
        actuelle = actions[i]
        precedente = actions[i - 1]
        action = actuelle.get("action")
        if action not in ("pose", "pioche", "passe"):
            continue

        idx = actuelle.get("auteur_index")
        if not isinstance(idx, int) or not (0 <= idx < len(joueurs)):
            continue
        if not predicat_joueur(joueurs[idx], idx):
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

        ids_tuiles_reelles = []
        if action == "pose":
            mains_apres = actuelle.get("mains_joueurs")
            if not isinstance(mains_apres, list) or not (0 <= idx < len(mains_apres)) \
                    or not isinstance(mains_apres[idx], dict):
                continue
            chevalet_apres = mains_apres[idx].get("tuiles")
            if not isinstance(chevalet_apres, list):
                continue
            ids_avant = {t.get("id") for t in chevalet_dict if isinstance(t, dict)}
            ids_apres = {t.get("id") for t in chevalet_apres if isinstance(t, dict)}
            ids_tuiles_reelles = sorted(ids_avant - ids_apres)

        mise_initiale_faite = any(
            a.get("action") == "pose" and a.get("auteur_index") == idx
            and (a.get("nb_tuiles_posees") or 0) > 0
            for a in actions[:i])

        joueurs_etat = [{"chevalet": [], "mise_initiale_faite": True}
                        for _ in joueurs]
        joueurs_etat[idx] = {"chevalet": chevalet_dict,
                             "mise_initiale_faite": mise_initiale_faite}

        tour = actuelle.get("tour")
        brutes[(tour, idx)] = {
            "tour": tour,
            "niveau": joueurs[idx].get("niveau"),
            "nom": joueurs[idx].get("nom"),
            "action": action,
            "nb_tuiles_jouees": actuelle.get("nb_tuiles_posees") or 0,
            "ids_tuiles_reelles": ids_tuiles_reelles,
            "moment": "apres_mise" if mise_initiale_faite else "avant_mise",
            "idx": idx,
            "etat": {
                "joueurs": joueurs_etat,
                "plateau": plateau_dict,
                "config": {"mise_initiale_min": config.MISE_INITIALE_MIN},
            },
        }

    cles = sorted(brutes, key=lambda k: (k[0] is None, k[0], k[1]))
    return [brutes[k] for k in cles]


def extraire_decisions_ia_toutes(data: dict) -> list:
    """Décisions pose/pioche/passe de n'importe quelle IA (point 1 de
    l'issue #193) — contrairement à ``extraire_decisions_ia``, qui ne
    regarde que pioche/passe (comportement #188 conservé tel quel)."""
    def predicat(joueur, idx):
        return joueur.get("est_ia") is True and bool(joueur.get("niveau"))
    return extraire_toutes_decisions(data, predicat)


def extraire_decisions_joueur(data: dict, nom: str) -> list:
    """Décisions pose/pioche/passe d'un joueur HUMAIN nommé ``nom`` (issue
    #193, point 6 ter — option ``--joueur`` du script)."""
    def predicat(joueur, idx):
        return joueur.get("est_ia") is False and joueur.get("nom") == nom
    return extraire_toutes_decisions(data, predicat)


# --------------------------------------------------------------------------- #
# Analyse généralisée d'une décision (pose comprise).
# --------------------------------------------------------------------------- #

def analyser_decision_complete(decision: dict, budget_genereux: float = 10.0,
                                budget_production: float = BUDGET_TEMPS_EXPERT) -> dict:
    """Généralise :func:`analyser_decision` aux poses (point 1 de l'issue
    #193) : pour une décision ``"pose"``, compare le nombre de tuiles
    RÉELLEMENT posées au maximum trouvé par le solveur (budget généreux),
    plutôt que de chercher un coup raté. Fonctionne pour n'importe quel
    joueur (IA ou humain) — ``budget_limite`` (distinction budget de
    production/généreux) ne reste calculé que pour le niveau ``"Expert"``.

    ``ecart = nb_tuiles_solveur - nb_tuiles_reel`` :
      - ``ecart > 0`` et action ``"pioche"``/``"passe"`` : ``coup_rate``.
      - ``ecart > 0`` et action ``"pose"`` : ``pose_sous_optimale``.
      - ``ecart < 0`` (uniquement possible pour une ``"pose"``, un joueur
        humain ne venant jamais du solveur) : ``joueur_bat_solveur`` — le
        solveur, même avec le budget généreux, fait moins bien que ce que le
        joueur a réellement posé (voir issue, point 6 ter, liste (b)).

    Si le budget généreux s'épuise sans qu'aucune branche n'ait abouti
    (``inconclusif``), aucune des trois catégories ci-dessus n'est retenue
    (absence de preuve, pas preuve d'absence — voir avertissement du
    module) : ne JAMAIS afficher ce cas comme « pas de coup raté », toujours
    comme « inconclusif » (point 3 de l'issue)."""
    def _essayer(budget):
        try:
            return resoudre_coup(decision["etat"], decision["idx"], budget_temps=budget)
        except BudgetDepasse:
            return "budget_depasse"

    resultat = _essayer(budget_genereux)
    inconclusif = resultat == "budget_depasse"
    coup = None if inconclusif or resultat is None else resultat
    nb_solveur = len(coup["ids_tuiles"]) if coup else 0
    ids_solveur = sorted(coup["ids_tuiles"]) if coup else []

    action = decision["action"]
    nb_reel = decision.get("nb_tuiles_jouees", 0) if action == "pose" else 0
    ecart = None if inconclusif else nb_solveur - nb_reel

    coup_rate = (not inconclusif) and action in ("pioche", "passe") and nb_solveur > 0
    pose_sous_optimale = (not inconclusif) and action == "pose" and ecart > 0
    joueur_bat_solveur = (not inconclusif) and action == "pose" and ecart < 0

    points_ouverture = None
    if coup and action != "pose" and decision["moment"] == "avant_mise":
        plateau_res = plateau_depuis_dict(coup["nouveau_plateau"])
        points_ouverture = _points_tuiles_posees(plateau_res, set(coup["ids_tuiles"]))

    budget_limite = None
    if decision["niveau"] == "Expert" and (coup_rate or pose_sous_optimale):
        resultat_prod = _essayer(budget_production)
        coup_prod = None if resultat_prod in (None, "budget_depasse") else resultat_prod
        nb_prod = len(coup_prod["ids_tuiles"]) if coup_prod else 0
        budget_limite = nb_prod < nb_solveur

    return {
        "tour": decision["tour"], "niveau": decision["niveau"], "nom": decision["nom"],
        "action": action, "moment": decision["moment"],
        "coup_rate": coup_rate,
        "pose_sous_optimale": pose_sous_optimale,
        "joueur_bat_solveur": joueur_bat_solveur,
        "nb_tuiles_solveur": nb_solveur,
        "nb_tuiles_reel": nb_reel,
        "ids_tuiles_solveur": ids_solveur,
        "nb_tuiles_manquantes": max(0, ecart) if ecart is not None else None,
        "nb_tuiles_excedentaires": max(0, -ecart) if ecart is not None else None,
        "points_ouverture": points_ouverture,
        "budget_limite": budget_limite,
        "inconclusif": inconclusif,
    }


def analyser_decisions_completes(decisions: list, budget_genereux: float = 10.0,
                                  budget_production: float = BUDGET_TEMPS_EXPERT,
                                  on_resultat=None) -> list:
    """Applique :func:`analyser_decision_complete` à une liste de décisions
    (callback de progression optionnel, comme :func:`analyser_journal`)."""
    resultats = []
    for decision in decisions:
        resultat = analyser_decision_complete(
            decision, budget_genereux=budget_genereux, budget_production=budget_production)
        resultats.append(resultat)
        if on_resultat is not None:
            on_resultat(decision, resultat)
    return resultats


# --------------------------------------------------------------------------- #
# Résumé par niveau d'IA et par phase, poses comprises.
# --------------------------------------------------------------------------- #

def _bucket_complet_vierge() -> dict:
    return {
        "decisions": 0,
        "pioche_passe_ratees": 0,
        "poses_sous_optimales": 0,
        "tuiles_manquantes_poses": 0,
        "joueur_bat_solveur": 0,
        "budget_limite": 0,
        "inconclusifs": 0,
    }


def calculer_resume_complet(resultats: list) -> dict:
    """Comme :func:`calculer_resume`, mais distingue, par niveau d'IA et par
    phase (point 1 de l'issue #193) : les pioches/passes alors qu'un coup
    existait (``pioche_passe_ratees``, comme avant) et les poses
    sous-optimales (``poses_sous_optimales``, nouveau — avec le total de
    tuiles manquantes cumulées ``tuiles_manquantes_poses``). ``niveau`` vaut
    ``None`` pour un joueur humain (voir ``extraire_decisions_joueur`` — pas
    l'usage prévu de cette fonction, voir plutôt
    :func:`resume_joueur_humain`)."""
    out: dict = {}
    for r in resultats:
        bucket = out.setdefault(r["niveau"], {}).setdefault(
            r["moment"], _bucket_complet_vierge())
        bucket["decisions"] += 1
        if r["inconclusif"]:
            bucket["inconclusifs"] += 1
            continue
        if r["coup_rate"]:
            bucket["pioche_passe_ratees"] += 1
            if r.get("budget_limite"):
                bucket["budget_limite"] += 1
        if r["pose_sous_optimale"]:
            bucket["poses_sous_optimales"] += 1
            bucket["tuiles_manquantes_poses"] += r["nb_tuiles_manquantes"] or 0
            if r.get("budget_limite"):
                bucket["budget_limite"] += 1
    return out


# --------------------------------------------------------------------------- #
# Budget nécessaire pour retrouver un coup raté / une pose sous-optimale.
# --------------------------------------------------------------------------- #

def budget_necessaire(decision: dict, nb_tuiles_cible: int,
                       budgets: tuple = BUDGETS_SERIE_DEFAUT) -> float:
    """Plus petit budget de ``budgets`` (ordre croissant) auquel le solveur
    retrouve au moins ``nb_tuiles_cible`` tuiles sur l'état de ``decision``
    (point 2 de l'issue #193). Retourne ``None`` si même le plus grand budget
    de la série n'y arrive pas (il faudrait chercher plus haut encore).

    Coûteux : relance le solveur une fois par palier jusqu'à la cible — à
    n'appeler que pour les décisions déjà identifiées comme coup raté ou
    pose sous-optimale, jamais en vrac sur toute une campagne."""
    for budget in sorted(budgets):
        try:
            resultat = resoudre_coup(decision["etat"], decision["idx"], budget_temps=budget)
        except BudgetDepasse:
            continue
        nb = len(resultat["ids_tuiles"]) if resultat else 0
        if nb >= nb_tuiles_cible:
            return budget
    return None


def repartition_budget_necessaire(valeurs: list, budgets: tuple = BUDGETS_SERIE_DEFAUT) -> dict:
    """Histogramme ``{budget: nb_coups_a_portee_de_ce_budget_ou_moins,
    "indetermine": nb_au_dela_du_plus_grand_budget_teste}`` à partir d'une
    liste de résultats de :func:`budget_necessaire` (``None`` tolérés)."""
    repartition = {b: 0 for b in sorted(budgets)}
    repartition["indetermine"] = 0
    for v in valeurs:
        if v is None:
            repartition["indetermine"] += 1
        else:
            repartition[v] += 1
    return repartition


def top_coups_rates_complet(resultats: list, n: int = 5) -> list:
    """Comme :func:`top_coups_rates`, mais inclut aussi les poses
    sous-optimales (triées par nombre de tuiles manquantes décroissant)."""
    rates = [r for r in resultats if r["coup_rate"] or r["pose_sous_optimale"]]
    rates.sort(key=lambda r: r.get("nb_tuiles_manquantes") or 0, reverse=True)
    return rates[:n]


# --------------------------------------------------------------------------- #
# Technique de la « réserve » d'un joueur humain (point 6 ter de l'issue).
# --------------------------------------------------------------------------- #

def _reserve_a_evite_pioche(decision_suivante: dict, ids_reserve: set,
                             budget: float = 5.0):
    """Sans les tuiles de ``ids_reserve``, le solveur ne trouve-t-il AUCUN
    coup sur l'état de ``decision_suivante`` ? Si oui, la réserve a permis
    d'éviter une pioche à ce tour suivant. Retourne ``None`` si le budget
    s'épuise sans conclure (ne sait pas trancher)."""
    etat = copy.deepcopy(decision_suivante["etat"])
    idx = decision_suivante["idx"]
    chevalet = etat["joueurs"][idx]["chevalet"]
    etat["joueurs"][idx]["chevalet"] = [t for t in chevalet if t.get("id") not in ids_reserve]
    try:
        coup = resoudre_coup(etat, idx, budget_temps=budget)
    except BudgetDepasse:
        return None
    return coup is None


def detecter_reserves_joueur(decisions: list, resultats: list, *,
                              verifier_a_evite_pioche: bool = False) -> dict:
    """Repère la technique de la « réserve » (point 6 ter de l'issue #193) :
    Alain garde parfois volontairement un coup pour le tour suivant (pose
    partielle, ou pioche alors qu'un coup existait) au lieu de tout jouer
    d'un coup. ``decisions``/``resultats`` doivent être les sorties, DANS LE
    MÊME ORDRE, de :func:`extraire_decisions_joueur` et
    :func:`analyser_decisions_completes` sur CE joueur (décisions déjà
    triées par tour) : la détection compare chaque décision marquée
    ``pose_sous_optimale``/``coup_rate`` à la décision SUIVANTE de ce même
    joueur.

    Une tuile que le solveur aurait posée à la décision ``k`` (donc ratée ou
    manquante) mais que le joueur a gardée en main, puis effectivement posée
    à la décision ``k+1``, est une « réserve réussie ». Si elle n'est pas
    posée au tour suivant (toujours en main, ou — rare — disparue), c'est une
    « réserve perdue » (ou un simple oubli : les deux sont indistinguables a
    posteriori, voir issue).

    Retourne ``{"reserves_reussies": [...], "reserves_perdues": [...],
    "indices_a_exclure": {i, ...}}`` — ``indices_a_exclure`` est l'ensemble
    des index de ``decisions``/``resultats`` à retirer des listes « coup
    raté »/« pose sous-optimale » de l'appelant (ces cas ne doivent JAMAIS y
    être comptés, voir issue)."""
    reussies, perdues, indices_a_exclure = [], [], set()

    for i, (d, r) in enumerate(zip(decisions, resultats)):
        if r["inconclusif"] or not (r["pose_sous_optimale"] or r["coup_rate"]):
            continue
        ids_reelles = set(d.get("ids_tuiles_reelles") or [])
        ids_manquees = set(r["ids_tuiles_solveur"]) - ids_reelles
        if not ids_manquees:
            continue
        ids_main_avant = {t.get("id") for t in d["etat"]["joueurs"][d["idx"]]["chevalet"]}
        # Tuiles que le solveur aurait posées ET que le joueur avait
        # effectivement en main (jamais vide pour une pose, trivialement
        # tout `ids_manquees` pour une pioche/passe).
        ids_gardees = ids_manquees & ids_main_avant
        if not ids_gardees:
            continue

        if i + 1 >= len(decisions):
            continue  # pas de tour suivant du même joueur dans ce journal.
        d2, r2 = decisions[i + 1], resultats[i + 1]

        ids_posees_suivant = set(d2.get("ids_tuiles_reelles") or [])
        reussies_ici = ids_gardees & ids_posees_suivant
        perdues_ici = ids_gardees - reussies_ici

        base = {"tour": d["tour"], "nom": d["nom"], "action": d["action"],
                "tour_suivant": d2["tour"]}
        if reussies_ici:
            entree = dict(base, tuiles=sorted(reussies_ici))
            if verifier_a_evite_pioche:
                entree["a_evite_pioche"] = _reserve_a_evite_pioche(d2, reussies_ici)
            reussies.append(entree)
            indices_a_exclure.add(i)
        if perdues_ici:
            perdues.append(dict(base, tuiles=sorted(perdues_ici)))
            # Une réserve PERDUE reste une réserve (intention probable) :
            # elle non plus ne doit pas être comptée comme un coup raté ordinaire.
            indices_a_exclure.add(i)

    return {"reserves_reussies": reussies, "reserves_perdues": perdues,
            "indices_a_exclure": indices_a_exclure}


def resume_joueur_humain(decisions: list, resultats: list, reserves: dict) -> dict:
    """Synthèse pour un joueur humain (point 6 ter) : deux listes séparées
    (hors réserves, voir ``reserves["indices_a_exclure"]``) —

    - ``coups_peut_etre_rates`` : tours où le joueur a posé moins que le
      solveur, ou a pioché/passé alors qu'un coup existait (à vérifier à la
      main, voir issue) ;
    - ``solveur_bat`` : tours où le joueur a posé PLUS de tuiles que le
      solveur n'en trouve même avec le budget généreux — les plus précieux
      pour améliorer le solveur (jamais de réserve ici, par construction :
      ``detecter_reserves_joueur`` ne regarde que les poses/pioches
      sous-optimales).

    Ainsi que quelques statistiques de style, purement descriptives (voir
    avertissement dans l'issue : ne jamais tirer de conclusion stratégique
    d'un petit échantillon de parties) : nombre de tours analysés, part des
    poses qui atteignent le maximum du solveur, nombre moyen de tuiles
    posées par tour contre le maximum, fréquence des pioches alors qu'un
    coup existait."""
    exclure = reserves["indices_a_exclure"]
    coups_peut_etre_rates, solveur_bat = [], []
    nb_poses = nb_poses_max = 0
    total_reel = total_solveur = 0
    nb_pioches = nb_pioches_coup_possible = 0
    # Nombre de tours (de CE joueur) pendant lesquels un joker reste en main
    # avant d'être joué (voir issue, point 6 ter) : repéré à la volée tuile
    # par tuile (id), pas seulement compté.
    jokers_vus_depuis: dict = {}
    jokers_tours_attente = []

    for i, (d, r) in enumerate(zip(decisions, resultats)):
        ids_main_avant = {t.get("id") for t in d["etat"]["joueurs"][d["idx"]]["chevalet"]}
        for jid in ids_main_avant:
            if jid.startswith("joker") and jid not in jokers_vus_depuis:
                jokers_vus_depuis[jid] = i
        for jid in d.get("ids_tuiles_reelles") or []:
            if jid.startswith("joker") and jid in jokers_vus_depuis:
                jokers_tours_attente.append(i - jokers_vus_depuis.pop(jid))

        if r["inconclusif"]:
            continue
        entree = {"tour": d["tour"], "action": d["action"], "moment": d["moment"],
                  "nb_tuiles_reel": r["nb_tuiles_reel"],
                  "nb_tuiles_solveur": r["nb_tuiles_solveur"]}
        if d["action"] == "pose":
            nb_poses += 1
            total_reel += r["nb_tuiles_reel"]
            total_solveur += r["nb_tuiles_solveur"]
            if r["nb_tuiles_reel"] >= r["nb_tuiles_solveur"]:
                nb_poses_max += 1
        if d["action"] == "pioche":
            nb_pioches += 1
            if r["coup_rate"]:
                nb_pioches_coup_possible += 1

        if i in exclure:
            continue
        if r["pose_sous_optimale"] or r["coup_rate"]:
            coups_peut_etre_rates.append(dict(entree, nb_tuiles_manquantes=r["nb_tuiles_manquantes"]))
        if r["joueur_bat_solveur"]:
            solveur_bat.append(dict(entree, nb_tuiles_excedentaires=r["nb_tuiles_excedentaires"]))

    return {
        "nb_tours_analyses": len([r for r in resultats if not r["inconclusif"]]),
        "coups_peut_etre_rates": coups_peut_etre_rates,
        "solveur_bat": solveur_bat,
        "reserves_reussies": reserves["reserves_reussies"],
        "reserves_perdues": reserves["reserves_perdues"],
        "style": {
            "nb_poses": nb_poses,
            "part_poses_au_max": (nb_poses_max / nb_poses) if nb_poses else None,
            "moyenne_tuiles_posees": (total_reel / nb_poses) if nb_poses else None,
            "moyenne_tuiles_max_solveur": (total_solveur / nb_poses) if nb_poses else None,
            "nb_pioches": nb_pioches,
            "part_pioches_coup_possible": (
                nb_pioches_coup_possible / nb_pioches) if nb_pioches else None,
            "nb_jokers_joues": len(jokers_tours_attente),
            "jokers_tours_attente_moyenne": (
                sum(jokers_tours_attente) / len(jokers_tours_attente))
                if jokers_tours_attente else None,
        },
    }
