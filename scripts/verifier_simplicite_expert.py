#!/usr/bin/env python3
"""Vérifie qu'Expert ne décompose jamais le plateau INUTILEMENT (issue #215,
suite de #199) et produit un fichier d'exemples lisibles par un non-programmeur.

Contexte
--------
Le profil d'Expert (``scripts/profil_joueur.py``) montre qu'environ deux tiers
de ses poses sont « grandes » (elles touchent 3 combinaisons du plateau ou
plus). Question d'Alain : ces grosses recompositions sont-elles toutes
NÉCESSAIRES, ou l'IA décompose-t-elle parfois le plateau pour rien ?

Le solveur d'Expert est censé l'éviter depuis #199 : « à nombre de tuiles
posées égal, préférer le coup qui perturbe le moins le plateau » (critère de
simplicité, ``moteur/solveur.mesurer_perturbation`` pour la MESURE, départage
dans ``moteur/solveur_exact.py`` pour le CALCUL). Ce script le vérifie de façon
SYSTÉMATIQUE, sur un ensemble de coups réels (journaux) ou simulés, plutôt que
sur quelques cas isolés.

Principe de la vérification
---------------------------
Pour chaque coup de pose d'Expert :

  1. on mesure la perturbation du coup RÉELLEMENT joué, ``mesurer_perturbation``
     (#199) : ``(tuiles du plateau déplacées, combinaisons modifiées)`` entre
     le plateau d'avant et le plateau d'après ;
  2. on interroge INDÉPENDAMMENT le solveur (le modèle EXACT maison
     ``moteur/solveur_exact`` s'il est disponible, sinon la recherche
     arborescente ``moteur/solveur``) avec un budget de temps GÉNÉREUX pour
     obtenir « le coup le plus simple qui pose le plus de tuiles » — à savoir
     le maximum de tuiles posables ce tour, puis, à ce nombre de tuiles,
     la perturbation minimale ;
  3. quand le coup d'Expert pose le MÊME nombre de tuiles que cet optimum
     (le cas normal — Expert maximise toujours le nombre de tuiles), on compare
     leurs deux perturbations : l'écart dit si Expert a décomposé plus que le
     strict nécessaire pour poser autant de tuiles.

Un écart nul (ou négatif) signifie qu'Expert est DÉJÀ au minimum de
perturbation : décomposition nécessaire. Un écart positif signale une
décomposition évitable — le critère de #199 n'a pas joué pour ce coup (budget de
production épuisé avant le départage, ou limite de l'algorithme). Conformément à
l'issue, ce script NE CORRIGE PAS le solveur : il se contente de SIGNALER ces
cas (une correction éventuelle fera l'objet d'une issue dédiée).

AVERTISSEMENT (comme ``persistance/coups_rates.py``) : l'optimum « généreux »
reste un budget de temps fini ; sur un plateau très chargé il peut lui-même ne
pas être prouvé. La mesure ``mesurer_perturbation`` est de plus une
approximation gloutonne (voir sa docstring) : un écart de 1 combinaison sur un
coup par ailleurs identique peut refléter la mesure plutôt qu'une vraie
décomposition superflue. Le fichier d'exemples montre TOUT le plateau avant et
après pour qu'Alain juge lui-même les cas douteux.

Deux sources de coups
---------------------
  (a) JOURNAUX — ``--journaux DIR`` : rejoue les poses d'Expert lues dans les
      journaux ``partie_*.json`` (fichiers d'une même partie reliés comme #202,
      ``persistance/parties_liees``). L'agent n'a pas accès aux journaux
      d'Alain : ce chemin se dégrade proprement si le dossier est absent/vide
      (message clair + la commande exacte à lancer).
  (b) SIMULATION — défaut si aucun journal : fait jouer Expert contre lui-même
      (``moteur``, jamais pywebview) et analyse chacune de ses poses.

Usage
-----
    # Simulation (fonctionne sans aucun journal) :
    PYTHONPATH=src python3 scripts/verifier_simplicite_expert.py --donnes 10

    # Sur les journaux d'Alain (commande à lancer par Alain, journaux activés) :
    PYTHONPATH=src python3 scripts/verifier_simplicite_expert.py \
        --journaux data/logs_parties --sortie /tmp/simplicite_expert

Le fichier d'exemples ``exemples_simplicite_expert.txt`` est écrit dans le
dossier de SORTIE (``--sortie``, par défaut un sous-dossier du répertoire
temporaire du système) — JAMAIS dans le dépôt.
"""

import argparse
import logging
import random
import sys
import tempfile
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "src"
SCRIPTS = RACINE / "scripts"
for _p in (SRC, SCRIPTS):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rummikub.config import NIVEAUX  # noqa: E402
from rummikub.moteur import description_coup  # noqa: E402
from rummikub.moteur import solveur as solveur_recherche  # noqa: E402
from rummikub.moteur import solveur_exact  # noqa: E402
from rummikub.moteur.solveur import mesurer_perturbation  # noqa: E402
from rummikub.moteur.ia import jouer_ia  # noqa: E402
from rummikub.moteur.partie import (  # noqa: E402
    annuler_tour, backup_debut_tour, creer_partie, jouer_tour, passer_tour,
    piocher,
)

