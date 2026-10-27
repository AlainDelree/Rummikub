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
import re

from rummikub import config
from rummikub.moteur import description_coup
from rummikub.moteur.ia import BUDGET_TEMPS_EXPERT
from rummikub.moteur.partie import plateau_depuis_dict, _points_tuiles_posees
from rummikub.moteur.solveur import resoudre_coup, BudgetDepasse
from rummikub.persistance.bilan import _joueurs_normalises

# Actions qui représentent une décision de piocher ou de passer (on exclut
# "pose" et "annulation", sans intérêt pour cette analyse).
_DECISIONS_SANS_POSE = {"pioche", "passe"}


# --------------------------------------------------------------------------- #
# Filtre par date sur le nom de fichier (issue #198, point 2).
# --------------------------------------------------------------------------- #

_RE_DATE_JOURNAL = re.compile(r"^partie_(\d{8})_\d{6}\.json$")


def filtrer_journaux_depuis(chemins: list, depuis: str = None) -> list:
    """Ne garde, parmi ``chemins`` (``Path`` vers des journaux nommés
    ``partie_AAAAMMJJ_HHMMSS.json``, voir ``persistance/journal.py``), que
    ceux dont la date dans le nom est égale ou postérieure à ``depuis``
    (``"AAAAMMJJ"``) — permet de limiter l'analyse aux parties jouées avec
    la dernière version d'une IA plutôt qu'un mélange de versions
    successives (point 2 de l'issue #198).

    Retourne ``chemins`` inchangé si ``depuis`` est vide/``None``. Un nom de
    fichier qui ne suit pas le format attendu est exclu (prudence : sans
    date fiable à comparer, impossible de garantir qu'il s'agit bien d'une
    partie récente)."""
    if not depuis:
        return list(chemins)
    retenus = []
    for chemin in chemins:
        m = _RE_DATE_JOURNAL.match(chemin.name)
        if m is not None and m.group(1) >= depuis:
            retenus.append(chemin)
    return retenus


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

# =========================================================================== #
# Issue #201 (suite de #193) : compter les tuiles RÉELLEMENT posées depuis
# la main, pas les tuiles déplacées.
# =========================================================================== #
#
# Pour un coup HUMAIN, ``data["ids_tuiles"]`` envoyé par ``jeu.js`` (variable
# ``tuilesCeTour``) mélange les tuiles venues de la main ET celles du plateau
# déplacées pendant le tour sans venir de la main (voir
# ``jeu.js:prendreTuileTapis``, qui alimente ``tuilesCeTour`` pour COLORER la
# tuile, pas pour compter ce qui a été posé). Avant #201, ``ui/api.py``
# journalisait ``nb_tuiles_posees = len(data["ids_tuiles"])`` : pour un coup
# humain qui déplace des tuiles déjà posées, ce compte est donc GONFLÉ par
# rapport au nombre réel de tuiles sorties de la main — faussant les listes
# « solveur battu », les poses sous-optimales (masquées par l'inflation) et
# les statistiques de style d'``--joueur``. Pour une IA, ``ids_tuiles`` ne
# contient JAMAIS que des tuiles de la main (voir ``moteur/solveur.py``,
# ``ids_main`` ; ``moteur/ia.py``) : son compte n'a jamais été affecté.
#
# Correctif (``extraire_toutes_decisions``, qui alimente TOUTE l'analyse
# ci-dessous, IA comme humain) : ``nb_tuiles_jouees`` n'est plus lu depuis le
# champ ``nb_tuiles_posees`` du journal, mais calculé comme
# ``len(ids_tuiles_reelles)`` — la différence entre la main d'avant et la
# main d'après le coup (déjà calculée pour ``ids_tuiles_reelles``, utilisée
# pour la détection de la technique de la « réserve »). Ce calcul corrige
# AUSSI les anciens journaux (écrits avant la correction de ``jeu_jouer_coup``
# ci-dessous) : il ne dépend jamais du champ ``nb_tuiles_posees``/
# ``nb_tuiles_deplacees`` du journal, seulement des deux instantanés de main
# (avant/après) déjà présents dans tout journal post-#185.
#
# ``ui/api.py:jeu_jouer_coup`` est corrigé en parallèle (changement de
# comportement du JOURNAL seulement, jamais du jeu) : il journalise
# désormais dans ``nb_tuiles_posees`` le nombre de tuiles de ``ids_tuiles``
# réellement présentes dans la main du joueur avant le coup, et le nombre de
# tuiles déplacées dans ``nb_tuiles_deplacees`` — mais ce module ne lit
# JAMAIS ces deux champs, précisément pour rester correct sur les journaux
# déjà écrits avant ce correctif (qui ne portent pas ``nb_tuiles_deplacees``).


