"""Tests de la brique « Inconnues » (issue #219) : calcul des tuiles
inconnues et de leurs probabilités, sans toucher au comportement du jeu.
"""

import copy
import json
import time
from pathlib import Path

import pytest

from rummikub import config
from rummikub.moteur.tuiles import Tuile, creer_sac, distribuer
from rummikub.moteur.partie import (
    creer_partie, jouer_tour, piocher, passer_tour,
    backup_debut_tour, annuler_tour,
)
from rummikub.moteur.ia import jouer_ia
from rummikub.moteur.inconnues import (
    TOTAL_TUILES,
    CLE_JOKER,
    calculer_inconnues,
    calculer_inconnues_depuis_etat,
    proba_instance_chez_adversaire,
    proba_instance_dans_pioche,
    proba_tuile_chez_adversaire,
    proba_tuile_chez_un_adversaire_quelconque,
    proba_tuile_dans_pioche,
    proba_joker_chez_adversaire,
    proba_joker_chez_un_adversaire_quelconque,
    diagnostiquer_coherence,
)


def t(v, c, label="a"):
    return Tuile(f"{c}_{v}_{label}", v, c)


def j(n=1):
    return Tuile(f"joker_{n}", None, None, est_joker=True)


# --------------------------------------------------------------------------- #
# Cas fabriqués à la main
# --------------------------------------------------------------------------- #

def test_total_tuiles_106():
    assert TOTAL_TUILES == 106
    assert TOTAL_TUILES == len(creer_sac())


def test_debut_partie_deux_joueurs():
    """106 tuiles - 2 mains de 14 - tapis vide = la pioche."""
    d = distribuer(creer_sac(), 2)
    ma_main = d["chevalets"][0]
    main_adverse = d["chevalets"][1]
    pioche = d["pioche"]
    assert len(pioche) == 106 - 28

    inc = calculer_inconnues([], ma_main, [len(main_adverse)], len(pioche))
    assert inc.nb_total_inconnues == len(main_adverse) + len(pioche)
    assert inc.nb_total_inconnues == 106 - len(ma_main)


def test_fin_partie_peu_de_tuiles():
    """Fin de partie : presque toutes les tuiles sont déjà visibles (tapis
    chargé + main), il n'en reste plus qu'une seule chez l'unique
    adversaire, aucune en pioche."""
    sac = creer_sac()
    ma_main = sac[:1]
    main_adverse_taille = 1
    plateau = [sac[1:105]]   # 104 tuiles posées sur le tapis ; sac[105] reste inconnue
    inc = calculer_inconnues(plateau, ma_main, [main_adverse_taille], 0)
    assert inc.nb_total_inconnues == 1
    assert inc.tailles_mains_adversaires == (1,)
    assert inc.taille_pioche == 0


def test_tapis_charge():
    plateau = [
        [t(1, "rouge"), t(2, "rouge"), t(3, "rouge"), t(4, "rouge")],
        [t(9, "bleu"), t(9, "noir"), t(9, "jaune")],
        [t(5, "noir"), t(6, "noir"), t(7, "noir"), j(1)],
    ]
    ma_main = [t(13, "noir"), t(10, "bleu")]
    inc = calculer_inconnues(plateau, ma_main, [14, 14], 50)
    vues = 4 + 3 + 3 + 1 + 2
    assert inc.nb_total_inconnues == 106 - vues


def test_exemplaires_restants_zero_un_deux():
    # rouge_7 : aucun exemplaire vu -> 2 restants.
    inc = calculer_inconnues([], [], [10], 10)
    assert inc.exemplaires_restants(("rouge", 7)) == 2

    # rouge_7 : un exemplaire sur le tapis -> 1 restant.
    inc = calculer_inconnues([[t(7, "rouge")]], [], [10], 10)
    assert inc.exemplaires_restants(("rouge", 7)) == 1

    # rouge_7 : les deux exemplaires en main -> 0 restant (absent de lister()).
    inc = calculer_inconnues([], [t(7, "rouge", "a"), t(7, "rouge", "b")],
                             [10], 10)
    assert inc.exemplaires_restants(("rouge", 7)) == 0
    assert ("rouge", 7) not in inc.tuiles