logger = logging.getLogger("verifier_simplicite_expert")

# Budget généreux (s) du JUGE indépendant par coup — plus large que le budget de
# production d'Expert (1,5 s) pour que l'optimum de simplicité soit, autant que
# possible, PROUVÉ et non limité par le temps. À monter (--budget-juge) pour une
# mesure plus sûre sur de gros états, au prix de la durée.
BUDGET_JUGE_DEFAUT = 5.0

NIVEAU_EXPERT = "Expert"


# --------------------------------------------------------------------------- #
# Description lisible (français, sans jargon) d'une combinaison et du plateau.
# --------------------------------------------------------------------------- #

def _valeurs_suite(combo: list) -> list:
    """Valeurs (joker compris, à sa position) d'une suite, dans l'ordre —
    déduites de la première tuile réelle et de sa position, comme
    ``description_coup._decrire_combo``."""
    reels = [(i, t) for i, t in enumerate(combo) if not t.get("est_joker")]
    if not reels:
        return []
    i0, t0 = reels[0]
    base = t0["valeur"] - i0
    return [base + i for i in range(len(combo))]


def decrire_combinaison(combo: list) -> str:
    """Décrit UNE combinaison en français clair et complet, lisible par un
    non-programmeur (issue #215) :
      - groupe : « groupe de 9 (bleu, jaune, noir) » ;
      - suite  : « suite rouge 5-6-7 » (un joker est écrit « joker » à sa
        position, ex. « suite bleue 4-joker-6 »).
    Repère le type avec le validateur du moteur ; se rabat sur une énumération
    nue si la combinaison n'est pas valide (ne devrait pas arriver sur un
    plateau réel)."""
    from rummikub.moteur.tuiles import tuile_depuis_dict
    from rummikub.moteur.validation import valider_combinaison

    objs = [tuile_depuis_dict(d) for d in combo]
    info = valider_combinaison(objs)
    type_ = info.get("type")

    if type_ == "groupe":
        valeur = next((t["valeur"] for t in combo if not t.get("est_joker")), None)
        couleurs = ["joker" if t.get("est_joker") else t["couleur"] for t in combo]
        return f"groupe de {valeur} ({', '.join(couleurs)})"

    if type_ == "suite":
        couleur = next((t["couleur"] for t in combo if not t.get("est_joker")), None)
        couleur_f = description_coup._couleur_suite(couleur)
        valeurs = _valeurs_suite(combo)
        morceaux = ["joker" if t.get("est_joker") else str(v)
                    for t, v in zip(combo, valeurs)]
        return f"suite {couleur_f} {'-'.join(morceaux)}"

    # Combinaison invalide (cas théorique) : énumération nue.
    return "combinaison " + ", ".join(description_coup._decrire_tuile(t) for t in combo)


def decrire_plateau(plateau: list) -> list:
    """Liste de descriptions, UNE par combinaison du plateau, triées pour une
    lecture stable (par type puis valeur/couleur). Un plateau vide renvoie une
    liste vide (l'appelant affiche « (plateau vide) »)."""
    descriptions = [decrire_combinaison(combo) for combo in plateau if combo]
    return sorted(descriptions)


def decrire_main(chevalet: list) -> str:
    """Énumère toutes les tuiles de la main, triées (couleur puis valeur,
    jokers en fin), pour une lecture lisible."""
    def cle(t):
        return (bool(t.get("est_joker")), t.get("couleur") or "",
                t.get("valeur") or 0)
    tuiles = sorted(chevalet, key=cle)
    return ", ".join(description_coup._decrire_tuile(t) for t in tuiles)


# --------------------------------------------------------------------------- #
# Mesure de perturbation et comparaison d'un coup réel à l'optimum de simplicité.
# --------------------------------------------------------------------------- #

def perturbation(plateau_avant: list, plateau_apres: list) -> tuple:
    """``(tuiles déplacées, combinaisons modifiées)`` entre deux états, mesure
    #199 (``moteur/solveur.mesurer_perturbation``)."""
    return mesurer_perturbation(plateau_avant or [], plateau_apres or [])


