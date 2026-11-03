#!/usr/bin/env python3
"""Compare deux niveaux d'IA Rummikub sur un grand nombre de parties à 2
joueurs, sans interface (uniquement le moteur Python, jamais pywebview — voir
CONTEXTE.md §7).

Chaque donne (distribution initiale des tuiles) est rejouée deux fois en
miroir, en échangeant les places des deux niveaux, pour annuler l'effet du
tirage et de l'ordre de passage : ``--donnes 50`` (défaut) joue donc 100
matchs. Avec la même ``--seed``, exactement les mêmes donnes sont rejouées.

Avec ``--manches N`` (défaut 1), chaque match se joue en N manches : le
vainqueur du match est le joueur au plus haut score cumulé (issue #203). Les
résultats sont donnés à la fois par match (victoires, score cumulé moyen) et
par manche (fins, durée, pénalités du perdant).

Usage :

    python scripts/comparer_niveaux_ia.py --niveau-a Avancé --niveau-b Expert
    python scripts/comparer_niveaux_ia.py --niveau-a Avancé --niveau-b Expert \
        --donnes 200 --seed 7 --manches 3

Options :
    --niveau-a NIVEAU   Premier niveau à comparer (obligatoire).
    --niveau-b NIVEAU   Second niveau à comparer (obligatoire).
    --donnes N          Nombre de donnes distinctes (défaut 50 ; 2N matchs).
    --manches N         Nombre de manches par match (défaut 1).
    --seed N            Graine aléatoire, pour une campagne reproductible
                        (défaut 0).
    --max-tours N       Garde-fou anti-blocage : nombre maximum de tours
                        (somme des deux joueurs) dans une même partie avant
                        abandon (défaut 300). Les parties arrêtées par ce
                        garde-fou sont comptées à part, jamais mêlées aux
                        victoires.
    --sans-preferer-simple
                        Désactive le critère de simplicité du solveur
                        Expert (#199, activé par défaut) — relancer la
                        même commande (même --seed) avec et sans ce
                        drapeau pour comparer les deux versions.
    --sans-verif-finition
                        Désactive la vérification de finition en fin de
                        partie (#221, Expert/Champion du Monde).
    --sans-garde-joker  Désactive « garder un joker en main » en fin de
                        partie (#225, Champion du Monde SEUL) — relancer
                        la même commande (même --seed) avec et sans ce
                        drapeau pour comparer Champion du Monde avec et
                        sans la stratégie.
    --export-resultats FICHIER
                        Écrit un fichier JSON Lines (un match par ligne)
                        pour la comparaison appariée de deux campagnes
                        (voir scripts/comparer_campagnes_appariees.py).
    --export-trace FICHIER
                        Écrit une trace BRUTE JSON Lines, une ligne par
                        tour de chaque manche (+ une ligne de résultat par
                        manche) — pour l'analyse par phases (prologue /
                        développement / fin, issue #226) via
                        scripts/analyser_phases.py. Indépendante de
                        --export-resultats. Désactivée par défaut (aucun
                        changement de comportement sans elle).
    -v, --verbose       Journalise chaque partie jouée.
"""

import argparse
import json
import logging
import random
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "src"
SCRIPTS = RACINE / "scripts"
for _p in (SRC, SCRIPTS):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import contextlib  # noqa: E402

from rummikub.config import NIVEAUX  # noqa: E402
from rummikub import reglages  # noqa: E402
from rummikub.moteur.ia import jouer_niveau_bride  # noqa: E402
from rummikub.moteur import evaluation_main  # noqa: E402
from rummikub.moteur import niveaux  # noqa: E402
from rummikub.moteur import solveur_exact  # noqa: E402
from rummikub.moteur import verification_finition  # noqa: E402
from _verif_solveur_exact import (  # noqa: E402
    entete_dependances, exiger_solveur_exact_ou_quitter,
)
from rummikub.moteur.partie import (  # noqa: E402
    annuler_tour,
    backup_debut_tour,
    creer_partie,
    jouer_tour,
    nouvelle_manche,
    passer_tour,
    piocher,
)
from rummikub.moteur.solveur import mesurer_perturbation  # noqa: E402
from rummikub.moteur.tuiles import creer_sac  # noqa: E402

logger = logging.getLogger("comparer_niveaux_ia")


@contextlib.contextmanager
def _verif_finition_desactivee():
    """Désactive temporairement la vérification de finition en fin de
    partie (#221) pour Expert ET Champion du Monde — pour la campagne
    « avant / après » demandée par l'issue (``--sans-verif-finition``),
    dans le même esprit que ``--sans-exact``/``--sans-preferer-simple``.
    Restaure les réglages d'origine à la sortie, même en cas d'exception."""
    originaux = {}
    for nom in ("Expert", "Champion du Monde"):
        b = niveaux.BRIDAGES[nom]
        originaux[nom] = b
        niveaux.BRIDAGES[nom] = niveaux.Bridage(
            perturbation_max=b.perturbation_max, taux_oubli=b.taux_oubli,
            verif_finition=False)
    try:
        yield
    finally:
        niveaux.BRIDAGES.update(originaux)


@contextlib.contextmanager
def _strategies_champion_forcees(strategies_actives):
    """Remplace temporairement la liste de stratégies ACTIVES de Champion du
    Monde par ``strategies_actives`` (ids de ``moteur.niveaux.STRATEGIES``,
    issue #228, point 2 — options ``--strategies-champion``/``--sans-
    strategie``) — DURANT la campagne seulement, jamais dans le jeu. Restaure
    le réglage d'origine à la sortie, même en cas d'exception. N'affecte
    jamais Expert ni les niveaux inférieurs (dans le même esprit que
    ``_garde_joker_desactive`` ci-dessous, qu'il ne remplace pas — les deux
    mécanismes peuvent se combiner, voir ``main``)."""
    nom = "Champion du Monde"
    original = niveaux.BRIDAGES[nom]
    niveaux.BRIDAGES[nom] = niveaux.bridage_champion_personnalise(strategies_actives)
    try:
        yield
    finally:
        niveaux.BRIDAGES[nom] = original


def _parser_strategies_champion(valeur: str | None) -> set:
    """Traduit l'option ``--strategies-champion`` (issue #228, point 2) : une
    liste séparée par des virgules, ou l'un des mots-clés ``aucune``/
    ``defaut``/``toutes``. ``None`` (option absente) équivaut à ``defaut``.
    Lève ``ValueError`` (message listant les noms valides) sur un nom de
    stratégie inconnu."""
    if valeur is None or valeur == "defaut":
        return set(niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)
    if valeur == "aucune":
        return set()
    if valeur == "toutes":
        return set(niveaux.strategies_champion_valides())
    noms = [n.strip() for n in valeur.split(",") if n.strip()]
    niveaux.valider_noms_strategies(noms)
    return set(noms)


# Extracteurs de compteurs génériques (issue #228, point 3) : UNE entrée par
# stratégie du registre, chacune traduisant les compteurs internes propres à
# CETTE stratégie (``stats_verif_finition``/``stats_garde_joker`` ci-dessous,
# conservés inchangés depuis #221/#225) vers les deux compteurs génériques
# déclarés par ``moteur.niveaux.Strategie.compteurs`` : « déclenchée » et « a
# changé le coup ». Le rapport de campagne et l'export par partie
# (``comparer``, ``afficher_rapport``) consomment ce dict SANS connaître le
# détail propre à chaque stratégie — ajouter une stratégie plus tard n'exige
# qu'une entrée ici, jamais de modifier la boucle d'affichage ou d'export.
def _compteurs_verif_finition(resume: dict) -> dict:
    stats = resume.get("stats_verif_finition") or {}
    statuts_executes = (
        verification_finition.BUDGET_EPUISE,
        verification_finition.APPLIQUEE_MEILLEUR_SUFFIT,
        verification_finition.APPLIQUEE_AUCUN_CANDIDAT,
        verification_finition.APPLIQUEE_AUTRE_COUP,
        verification_finition.APPLIQUEE_GARDE_JOKER,
    )
    declenchee = sum(stats.get(c, 0) for c in statuts_executes)
    change = (stats.get(verification_finition.APPLIQUEE_AUTRE_COUP, 0)
             + stats.get(verification_finition.APPLIQUEE_GARDE_JOKER, 0))
    return {"declenchee": declenchee, "a_change_le_coup": change}


def _compteurs_garde_joker(resume: dict) -> dict:
    stats = resume.get("stats_garde_joker") or {}
    return {"declenchee": stats.get("tours_joker_en_main", 0),
           "a_change_le_coup": stats.get("choisi", 0)}


def _compteurs_reserve_tuile(resume: dict) -> dict:
    stats = resume.get("stats_reserve_tuile") or {}
    return {"declenchee": stats.get("declenchee", 0),
           "a_change_le_coup": stats.get("choisi", 0)}


def _compteurs_retenue_debut(resume: dict) -> dict:
    stats = resume.get("stats_retenue_debut") or {}
    return {"declenchee": stats.get("declenchee", 0),
           "a_change_le_coup": stats.get("choisi", 0)}


EXTRACTEURS_COMPTEURS_STRATEGIES = {
    "verif_finition": _compteurs_verif_finition,
    "garde_joker": _compteurs_garde_joker,
    "reserve_tuile": _compteurs_reserve_tuile,
    "retenue_debut": _compteurs_retenue_debut,
}