# --------------------------------------------------------------------------- #
# Description en français + complexité d'un coup (issue #196, suite de #193).
# --------------------------------------------------------------------------- #

def _signature_tuile(t: dict) -> tuple:
    return (t.get("valeur"), t.get("couleur"), bool(t.get("est_joker")))


def _relabeler_tuiles_indiscernables(plateau_avant: list, plateau_apres: list) -> list:
    """Corrige, dans une COPIE de ``plateau_apres``, un artefact bénin du
    solveur (``moteur/solveur.py`` ne raisonne que sur des « emplacements »
    (couleur, valeur) — voir sa docstring — jamais sur l'identifiant physique
    exact d'une tuile) : deux tuiles du plateau déjà posées avant le coup,
    strictement indiscernables (même valeur/couleur, non joker), peuvent
    échanger leurs identifiants entre deux combinaisons SANS aucun
    changement réel de contenu. ``moteur/description_coup.py`` (#191), qui
    suit chaque tuile par son identifiant, y lit alors un cycle de
    dépendance (sa propre docstring : « dépendance cyclique improbable »)
    qui casse son tri causal — jamais rencontré avec un coup réellement
    joué (déterministe), mais possible avec un coup PROPOSÉ par le solveur
    (nouveau cas d'usage de l'issue #196).

    Repère les combinaisons d'après dont le CONTENU (multiset
    valeur/couleur/joker, ignorant l'identifiant précis) est IDENTIQUE à une
    combinaison d'avant encore non appariée, et relabellise ses tuiles pour
    reprendre exactement les identifiants de cette combinaison d'avant —
    cette combinaison devient alors un pur no-op pour
    ``_construire_operations`` (ids avant == ids après), ce qui élimine
    l'artefact. Ne modifie JAMAIS une tuile posée depuis la main (elle
    n'apparaît dans aucune combinaison d'avant) ni une combinaison dont le
    contenu a réellement changé — aucune information de jeu n'est perdue :
    deux tuiles indiscernables échangées sans effet visible restent, par
    définition, indiscernables pour le joueur."""
    def _cle_tri(s):
        return (s[0] is None, s[0] or 0, s[1] or "", s[2])

    def _signature_combo(combo):
        return tuple(sorted((_signature_tuile(t) for t in combo), key=_cle_tri))

    plateau_apres = copy.deepcopy(plateau_apres)
    avant_disponibles = {i: combo for i, combo in enumerate(plateau_avant) if combo}
    ids_avant_total = {t["id"] for combo in plateau_avant for t in combo}
    deja_apparies = set()

    for combo_apres in plateau_apres:
        if not combo_apres:
            continue
        if any(t["id"] not in ids_avant_total for t in combo_apres):
            # Au moins une tuile de cette combinaison vient de la main (pas
            # du plateau d'avant) : un changement RÉEL a eu lieu, jamais un
            # pur artefact d'étiquetage — ne jamais relabelliser, même si le
            # contenu ressemble par coïncidence à une combinaison d'avant.
            continue
        signature = _signature_combo(combo_apres)
        for i, combo_avant in avant_disponibles.items():
            if i in deja_apparies:
                continue
            if _signature_combo(combo_avant) != signature:
                continue
            dispo = list(combo_avant)
            for k, t in enumerate(combo_apres):
                cle = _signature_tuile(t)
                for pos, cand in enumerate(dispo):
                    if _signature_tuile(cand) == cle:
                        combo_apres[k] = dict(t, id=cand["id"])
                        dispo.pop(pos)
                        break
            deja_apparies.add(i)
            break

    return plateau_apres