def evaluer_simplicite(plateau_avant: list, plateau_apres_reel: list,
                       nb_tuiles_reel: int, plateau_apres_opt, nb_tuiles_opt) -> dict:
    """Compare le coup réellement joué par Expert au coup le plus simple posant
    le même nombre de tuiles (l'optimum trouvé par le juge indépendant).

    Retourne un dict :
      - ``pert_reel`` / ``pert_opt`` : ``(déplacées, modifiées)`` de chaque coup ;
      - ``comparable`` : vrai seulement si l'optimum pose EXACTEMENT autant de
        tuiles que le coup réel (sinon la comparaison de perturbation n'a pas de
        sens — plus de tuiles perturbe naturellement davantage) ;
      - ``ecart_deplacees`` / ``ecart_combos`` : coup réel moins optimum (≥ 0
        attendu : l'optimum est le minimum) — ``None`` si non comparable ;
      - ``minimal`` : vrai si Expert ne déplace pas plus de tuiles que
        l'optimum (décomposition nécessaire) ;
      - ``evitable`` : vrai si Expert déplace STRICTEMENT plus de tuiles
        (décomposition évitable) ;
      - ``optimum_absent`` : vrai si le juge n'a trouvé aucun optimum
        exploitable (budget épuisé, dépendances absentes) ;
      - ``moins_que_optimum`` : vrai si Expert a posé MOINS de tuiles que
        l'optimum (hors sujet de la simplicité : question de « coup raté » /
        budget, voir ``coups_rates`` — comptée à part)."""
    pert_reel = perturbation(plateau_avant, plateau_apres_reel)
    resultat = {
        "pert_reel": pert_reel,
        "pert_opt": None,
        "nb_tuiles_reel": nb_tuiles_reel,
        "nb_tuiles_opt": nb_tuiles_opt,
        "comparable": False,
        "ecart_deplacees": None,
        "ecart_combos": None,
        "minimal": False,
        "evitable": False,
        "optimum_absent": plateau_apres_opt is None,
        "moins_que_optimum": False,
    }
    if plateau_apres_opt is None or nb_tuiles_opt is None:
        return resultat

    pert_opt = perturbation(plateau_avant, plateau_apres_opt)
    resultat["pert_opt"] = pert_opt

    if nb_tuiles_reel < nb_tuiles_opt:
        # Expert a posé moins de tuiles que le maximum : ce n'est pas une
        # question de simplicité (plutôt budget/coup raté) — comptée à part.
        resultat["moins_que_optimum"] = True
        return resultat
    if nb_tuiles_reel > nb_tuiles_opt:
        # Le juge (budget fini) a trouvé moins de tuiles qu'Expert : optimum non
        # fiable pour ce coup, on ne compare pas.
        resultat["optimum_absent"] = True
        return resultat

    # Même nombre de tuiles : comparaison de perturbation légitime.
    resultat["comparable"] = True
    ecart_deplacees = pert_reel[0] - pert_opt[0]
    ecart_combos = pert_reel[1] - pert_opt[1]
    resultat["ecart_deplacees"] = ecart_deplacees
    resultat["ecart_combos"] = ecart_combos
    resultat["minimal"] = ecart_deplacees <= 0
    resultat["evitable"] = ecart_deplacees > 0
    return resultat


# --------------------------------------------------------------------------- #
# Juge indépendant : le coup le plus simple posant le plus de tuiles.
# --------------------------------------------------------------------------- #

def juge_optimum(etat: dict, idx: int, budget_temps: float):
    """Interroge le solveur, indépendamment du coup joué par Expert, pour
    obtenir le coup le plus simple posant le plus de tuiles (max de tuiles, puis
    perturbation minimale — critère #199). Préfère le modèle EXACT maison
    (``solveur_exact``, qui prouve l'optimum) ; se replie sur la recherche
    arborescente (``solveur``) si ``highspy``/``numpy`` manque.

    Retourne ``(nouveau_plateau, nb_tuiles)`` ou ``(None, None)`` si rien n'est
    posable ou si le budget est épuisé sans solution (prudence : absence de
    preuve, pas preuve d'absence)."""
    if solveur_exact.DISPONIBLE:
        try:
            coup = solveur_exact.resoudre_coup_exact(
                etat, idx, budget_temps=budget_temps, preferer_simple=True)
        except solveur_exact.BudgetExactDepasse:
            coup = None
        except Exception:
            logger.exception("Juge exact en échec — repli recherche")
            coup = None
        if coup is not None:
            return coup["nouveau_plateau"], len(coup["ids_tuiles"])
        # Le modèle exact peut renvoyer None (rien de posable OU repli) : on
        # tente quand même la recherche arborescente ci-dessous, par prudence.
    try:
        coup = solveur_recherche.resoudre_coup(
            etat, idx, budget_temps=budget_temps, preferer_simple=True)
    except solveur_recherche.BudgetDepasse:
        return None, None
    if coup is None:
        return None, None
    return coup["nouveau_plateau"], len(coup["ids_tuiles"])


# --------------------------------------------------------------------------- #
# Un enregistrement d'analyse par coup de pose d'Expert.
# --------------------------------------------------------------------------- #