def compteurs_strategies(resume: dict) -> dict:
    """Compteurs génériques (« déclenchée »/« a changé le coup ») de chaque
    stratégie du registre, à partir du résumé de campagne ``resume`` (issue
    #228, point 3)."""
    return {sid: extracteur(resume)
           for sid, extracteur in EXTRACTEURS_COMPTEURS_STRATEGIES.items()}


@contextlib.contextmanager
def _garde_joker_desactive():
    """Désactive temporairement « garder un joker en main » (#225) pour
    Champion du Monde SEUL (Expert n'y a jamais eu droit) — pour la campagne
    « avec / sans » demandée par l'issue (``--sans-garde-joker``), dans le
    même esprit que ``--sans-verif-finition``. Restaure le réglage d'origine
    à la sortie, même en cas d'exception."""
    nom = "Champion du Monde"
    original = niveaux.BRIDAGES[nom]
    niveaux.BRIDAGES[nom] = niveaux.Bridage(
        perturbation_max=original.perturbation_max,
        taux_oubli=original.taux_oubli,
        verif_finition=original.verif_finition,
        garder_joker_fin_partie=False)
    try:
        yield
    finally:
        niveaux.BRIDAGES[nom] = original


@contextlib.contextmanager
def _compter_appels_solveur_verif(compteur: list):
    """Compte, dans ``compteur`` (liste à un seul élément, mutable), le
    nombre d'appels à ``resoudre_exact`` faits DEPUIS ``verification_
    finition.py`` (donc les appels SUPPLÉMENTAIRES de la vérification de
    finition, #221 point 7 — jamais l'appel normal du coup du tour, qui
    passe par ``moteur/ia.py`` et n'est pas concerné par ce compteur)."""
    original = verification_finition.resoudre_exact

    def _compte(*args, **kwargs):
        compteur[0] += 1
        return original(*args, **kwargs)

    verification_finition.resoudre_exact = _compte
    try:
        yield
    finally:
        verification_finition.resoudre_exact = original


# Les 106 IDs de référence (#187) : utilisés pour vérifier, à chaque coup,
# qu'aucune tuile n'a disparu ni n'a été dupliquée entre les mains, le
# plateau et la pioche (voir ``_anomalies_conservation``).
_IDS_REFERENCE = frozenset(t.id for t in creer_sac())

# Statuts qui font réellement tourner ``verification_finition.verifier``
# (donc consultent le solveur) — les autres (#223, point 4) sont des
# replis/non-exécutions AVANT d'y arriver (chevalet trop grand, pas de coup
# à comparer, solveur non exact) et n'appellent jamais le solveur.
_STATUTS_VERIFIES = frozenset((
    verification_finition.BUDGET_EPUISE,
    verification_finition.APPLIQUEE_MEILLEUR_SUFFIT,
    verification_finition.APPLIQUEE_AUCUN_CANDIDAT,
    verification_finition.APPLIQUEE_AUTRE_COUP,
    verification_finition.APPLIQUEE_GARDE_JOKER,
))


def _anomalies_conservation(etat: dict) -> list[str]:
    """Vérifie que les 106 tuiles de référence sont chacune présentes une
    seule fois, au total, entre les mains, le plateau et la pioche (#187) —
    la campagne de #186 ne contrôlait pas cette invariant et n'avait donc
    rien signalé quand le solveur Expert faisait disparaître des tuiles du
    plateau tant que sa mise initiale n'était pas faite."""
    compte: dict[str, int] = {}
    for joueur in etat["joueurs"]:
        for t in joueur["chevalet"]:
            compte[t["id"]] = compte.get(t["id"], 0) + 1
    for combo in etat["plateau"]:
        for t in combo:
            compte[t["id"]] = compte.get(t["id"], 0) + 1
    for t in etat["pioche"]:
        compte[t["id"]] = compte.get(t["id"], 0) + 1

    anomalies = []
    for tid in sorted(_IDS_REFERENCE):
        n = compte.pop(tid, 0)
        if n != 1:
            anomalies.append(f"{tid} présent {n} fois (attendu 1)")
    for tid in sorted(compte):
        anomalies.append(f"{tid} inconnu (en trop)")
    return anomalies


# --------------------------------------------------------------------------- #
# Trace brute par tour (issue #226) — mesure PURE : lit l'état complet de la
# partie (ce n'est pas une décision d'IA) et n'influence jamais le jeu. Le
# fichier n'est ouvert, et ces fonctions ne sont appelées, que si
# ``--export-trace`` est fourni ; par défaut ``trace_ctx`` est ``None`` et
# tout ce bloc est inerte.
# --------------------------------------------------------------------------- #

def _ecrire_ligne_trace(trace_ctx: dict, donnees: dict) -> None:
    ligne = {
        "donne": trace_ctx["donne"], "ordre": trace_ctx["ordre"],
        "niveau_a": trace_ctx["niveau_a"], "niveau_b": trace_ctx["niveau_b"],
    }
    ligne.update(donnees)
    trace_ctx["fichier"].write(json.dumps(ligne, ensure_ascii=False) + "\n")
    # Flush immédiat (issue #228, point 5 — reprise après coupure brutale) :
    # une ligne par tour doit être relisible même si le processus est tué
    # juste après l'avoir écrite (``scripts/matrice_strategies.py``).
    trace_ctx["fichier"].flush()


def _ecrire_trace_tour(trace_ctx: dict, manche_numero: int, idx: int,
                       camp: str, niveau: str, tour_numero: int,
                       chevalet_avant: int, ouvert_avant: bool,
                       taille_pioche_avant: int, joker_avant: bool,
                       action: str, nb_tuiles_posees: int, points_poses: int,
                       chevalet_apres: int, ouvert_apres: bool) -> None:
    """Une ligne par tour joué. ``action`` est l'action RÉELLEMENT exécutée
    (``"pose"``/``"pioche"``/``"passe"``) — un coup proposé par l'IA mais
    rejeté retombe sur une pioche de secours (comme côté UI), tracée comme
    telle plutôt que comme le coup invalide."""
    if trace_ctx is None:
        return
    _ecrire_ligne_trace(trace_ctx, {
        "type": "tour", "manche": manche_numero, "tour": tour_numero,
        "camp": camp, "niveau": niveau, "index_joueur": idx,
        "chevalet_avant": chevalet_avant, "chevalet_apres": chevalet_apres,
        "ouvert_avant": ouvert_avant, "ouvert_apres": ouvert_apres,
        "action": action, "nb_tuiles_posees": nb_tuiles_posees,
        "points_poses": points_poses,
        "taille_pioche_avant": taille_pioche_avant,
        "joker_en_main_avant": joker_avant,
    })


def _ecrire_trace_resultat(trace_ctx: dict, manche_numero: int,
                           camps: tuple, niveau_camp: dict,
                           res_manche: dict) -> None:
    """Une ligne de résultat à la fin de chaque manche (vainqueur, tuiles
    restantes du perdant)."""
    if trace_ctx is None:
        return
    gi = res_manche["gagnant_manche_index"]
    pi = 1 - gi
    _ecrire_ligne_trace(trace_ctx, {
        "type": "resultat", "manche": manche_numero,
        "vainqueur_camp": camps[gi], "vainqueur_niveau": niveau_camp[camps[gi]],
        "perdant_camp": camps[pi], "perdant_niveau": niveau_camp[camps[pi]],
        "tuiles_restantes_perdant": res_manche["tuiles_restantes"][pi],
        "fin": "pioche_vide" if res_manche["pioche_vide"] else "chevalet_vide",
        "tours": res_manche["tours"],
    })


# --------------------------------------------------------------------------- #
# Un tour d'IA (même logique que scripts/simulation_ia.py, + chronométrage de
# la décision IA par niveau).
# --------------------------------------------------------------------------- #