def test_un_deux_trois_adversaires():
    sac = creer_sac()
    ma_main = sac[:14]
    reste = sac[14:]           # 92 tuiles, toutes inconnues (rien sur le tapis)
    for nb_adv in (1, 2, 3):
        taille_adv = 10
        tailles = [taille_adv] * nb_adv
        n_adv_total = taille_adv * nb_adv
        taille_pioche = len(reste) - n_adv_total
        inc = calculer_inconnues([], ma_main, tailles, taille_pioche)
        assert inc.nb_adversaires == nb_adv
        assert inc.nb_total_inconnues == len(reste)
        assert inc.nb_total_inconnues == sum(tailles) + taille_pioche


def test_jokers_sur_tapis_en_main_et_inconnus():
    # Un joker sur le tapis, aucun en main -> 1 restant.
    inc = calculer_inconnues([[j(1)]], [], [14], 50)
    assert inc.exemplaires_restants(CLE_JOKER) == 1

    # Les deux jokers en main -> 0 restant.
    inc = calculer_inconnues([], [j(1), j(2)], [14], 50)
    assert inc.exemplaires_restants(CLE_JOKER) == 0

    # Aucun joker visible -> 2 restants (les deux sont inconnus).
    inc = calculer_inconnues([], [], [14], 50)
    assert inc.exemplaires_restants(CLE_JOKER) == 2


def test_aucune_tuile_comptee_en_trop():
    """Pour toute clé, exemplaires_restants reste dans [0, max]."""
    plateau = [[t(v, c) for c in config.COULEURS] for v in range(1, 14)]
    inc = calculer_inconnues(plateau, [], [1], 1)
    for tuile in inc.lister():
        maxi = 2 if not tuile.est_joker else config.NB_JOKERS
        assert 0 <= tuile.exemplaires_restants <= maxi


# --------------------------------------------------------------------------- #
# Pas de triche : jamais le contenu réel de la main adverse
# --------------------------------------------------------------------------- #

def _etat_deux_joueurs():
    etat = creer_partie(
        [{"nom": "A", "est_ia": False}, {"nom": "B", "est_ia": False}],
        {},
    )
    return etat


def test_equite_pas_de_triche_contenu_main_adverse():
    """Changer le CONTENU de la main d'un adversaire sans changer sa TAILLE
    ne doit changer AUCUN résultat — le module ne doit jamais lire le
    contenu réel d'une main adverse, seulement sa taille."""
    etat = _etat_deux_joueurs()
    inc_avant = calculer_inconnues_depuis_etat(etat, 0)

    # On remplace entièrement la main de l'adversaire (joueur 1) par 14
    # AUTRES tuiles (prises arbitrairement dans le sac), sans changer sa
    # longueur. Le résultat pour le joueur 0 doit être identique.
    autre_sac = creer_sac()
    etat["joueurs"][1]["chevalet"] = [
        tu.as_dict() for tu in autre_sac[:len(etat["joueurs"][1]["chevalet"])]
    ]
    inc_apres = calculer_inconnues_depuis_etat(etat, 0)

    assert inc_avant.nb_total_inconnues == inc_apres.nb_total_inconnues
    assert inc_avant.tailles_mains_adversaires == inc_apres.tailles_mains_adversaires
    assert {k: v.exemplaires_restants for k, v in inc_avant.tuiles.items()} == \
           {k: v.exemplaires_restants for k, v in inc_apres.tuiles.items()}


def test_wrapper_etat_nutilise_que_len_sur_main_adverse():
    """Variante structurelle du test d'équité : on vide la main adverse en
    la remplaçant par une liste fictive de la même longueur dont les
    éléments ne sont pas de vraies tuiles (dicts incomplets) — si le module
    lisait leur contenu, il lèverait une exception ou produirait un résultat
    différent."""
    etat = _etat_deux_joueurs()
    inc_avant = calculer_inconnues_depuis_etat(etat, 0)

    n = len(etat["joueurs"][1]["chevalet"])
    etat["joueurs"][1]["chevalet"] = [{"id": f"factice_{i}"} for i in range(n)]
    inc_apres = calculer_inconnues_depuis_etat(etat, 0)

    assert inc_avant.nb_total_inconnues == inc_apres.nb_total_inconnues