def analyser_coup(plateau_avant: list, plateau_apres_reel: list, chevalet: list,
                  etat: dict, idx: int, nom: str, tour, budget_juge: float) -> dict:
    """Construit l'enregistrement complet d'un coup : mesure du coup réel,
    optimum du juge, écart de simplicité, taille (combinaisons touchées) et
    descriptions françaises prêtes pour le fichier d'exemples."""
    mesure = description_coup.mesurer_coup_ia(plateau_avant, plateau_apres_reel)
    nb_touchees = (mesure["nb_combinaisons_modifiees"]
                   + mesure["nb_combinaisons_creees"])
    nb_tuiles_reel = mesure["nb_tuiles_posees"]

    plateau_apres_opt, nb_tuiles_opt = juge_optimum(etat, idx, budget_juge)
    eva = evaluer_simplicite(plateau_avant, plateau_apres_reel, nb_tuiles_reel,
                             plateau_apres_opt, nb_tuiles_opt)

    resume = description_coup.decrire_coup_ia(plateau_avant, plateau_apres_reel,
                                              nom=nom)
    etapes = description_coup.etapes_coup_ia(plateau_avant, plateau_apres_reel,
                                             mode="modification")

    description_opt = None
    if plateau_apres_opt is not None:
        description_opt = description_coup.decrire_coup_ia(
            plateau_avant, plateau_apres_opt, nom=nom)

    if nb_touchees <= 1:
        taille = "petit"
    elif nb_touchees == 2:
        taille = "moyen"
    else:
        taille = "grand"

    return {
        "tour": tour,
        "nom": nom,
        "plateau_avant": plateau_avant,
        "plateau_apres_reel": plateau_apres_reel,
        "plateau_apres_opt": plateau_apres_opt,
        "chevalet": chevalet,
        "nb_tuiles_reel": nb_tuiles_reel,
        "nb_tuiles_opt": nb_tuiles_opt,
        "nb_combinaisons_touchees": nb_touchees,
        "nb_tuiles_plateau_deplacees": mesure["nb_tuiles_plateau_deplacees"],
        "taille": taille,
        "resume_reel": resume,
        "etapes_reel": etapes,
        "description_opt": description_opt,
        "eval": eva,
    }


# --------------------------------------------------------------------------- #
# Collecte des coups : simulation Expert contre lui-même.
# --------------------------------------------------------------------------- #

def collecter_depuis_simulation(nb_donnes: int, seed: int, max_tours: int,
                                budget_juge: float) -> list:
    """Simule ``nb_donnes`` parties d'Expert en miroir (deux sièges Expert) et
    renvoie la liste des enregistrements (:func:`analyser_coup`) de toutes ses
    poses. Reproductible pour une graine donnée."""
    enregistrements = []
    rng_graines = random.Random(seed)

    for n in range(nb_donnes):
        graine = rng_graines.randrange(2 ** 32)
        random.seed(graine)
        config_joueurs = [
            {"nom": f"Expert#0", "est_ia": True, "niveau": NIVEAU_EXPERT},
            {"nom": f"Expert#1", "est_ia": True, "niveau": NIVEAU_EXPERT},
        ]
        etat = creer_partie(config_joueurs,
                            {"nb_manches": 1, "graine_ia": graine})
        backup_debut_tour(etat)

        tours = 0
        while not etat["manche_terminee"]:
            tours += 1
            if tours > max_tours:
                break
            idx = etat["index_joueur_actuel"]
            etat = _jouer_et_analyser(etat, idx, enregistrements, budget_juge)
            backup_debut_tour(etat)
        logger.info("Partie %d/%d simulée (%d tours, %d poses cumulées)",
                    n + 1, nb_donnes, tours, len(enregistrements))
    return enregistrements


def _jouer_et_analyser(etat: dict, idx: int, enregistrements: list,
                       budget_juge: float) -> dict:
    """Joue un tour d'Expert (``jouer_ia``, comportement de production) et, si
    c'est une POSE, l'analyse avant de passer au tour suivant. Même repli que
    l'UI/les simulations existantes en cas de coup invalide (pioche de
    secours)."""
    import copy

    plateau_avant = copy.deepcopy(etat["plateau"])
    nom = etat["joueurs"][idx]["nom"]
    chevalet_avant = copy.deepcopy(etat["joueurs"][idx]["chevalet"])
    tour = etat.get("tour_numero")
    # État figé AVANT le coup, pour interroger le juge indépendamment du coup
    # qu'Expert choisira (le juge lit chevalet/plateau/mise initiale).
    etat_avant = copy.deepcopy(etat)

    backup_debut_tour(etat)
    try:
        res_ia = jouer_ia(etat, idx)
    except Exception:
        logger.exception("Exception IA au tour %s", tour)
        annuler_tour(etat)
        return piocher(etat)["etat"]

    action = res_ia.get("action")
    if action == "jouer":
        res = jouer_tour(etat, res_ia["ids_tuiles"], res_ia["nouveau_plateau"])
        if res["ok"]:
            enr = analyser_coup(plateau_avant, res_ia["nouveau_plateau"],
                                chevalet_avant, etat_avant, idx, nom, tour,
                                budget_juge)
            enregistrements.append(enr)
            return res["etat"]
        annuler_tour(etat)
        return piocher(etat)["etat"]
    if action == "piocher":
        return piocher(etat)["etat"]
    if action == "passer":
        return passer_tour(etat)["etat"]
    annuler_tour(etat)
    return piocher(etat)["etat"]