def jouer_un_tour(etat: dict, idx: int, temps_par_niveau: dict,
                  replis_expert: dict, preferer_simple: bool,
                  perturbations_expert: list,
                  eval_configs: list = None,
                  stats_verif_finition: dict = None,
                  appels_solveur_verif: list = None,
                  aucun_coup_expert: list = None,
                  stats_garde_joker: dict = None,
                  trace_ctx: dict = None,
                  manche_numero: int = 1,
                  budget_temps: float = None,
                  stats_reserve_tuile: dict = None,
                  suivi_reserve_tuile: dict = None,
                  stats_retenue_debut: dict = None) -> tuple[dict, bool, bool]:
    """Joue le tour de l'IA à l'index ``idx``.

    ``budget_temps`` (issue #228, point 5) : budget de temps du solveur par
    coup transmis à ``jouer_niveau_bride`` — ``None`` (défaut) laisse le
    jeu décider (``ia.BUDGET_TEMPS_EXPERT``, 1,5 s), inchangé pour tout
    appelant existant. Une valeur explicite (machine lente) s'applique de la
    même façon à TOUS les niveaux joués par ce script, jamais au jeu.

    Chronomètre l'appel à ``jouer_ia`` et l'ajoute à
    ``temps_par_niveau[niveau]``. Retourne ``(etat, coup_invalide,
    tuiles_disparues)`` ; ``coup_invalide`` est True si l'IA a proposé un
    coup rejeté (ou une exception), auquel cas on se replie sur une pioche
    de secours, comme côté UI (``Api.jeu_ia_jouer``). ``tuiles_disparues``
    est True si le rejet vient spécifiquement du garde-fou anti-disparition
    de tuiles (#187) — distingué des autres motifs de rejet (ex. mise
    initiale insuffisante) pour que ce type d'anomalie, bien plus grave,
    ressorte clairement dans le rapport de la campagne.

    Pour le niveau Expert, appelle ``jouer_niveau_bride`` (le MÊME chemin de
    production que ``jouer_ia``, #223 point 3) avec ``on_repli``/``on_aucun``
    (points d'observation du moteur, #190/#223 point 2) afin de compter, dans
    ``replis_expert``, les tours où Expert s'est replié sur la recherche
    arborescente, SÉPARÉS par cause réelle (#223, point 2 — l'incident de la
    campagne perdue faute de ``highspy``/``numpy`` venait d'une étiquette
    inexacte ici) :
      * ``replis_expert["budget_depasse"]`` : dépassement du budget de temps
        sans avoir rien trouvé (:class:`BudgetExactDepasse`) ;
      * ``replis_expert["deps_absentes"]`` : ``highspy``/``numpy`` absents
        (vérifié directement via ``solveur_exact.DISPONIBLE`` au moment de
        l'appel, jamais deviné depuis le seul booléen ``timeout``) ;
      * ``replis_expert["autre"]`` : tout le reste (résultat non valide,
        exception) — un cas qui ne devrait normalement jamais survenir ici
        puisque le script refuse de démarrer sans solveur exact (sauf
        ``--sans-exact``, qui désactive ce comptage).
    ``aucun_coup_expert`` (liste à un élément) compte séparément les tours où
    le modèle exact PROUVE qu'aucun coup n'est posable — un cas légitime,
    PAS un repli (Expert reste décidé par le modèle exact).

    ``preferer_simple`` (#199) est transmis tel quel à ``jouer_niveau_
    expert`` ; quand Expert pose effectivement un coup, sa perturbation du
    plateau (``mesurer_perturbation``, voir ``moteur/solveur.py``) est
    ajoutée à ``perturbations_expert`` pour la mesure de campagne.

    ``stats_verif_finition``/``appels_solveur_verif`` (issue #221, point 7) :
    les deux niveaux jouent désormais par le MÊME chemin que le jeu (issue
    #223, point 3) — ``jouer_niveau_bride`` (ce que ``jouer_ia`` appelle lui
    aussi, après résolution du niveau). Aucun appel manuel à la vérification
    de finition ni échéance propre au script : la vérification, l'échéance
    PARTAGÉE avec le coup normal, et le statut qui en résulte (clé
    ``verif_finition`` du coup renvoyé) viennent intégralement de
    ``jouer_niveau_bride`` — seule différence avec ``jouer_ia`` : Expert
    reçoit ``on_repli``/``on_aucun``/``preferer_simple``/``eval_config``
    (points d'observation du moteur, pas une logique dupliquée) pour que la
    campagne compte les replis et compare les réglages d'évaluation, comme
    avant #223.

    ``trace_ctx``/``manche_numero`` (issue #226, mesure PURE — lit l'état
    complet pour ÉCRIRE une trace, ne décide jamais rien) : si ``trace_ctx``
    n'est pas ``None`` (``--export-trace``), écrit une ligne JSON par tour
    via ``_ecrire_trace_tour`` (voir ce bloc plus haut).

    ``stats_reserve_tuile``/``suivi_reserve_tuile``/``stats_retenue_debut``
    (issue #229, point 4) : mêmes compteurs bruts que ``stats_garde_joker``
    pour les deux nouvelles stratégies, à partir des clés ``reserve_tuile_
    info``/``retenue_debut_info`` du coup renvoyé par ``jouer_niveau_bride``.
    ``suivi_reserve_tuile`` (dict mutable ``{idx: id_tuile_gardee}``, créé
    frais à CHAQUE MANCHE par l'appelant — les mains sont redistribuées à
    chaque manche, rien à suivre d'une manche à l'autre) permet de détecter,
    au TOUR SUIVANT du MÊME joueur, le mécanisme visé par la stratégie : une
    pioche évitée (le joueur a joué plutôt que pioché) et la tuile gardée
    effectivement posée."""
    niveau = etat["joueurs"][idx]["niveau"]
    backup_debut_tour(etat)
    plateau_avant = etat["plateau"]

    joueur_avant = etat["joueurs"][idx]
    camp_trace = trace_ctx["ordre"][idx] if trace_ctx is not None else None
    tour_numero_avant = etat["tour_numero"]
    chevalet_avant = len(joueur_avant["chevalet"])
    ouvert_avant = joueur_avant["mise_initiale_faite"]
    taille_pioche_avant = len(etat["pioche"])
    joker_avant = any(t.get("est_joker") for t in joueur_avant["chevalet"])

    def _issue(etat_final, invalide, tuiles_disparues, action,
              nb_tuiles_posees=0, points_poses=0):
        if trace_ctx is not None:
            joueur_apres = etat_final["joueurs"][idx]
            _ecrire_trace_tour(
                trace_ctx, manche_numero, idx, camp_trace, niveau,
                tour_numero_avant, chevalet_avant, ouvert_avant,
                taille_pioche_avant, joker_avant, action, nb_tuiles_posees,
                points_poses, len(joueur_apres["chevalet"]),
                joueur_apres["mise_initiale_faite"])
        return etat_final, invalide, tuiles_disparues

    def _compter_repli(timeout):
        if timeout:
            replis_expert["budget_depasse"] += 1
        elif not solveur_exact.DISPONIBLE:
            replis_expert["deps_absentes"] += 1
        else:
            replis_expert["autre"] += 1

    def _compter_aucun():
        if aucun_coup_expert is not None:
            aucun_coup_expert[0] += 1

    avant_appels = appels_solveur_verif[0] if appels_solveur_verif else 0
    debut = time.monotonic()
    try:
        if niveau == "Expert":
            eval_config = eval_configs[idx] if eval_configs else None
            res_ia = jouer_niveau_bride(
                etat, idx, "Expert", budget_temps=budget_temps,
                on_repli=_compter_repli, preferer_simple=preferer_simple,
                eval_config=eval_config, on_aucun=_compter_aucun)
        else:
            # Appel direct (plutôt que ``jouer_ia``, qui ne transmet aucun
            # paramètre) : équivalent à ``jouer_ia`` quand ``budget_temps``
            # est ``None`` (défaut du jeu), et permet un budget de temps du
            # solveur explicite (#228, point 5) pour une machine lente —
            # ``niveau`` vient de ``config_joueurs`` et est toujours valide.
            res_ia = jouer_niveau_bride(etat, idx, niveau,
                                        budget_temps=budget_temps)
    except Exception:
        temps_par_niveau.setdefault(niveau, []).append(time.monotonic() - debut)
        logger.exception("Exception de l'IA %s au tour %d", niveau, etat["tour_numero"])
        annuler_tour(etat)
        return _issue(piocher(etat)["etat"], True, False, "pioche")
    temps_par_niveau.setdefault(niveau, []).append(time.monotonic() - debut)

    if stats_verif_finition is not None and res_ia.get("verif_finition") is not None:
        statut_verif = res_ia["verif_finition"]
        stats_verif_finition.setdefault(statut_verif, 0)
        stats_verif_finition[statut_verif] += 1
        # Nombre d'appels supplémentaires au solveur : seulement sur les
        # tours où la vérification a été réellement TENTÉE.
        if appels_solveur_verif and statut_verif in _STATUTS_VERIFIES:
            stats_verif_finition.setdefault("appels_par_tour", []).append(
                appels_solveur_verif[0] - avant_appels)

    if stats_garde_joker is not None and res_ia.get("garde_joker_info") is not None:
        info = res_ia["garde_joker_info"]
        if info.get("joker_en_main"):
            stats_garde_joker["tours_joker_en_main"] = (
                stats_garde_joker.get("tours_joker_en_main", 0) + 1)
        if info.get("candidat_existe"):
            stats_garde_joker["candidat_existe"] = (
                stats_garde_joker.get("candidat_existe", 0) + 1)
        if info.get("permet_de_finir"):
            stats_garde_joker["permet_de_finir"] = (
                stats_garde_joker.get("permet_de_finir", 0) + 1)
        if info.get("choisi"):
            stats_garde_joker["choisi"] = stats_garde_joker.get("choisi", 0) + 1

    # « Réserve d'une tuile » (#229, point 4) : d'abord le mécanisme VISÉ par
    # la stratégie — au tour suivant du MÊME joueur, a-t-il joué plutôt que
    # pioché (pioche évitée), et la tuile gardée a-t-elle été effectivement
    # posée ? — AVANT de mettre à jour ``suivi_reserve_tuile`` avec la
    # décision de CE tour (sinon on comparerait un coup à lui-même).
    if suivi_reserve_tuile is not None:
        tuile_en_attente = suivi_reserve_tuile.get(idx)
        if tuile_en_attente is not None:
            if stats_reserve_tuile is not None:
                if res_ia.get("action") == "jouer":
                    stats_reserve_tuile["pioche_evitee"] = (
                        stats_reserve_tuile.get("pioche_evitee", 0) + 1)
                    if tuile_en_attente in (res_ia.get("ids_tuiles") or []):
                        stats_reserve_tuile["tuile_gardee_posee"] = (
                            stats_reserve_tuile.get("tuile_gardee_posee", 0) + 1)
            suivi_reserve_tuile[idx] = None

    info_reserve = res_ia.get("reserve_tuile_info")
    if info_reserve is not None:
        if stats_reserve_tuile is not None:
            if info_reserve.get("declenchee"):
                stats_reserve_tuile["declenchee"] = (
                    stats_reserve_tuile.get("declenchee", 0) + 1)
            if info_reserve.get("choisi"):
                stats_reserve_tuile["choisi"] = (
                    stats_reserve_tuile.get("choisi", 0) + 1)
                stats_reserve_tuile.setdefault("nb_tuiles_gardees_liste", []).append(
                    info_reserve["nb_tuiles_gardees"])
        if suivi_reserve_tuile is not None and info_reserve.get("choisi"):
            suivi_reserve_tuile[idx] = info_reserve.get("id_tuile_gardee")

    if stats_retenue_debut is not None and res_ia.get("retenue_debut_info") is not None:
        info_retenue = res_ia["retenue_debut_info"]
        if info_retenue.get("declenchee"):
            stats_retenue_debut["declenchee"] = (
                stats_retenue_debut.get("declenchee", 0) + 1)
        if info_retenue.get("choisi"):
            stats_retenue_debut["choisi"] = (
                stats_retenue_debut.get("choisi", 0) + 1)

    if niveau == "Expert" and res_ia.get("action") == "jouer":
        perturbations_expert.append(
            mesurer_perturbation(plateau_avant, res_ia["nouveau_plateau"]))

    action = res_ia.get("action")
    if action == "jouer":
        res = jouer_tour(etat, res_ia["ids_tuiles"], res_ia["nouveau_plateau"])
        if res["ok"]:
            points_poses = res["etat"]["historique"][-1]["points"]
            return _issue(res["etat"], False, False, "pose",
                         len(res_ia["ids_tuiles"]), points_poses)
        tuiles_disparues = bool(res.get("tuiles_disparues"))
        if tuiles_disparues:
            logger.error("ANOMALIE : coup refusé (%s) au tour %d car des "
                         "tuiles du plateau auraient disparu : %s",
                         niveau, etat["tour_numero"], res["erreur"])
        else:
            logger.warning("Coup invalide (%s) au tour %d : %s",
                           niveau, etat["tour_numero"], res["erreur"])
        annuler_tour(etat)
        return _issue(piocher(etat)["etat"], True, tuiles_disparues, "pioche")
    if action == "piocher":
        return _issue(piocher(etat)["etat"], False, False, "pioche")
    if action == "passer":
        return _issue(passer_tour(etat)["etat"], False, False, "passe")

    logger.warning("Action IA inconnue %r (%s) au tour %d",
                   action, niveau, etat["tour_numero"])
    annuler_tour(etat)
    return _issue(piocher(etat)["etat"], True, False, "pioche")