# --------------------------------------------------------------------------- #
# Probabilités
# --------------------------------------------------------------------------- #

def test_proba_instance_uniforme_et_somme_egale_taille_main():
    d = distribuer(creer_sac(), 3)
    ma_main = d["chevalets"][0]
    tailles_adv = [len(d["chevalets"][1]), len(d["chevalets"][2])]
    pioche = len(d["pioche"])

    inc = calculer_inconnues([], ma_main, tailles_adv, pioche)
    for idx, taille in enumerate(tailles_adv):
        p = proba_instance_chez_adversaire(inc, idx)
        assert p == pytest.approx(taille / inc.nb_total_inconnues)
        # Somme sur toutes les tuiles inconnues (une proba uniforme par
        # exemplaire) == taille de la main de cet adversaire.
        somme = sum(tu.exemplaires_restants * p for tu in inc.lister())
        assert somme == pytest.approx(taille)

    p_pioche = proba_instance_dans_pioche(inc)
    assert p_pioche == pytest.approx(pioche / inc.nb_total_inconnues)
    somme_pioche = sum(tu.exemplaires_restants * p_pioche for tu in inc.lister())
    assert somme_pioche == pytest.approx(pioche)


def test_proba_un_seul_exemplaire_reduit_a_formule_simple():
    """Avec un seul exemplaire restant (k=1) et un seul adversaire, la
    probabilité « au moins un exemplaire chez l'adversaire » coïncide avec
    la formule uniforme simple de l'issue (n / N), et son complément est
    exactement la probabilité symétrique pour la pioche (les deux seules
    destinations possibles)."""
    # 6 tuiles visibles (1 des 2 rouge_7 + 5 autres distinctes) -> 100 inconnues.
    plateau = [[t(7, "rouge", "a"), t(1, "bleu"), t(2, "bleu"),
                t(3, "bleu"), t(4, "bleu"), t(5, "bleu")]]
    inc = calculer_inconnues(plateau, [], [9], 91)
    assert inc.nb_total_inconnues == 100
    p_adv = proba_tuile_chez_adversaire(inc, ("rouge", 7), 0)
    p_pioche = proba_tuile_dans_pioche(inc, ("rouge", 7))

    assert p_adv == pytest.approx(9 / 100)
    assert p_pioche == pytest.approx(91 / 100)
    assert p_adv + p_pioche == pytest.approx(1.0)


def test_proba_deux_exemplaires_entre_0_et_1():
    inc = calculer_inconnues([], [], [14, 14, 14], 50)
    for idx in range(3):
        p = proba_tuile_chez_adversaire(inc, ("rouge", 7), idx)
        assert 0.0 <= p <= 1.0
    p_un_quelconque = proba_tuile_chez_un_adversaire_quelconque(inc, ("rouge", 7))
    assert 0.0 <= p_un_quelconque <= 1.0
    # Avoir plus d'adversaires ne peut qu'augmenter (ou laisser égale) la
    # probabilité qu'au moins un exemplaire soit chez l'un d'eux.
    assert p_un_quelconque >= p


def test_proba_joker():
    inc = calculer_inconnues([[j(1)]], [], [14], 50)  # 1 joker restant (k=1)
    p = proba_joker_chez_adversaire(inc, 0)
    # k=1 -> réduit exactement à la formule uniforme simple (n / N).
    assert p == pytest.approx(14 / inc.nb_total_inconnues)
    assert proba_joker_chez_un_adversaire_quelconque(inc) == pytest.approx(p)


def test_proba_tuile_sans_exemplaire_restant_est_nulle():
    inc = calculer_inconnues([], [t(7, "rouge", "a"), t(7, "rouge", "b")],
                             [14], 50)
    assert proba_tuile_chez_adversaire(inc, ("rouge", 7), 0) == 0.0
    assert proba_tuile_dans_pioche(inc, ("rouge", 7)) == 0.0