# --------------------------------------------------------------------------- #
# Collecte des coups : journaux de parties réelles (comme #202).
# --------------------------------------------------------------------------- #

def collecter_depuis_journaux(dossier: Path, budget_juge: float) -> list | None:
    """Rejoue les poses d'Expert lues dans les journaux de ``dossier`` (fichiers
    d'une même partie reliés comme #202) et renvoie leurs enregistrements.
    Retourne ``None`` si aucun journal exploitable (dossier absent/vide) — le
    chemin se dégrade proprement (message + commande à lancer)."""
    from rummikub.persistance.bilan import charger_journal, lister_journaux
    from rummikub.persistance.coups_rates import extraire_decisions_ia_toutes
    from rummikub.persistance.parties_liees import fusionner_journaux

    if not dossier.is_dir():
        return None

    journaux = []
    for chemin in lister_journaux(dossier):
        data = charger_journal(chemin)
        if data is not None:
            journaux.append({"nom": chemin.name, "data": data})
    if not journaux:
        return None

    enregistrements = []
    for partie in fusionner_journaux(journaux):
        decisions = extraire_decisions_ia_toutes(
            partie["data"], partie["debut_present"])
        for d in decisions:
            if d.get("niveau") != NIVEAU_EXPERT or d.get("action") != "pose":
                continue
            if d.get("moment") == "inconnu" or d.get("mise_initiale_inconnue"):
                continue
            plateau_apres_reel = d.get("plateau_apres_reel")
            if plateau_apres_reel is None:
                continue
            plateau_avant = d["etat"].get("plateau") or []
            chevalet = d["etat"]["joueurs"][d["idx"]]["chevalet"]
            enr = analyser_coup(plateau_avant, plateau_apres_reel, chevalet,
                                d["etat"], d["idx"], d.get("nom"), d.get("tour"),
                                budget_juge)
            enregistrements.append(enr)
    return enregistrements


# --------------------------------------------------------------------------- #
# Synthèse chiffrée.
# --------------------------------------------------------------------------- #

def resumer(enregistrements: list) -> dict:
    """Agrège les écarts de simplicité par taille de coup et globalement."""
    resume = {
        "total": len(enregistrements),
        "comparables": 0,
        "minimaux": 0,
        "evitables": 0,
        "moins_que_optimum": 0,
        "optimum_absent": 0,
        "ecarts_deplacees": [],      # écarts (>0) des coups évitables
        "ecarts_combos": [],
        "par_taille": {},            # taille -> {total, comparables, minimaux, evitables}
    }
    for enr in enregistrements:
        eva = enr["eval"]
        taille = enr["taille"]
        bucket = resume["par_taille"].setdefault(
            taille, {"total": 0, "comparables": 0, "minimaux": 0, "evitables": 0})
        bucket["total"] += 1
        if eva["moins_que_optimum"]:
            resume["moins_que_optimum"] += 1
            continue
        if eva["optimum_absent"] or not eva["comparable"]:
            resume["optimum_absent"] += 1
            continue
        resume["comparables"] += 1
        bucket["comparables"] += 1
        if eva["evitable"]:
            resume["evitables"] += 1
            bucket["evitables"] += 1
            resume["ecarts_deplacees"].append(eva["ecart_deplacees"])
            resume["ecarts_combos"].append(eva["ecart_combos"])
        else:
            resume["minimaux"] += 1
            bucket["minimaux"] += 1
    return resume


def _pct(n, d):
    return f"{100 * n / d:.1f} %" if d else "n/a"