# --------------------------------------------------------------------------- #
# Un match à 2 joueurs (1 à N manches)
# --------------------------------------------------------------------------- #

def _jouer_une_manche(etat: dict, max_tours: int, temps_par_niveau: dict,
                      replis_expert: dict, preferer_simple: bool,
                      perturbations_expert: list,
                      eval_configs: list = None,
                      stats_verif_finition: dict = None,
                      appels_solveur_verif: list = None,
                      aucun_coup_expert: list = None,
                      stats_garde_joker: dict = None,
                      trace_ctx: dict = None,
                      manche_numero: int = 1,
                      budget_temps: float = None,
                      stats_reserve_tuile: dict = None,
                      stats_retenue_debut: dict = None) -> dict:
    """Joue la manche courante de ``etat`` jusqu'à sa fin naturelle (chevalet
    vidé ou pioche épuisée) ou jusqu'au garde-fou ``max_tours``. Retourne les
    statistiques de CETTE manche ; ``etat`` est muté en place.

    ``suivi_reserve_tuile`` (issue #229, point 4) est créé ICI, frais à
    chaque manche (les mains sont redistribuées à chaque nouvelle manche,
    voir ``jouer_un_tour``) — jamais transmis par l'appelant."""
    tours = 0
    coups_invalides = 0
    coups_tuiles_disparues = 0
    anomalies_conservation = 0
    arretee_garde_fou = False
    suivi_reserve_tuile: dict = {}

    while not etat["manche_terminee"]:
        tours += 1
        if tours > max_tours:
            arretee_garde_fou = True
            break
        idx = etat["index_joueur_actuel"]
        etat, invalide, tuiles_disparues = jouer_un_tour(
            etat, idx, temps_par_niveau, replis_expert, preferer_simple,
            perturbations_expert, eval_configs,
            stats_verif_finition, appels_solveur_verif, aucun_coup_expert,
            stats_garde_joker, trace_ctx, manche_numero, budget_temps,
            stats_reserve_tuile=stats_reserve_tuile,
            suivi_reserve_tuile=suivi_reserve_tuile,
            stats_retenue_debut=stats_retenue_debut)
        if invalide:
            coups_invalides += 1
        if tuiles_disparues:
            coups_tuiles_disparues += 1
        anomalies = _anomalies_conservation(etat)
        if anomalies:
            anomalies_conservation += len(anomalies)
            logger.error("ANOMALIE DE CONSERVATION au tour %d : %s",
                        tours, "; ".join(anomalies))
        backup_debut_tour(etat)

    pioche_vide = (not arretee_garde_fou and len(etat["pioche"]) == 0
                  and all(len(j["chevalet"]) > 0 for j in etat["joueurs"]))

    return {
        "tours": tours,
        "arretee_garde_fou": arretee_garde_fou,
        "pioche_vide": pioche_vide,
        "gagnant_manche_index": etat["gagnant_manche_index"],
        "scores_manche": [j["score_manche"] for j in etat["joueurs"]],
        "tuiles_restantes": [len(j["chevalet"]) for j in etat["joueurs"]],
        "coups_invalides": coups_invalides,
        "coups_tuiles_disparues": coups_tuiles_disparues,
        "anomalies_conservation": anomalies_conservation,
    }


def jouer_match(config_joueurs: list[dict], nb_manches: int, max_tours: int,
                temps_par_niveau: dict, replis_expert: dict,
                preferer_simple: bool, perturbations_expert: list,
                eval_configs: list = None, graine_ia=None,
                stats_verif_finition: dict = None,
                appels_solveur_verif: list = None,
                aucun_coup_expert: list = None,
                stats_garde_joker: dict = None,
                trace_ctx: dict = None,
                budget_temps: float = None,
                stats_reserve_tuile: dict = None,
                stats_retenue_debut: dict = None) -> dict:
    """Joue un MATCH complet à 2 joueurs de ``nb_manches`` manches (issue
    #203). Les manches s'enchaînent via ``nouvelle_manche`` (score cumulé
    conservé, nouvelle donne et mise initiale remise à zéro à chaque manche).
    Si une manche est arrêtée par le garde-fou ``max_tours``, le match entier
    est marqué comme arrêté (``arretee_garde_fou``) et abandonné.

    ``garde_joker_applique`` (issue #225, point 3), dans le résultat : vrai si
    « garder un joker en main » a été CHOISI au moins une fois pendant ce
    match (détecté par la variation de ``stats_garde_joker["choisi"]`` avant/
    après) — permet à ``comparer`` d'enregistrer qui a gagné les parties où la
    stratégie a réellement changé un coup. ``strategies_changees`` (issue
    #228, point 3) généralise cette détection à TOUTE stratégie du registre
    (``EXTRACTEURS_COMPTEURS_STRATEGIES``), sans code spécifique par
    stratégie : ``{id_strategie: bool}``, vrai si son compteur « a changé le
    coup » a progressé pendant ce match précis.

    ``trace_ctx`` (issue #226) : si fourni, chaque tour de chaque manche est
    tracé (``jouer_un_tour``) et une ligne de résultat est écrite à la fin
    de chaque manche effectivement jouée (``_ecrire_trace_resultat``)."""
    camps_trace = tuple(trace_ctx["ordre"]) if trace_ctx is not None else None
    niveau_camp_trace = ({"A": trace_ctx["niveau_a"], "B": trace_ctx["niveau_b"]}
                        if trace_ctx is not None else None)
    # graine_ia (#213) : rend reproductible l'affaiblissement des niveaux bridés
    # (tirage d'oubli) — sans elle, l'oubli tire sur l'entropie système et la
    # campagne n'est pas reproductible. Dérivée de la graine de la donne.
    etat = creer_partie(config_joueurs,
                        {"nb_manches": nb_manches, "graine_ia": graine_ia})
    backup_debut_tour(etat)

    manches = []
    coups_invalides = coups_tuiles_disparues = anomalies_conservation = 0
    arretee_garde_fou = False
    choisi_avant = stats_garde_joker.get("choisi", 0) if stats_garde_joker else 0
    _resume_partiel = {"stats_verif_finition": stats_verif_finition,
                       "stats_garde_joker": stats_garde_joker,
                       "stats_reserve_tuile": stats_reserve_tuile,
                       "stats_retenue_debut": stats_retenue_debut}
    compteurs_avant = {sid: extracteur(_resume_partiel)["a_change_le_coup"]
                       for sid, extracteur in EXTRACTEURS_COMPTEURS_STRATEGIES.items()}

    for numero in range(1, nb_manches + 1):
        res = _jouer_une_manche(etat, max_tours, temps_par_niveau,
                                replis_expert, preferer_simple,
                                perturbations_expert, eval_configs,
                                stats_verif_finition, appels_solveur_verif,
                                aucun_coup_expert, stats_garde_joker,
                                trace_ctx, numero, budget_temps,
                                stats_reserve_tuile=stats_reserve_tuile,
                                stats_retenue_debut=stats_retenue_debut)
        coups_invalides += res["coups_invalides"]
        coups_tuiles_disparues += res["coups_tuiles_disparues"]
        anomalies_conservation += res["anomalies_conservation"]
        if res["arretee_garde_fou"]:
            arretee_garde_fou = True
            break
        res["numero"] = numero
        manches.append(res)
        if trace_ctx is not None:
            _ecrire_trace_resultat(trace_ctx, numero, camps_trace,
                                   niveau_camp_trace, res)
        if numero < nb_manches:
            etat = nouvelle_manche(etat)
            backup_debut_tour(etat)

    garde_joker_applique = (stats_garde_joker is not None
                            and stats_garde_joker.get("choisi", 0) > choisi_avant)
    compteurs_apres = {sid: extracteur(_resume_partiel)["a_change_le_coup"]
                       for sid, extracteur in EXTRACTEURS_COMPTEURS_STRATEGIES.items()}
    strategies_changees = {sid: compteurs_apres[sid] > compteurs_avant[sid]
                           for sid in EXTRACTEURS_COMPTEURS_STRATEGIES}

    return {
        "etat": etat,
        "manches": manches,
        "arretee_garde_fou": arretee_garde_fou,
        "strategies_changees": strategies_changees,
        "coups_invalides": coups_invalides,
        "coups_tuiles_disparues": coups_tuiles_disparues,
        "anomalies_conservation": anomalies_conservation,
        "garde_joker_applique": garde_joker_applique,
    }


