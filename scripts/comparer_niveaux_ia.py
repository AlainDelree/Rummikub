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
    -v, --verbose       Journalise chaque partie jouée.
"""

import argparse
import logging
import random
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rummikub.config import NIVEAUX  # noqa: E402
from rummikub.moteur.ia import jouer_ia, jouer_niveau_expert  # noqa: E402
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

# Les 106 IDs de référence (#187) : utilisés pour vérifier, à chaque coup,
# qu'aucune tuile n'a disparu ni n'a été dupliquée entre les mains, le
# plateau et la pioche (voir ``_anomalies_conservation``).
_IDS_REFERENCE = frozenset(t.id for t in creer_sac())


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
# Un tour d'IA (même logique que scripts/simulation_ia.py, + chronométrage de
# la décision IA par niveau).
# --------------------------------------------------------------------------- #

def jouer_un_tour(etat: dict, idx: int, temps_par_niveau: dict,
                  replis_expert: list, preferer_simple: bool,
                  perturbations_expert: list) -> tuple[dict, bool, bool]:
    """Joue le tour de l'IA à l'index ``idx``.

    Chronomètre l'appel à ``jouer_ia`` et l'ajoute à
    ``temps_par_niveau[niveau]``. Retourne ``(etat, coup_invalide,
    tuiles_disparues)`` ; ``coup_invalide`` est True si l'IA a proposé un
    coup rejeté (ou une exception), auquel cas on se replie sur une pioche
    de secours, comme côté UI (``Api.jeu_ia_jouer``). ``tuiles_disparues``
    est True si le rejet vient spécifiquement du garde-fou anti-disparition
    de tuiles (#187) — distingué des autres motifs de rejet (ex. mise
    initiale insuffisante) pour que ce type d'anomalie, bien plus grave,
    ressorte clairement dans le rapport de la campagne.

    Pour le niveau Expert, appelle ``jouer_niveau_expert`` directement
    (plutôt que le ``jouer_ia`` générique) avec ``on_repli`` (#190) afin de
    compter, dans ``replis_expert``, le nombre de tours où Expert s'est
    replié sur Avancé — ``replis_expert[0]`` : total (toute cause) ;
    ``replis_expert[1]`` : parmi eux, ceux dus à un dépassement du budget
    de temps SANS avoir rien trouvé (:class:`BudgetDepasse` — la seule
    cause que l'accélération de #190 peut réduire : l'autre cause, un coup
    légitimement impossible, ne dépend pas de la vitesse de recherche).
    ``preferer_simple`` (#199) est transmis tel quel à ``jouer_niveau_
    expert`` ; quand Expert pose effectivement un coup, sa perturbation du
    plateau (``mesurer_perturbation``, voir ``moteur/solveur.py``) est
    ajoutée à ``perturbations_expert`` pour la mesure de campagne.
    """
    niveau = etat["joueurs"][idx]["niveau"]
    backup_debut_tour(etat)
    plateau_avant = etat["plateau"]

    def _compter_repli(timeout):
        replis_expert[0] += 1
        if timeout:
            replis_expert[1] += 1

    debut = time.monotonic()
    try:
        if niveau == "Expert":
            res_ia = jouer_niveau_expert(
                etat, idx, on_repli=_compter_repli,
                preferer_simple=preferer_simple)
        else:
            res_ia = jouer_ia(etat, idx)
    except Exception:
        temps_par_niveau.setdefault(niveau, []).append(time.monotonic() - debut)
        logger.exception("Exception de l'IA %s au tour %d", niveau, etat["tour_numero"])
        annuler_tour(etat)
        return piocher(etat)["etat"], True, False
    temps_par_niveau.setdefault(niveau, []).append(time.monotonic() - debut)

    if niveau == "Expert" and res_ia.get("action") == "jouer":
        perturbations_expert.append(
            mesurer_perturbation(plateau_avant, res_ia["nouveau_plateau"]))

    action = res_ia.get("action")
    if action == "jouer":
        res = jouer_tour(etat, res_ia["ids_tuiles"], res_ia["nouveau_plateau"])
        if res["ok"]:
            return res["etat"], False, False
        tuiles_disparues = bool(res.get("tuiles_disparues"))
        if tuiles_disparues:
            logger.error("ANOMALIE : coup refusé (%s) au tour %d car des "
                         "tuiles du plateau auraient disparu : %s",
                         niveau, etat["tour_numero"], res["erreur"])
        else:
            logger.warning("Coup invalide (%s) au tour %d : %s",
                           niveau, etat["tour_numero"], res["erreur"])
        annuler_tour(etat)
        return piocher(etat)["etat"], True, tuiles_disparues
    if action == "piocher":
        return piocher(etat)["etat"], False, False
    if action == "passer":
        return passer_tour(etat)["etat"], False, False

    logger.warning("Action IA inconnue %r (%s) au tour %d",
                   action, niveau, etat["tour_numero"])
    annuler_tour(etat)
    return piocher(etat)["etat"], True, False


# --------------------------------------------------------------------------- #
# Un match à 2 joueurs (1 à N manches)
# --------------------------------------------------------------------------- #

def _jouer_une_manche(etat: dict, max_tours: int, temps_par_niveau: dict,
                      replis_expert: list, preferer_simple: bool,
                      perturbations_expert: list) -> dict:
    """Joue la manche courante de ``etat`` jusqu'à sa fin naturelle (chevalet
    vidé ou pioche épuisée) ou jusqu'au garde-fou ``max_tours``. Retourne les
    statistiques de CETTE manche ; ``etat`` est muté en place."""
    tours = 0
    coups_invalides = 0
    coups_tuiles_disparues = 0
    anomalies_conservation = 0
    arretee_garde_fou = False

    while not etat["manche_terminee"]:
        tours += 1
        if tours > max_tours:
            arretee_garde_fou = True
            break
        idx = etat["index_joueur_actuel"]
        etat, invalide, tuiles_disparues = jouer_un_tour(
            etat, idx, temps_par_niveau, replis_expert, preferer_simple,
            perturbations_expert)
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
                temps_par_niveau: dict, replis_expert: list,
                preferer_simple: bool, perturbations_expert: list) -> dict:
    """Joue un MATCH complet à 2 joueurs de ``nb_manches`` manches (issue
    #203). Les manches s'enchaînent via ``nouvelle_manche`` (score cumulé
    conservé, nouvelle donne et mise initiale remise à zéro à chaque manche).
    Si une manche est arrêtée par le garde-fou ``max_tours``, le match entier
    est marqué comme arrêté (``arretee_garde_fou``) et abandonné.
    """
    etat = creer_partie(config_joueurs, {"nb_manches": nb_manches})
    backup_debut_tour(etat)

    manches = []
    coups_invalides = coups_tuiles_disparues = anomalies_conservation = 0
    arretee_garde_fou = False

    for numero in range(1, nb_manches + 1):
        res = _jouer_une_manche(etat, max_tours, temps_par_niveau,
                                replis_expert, preferer_simple,
                                perturbations_expert)
        coups_invalides += res["coups_invalides"]
        coups_tuiles_disparues += res["coups_tuiles_disparues"]
        anomalies_conservation += res["anomalies_conservation"]
        if res["arretee_garde_fou"]:
            arretee_garde_fou = True
            break
        res["numero"] = numero
        manches.append(res)
        if numero < nb_manches:
            etat = nouvelle_manche(etat)
            backup_debut_tour(etat)

    return {
        "etat": etat,
        "manches": manches,
        "arretee_garde_fou": arretee_garde_fou,
        "coups_invalides": coups_invalides,
        "coups_tuiles_disparues": coups_tuiles_disparues,
        "anomalies_conservation": anomalies_conservation,
    }


# --------------------------------------------------------------------------- #
# Campagne complète : N donnes, chacune jouée 2 fois en miroir
# --------------------------------------------------------------------------- #

def comparer(niveau_a: str, niveau_b: str, nb_donnes: int, seed: int,
            max_tours: int, nb_manches: int = 1,
            preferer_simple: bool = True) -> dict:
    """``nb_manches`` (#203) : nombre de manches par match — chaque donne est
    jouée en miroir (places échangées) sur un match complet, le vainqueur du
    match étant le joueur au plus haut score cumulé. Les résultats sont donnés
    à la fois par match (victoires, score cumulé moyen) et par manche.

    ``preferer_simple`` (#199) : réglage transmis à chaque appel d'Expert —
    comparer deux campagnes identiques (même graine), l'une avec et l'autre
    sans, permet de mesurer l'effet du critère de simplicité sur la force
    d'Expert (voir CONTEXTE.md §9 et §13)."""
    rng_graines = random.Random(seed)
    graines = [rng_graines.randrange(2**32) for _ in range(nb_donnes)]

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
    # Liste (plutôt qu'un tuple d'int) : mutable, modifiable depuis la
    # fermeture ``_compter_repli`` de ``jouer_un_tour`` sans variable
    # ``nonlocal`` ni retour supplémentaire à faire remonter à travers
    # ``jouer_partie``. [0] = replis total (toute cause), [1] = parmi eux,
    # ceux dus à un dépassement de budget sans rien trouvé (voir #190).
    replis_expert = [0, 0]
    # Perturbation (#199) de chaque coup effectivement posé par Expert :
    # liste de ``(tuiles_deplacees, combos_modifiees)`` (voir
    # ``mesurer_perturbation``, ``moteur/solveur.py``).
    perturbations_expert: list[tuple[int, int]] = []

    for i, graine in enumerate(graines):
        for ordre, camps in enumerate((("A", "B"), ("B", "A"))):
            random.seed(graine)
            niveau_camp = {"A": niveau_a, "B": niveau_b}
            config_joueurs = [
                {"nom": f"{camp}:{niveau_camp[camp]}", "est_ia": True,
                 "niveau": niveau_camp[camp]}
                for camp in camps
            ]
            resultat = jouer_match(config_joueurs, nb_manches, max_tours,
                                   temps_par_niveau, replis_expert,
                                   preferer_simple, perturbations_expert)
            coups_invalides_total += resultat["coups_invalides"]
            coups_tuiles_disparues_total += resultat["coups_tuiles_disparues"]
            anomalies_conservation_total += resultat["anomalies_conservation"]

            if resultat["arretee_garde_fou"]:
                fins["garde_fou"] += 1
                logger.warning(
                    "Donne %d (ordre %s) : match arrêté par le garde-fou",
                    i + 1, camps)
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

            if logger.isEnabledFor(logging.INFO):
                logger.info(
                    "Donne %d (ordre %s) : match %s (%d manche(s)) — "
                    "cumul A=%d B=%d",
                    i + 1, camps,
                    "nul" if camp_gagnant is None
                    else f"gagné par {camp_gagnant} ({niveau_camp[camp_gagnant]})",
                    len(resultat["manches"]), cumul_a, cumul_b)

    return {
        "niveau_a": niveau_a,
        "niveau_b": niveau_b,
        "nb_manches": nb_manches,
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
        "replis_expert_total": replis_expert[0],
        "replis_expert_timeout": replis_expert[1],
        "perturbations_expert": perturbations_expert,
        "preferer_simple": preferer_simple,
        "nb_donnes": nb_donnes,
        "nb_parties": 2 * nb_donnes,
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

    print("=" * 70)
    print(f"COMPARAISON : {niveau_a} (camp A) vs {niveau_b} (camp B)")
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

    tours_expert = len(resume["temps_par_niveau"].get("Expert", []))
    if tours_expert:
        replis = resume["replis_expert_total"]
        replis_timeout = resume["replis_expert_timeout"]
        print(f"  Replis d'Expert sur Avancé, toute cause : "
             f"{replis}/{tours_expert} tour(s) ({replis / tours_expert * 100:.1f} %)")
        print(f"    — dont faute de résultat dans le budget (#190, seule "
             f"cause visée par l'accélération) : {replis_timeout}/{tours_expert} "
             f"tour(s) ({replis_timeout / tours_expert * 100:.1f} %)")
        print(f"    — dont coup légitimement impossible (aucun rapport "
             f"avec la vitesse) : {replis - replis_timeout}/{tours_expert} "
             f"tour(s) ({(replis - replis_timeout) / tours_expert * 100:.1f} %)")

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
    parser.add_argument("--sans-exact", action="store_true",
                        help="Fige Expert sur son ANCIENNE recherche "
                             "arborescente (moteur/solveur.py) au lieu du "
                             "modèle exact HiGHS (#206) — pour la campagne "
                             "« avant / après » (relancer la même commande "
                             "avec et sans ce drapeau, même --seed).")
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

    if args.sans_exact:
        # Rejoue le comportement d'avant #206 : Expert n'utilise que la
        # recherche arborescente (modèle exact HiGHS désactivé globalement).
        from rummikub.moteur import ia as _ia
        _ia.UTILISER_SOLVEUR_EXACT = False
        print("[#206] Modèle exact DÉSACTIVÉ (Expert = recherche arborescente).")

    debut = time.monotonic()
    resume = comparer(args.niveau_a, args.niveau_b, args.donnes, args.seed,
                      args.max_tours, nb_manches=args.manches,
                      preferer_simple=not args.sans_preferer_simple)
    duree = time.monotonic() - debut

    afficher_rapport(resume)
    print(f"Temps total de la campagne : {duree:.1f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