_PLURIEL_TAILLE = {"petit": "petits", "moyen": "moyens", "grand": "grands"}


def _taille_coup(nb_touchees: int) -> str:
    """Taille d'un coup d'après le nombre de combinaisons du plateau
    touchées (point 1 de l'issue #198) : ``"petit"`` (1 ou 2), ``"moyen"``
    (3 à 5), ``"grand"`` (6 ou plus) — un découpage plus fin que l'ancien
    simple/complexe (voir ``categorie`` ci-dessous, conservé pour la
    continuité des mesures), qui regroupait à tort un échange simple avec
    joker et un coup à une douzaine de combinaisons dans la même catégorie
    « complexe »."""
    if nb_touchees <= 2:
        return "petit"
    if nb_touchees <= 5:
        return "moyen"
    return "grand"


def _complexite_coup(resume: dict, etapes: list) -> dict:
    """Mesure de la complexité d'un coup décrit par
    ``moteur/description_coup.py`` : nombre de combinaisons du plateau
    touchées (défaites + créées + modifiées), présence d'au moins un
    échange de joker, nombre d'étapes RÉELLES du rejeu pas à pas (celles à
    titre vide — les écrans d'information « Départ »/« Les jokers » ne
    comptent pas, par cohérence avec ``nbChangementsPasAPas`` côté
    front-end).

    ``taille`` (issue #198, point 1) : ``"petit"``/``"moyen"``/``"grand"``,
    voir :func:`_taille_coup` — avec ``a_joker``, permet de juger si un coup
    raté est à la portée d'un humain, ce que l'ancien ``categorie`` seul ne
    permettait pas (un coup avec joker simple et un coup à 12 combinaisons
    étaient tous deux « complexe »).

    ``categorie`` (issue #196, CONSERVÉ pour la continuité des mesures) :
    ``"complexe"`` si le coup touche 3 combinaisons ou plus, ou s'il déplace
    au moins un joker ; sinon ``"simple"``."""
    nb_touchees = (resume["nb_combinaisons_defaites"] + resume["nb_combinaisons_creees"]
                   + resume["nb_combinaisons_modifiees"])
    a_joker = bool(resume["jokers_deplaces"])
    nb_etapes = len([e for e in etapes if not e["titre"]])
    categorie = "complexe" if (nb_touchees >= 3 or a_joker) else "simple"
    return {"nb_combinaisons_touchees": nb_touchees, "a_joker": a_joker,
            "nb_etapes": nb_etapes, "categorie": categorie,
            "taille": _taille_coup(nb_touchees)}