# --------------------------------------------------------------------------- #
# Campagne complète : N donnes, chacune jouée 2 fois en miroir
# --------------------------------------------------------------------------- #

def comparer(niveau_a: str, niveau_b: str, nb_donnes: int, seed: int,
            max_tours: int, nb_manches: int = 1,
            preferer_simple: bool = True,
            eval_a: str = "off", eval_b: str = "off",
            sans_exact: bool = False,
            export_resultats: str = None,
            export_trace: str = None,
            budget_temps: float = None,
            donnes_debut: int = 0,
            donnes_fin: int = None,
            mode_fichier: str = "w") -> dict:
    """``budget_temps`` (issue #228, point 5) : budget de temps du solveur par
    coup, transmis à TOUS les niveaux joués — ``None`` (défaut) laisse le jeu
    décider (1,5 s). ``donnes_debut``/``donnes_fin`` (issue #228, point 5,
    reprise de ``scripts/matrice_strategies.py``) : ne jouent qu'un sous-
    ensemble ``[donnes_debut, donnes_fin)`` des ``nb_donnes`` donnes tirées de
    ``seed`` (la liste complète des graines reste calculée à l'identique,
    SEULE la plage jouée change) — ``donnes_fin=None`` vaut ``nb_donnes``.
    ``mode_fichier`` (``"w"``/``"a"``) : mode d'ouverture d'``export_
    resultats``/``export_trace``, pour reprendre une campagne interrompue en
    AJOUTANT à des fichiers déjà partiellement écrits plutôt qu'en les
    écrasant — chaque ligne est immédiatement ``flush()``ée (écriture ligne
    par ligne, tolérante à une coupure brutale, voir CONTEXTE.md §13).

    ``nb_manches`` (#203) : nombre de manches par match — chaque donne est
    jouée en miroir (places échangées) sur un match complet, le vainqueur du
    match étant le joueur au plus haut score cumulé. Les résultats sont donnés
    à la fois par match (victoires, score cumulé moyen) et par manche.

    ``preferer_simple`` (#199) : réglage transmis à chaque appel d'Expert —
    comparer deux campagnes identiques (même graine), l'une avec et l'autre
    sans, permet de mesurer l'effet du critère de simplicité sur la force
    d'Expert (voir CONTEXTE.md §9 et §13).

    ``eval_a``/``eval_b`` (#211) : preset d'évaluation de la main restante
    (``moteur/evaluation_main.depuis_preset``) appliqué au niveau Expert du
    camp A / du camp B. Permet de comparer, EN MIROIR dans une même campagne,
    deux réglages d'Expert (p. ex. ``off`` contre ``complet``, ou deux poids de
    points), le reste étant strictement identique. Sans effet sur un camp qui
    n'est pas Expert.

    ``sans_exact`` : SANS EFFET sur le déroulement (le vrai interrupteur est
    le global ``ia.UTILISER_SOLVEUR_EXACT``, positionné par ``main`` avant
    l'appel) — reporté tel quel dans le résultat pour que l'en-tête du
    rapport indique honnêtement si le solveur exact était actif (#223,
    point 1).

    ``export_resultats`` (issue #225, point 5bis) : chemin d'un fichier où
    écrire UNE ligne JSON par match joué (donne, ordre des joueurs, vainqueur,
    scores) — pour la comparaison appariée de deux campagnes identiques (même
    seed), voir ``scripts/comparer_campagnes_appariees.py``.

    ``export_trace`` (issue #226) : chemin d'un fichier où écrire une trace
    BRUTE JSON Lines, une ligne par TOUR de chaque manche + une ligne de
    résultat par manche — pour l'analyse par phases (prologue/développement/
    fin), voir ``scripts/analyser_phases.py``. Indépendant d'``export_
    resultats`` ; mesure pure, ne change jamais le déroulement de la partie."""
    cfg_eval = {"A": evaluation_main.depuis_preset(eval_a, nb_manches),
                "B": evaluation_main.depuis_preset(eval_b, nb_manches)}
    rng_graines = random.Random(seed)
    graines = [rng_graines.randrange(2**32) for _ in range(nb_donnes)]
    fin = nb_donnes if donnes_fin is None else donnes_fin
    graines_jouees = list(enumerate(graines))[donnes_debut:fin]
    fichier_export = (open(export_resultats, mode_fichier, encoding="utf-8")
                      if export_resultats else None)
    fichier_trace = (open(export_trace, mode_fichier, encoding="utf-8")
                     if export_trace else None)

    # Niveau MATCH (issue #203) : victoire par score cumulé, nuls comptés à
    # part ; score cumulé moyen de chaque camp.
    victoires = {"A": 0, "B": 0}
    matchs_nuls = 0
    cumul_par_camp: dict[str, list[int]] = {"A": [], "B": []}
    matchs_decides = 0
    # Niveau MANCHE : statistiques agrégées sur toutes les manches jouées.
    penalites_perdant: list[int] = []
    tuiles_perdant: list[int] = []
    tours_decidees: list[int] = []
    fins = {"chevalet_vide": 0, "pioche_vide": 0, "garde_fou": 0}
    temps_par_niveau: dict[str, list[float]] = {}
    coups_invalides_total = 0
    coups_tuiles_disparues_total = 0
    anomalies_conservation_total = 0
    # Dict (plutôt qu'un tuple d'int) : mutable, modifiable depuis la
    # fermeture ``_compter_repli`` de ``jouer_un_tour`` sans variable
    # ``nonlocal`` ni retour supplémentaire à faire remonter à travers
    # ``jouer_partie``. Causes SÉPARÉES (#223, point 2 — l'ancien compteur
    # ne distinguait que « timeout »/« pas timeout », et le second bucket
    # a été, dans l'incident qui a motivé #223, étiqueté à tort « coup
    # légitimement impossible » alors qu'il s'agissait de dépendances
    # absentes). ``aucun_coup_expert`` est un cas LÉGITIME, pas un repli :
    # compté séparément (le modèle exact a prouvé qu'aucun coup n'existait).
    replis_expert = {"budget_depasse": 0, "deps_absentes": 0, "autre": 0}
    aucun_coup_expert = [0]
    # Perturbation (#199) de chaque coup effectivement posé par Expert :
    # liste de ``(tuiles_deplacees, combos_modifiees)`` (voir
    # ``mesurer_perturbation``, ``moteur/solveur.py``).
    perturbations_expert: list[tuple[int, int]] = []
    # Vérification de finition en fin de partie (#221, point 7 ; statuts
    # affinés par #223, point 4 — voir ``verification_finition.LIBELLES``)
    # : compte des statuts + nombre d'appels SUPPLÉMENTAIRES au solveur par
    # tour concerné (clé ``"appels_par_tour"``, liste).
    stats_verif_finition: dict = {}
    appels_solveur_verif = [0]
    # « Garder un joker en main » (#225, point 3) : compteurs bruts (voir
    # ``jouer_un_tour``) + liste des parties où la stratégie a CHOISI un coup
    # au moins une fois, avec le niveau vainqueur de CETTE partie (ou ``None``
    # si nulle) — pour répondre à « qui a gagné quand la stratégie s'est
    # appliquée ? ».
    stats_garde_joker: dict = {}
    parties_garde_joker: list = []
    # « Réserve d'une tuile »/« Retenue au début » (#229, point 4) : mêmes
    # compteurs bruts que ``stats_garde_joker`` ci-dessus, voir
    # ``jouer_un_tour``/``_compteurs_reserve_tuile``/``_compteurs_retenue_debut``.
    stats_reserve_tuile: dict = {}
    stats_retenue_debut: dict = {}
    pile_appels = contextlib.ExitStack()
    pile_appels.enter_context(_compter_appels_solveur_verif(appels_solveur_verif))

    for i, graine in graines_jouees:
        for ordre, camps in enumerate((("A", "B"), ("B", "A"))):
            random.seed(graine)
            niveau_camp = {"A": niveau_a, "B": niveau_b}
            config_joueurs = [
                {"nom": f"{camp}:{niveau_camp[camp]}", "est_ia": True,
                 "niveau": niveau_camp[camp]}
                for camp in camps
            ]
            # Config d'évaluation alignée sur l'index du joueur (camp camps[k]).
            eval_configs = [cfg_eval[camp] for camp in camps]
            trace_ctx = ({"fichier": fichier_trace, "donne": i + 1,
                         "ordre": list(camps), "niveau_a": niveau_a,
                         "niveau_b": niveau_b}
                        if fichier_trace else None)
            resultat = jouer_match(config_joueurs, nb_manches, max_tours,
                                   temps_par_niveau, replis_expert,
                                   preferer_simple, perturbations_expert,
                                   eval_configs, graine_ia=graine,
                                   stats_verif_finition=stats_verif_finition,
                                   appels_solveur_verif=appels_solveur_verif,
                                   aucun_coup_expert=aucun_coup_expert,
                                   stats_garde_joker=stats_garde_joker,
                                   trace_ctx=trace_ctx, budget_temps=budget_temps,
                                   stats_reserve_tuile=stats_reserve_tuile,
                                   stats_retenue_debut=stats_retenue_debut)
            coups_invalides_total += resultat["coups_invalides"]
            coups_tuiles_disparues_total += resultat["coups_tuiles_disparues"]
            anomalies_conservation_total += resultat["anomalies_conservation"]

            if resultat["arretee_garde_fou"]:
                fins["garde_fou"] += 1
                logger.warning(
                    "Donne %d (ordre %s) : match arrêté par le garde-fou",
                    i + 1, camps)
                if fichier_export:
                    fichier_export.write(json.dumps({
                        "donne": i + 1, "ordre": list(camps),
                        "niveau_a": niveau_a, "niveau_b": niveau_b,
                        "vainqueur_camp": None, "arretee_garde_fou": True,
                        "score_a": None, "score_b": None,
                    }, ensure_ascii=False) + "\n")
                    fichier_export.flush()
                continue

            etat = resultat["etat"]

            # Statistiques par MANCHE (toutes les manches du match).
            for m in resultat["manches"]:
                gi = m["gagnant_manche_index"]
                perdant_idx = 1 - gi
                tours_decidees.append(m["tours"])
                fins["pioche_vide" if m["pioche_vide"] else "chevalet_vide"] += 1
                penalites_perdant.append(-m["scores_manche"][perdant_idx])
                tuiles_perdant.append(m["tuiles_restantes"][perdant_idx])

            # Résultat du MATCH : vainqueur par score cumulé (issue #203).
            cumul_a = etat["joueurs"][camps.index("A")]["score_cumul"]
            cumul_b = etat["joueurs"][camps.index("B")]["score_cumul"]
            cumul_par_camp["A"].append(cumul_a)
            cumul_par_camp["B"].append(cumul_b)
            matchs_decides += 1
            if cumul_a == cumul_b:
                matchs_nuls += 1
                camp_gagnant = None
            else:
                camp_gagnant = "A" if cumul_a > cumul_b else "B"
                victoires[camp_gagnant] += 1

            if fichier_export:
                fichier_export.write(json.dumps({
                    "donne": i + 1, "ordre": list(camps),
                    "niveau_a": niveau_a, "niveau_b": niveau_b,
                    "vainqueur_camp": camp_gagnant, "arretee_garde_fou": False,
                    "score_a": cumul_a, "score_b": cumul_b,
                    "strategies_changees": resultat["strategies_changees"],
                }, ensure_ascii=False) + "\n")
                fichier_export.flush()

            if resultat["garde_joker_applique"]:
                parties_garde_joker.append({
                    "donne": i + 1, "ordre": list(camps),
                    "vainqueur_niveau": (None if camp_gagnant is None
                                        else niveau_camp[camp_gagnant]),
                })

            if logger.isEnabledFor(logging.INFO):
                logger.info(
                    "Donne %d (ordre %s) : match %s (%d manche(s)) — "
                    "cumul A=%d B=%d",
                    i + 1, camps,
                    "nul" if camp_gagnant is None
                    else f"gagné par {camp_gagnant} ({niveau_camp[camp_gagnant]})",
                    len(resultat["manches"]), cumul_a, cumul_b)

    pile_appels.close()
    if fichier_export:
        fichier_export.close()
    if fichier_trace:
        fichier_trace.close()
    return {
        "niveau_a": niveau_a,
        "niveau_b": niveau_b,
        "nb_manches": nb_manches,
        "stats_verif_finition": stats_verif_finition,
        "stats_garde_joker": stats_garde_joker,
        "parties_garde_joker": parties_garde_joker,
        "stats_reserve_tuile": stats_reserve_tuile,
        "stats_retenue_debut": stats_retenue_debut,
        "victoires": victoires,
        "matchs_nuls": matchs_nuls,
        "matchs_decides": matchs_decides,
        "cumul_par_camp": cumul_par_camp,
        "fins": fins,
        "penalites_perdant": penalites_perdant,
        "tuiles_perdant": tuiles_perdant,
        "tours_decidees": tours_decidees,
        "temps_par_niveau": temps_par_niveau,
        "coups_invalides_total": coups_invalides_total,
        "coups_tuiles_disparues_total": coups_tuiles_disparues_total,
        "anomalies_conservation_total": anomalies_conservation_total,
        "replis_expert": dict(replis_expert),
        "aucun_coup_expert": aucun_coup_expert[0],
        "perturbations_expert": perturbations_expert,
        "preferer_simple": preferer_simple,
        "eval_a": eval_a,
        "eval_b": eval_b,
        # Donnes RÉELLEMENT jouées par CET appel (issue #228, point 5) —
        # ``nb_donnes`` reste le total demandé pour tout le cas d'usage
        # ``matrice_strategies.py`` (reprise par tranches) : utiliser
        # ``len(graines_jouees)`` pour les additionner correctement entre
        # plusieurs appels successifs.
        "nb_donnes": nb_donnes,
        "nb_donnes_jouees": len(graines_jouees),
        "nb_parties": 2 * len(graines_jouees),
        "sans_exact": sans_exact,
        # Coût d'un joker resté en main en fin de manche (issue #225, point
        # 4) : lu depuis les réglages par défaut du moteur (``valeur_joker_
        # penalite``, ``reglages.DEFAUTS``) — les campagnes ne passent jamais
        # de config personnalisée pour ce réglage (voir ``jouer_match`` /
        # ``creer_partie``).
        "valeur_joker_penalite": reglages.DEFAUTS.get("valeur_joker_penalite", 30),
    }