def afficher_resume(resume: dict) -> None:
    print("=" * 78)
    print("VÉRIFICATION DE LA SIMPLICITÉ DES COUPS D'EXPERT (issue #215, suite #199)")
    print("-" * 78)
    print(f"Poses d'Expert analysées            : {resume['total']}")
    print(f"  dont comparables (même nb tuiles) : {resume['comparables']}")
    print(f"  dont « a posé moins que l'optimum » (budget/coup raté, hors sujet) : "
          f"{resume['moins_que_optimum']}")
    print(f"  dont optimum indéterminé (budget) : {resume['optimum_absent']}")
    print("-" * 78)
    comp = resume["comparables"]
    print(f"Coups DÉJÀ au minimum de perturbation (décomposition nécessaire) : "
          f"{resume['minimaux']} / {comp}  ({_pct(resume['minimaux'], comp)})")
    print(f"Coups qui décomposent PLUS que nécessaire (décomposition évitable) : "
          f"{resume['evitables']} / {comp}  ({_pct(resume['evitables'], comp)})")
    if resume["ecarts_deplacees"]:
        ed = resume["ecarts_deplacees"]
        ec = resume["ecarts_combos"]
        print(f"  Écart de tuiles déplacées (coups évitables) : "
              f"moyen {sum(ed) / len(ed):.2f}, max {max(ed)}")
        print(f"  Écart de combinaisons modifiées            : "
              f"moyen {sum(ec) / len(ec):.2f}, max {max(ec)}")
    print("-" * 78)
    print("Répartition par taille de coup (combinaisons touchées) :")
    for taille in ("petit", "moyen", "grand"):
        b = resume["par_taille"].get(taille)
        if not b:
            continue
        print(f"  {taille:<6s} : {b['total']:>4d} coups | comparables {b['comparables']:>4d} "
              f"| nécessaires {b['minimaux']:>4d} | évitables {b['evitables']:>4d} "
              f"({_pct(b['evitables'], b['comparables'])})")
    grand = resume["par_taille"].get("grand")
    if grand and grand["comparables"]:
        part_necessaires = _pct(grand["minimaux"], grand["comparables"])
        print("-" * 78)
        print(f"RÉPONSE À LA QUESTION D'ALAIN : parmi les GROS coups d'Expert "
              f"(3 combinaisons ou plus),")
        print(f"{part_necessaires} sont des décompositions NÉCESSAIRES "
              f"(impossible de poser autant de tuiles plus simplement).")
        if grand["evitables"] == 0:
            print("Aucune décomposition évitable détectée : le critère de "
                  "simplicité de #199 tient ses promesses sur cet échantillon.")
        else:
            print(f"{grand['evitables']} gros coup(s) décomposent plus que "
                  f"nécessaire — signalés dans le fichier d'exemples (voir #199, "
                  f"correction = issue dédiée).")
    print("=" * 78)


# --------------------------------------------------------------------------- #
# Fichier d'exemples lisibles pour Alain.
# --------------------------------------------------------------------------- #

def choisir_exemples(enregistrements: list, nb_max: int = 10) -> list:
    """Choisit une dizaine de cas VARIÉS (petits, moyens, grands ; au moins un
    où Expert décompose beaucoup ; les décompositions évitables en priorité si
    elles existent), en évitant de répéter dix fois le même schéma."""
    comparables = [e for e in enregistrements if e["eval"]["comparable"]]
    evitables = [e for e in comparables if e["eval"]["evitable"]]

    choisis = []
    vus = set()

    def signature(e):
        # Schéma d'un cas : taille, nb de tuiles posées, nb de combos du plateau.
        return (e["taille"], e["nb_tuiles_reel"], len(e["plateau_avant"]))

    def ajouter(e):
        sig = signature(e)
        if sig in vus or e in choisis:
            return False
        vus.add(sig)
        choisis.append(e)
        return True

    # 1) Toutes les décompositions évitables (le cas le plus intéressant),
    #    triées par écart décroissant — on veut les montrer en priorité.
    for e in sorted(evitables, key=lambda e: e["eval"]["ecart_deplacees"],
                    reverse=True):
        if len(choisis) >= nb_max:
            break
        ajouter(e)

    # 2) Le coup qui décompose LE PLUS (plus grand nombre de combinaisons
    #    touchées) — le « gros coup » demandé explicitement par l'issue.
    if comparables:
        ajouter(max(comparables, key=lambda e: e["nb_combinaisons_touchees"]))

    # 3) Un échantillon ÉQUILIBRÉ par taille (des petits, des moyens, des
    #    grands) : tour à tour un cas de chaque taille, jamais dix fois le même
    #    schéma. Chaque pool est trié pour couvrir un éventail de nombres de
    #    tuiles posées.
    pools = {}
    for taille in ("petit", "moyen", "grand"):
        pool = [e for e in comparables if e["taille"] == taille]
        pool.sort(key=lambda e: (e["nb_tuiles_reel"],
                                 e["nb_combinaisons_touchees"]))
        pools[taille] = pool
    positions = {taille: 0 for taille in pools}
    reste = True
    while reste and len(choisis) < nb_max:
        reste = False
        for taille in ("petit", "moyen", "grand"):
            pool = pools[taille]
            while positions[taille] < len(pool):
                e = pool[positions[taille]]
                positions[taille] += 1
                reste = True
                if ajouter(e):
                    break
            if len(choisis) >= nb_max:
                break

    # Ordre de lecture final : du plus petit au plus grand coup.
    choisis.sort(key=lambda e: (e["nb_combinaisons_touchees"], e["nb_tuiles_reel"]))
    return choisis[:nb_max]


def _bloc_etapes(etapes: list) -> list:
    """Transforme les étapes du pas-à-pas en lignes de texte lisibles (on saute
    l'écran « Départ », purement informatif ; on garde « Les jokers » et chaque
    modification)."""
    lignes = []
    numero = 0
    for etape in etapes:
        titre = etape.get("titre") or ""
        texte = etape.get("texte") or ""
        if titre == "Départ":
            continue
        if titre == "Les jokers":
            lignes.append(f"    • (jokers) {texte}")
            continue
        if not texte or texte == "Après le coup.":
            continue
        numero += 1
        lignes.append(f"    {numero}. {texte}")
    return lignes