# --------------------------------------------------------------------------- #
# Diagnostic de cohérence
# --------------------------------------------------------------------------- #

def test_diagnostiquer_coherence_ras():
    plateau = [[t(1, "rouge")]]   # 1 tuile visible -> 105 inconnues
    assert diagnostiquer_coherence(plateau, [], [14, 14, 14], 63) == []


def test_diagnostiquer_coherence_detecte_tuile_en_trop():
    # Trois exemplaires de rouge_7 vus (tapis + main) alors qu'il n'en
    # existe que deux : anomalie de données (journal corrompu par exemple).
    plateau = [[t(7, "rouge", "a"), t(7, "rouge", "b")]]
    main = [t(7, "rouge", "c")]
    anomalies = diagnostiquer_coherence(plateau, main, [14], 50)
    assert anomalies
    assert any("rouge" in a and "7" in a for a in anomalies)


# --------------------------------------------------------------------------- #
# Vérification sur des parties simulées (issue #219, point 4)
# --------------------------------------------------------------------------- #

def _jouer_un_tour_simule(etat, idx):
    """Variante minimale de ``scripts/simulation_ia.jouer_un_tour`` : fait
    jouer l'IA à l'index ``idx`` et retourne l'état résultant. Se replie sur
    une pioche de secours en cas de coup invalide, comme côté UI."""
    backup_debut_tour(etat)
    res_ia = jouer_ia(etat, idx)
    action = res_ia.get("action")
    if action == "jouer":
        res = jouer_tour(etat, res_ia["ids_tuiles"], res_ia["nouveau_plateau"])
        if not res["ok"]:
            annuler_tour(etat)
            res = piocher(etat)
    elif action == "piocher":
        res = piocher(etat)
    else:
        res = passer_tour(etat)
    return res["etat"]


def _config_joueurs(n):
    niveaux = ["Débutant", "Avancé", "Expert", "Intermédiaire"]
    return [{"nom": f"IA-{i}", "est_ia": True, "niveau": niveaux[i % 4]}
           for i in range(n)]


def test_verification_sur_parties_simulees():
    """À défaut de journaux réels (``data/logs_parties``, absents de ce
    worktree), vérifie les invariants de la brique « Inconnues » à CHAQUE
    tour de PLUSIEURS parties simulées par le moteur (même mécanisme que
    ``scripts/simulation_ia.py``) : le nombre de tuiles inconnues égale la
    somme des mains adverses et de la pioche, la somme des probabilités
    d'un adversaire égale la taille de sa main, et aucune tuile n'est
    comptée en trop. Rapporte le nombre de parties/tours vérifiés."""
    import random
    random.seed(20219)

    nb_parties = 5
    nb_tours_total = 0
    nb_verifs = 0
    anomalies = []

    for num_partie in range(nb_parties):
        nb_joueurs = 2 + (num_partie % 3)   # 2, 3, 4, 2, 3
        etat = creer_partie(_config_joueurs(nb_joueurs), {})
        backup_debut_tour(etat)

        for _tour in range(300):
            if etat["manche_terminee"]:
                break
            idx = etat["index_joueur_actuel"]
            etat = _jouer_un_tour_simule(etat, idx)
            nb_tours_total += 1

            for i in range(len(etat["joueurs"])):
                inc = calculer_inconnues_depuis_etat(etat, i)
                nb_verifs += 1

                attendu = (sum(len(j["chevalet"]) for k, j in
                              enumerate(etat["joueurs"]) if k != i)
                          + len(etat["pioche"]))
                if inc.nb_total_inconnues != attendu:
                    anomalies.append(
                        f"partie {num_partie} tour {_tour} joueur {i} : "
                        f"{inc.nb_total_inconnues} != {attendu}")
                    continue

                for idx_adv, taille_adv in enumerate(inc.tailles_mains_adversaires):
                    p = proba_instance_chez_adversaire(inc, idx_adv)
                    somme = sum(tu.exemplaires_restants * p
                               for tu in inc.lister())
                    if somme != pytest.approx(taille_adv):
                        anomalies.append(
                            f"partie {num_partie} tour {_tour} joueur {i} "
                            f"adversaire {idx_adv} : somme proba {somme} != "
                            f"taille main {taille_adv}")

                for tuile in inc.lister():
                    maxi = 2 if not tuile.est_joker else config.NB_JOKERS
                    if not (0 <= tuile.exemplaires_restants <= maxi):
                        anomalies.append(
                            f"partie {num_partie} tour {_tour} joueur {i} : "
                            f"{tuile.cle} a {tuile.exemplaires_restants} "
                            f"exemplaires restants (max {maxi})")

    print(f"\n[inconnues] {nb_parties} partie(s) simulée(s), "
          f"{nb_tours_total} tour(s), {nb_verifs} vérification(s) "
          f"par-joueur, {len(anomalies)} anomalie(s).")
    assert not anomalies, "\n".join(anomalies[:20])
    assert nb_tours_total > 0
    assert nb_verifs > 0