def decrire_coup(plateau_avant: list, plateau_apres: list, nom: str = None) -> dict:
    """Décrit en français un coup (celui proposé par le solveur, ou celui
    réellement joué, pour comparaison) à partir du plateau avant/après,
    accompagné de sa mesure de complexité (issue #196, points 1 et 3).
    Réutilise tel quel ``moteur/description_coup.py`` (#189/#191) — aucun
    changement au solveur, à l'IA ni au moteur.

    Retourne ``{"texte": str, "etapes": [...], "complexite": {...}}``."""
    plateau_apres = _relabeler_tuiles_indiscernables(plateau_avant or [], plateau_apres or [])
    resume = description_coup.decrire_coup_ia(plateau_avant, plateau_apres, nom=nom)
    etapes = description_coup.etapes_coup_ia(plateau_avant, plateau_apres)
    return {"texte": resume["texte"], "etapes": etapes,
            "complexite": _complexite_coup(resume, etapes)}


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
    :func:`detecter_reserves_joueur` ; ``plateau_apres_reel`` (le plateau tel
    qu'enregistré par cette même action, ``None`` pour une pioche/passe) sert
    à décrire en français le coup RÉELLEMENT joué, pour comparaison avec le
    coup proposé par le solveur (issue #196, cas où le joueur bat le
    solveur).
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
        plateau_apres_reel = None
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
            plateau_apres_courant = actuelle.get("plateau")
            if isinstance(plateau_apres_courant, list):
                plateau_apres_reel = plateau_apres_courant

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
            # Nombre de tuiles RÉELLEMENT sorties de la main (issue #201) :
            # calculé à partir de la variation de la main (``ids_tuiles_reelles``
            # ci-dessus), jamais depuis le champ ``nb_tuiles_posees`` du
            # journal — qui, pour un coup HUMAIN écrit avant #201, comptait
            # aussi les tuiles du plateau déplacées ce tour (voir
            # ``ui/api.py:jeu_jouer_coup`` et sa docstring). Toujours 0 pour
            # une pioche/passe (``ids_tuiles_reelles`` reste vide). Pour une
            # IA, coïncide avec le champ du journal (``ids_tuiles`` du
            # solveur ne contient jamais que des tuiles de la main) — voir
            # test d'intégration dédié.
            "nb_tuiles_jouees": len(ids_tuiles_reelles),
            "ids_tuiles_reelles": ids_tuiles_reelles,
            "plateau_apres_reel": plateau_apres_reel,
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
    comme « inconclusif » (point 3 de l'issue).

    Issue #196 (suite de #193) : pour toute décision signalée (``coup_rate``,
    ``pose_sous_optimale`` ou ``joueur_bat_solveur``) où le solveur a
    effectivement proposé un plateau, ``description_solveur`` (voir
    :func:`decrire_coup`) donne le texte français du coup proposé, ses
    étapes et sa complexité — ``None`` sinon (y compris si le solveur ne
    trouve littéralement aucun coup). Pour ``joueur_bat_solveur``,
    ``description_reel`` décrit en plus, de la même façon, le coup
    RÉELLEMENT joué par le joueur (à partir de ``plateau_apres_reel``), pour
    comparaison."""
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

    # Description en français + complexité du coup proposé par le solveur
    # (issue #196) : seulement pour les décisions signalées (sinon rien à
    # comparer), et seulement si le solveur a effectivement proposé un
    # plateau (``coup`` peut être ``None`` même avec ``joueur_bat_solveur``,
    # si le solveur ne trouve absolument aucun coup, ``nb_solveur == 0``).
    description_solveur = None
    if coup is not None and (coup_rate or pose_sous_optimale or joueur_bat_solveur):
        description_solveur = decrire_coup(decision["etat"].get("plateau") or [],
                                            coup["nouveau_plateau"],
                                            nom=decision.get("nom"))

    # Description du coup RÉELLEMENT joué par le joueur, pour comparaison,
    # uniquement quand le solveur est battu (le cas le plus précieux —
    # point 1 de l'issue #196).
    description_reel = None
    if joueur_bat_solveur and decision.get("plateau_apres_reel") is not None:
        description_reel = decrire_coup(decision["etat"].get("plateau") or [],
                                         decision["plateau_apres_reel"],
                                         nom=decision.get("nom"))

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
        "description_solveur": description_solveur,
        "description_reel": description_reel,
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
        "coups_simples": 0,
        "coups_complexes": 0,
        "coups_petits": 0,
        "coups_moyens": 0,
        "coups_grands": 0,
        "coups_avec_joker": 0,
        "coups_sans_joker": 0,
    }


def calculer_resume_complet(resultats: list) -> dict:
    """Comme :func:`calculer_resume`, mais distingue, par niveau d'IA et par
    phase (point 1 de l'issue #193) : les pioches/passes alors qu'un coup
    existait (``pioche_passe_ratees``, comme avant) et les poses
    sous-optimales (``poses_sous_optimales``, nouveau — avec le total de
    tuiles manquantes cumulées ``tuiles_manquantes_poses``). ``niveau`` vaut
    ``None`` pour un joueur humain (voir ``extraire_decisions_joueur`` — pas
    l'usage prévu de cette fonction, voir plutôt
    :func:`resume_joueur_humain`).

    Issue #196 (point 3) : ``coups_simples``/``coups_complexes`` répartissent
    l'ensemble des coups ratés/poses sous-optimales (les deux catégories
    ci-dessus confondues) selon la complexité du coup proposé par le solveur
    (voir :func:`decrire_coup`/:func:`_complexite_coup`) — CONSERVÉS pour la
    continuité des mesures.

    Issue #198 (point 1, remplace la granularité trop grossière de #196) :
    ``coups_petits``/``coups_moyens``/``coups_grands`` répartissent le même
    ensemble selon ``complexite["taille"]`` ; ``coups_avec_joker``/
    ``coups_sans_joker`` selon ``complexite["a_joker"]`` — c'est cette
    répartition (taille x joker) qui dit si les coups ratés sont à la
    portée d'un humain, ce qu'un simple/complexe binaire ne permettait pas
    de distinguer."""
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
        if r["coup_rate"] or r["pose_sous_optimale"]:
            complexite = (r.get("description_solveur") or {}).get("complexite")
            if complexite:
                if complexite["categorie"] == "simple":
                    bucket["coups_simples"] += 1
                else:
                    bucket["coups_complexes"] += 1
                bucket[f"coups_{_PLURIEL_TAILLE[complexite['taille']]}"] += 1
                if complexite["a_joker"]:
                    bucket["coups_avec_joker"] += 1
                else:
                    bucket["coups_sans_joker"] += 1
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
    coup existait.

    Issue #196 (point 1/3) : chaque entrée de ``coups_peut_etre_rates``/
    ``solveur_bat`` porte en plus ``description_solveur`` (texte, étapes,
    complexité du coup proposé par le solveur — voir :func:`decrire_coup`) ;
    ``solveur_bat`` porte aussi ``description_reel`` (le coup réellement
    joué, pour comparaison). ``complexite`` répartit ``coups_peut_etre_rates``
    en coups simples/complexes (même seuil que pour l'IA, CONSERVÉ pour la
    continuité des mesures, voir :func:`calculer_resume_complet`), et
    (issue #198, point 1) par taille (``petits``/``moyens``/``grands``) et
    présence de joker (``avec_joker``/``sans_joker``)."""
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
            coups_peut_etre_rates.append(dict(
                entree, nb_tuiles_manquantes=r["nb_tuiles_manquantes"],
                description_solveur=r.get("description_solveur")))
        if r["joueur_bat_solveur"]:
            solveur_bat.append(dict(
                entree, nb_tuiles_excedentaires=r["nb_tuiles_excedentaires"],
                description_solveur=r.get("description_solveur"),
                description_reel=r.get("description_reel")))

    # Répartition simple/complexe (issue #196, CONSERVÉE pour la continuité
    # des mesures) et par taille/joker (issue #198, point 1 — remplace la
    # granularité trop grossière de #196) des coups peut-être ratés — comme
    # pour l'IA (voir calculer_resume_complet), seulement sur les cas où le
    # solveur a effectivement proposé un coup décrit.
    nb_simples = nb_complexes = 0
    nb_petits = nb_moyens = nb_grands = 0
    nb_avec_joker = nb_sans_joker = 0
    for e in coups_peut_etre_rates:
        complexite = (e.get("description_solveur") or {}).get("complexite")
        if not complexite:
            continue
        if complexite["categorie"] == "simple":
            nb_simples += 1
        else:
            nb_complexes += 1
        if complexite["taille"] == "petit":
            nb_petits += 1
        elif complexite["taille"] == "moyen":
            nb_moyens += 1
        else:
            nb_grands += 1
        if complexite["a_joker"]:
            nb_avec_joker += 1
        else:
            nb_sans_joker += 1

    return {
        "nb_tours_analyses": len([r for r in resultats if not r["inconclusif"]]),
        "coups_peut_etre_rates": coups_peut_etre_rates,
        "solveur_bat": solveur_bat,
        "reserves_reussies": reserves["reserves_reussies"],
        "reserves_perdues": reserves["reserves_perdues"],
        "complexite": {
            "simples": nb_simples, "complexes": nb_complexes,
            "petits": nb_petits, "moyens": nb_moyens, "grands": nb_grands,
            "avec_joker": nb_avec_joker, "sans_joker": nb_sans_joker,
        },
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