def _ligne_conclusion(eva: dict) -> str:
    if not eva["comparable"]:
        if eva["moins_que_optimum"]:
            return ("(coup posant moins de tuiles que l'optimum : question de "
                    "budget/coup raté, hors du sujet de la simplicité)")
        return "(optimum indéterminé pour ce coup — budget du juge épuisé)"
    if eva["minimal"]:
        return "CONCLUSION : décomposition NÉCESSAIRE (Expert est au minimum)."
    return (f"CONCLUSION : décomposition ÉVITABLE "
            f"(écart de {eva['ecart_combos']} combinaison(s) modifiée(s) et "
            f"{eva['ecart_deplacees']} tuile(s) déplacée(s) de plus que le "
            f"coup le plus simple).")


def _ecrire_plateau(lignes: list, titre: str, plateau: list) -> None:
    lignes.append(titre)
    descriptions = decrire_plateau(plateau)
    if not descriptions:
        lignes.append("    (plateau vide)")
    else:
        for d in descriptions:
            lignes.append(f"    - {d}")


def rediger_exemple(num: int, enr: dict) -> str:
    eva = enr["eval"]
    lignes = []
    lignes.append("=" * 78)
    lignes.append(f"EXEMPLE {num} — coup « {enr['taille']} » "
                  f"({enr['nb_combinaisons_touchees']} combinaison(s) touchée(s)), "
                  f"tour {enr['tour']}, joueur {enr['nom']}")
    lignes.append("=" * 78)
    lignes.append("")

    _ecrire_plateau(lignes, "PLATEAU DE DÉPART (tout le tapis avant le coup) :",
                    enr["plateau_avant"])
    lignes.append("")
    lignes.append("MAIN COMPLÈTE DE L'IA :")
    lignes.append(f"    {decrire_main(enr['chevalet'])}")
    lignes.append("")
    lignes.append(f"Nombre de tuiles posables au maximum ce tour-là : "
                  f"{enr['nb_tuiles_opt']}.")
    lignes.append(f"Expert a posé {enr['nb_tuiles_reel']} tuile(s).")
    lignes.append("")

    lignes.append("CE QU'EXPERT A JOUÉ :")
    lignes.append(f"    Résumé : {enr['resume_reel']['texte']}")
    etapes = _bloc_etapes(enr["etapes_reel"])
    if etapes:
        lignes.append("    Étape par étape :")
        lignes.extend(etapes)
    pr = eva["pert_reel"]
    lignes.append(f"    Perturbation de ce coup : {pr[0]} tuile(s) du plateau "
                  f"déplacée(s), {pr[1]} combinaison(s) modifiée(s).")
    lignes.append("")

    _ecrire_plateau(lignes, "PLATEAU D'ARRIVÉE (tout le tapis après le coup "
                    "d'Expert) :", enr["plateau_apres_reel"])
    lignes.append("")

    # Coup plus simple (optimum), pour comparaison, seulement s'il diffère.
    if eva["comparable"] and eva["evitable"] and enr["plateau_apres_opt"] is not None:
        po = eva["pert_opt"]
        lignes.append("IL EXISTAIT UN COUP PLUS SIMPLE posant autant de tuiles :")
        if enr["description_opt"]:
            lignes.append(f"    Résumé : {enr['description_opt']['texte']}")
        lignes.append(f"    Perturbation de ce coup plus simple : {po[0]} tuile(s) "
                      f"déplacée(s), {po[1]} combinaison(s) modifiée(s).")
        lignes.append("")
        _ecrire_plateau(lignes, "    PLATEAU D'ARRIVÉE du coup plus simple "
                        "(tout le tapis) :", enr["plateau_apres_opt"])
        lignes.append("")

    lignes.append(_ligne_conclusion(eva))
    lignes.append("")
    return "\n".join(lignes)


def ecrire_fichier_exemples(enregistrements: list, chemin: Path, resume: dict,
                            commande: str, nb_max: int = 10) -> int:
    exemples = choisir_exemples(enregistrements, nb_max=nb_max)
    comp = resume["comparables"]
    entete = [
        "EXEMPLES LISIBLES — EXPERT DÉCOMPOSE-T-IL LE PLATEAU INUTILEMENT ?",
        "(issue #215, suite de #199)",
        "",
        "Comment lire ce fichier : chaque exemple est une situation complète. On",
        "voit TOUT le tapis et TOUTE la main avant le coup, ce qu'Expert a fait,",
        "et TOUT le tapis après. S'il existait un coup aussi payant mais plus",
        "simple (qui remue moins le plateau), il est montré lui aussi, en entier,",
        "pour comparaison. La dernière ligne de chaque exemple dit si la",
        "décomposition était NÉCESSAIRE ou ÉVITABLE.",
        "",
        "« Perturbation » = combien de tuiles DÉJÀ posées sur le tapis ont changé",
        "de combinaison (déplacées), et combien de combinaisons ont été modifiées.",
        "Poser des tuiles de sa main en prolongeant une combinaison ne « déplace »",
        "aucune tuile : la perturbation reste faible. Défaire puis recomposer des",
        "combinaisons déplace des tuiles : la perturbation monte.",
        "",
        f"Bilan chiffré sur cet échantillon : {resume['total']} poses d'Expert, "
        f"{comp} comparables,",
        f"{resume['minimaux']} au minimum de perturbation "
        f"({_pct(resume['minimaux'], comp)}), "
        f"{resume['evitables']} décomposition(s) évitable(s) "
        f"({_pct(resume['evitables'], comp)}).",
        "",
        "Pour régénérer ce fichier sur vos propres parties :",
        f"    {commande}",
        "",
    ]
    contenu = "\n".join(entete) + "\n"
    for i, enr in enumerate(exemples, start=1):
        contenu += rediger_exemple(i, enr) + "\n"

    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(contenu, encoding="utf-8")
    return len(exemples)