def test_verification_sur_journaux_reels_si_disponibles():
    """Même vérification que ci-dessus, mais sur de VRAIS journaux de
    parties (``data/logs_parties/partie_*.json``, ignorés par git, présents
    uniquement sur la machine d'Alain). Ignoré proprement si aucun journal
    n'est disponible (cas de ce worktree isolé)."""
    dossier = config.RACINE_DATA / "logs_parties"
    fichiers = sorted(dossier.glob("partie_*.json")) if dossier.is_dir() else []
    if not fichiers:
        pytest.skip("Aucun journal de partie disponible dans ce worktree "
                    "(data/logs_parties, voir issue #219 point 4).")

    nb_tours_total = 0
    anomalies = []

    for fichier in fichiers:
        try:
            data = json.loads(fichier.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            anomalies.append(f"{fichier.name} : journal illisible ({e})")
            continue

        for action in data.get("actions", []):
            mains = action.get("mains_joueurs")
            plateau = action.get("plateau")
            if mains is None or plateau is None:
                anomalies.append(
                    f"{fichier.name} tour {action.get('tour')} : "
                    f"journal incomplet (mains_joueurs/plateau absents)")
                continue
            taille_pioche = action.get("sac_restant", len(action.get("pioche", [])))
            nb_tours_total += 1

            for i in range(len(mains)):
                tailles_adv = [len(mains[k]["tuiles"]) for k in range(len(mains))
                              if k != i]
                diag = diagnostiquer_coherence(
                    plateau, mains[i]["tuiles"], tailles_adv, taille_pioche)
                if diag:
                    anomalies.append(
                        f"{fichier.name} tour {action.get('tour')} "
                        f"joueur {i} : {diag}")

    print(f"\n[inconnues] {len(fichiers)} journal(aux) réel(s), "
          f"{nb_tours_total} tour(s) vérifié(s), {len(anomalies)} anomalie(s).")
    assert not anomalies, "\n".join(anomalies[:20])


# --------------------------------------------------------------------------- #
# Performance (indicatif, pas de seuil bloquant)
# --------------------------------------------------------------------------- #

def test_performance_ordre_de_grandeur():
    d = distribuer(creer_sac(), 4)
    ma_main = d["chevalets"][0]
    tailles_adv = [len(c) for c in d["chevalets"][1:]]
    pioche = len(d["pioche"])

    n = 2000
    debut = time.perf_counter()
    for _ in range(n):
        inc = calculer_inconnues([], ma_main, tailles_adv, pioche)
        for idx in range(len(tailles_adv)):
            proba_joker_chez_adversaire(inc, idx)
    duree = time.perf_counter() - debut

    print(f"\n[inconnues] {n} appels en {duree:.4f}s "
          f"({1000 * duree / n:.4f} ms/appel).")
    # Pas de seuil bloquant (dépend de la machine) : juste une garantie très
    # large que l'appel est bien négligeable devant le temps du solveur
    # (de l'ordre de la centaine de ms à quelques secondes, voir §8bis/§9).
    assert duree / n < 0.05