# --------------------------------------------------------------------------- #
# Statistiques
# --------------------------------------------------------------------------- #

def moyenne(valeurs: list[float]) -> float:
    return sum(valeurs) / len(valeurs) if valeurs else 0.0


def intervalle_confiance_95(victoires: int, total: int) -> tuple[float, float]:
    """Taux de victoire et marge d'erreur (approximation normale de Wald,
    IC à 95 % : ±1.96·sqrt(p(1-p)/n))."""
    if total == 0:
        return 0.0, 0.0
    p = victoires / total
    marge = 1.96 * (p * (1 - p) / total) ** 0.5
    return p, marge


# --------------------------------------------------------------------------- #
# Affichage du rapport
# --------------------------------------------------------------------------- #

def afficher_rapport(resume: dict) -> None:
    niveau_a, niveau_b = resume["niveau_a"], resume["niveau_b"]
    victoires = resume["victoires"]
    fins = resume["fins"]
    nb_manches = resume["nb_manches"]
    n_matchs = resume["matchs_decides"]
    n_manches = len(resume["tours_decidees"])

    tours_expert = len(resume["temps_par_niveau"].get("Expert", []))
    replis = resume.get("replis_expert") or {}
    replis_deps_absentes = replis.get("deps_absentes", 0)

    print("=" * 70)
    for ligne in entete_dependances(sans_exact=resume.get("sans_exact", False)):
        print(ligne)
    if replis_deps_absentes and tours_expert:
        # Avertissement visible (#223, point 2) : si le solveur exact s'est
        # révélé indisponible PENDANT la campagne (et pas seulement signalé
        # au démarrage), la mesure d'Expert est faussée pour ces tours — la
        # situation même qui a motivé cette issue (campagne perdue faute de
        # highspy/numpy, étiquetée à tort « coup légitimement impossible »).
        print("!" * 70)
        print(f"  ATTENTION : {replis_deps_absentes}/{tours_expert} tour(s) "
             f"d'Expert joués SANS solveur exact (highspy/numpy indisponible "
             f"pendant la campagne) — ces tours ne mesurent PAS Expert, voir "
             f"CONTEXTE.md (incident #223).")
        print("!" * 70)
    suffixe_a = f" [eval={resume['eval_a']}]" if resume.get("eval_a", "off") != "off" else ""
    suffixe_b = f" [eval={resume['eval_b']}]" if resume.get("eval_b", "off") != "off" else ""
    print(f"COMPARAISON : {niveau_a} (camp A){suffixe_a} vs "
          f"{niveau_b} (camp B){suffixe_b}")
    print(f"Matchs de {nb_manches} manche(s) — "
         f"{resume['nb_donnes']} donne(s) x 2 (miroir) = "
         f"{resume['nb_parties']} match(s) demandé(s), "
         f"{n_matchs} match(s) décidé(s)")
    print("-" * 70)
    print("  RÉSULTATS PAR MATCH (vainqueur = plus haut score cumulé) :")

    for camp, niveau in (("A", niveau_a), ("B", niveau_b)):
        p, marge = intervalle_confiance_95(victoires[camp], n_matchs)
        print(f"  {niveau} (camp {camp}) : {victoires[camp]}/{n_matchs} "
             f"victoires — taux {p * 100:.1f} % ± {marge * 100:.1f} pt "
             f"(IC 95 %) ; score cumulé moyen "
             f"{moyenne(resume['cumul_par_camp'][camp]):.1f}")
    if resume["matchs_nuls"]:
        print(f"  Matchs nuls (score cumulé identique) : {resume['matchs_nuls']}")

    if n_matchs:
        p_a, marge_a = intervalle_confiance_95(victoires["A"], n_matchs)
        ecart_significatif = abs(p_a - 0.5) > marge_a
        print(f"  Écart par rapport à 50/50 "
             f"{'significatif' if ecart_significatif else 'NON significatif'} "
             f"au seuil de confiance 95 %.")

    print("-" * 70)
    print(f"  RÉSULTATS PAR MANCHE ({n_manches} manche(s) jouée(s)) :")
    print(f"  Fins de manche : {fins['chevalet_vide']} par chevalet vidé, "
         f"{fins['pioche_vide']} par pioche épuisée (bloqué), "
         f"{fins['garde_fou']} match(s) arrêté(s) par le garde-fou (max tours).")
    print(f"  Durée moyenne d'une manche décidée : "
         f"{moyenne(resume['tours_decidees']):.1f} tour(s).")
    print(f"  Perdant de manche : en moyenne "
         f"{moyenne(resume['tuiles_perdant']):.1f} tuile(s) restante(s), "
         f"{moyenne(resume['penalites_perdant']):.1f} point(s) de pénalité.")
    if resume["coups_invalides_total"]:
        print(f"  Coups invalides proposés par l'IA (repli pioche) : "
             f"{resume['coups_invalides_total']}")
    print(f"  Anomalies de conservation des tuiles (#187, attendu 0) : "
         f"{resume['anomalies_conservation_total']}")
    if resume["coups_tuiles_disparues_total"]:
        print(f"  *** ANOMALIE : {resume['coups_tuiles_disparues_total']} "
             f"coup(s) refusé(s) par le garde-fou anti-disparition de "
             f"tuiles (#187) — un niveau d'IA a proposé un plateau ayant "
             f"perdu des tuiles déjà posées. ***")

    print("-" * 70)
    print("  Temps de calcul par tour (décision IA), par niveau :")
    for niveau, temps in sorted(resume["temps_par_niveau"].items()):
        print(f"    {niveau:15s} : moyenne {moyenne(temps) * 1000:.1f} ms, "
             f"max {max(temps) * 1000:.1f} ms, sur {len(temps)} tour(s)")

    if tours_expert:
        budget_depasse = replis.get("budget_depasse", 0)
        autre = replis.get("autre", 0)
        total_replis = budget_depasse + replis_deps_absentes + autre
        aucun_coup = resume.get("aucun_coup_expert", 0)
        print(f"  Replis d'Expert sur la recherche arborescente, toute "
             f"cause : {total_replis}/{tours_expert} tour(s) "
             f"({total_replis / tours_expert * 100:.1f} %)")
        print(f"    — dont budget de temps réellement dépassé (#190, seule "
             f"cause visée par l'accélération) : {budget_depasse}/{tours_expert} "
             f"tour(s) ({budget_depasse / tours_expert * 100:.1f} %)")
        print(f"    — dont solveur exact indisponible (dépendances "
             f"absentes) : {replis_deps_absentes}/{tours_expert} tour(s) "
             f"({replis_deps_absentes / tours_expert * 100:.1f} %)")
        if autre:
            print(f"    — dont autre anomalie (résultat non valide ou "
                 f"exception, PAS un coup légitimement impossible) : "
                 f"{autre}/{tours_expert} tour(s) "
                 f"({autre / tours_expert * 100:.1f} %)")
        print(f"  Aucun coup possible (cas légitime, PAS un repli : le "
             f"modèle exact a prouvé qu'il n'y avait rien à jouer) : "
             f"{aucun_coup}/{tours_expert} tour(s) "
             f"({aucun_coup / tours_expert * 100:.1f} %)")

    stats_verif = resume.get("stats_verif_finition") or {}
    statuts_verif = {k: v for k, v in stats_verif.items() if k != "appels_par_tour"}
    if statuts_verif:
        statuts_executes = (
            verification_finition.BUDGET_EPUISE,
            verification_finition.APPLIQUEE_MEILLEUR_SUFFIT,
            verification_finition.APPLIQUEE_AUCUN_CANDIDAT,
            verification_finition.APPLIQUEE_AUTRE_COUP,
            verification_finition.APPLIQUEE_GARDE_JOKER,
        )
        tentes = sum(statuts_verif.get(c, 0) for c in statuts_executes)
        changes = (statuts_verif.get(verification_finition.APPLIQUEE_AUTRE_COUP, 0)
                  + statuts_verif.get(verification_finition.APPLIQUEE_GARDE_JOKER, 0))
        print("-" * 70)
        print("  Vérification de finition en fin de partie (#221, statuts "
             "affinés par #223, #225) :")
        for code in (
                verification_finition.NON_APPLICABLE,
                verification_finition.PAS_DE_COUP_A_COMPARER,
                verification_finition.SOLVEUR_NON_EXACT,
                verification_finition.BUDGET_EPUISE,
                verification_finition.APPLIQUEE_MEILLEUR_SUFFIT,
                verification_finition.APPLIQUEE_AUCUN_CANDIDAT,
                verification_finition.APPLIQUEE_AUTRE_COUP,
                verification_finition.APPLIQUEE_GARDE_JOKER):
            n = statuts_verif.get(code, 0)
            print(f"    {verification_finition.LIBELLES[code]:52s} : {n}")
        if tentes:
            print(f"    Fréquence d'activation (coup changé / tours où la "
                 f"vérification a tourné jusqu'au bout) : {changes}/{tentes} "
                 f"({changes / tentes * 100:.1f} %)")
        appels = stats_verif.get("appels_par_tour") or []
        if appels:
            print(f"    Appels supplémentaires au solveur par tour concerné : "
                 f"moyenne {moyenne(appels):.2f}, maximum {max(appels)}, "
                 f"sur {len(appels)} tour(s).")

    stats_gj = resume.get("stats_garde_joker") or {}
    if stats_gj.get("tours_joker_en_main"):
        tours_joker = stats_gj["tours_joker_en_main"]
        existe = stats_gj.get("candidat_existe", 0)
        permet = stats_gj.get("permet_de_finir", 0)
        choisi = stats_gj.get("choisi", 0)
        parties_gj = resume.get("parties_garde_joker") or []
        print("-" * 70)
        print("  Garder un joker en main en fin de partie (#225, Champion du "
             "Monde seul) :")
        print(f"    Coût d'un joker resté en main en fin de manche : "
             f"{resume.get('valeur_joker_penalite')} point(s) (réglage "
             f"\"valeur_joker_penalite\", défaut 30, configurable).")
        print(f"    Tours de fin de partie avec un joker en main : {tours_joker}")
        print(f"    Troisième candidat (garder le joker) construit : "
             f"{existe}/{tours_joker} tour(s)")
        print(f"    ... permettant de finir au tour suivant (évalué jusqu'au "
             f"bout seulement) : {permet}/{tours_joker} tour(s)")
        print(f"    ... choisi : {choisi}/{tours_joker} tour(s)")
        if parties_gj:
            gagnees = {}
            for p in parties_gj:
                v = p["vainqueur_niveau"] or "nulle"
                gagnees[v] = gagnees.get(v, 0) + 1
            detail = ", ".join(f"{v} : {n}" for v, n in sorted(gagnees.items()))
            print(f"    Parties où la stratégie a été CHOISIE au moins une "
                 f"fois : {len(parties_gj)} ({detail})")

    stats_rt = resume.get("stats_reserve_tuile") or {}
    if stats_rt.get("declenchee"):
        declenchee_rt = stats_rt["declenchee"]
        choisi_rt = stats_rt.get("choisi", 0)
        gardees = stats_rt.get("nb_tuiles_gardees_liste") or []
        print("-" * 70)
        print("  Réserve d'une tuile (#229, hypothèse H2, Champion du Monde "
             "seul) :")
        print(f"    Tours examinés : {declenchee_rt}")
        print(f"    ... coup changé (conditions (a)-(d) réunies) : "
             f"{choisi_rt}/{declenchee_rt} tour(s)")
        if gardees:
            print(f"    Tuiles gardées par coup changé : moyenne "
                 f"{moyenne(gardees):.2f}, sur {len(gardees)} coup(s).")
        print(f"    ... pioche évitée au tour suivant du même joueur : "
             f"{stats_rt.get('pioche_evitee', 0)}/{choisi_rt} coup(s) changé(s)")
        print(f"    ... tuile gardée effectivement posée au tour suivant : "
             f"{stats_rt.get('tuile_gardee_posee', 0)}/{choisi_rt} coup(s) changé(s)")

    stats_rd = resume.get("stats_retenue_debut") or {}
    if stats_rd.get("declenchee"):
        declenchee_rd = stats_rd["declenchee"]
        print("-" * 70)
        print("  Retenue au début (#229, hypothèse H1, Champion du Monde "
             "seul) :")
        print(f"    Tours examinés (fenêtre d'ouverture) : {declenchee_rd}")
        print(f"    ... coup plafonné : {stats_rd.get('choisi', 0)}/"
             f"{declenchee_rd} tour(s)")

    compteurs = compteurs_strategies(resume)
    if any(c["declenchee"] for c in compteurs.values()):
        print("-" * 70)
        print("  Compteurs génériques par stratégie (registre, #228) :")
        for sid, c in compteurs.items():
            strat = niveaux.STRATEGIES[sid]
            print(f"    {sid:15s} : déclenchée {c['declenchee']}, a changé "
                 f"le coup {c['a_change_le_coup']} — {strat.description}")

    perturbations = resume["perturbations_expert"]
    if perturbations:
        deplacees = [d for d, _ in perturbations]
        modifiees = [m for _, m in perturbations]
        reglage = "activé" if resume["preferer_simple"] else "désactivé"
        print(f"  Perturbation du plateau par coup d'Expert (#199, "
             f"preferer_simple {reglage}) : en moyenne "
             f"{moyenne(deplacees):.2f} tuile(s) déplacée(s) et "
             f"{moyenne(modifiees):.2f} combinaison(s) modifiée(s), "
             f"sur {len(perturbations)} coup(s) posé(s) par Expert.")
    print("=" * 70)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Compare deux niveaux d'IA Rummikub sur un grand nombre "
                    "de parties à 2 joueurs (sans interface).")
    parser.add_argument("--niveau-a", required=True, choices=NIVEAUX,
                        help="Premier niveau à comparer.")
    parser.add_argument("--niveau-b", required=True, choices=NIVEAUX,
                        help="Second niveau à comparer.")
    parser.add_argument("--donnes", type=int, default=50,
                        help="Nombre de donnes distinctes (défaut 50 ; "
                             "chacune jouée 2 fois en miroir).")
    parser.add_argument("--seed", type=int, default=0,
                        help="Graine aléatoire (défaut 0, reproductible).")
    parser.add_argument("--manches", type=int, default=1,
                        help="Nombre de manches par match (défaut 1 ; "
                             "vainqueur du match = plus haut score cumulé).")
    parser.add_argument("--max-tours", type=int, default=300,
                        help="Garde-fou anti-blocage par manche (défaut 300).")
    parser.add_argument("--sans-preferer-simple", action="store_true",
                        help="Désactive le critère de simplicité du "
                             "solveur Expert (#199, activé par défaut) — "
                             "pour comparer les deux versions par "
                             "simulation (relancer la même commande avec "
                             "et sans ce drapeau, même --seed).")
    parser.add_argument("--eval-a", default="off",
                        help="Preset d'évaluation de la main restante (#211) "
                             "pour l'Expert du camp A (défaut off). Presets : "
                             + ", ".join(evaluation_main.PRESETS) + " ; suffixe "
                             "-avant/-apres pour la position vs la simplicité.")
    parser.add_argument("--eval-b", default="off",
                        help="Preset d'évaluation de la main restante (#211) "
                             "pour l'Expert du camp B (défaut off).")
    parser.add_argument("--sans-exact", action="store_true",
                        help="Fige Expert sur son ANCIENNE recherche "
                             "arborescente (moteur/solveur.py) au lieu du "
                             "modèle exact HiGHS (#206) — pour la campagne "
                             "« avant / après » (relancer la même commande "
                             "avec et sans ce drapeau, même --seed).")
    parser.add_argument("--sans-verif-finition", action="store_true",
                        help="Désactive la vérification de finition en fin "
                             "de partie (#221, activée par défaut pour "
                             "Expert et Champion du Monde) — pour la "
                             "campagne « avant / après » (relancer la même "
                             "commande avec et sans ce drapeau, même "
                             "--seed).")
    parser.add_argument("--sans-garde-joker", action="store_true",
                        help="Désactive « garder un joker en main » en fin "
                             "de partie (#225, activée par défaut pour "
                             "Champion du Monde SEUL — Expert n'y a jamais "
                             "eu droit) — pour comparer Champion du Monde "
                             "avec et sans cette stratégie (relancer la "
                             "même commande avec et sans ce drapeau, même "
                             "--seed).")
    parser.add_argument("--strategies-champion", default=None,
                        help="Stratégies ACTIVES pour Champion du Monde "
                             "PENDANT la campagne (issue #228), remplace la "
                             "liste par défaut sans jamais toucher au jeu : "
                             "une liste séparée par des virgules, ou "
                             "'aucune'/'defaut' (= ce que joue le jeu, "
                             "défaut de cette option)/'toutes'. Noms valides "
                             "du registre (moteur/niveaux.py) : "
                             + ", ".join(niveaux.strategies_champion_valides())
                             + ".")
    parser.add_argument("--sans-strategie", action="append", default=[],
                        metavar="NOM",
                        help="Retire NOM (répétable) de la liste de "
                             "stratégies de Champion du Monde pour cette "
                             "campagne, appliqué APRÈS --strategies-champion "
                             "(issue #228) — p. ex. --sans-strategie "
                             "garde_joker.")
    parser.add_argument("--budget-solveur-expert", type=float, default=None,
                        help="Budget de temps du solveur par coup, en "
                             "secondes, appliqué à TOUS les niveaux joués "
                             "(issue #228, point 5) — défaut : celui du jeu "
                             "(1,5 s, ia.BUDGET_TEMPS_EXPERT), inchangé sans "
                             "cette option. À relever sur une machine lente "
                             "(appliquer la MÊME valeur à tous les bras "
                             "d'une même série de comparaisons, voir "
                             "scripts/matrice_strategies.py).")
    parser.add_argument("--export-resultats",
                        help="Écrit un fichier JSON Lines (une ligne par "
                             "match : donne, ordre, vainqueur, scores) — "
                             "pour comparer deux campagnes identiques (même "
                             "--seed) avec "
                             "scripts/comparer_campagnes_appariees.py (#225, "
                             "point 5bis).")
    parser.add_argument("--export-trace",
                        help="Écrit une trace BRUTE JSON Lines, une ligne "
                             "par tour de chaque manche + une ligne de "
                             "résultat par manche — pour l'analyse par "
                             "phases avec scripts/analyser_phases.py "
                             "(#226). Indépendant de --export-resultats ; "
                             "désactivé par défaut (aucun changement de "
                             "comportement sans cette option).")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Journalise chaque partie jouée.")
    args = parser.parse_args(argv[1:])

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )
    if args.verbose:
        logger.setLevel(logging.INFO)

    if args.manches < 1:
        parser.error("--manches doit être au moins 1")

    # Échec franc sans solveur exact (issue #223, point 1) : AVANT toute
    # autre validation, sauf désactivation volontaire et assumée
    # (--sans-exact). Voir l'incident documenté dans _verif_solveur_exact.py.
    exiger_solveur_exact_ou_quitter(sans_exact=args.sans_exact)

    if args.sans_exact:
        # Rejoue le comportement d'avant #206 : Expert n'utilise que la
        # recherche arborescente (modèle exact HiGHS désactivé globalement).
        from rummikub.moteur import ia as _ia
        _ia.UTILISER_SOLVEUR_EXACT = False
        print("[#206] Modèle exact DÉSACTIVÉ (Expert = recherche arborescente).")

    # Validation précoce des presets d'évaluation (message clair).
    try:
        evaluation_main.depuis_preset(args.eval_a, args.manches)
        evaluation_main.depuis_preset(args.eval_b, args.manches)
    except ValueError as exc:
        parser.error(str(exc))

    if args.sans_verif_finition:
        print("[#221] Vérification de finition en fin de partie DÉSACTIVÉE "
             "(Expert/Champion du Monde).")
    if args.sans_garde_joker:
        print("[#225] « Garder un joker en main » DÉSACTIVÉE (Champion du "
             "Monde).")
    if args.export_trace:
        print(f"[#226] Trace brute par tour activée : {args.export_trace}")

    # Option unique de stratégies de Champion du Monde (issue #228, point 2) :
    # --strategies-champion fixe la base (défaut : ce que joue le jeu),
    # --sans-strategie en retire ensuite — validation précoce, message
    # listant les noms valides sur un nom inconnu.
    try:
        strategies_champion = _parser_strategies_champion(args.strategies_champion)
        if args.sans_strategie:
            niveaux.valider_noms_strategies(args.sans_strategie)
            strategies_champion -= set(args.sans_strategie)
    except ValueError as exc:
        parser.error(str(exc))
    champion_personnalise = bool(args.strategies_champion) or bool(args.sans_strategie)
    if champion_personnalise:
        print(f"[#228] Stratégies de Champion du Monde pour cette campagne : "
             f"{', '.join(sorted(strategies_champion)) or '(aucune)'}.")

    debut = time.monotonic()
    with (_strategies_champion_forcees(strategies_champion)
          if champion_personnalise else contextlib.nullcontext()), \
         (_verif_finition_desactivee() if args.sans_verif_finition
          else contextlib.nullcontext()), \
         (_garde_joker_desactive() if args.sans_garde_joker
          else contextlib.nullcontext()):
        resume = comparer(args.niveau_a, args.niveau_b, args.donnes, args.seed,
                          args.max_tours, nb_manches=args.manches,
                          preferer_simple=not args.sans_preferer_simple,
                          eval_a=args.eval_a, eval_b=args.eval_b,
                          sans_exact=args.sans_exact,
                          export_resultats=args.export_resultats,
                          export_trace=args.export_trace,
                          budget_temps=args.budget_solveur_expert)
    duree = time.monotonic() - debut

    afficher_rapport(resume)
    print(f"Temps total de la campagne : {duree:.1f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