# --------------------------------------------------------------------------- #
# Dégradation propre (aucun journal) et CLI.
# --------------------------------------------------------------------------- #

def _message_degradation(dossier: Path) -> None:
    print("-" * 70)
    print(f"Aucun journal exploitable dans {dossier}.")
    print("Pour analyser VOS parties, activez le journal (clé \"log_parties\" de")
    print("config.json), jouez quelques parties contre Expert jusqu'au terme, puis :")
    print("    PYTHONPATH=src python3 scripts/verifier_simplicite_expert.py \\")
    print(f"        --journaux {dossier}")
    print("À défaut, ce script simule des parties d'Expert (--donnes N).")
    print("-" * 70)


def _commande_regeneration(args, mode: str, sortie: Path) -> str:
    if mode == "journaux":
        return ("PYTHONPATH=src python3 scripts/verifier_simplicite_expert.py "
                f"--journaux {args.journaux} --sortie {sortie}")
    return ("PYTHONPATH=src python3 scripts/verifier_simplicite_expert.py "
            f"--donnes {args.donnes} --seed {args.seed} --sortie {sortie}")


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        description="Vérifie qu'Expert ne décompose jamais le plateau "
                    "inutilement (issue #215) et produit un fichier d'exemples "
                    "lisibles.")
    parser.add_argument("--journaux", default=None,
                        help="Dossier de journaux de parties (sinon, simulation).")
    parser.add_argument("--donnes", type=int, default=10,
                        help="Parties simulées d'Expert en miroir (défaut 10).")
    parser.add_argument("--seed", type=int, default=0,
                        help="Graine aléatoire (défaut 0, reproductible).")
    parser.add_argument("--max-tours", type=int, default=300,
                        help="Garde-fou anti-blocage par manche (défaut 300).")
    parser.add_argument("--budget-juge", type=float, default=BUDGET_JUGE_DEFAUT,
                        help=f"Budget (s) du juge indépendant par coup (défaut "
                             f"{BUDGET_JUGE_DEFAUT}).")
    parser.add_argument("--sortie", default=None,
                        help="Dossier de SORTIE du fichier d'exemples (défaut : "
                             "sous-dossier du répertoire temporaire du système ; "
                             "JAMAIS dans le dépôt).")
    parser.add_argument("--max-exemples", type=int, default=10,
                        help="Nombre d'exemples à écrire (défaut 10).")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Journalise le détail.")
    args = parser.parse_args(argv[1:])

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")

    if not solveur_exact.DISPONIBLE:
        print("ATTENTION : highspy/numpy absent — le juge utilise la recherche "
              "arborescente (moteur/solveur), approximation de la perturbation.\n")

    sortie = Path(args.sortie) if args.sortie \
        else Path(tempfile.gettempdir()) / "rummikub_simplicite"

    debut = time.monotonic()

    if args.journaux:
        dossier = Path(args.journaux)
        mode = "journaux"
        enregistrements = collecter_depuis_journaux(dossier, args.budget_juge)
        if not enregistrements:
            _message_degradation(dossier)
            print("Repli : simulation de parties d'Expert.\n")
            mode = "simulation"
            enregistrements = collecter_depuis_simulation(
                args.donnes, args.seed, args.max_tours, args.budget_juge)
    else:
        mode = "simulation"
        enregistrements = collecter_depuis_simulation(
            args.donnes, args.seed, args.max_tours, args.budget_juge)

    if not enregistrements:
        print("Aucune pose d'Expert à analyser.")
        return 1

    resume = resumer(enregistrements)
    afficher_resume(resume)

    chemin = sortie / "exemples_simplicite_expert.txt"
    commande = _commande_regeneration(args, mode, sortie)
    nb = ecrire_fichier_exemples(enregistrements, chemin, resume, commande,
                                 nb_max=args.max_exemples)
    print(f"\n{nb} exemple(s) lisible(s) écrit(s) dans : {chemin}")
    print(f"(À ouvrir avec un simple éditeur de texte.)")
    print(f"Temps total : {time.monotonic() - debut:.1f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
