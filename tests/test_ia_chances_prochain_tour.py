"""Tests de la stratégie ``chances_prochain_tour`` (issue #231, anciennement
« tuiles vivantes ») : à nombre de tuiles posées égal, préférer le coup qui
laisse le chevalet le plus susceptible de pouvoir encore jouer au tour
suivant.

Positions de test fixes (point 7 de l'issue), construites à la main — même
convention que ``tests/test_ia_petits_chiffres.py``."""

import pytest

from rummikub.moteur import ia, niveaux
from rummikub.moteur import solveur_exact as se

besoin_exact = pytest.mark.skipif(
    not se.DISPONIBLE,
    reason="highspy/numpy absents (dépendances du modèle exact d'Expert)")

_COULEURS = ("rouge", "bleu", "jaune", "noir")


def T(id_, v, c, j=False):
    return {"id": id_, "valeur": v, "couleur": c, "est_joker": j}


def _fillers(n, depart=50):
    return [T(f"{_COULEURS[i % 4]}_{depart + i}_f", depart + i, _COULEURS[i % 4])
           for i in range(n)]


def _etat(chevalet, plateau=None, niveau="Champion du Monde"):
    return {
        "joueurs": [
            {"nom": "Humain", "est_ia": False, "niveau": None,
             "chevalet": [], "mise_initiale_faite": True},
            {"nom": "Bot", "est_ia": True, "niveau": niveau,
             "chevalet": chevalet, "mise_initiale_faite": True},
        ],
        "plateau": plateau or [],
        "config": {"nb_manches": 1, "valeur_joker_penalite": 30,
                   "mise_initiale_min": 30},
        "index_joueur_actuel": 1,
        "historique": [],
    }


def _bridage_chances_seule():
    return niveaux.bridage_champion_personnalise(["chances_prochain_tour"])


# --------------------------------------------------------------------------- #
# Point 7 : deux coups posant le même nombre de tuiles (3) mais laissant des
# chevalets de scores différents — le meilleur score est choisi.
#
# Dilemme : un seul joker du chevalet, disputé par deux paires qui ne peuvent
# chacune être complétée QUE par lui — une suite rouge au bord du tapis
# (11-12-13, 36 points, choisie par défaut faute d'autre critère) et un
# groupe-pont bleu au milieu (2-3-4, 9 points). La suite rouge, au bord,
# laisse en main une paire bleue PAUVRE en sorties (une seule extension
# possible, le tapis étant au bord) ; le groupe-pont bleu, lui, laisse en
# main une paire rouge toujours RICHE en sorties (suite à deux extensions).
# --------------------------------------------------------------------------- #

def _chevalet_dilemme(nb_filler):
    return ([T("rouge_12_a", 12, "rouge"), T("rouge_13_a", 13, "rouge"),
            T("bleu_2_a", 2, "bleu"), T("bleu_4_a", 4, "bleu"),
            T("joker_1", None, "noir", j=True)]
           + _fillers(nb_filler))


@besoin_exact
def test_chances_prochain_tour_choisit_le_coup_au_meilleur_score():
    etat = _etat(_chevalet_dilemme(nb_filler=5))
    taille_main = len(etat["joueurs"][1]["chevalet"])
    assert taille_main > niveaux.SEUIL_FIN_PARTIE_VERIF_FINITION

    # Sans la stratégie (solveur seul) : la suite rouge, plus de points.
    attendu_sans_strategie = ia.jouer_niveau_expert(etat, 1)
    assert set(attendu_sans_strategie["ids_tuiles"]) == {
        "rouge_12_a", "rouge_13_a", "joker_1"}

    niveaux.BRIDAGES["Champion du Monde"] = _bridage_chances_seule()
    try:
        coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")
    finally:
        niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
            niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)

    assert coup["action"] == "jouer"
    # Avec la stratégie : bascule sur le groupe-pont bleu, au score supérieur,
    # MÊME NOMBRE de tuiles posées (3) que le coup du solveur seul.
    assert len(coup["ids_tuiles"]) == 3
    assert set(coup["ids_tuiles"]) == {"bleu_2_a", "bleu_4_a", "joker_1"}
    assert coup["solveur"] == ia.SOLVEUR_CHANCES_PROCHAIN_TOUR
    info = coup["chances_prochain_tour_info"]
    assert info["declenchee"] is True
    assert info["choisi"] is True
    assert info["meilleur_score"] > info["score_avant"]


@besoin_exact
def test_chances_prochain_tour_desactivee_decision_identique_a_avant():
    """Stratégie désactivée (registre par défaut, #228) : décision identique
    à celle du solveur seul (aucun changement de comportement sans elle)."""
    etat = _etat(_chevalet_dilemme(nb_filler=5))
    attendu = ia.jouer_niveau_expert(etat, 1)
    coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == set(attendu["ids_tuiles"])
    assert "chances_prochain_tour_info" not in coup


@besoin_exact
def test_expert_inchange_meme_position():
    """Expert n'a jamais accès à ``chances_prochain_tour`` (registre, #228/
    #231) : même décision avec ou sans la stratégie forcée pour Champion du
    Monde uniquement."""
    etat = _etat(_chevalet_dilemme(nb_filler=5), niveau="Expert")
    attendu = ia.jouer_niveau_expert(etat, 1)

    niveaux.BRIDAGES["Champion du Monde"] = _bridage_chances_seule()
    try:
        coup = ia.jouer_niveau_bride(etat, 1, "Expert")
    finally:
        niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
            niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == set(attendu["ids_tuiles"])
    assert "chances_prochain_tour_info" not in coup


# --------------------------------------------------------------------------- #
# Point 5 : un coup qui vide la main est joué sans modification.
# --------------------------------------------------------------------------- #

@besoin_exact
def test_chances_prochain_tour_coup_qui_vide_la_main_joue_tel_quel():
    niveaux.BRIDAGES["Champion du Monde"] = _bridage_chances_seule()
    try:
        etat = _etat([T("rouge_3_a", 3, "rouge"), T("bleu_3_a", 3, "bleu"),
                     T("noir_3_a", 3, "noir")])
        coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")
    finally:
        niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
            niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_3_a", "bleu_3_a", "noir_3_a"}
    assert "chances_prochain_tour_info" not in coup


# --------------------------------------------------------------------------- #
# Point 5 : désactivée dès que le chevalet restant compte au plus une tuile.
# --------------------------------------------------------------------------- #

@besoin_exact
def test_chances_prochain_tour_chevalet_restant_trop_petit_sans_effet():
    niveaux.BRIDAGES["Champion du Monde"] = _bridage_chances_seule()
    try:
        etat = _etat([T("rouge_3_a", 3, "rouge"), T("bleu_3_a", 3, "bleu"),
                     T("noir_3_a", 3, "noir"), T("rouge_9_a", 9, "rouge")])
        attendu = ia.jouer_niveau_expert(etat, 1)
        coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")
    finally:
        niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
            niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == set(attendu["ids_tuiles"])
    info = coup["chances_prochain_tour_info"]
    assert info["declenchee"] is False
