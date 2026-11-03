"""Tests de la stratégie ``reserve_tuile`` (issue #229, hypothèse H2) :
garder une tuile du chevalet que le meilleur coup du solveur aurait posée,
pour disposer d'un coup au tour suivant plutôt que de piocher.

Positions de test fixes (point 5 de l'issue), construites à la main. Les
tuiles de remplissage (préfixe ``_f``) sont choisies pour ne jamais former
de combinaison entre elles (valeurs toutes distinctes) ni avec le reste de
la main — seulement pour ajuster la taille du chevalet."""

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
    """``n`` tuiles de remplissage, toutes de valeurs distinctes (aucune
    combinaison possible, ni entre elles ni avec le reste de la main)."""
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


def _bridage_reserve_seule():
    return niveaux.bridage_champion_personnalise(["reserve_tuile"])


# Groupe de 3 tuiles au tapis (valeur 7) + 4e tuile en main (jaune 7) + une
# AUTRE combinaison posable (suite jaune 10-11-12) : le meilleur coup du
# solveur pose les 4 tuiles (jaune 7 + la suite) ; le candidat « réserve »
# garde jaune 7 et ne pose que la suite (3 tuiles, écart 1 ≤ ECART_MAX_RESERVE).
def _chevalet_reserve(nb_filler):
    return ([T("jaune_7_a", 7, "jaune"),
            T("jaune_10_a", 10, "jaune"), T("jaune_11_a", 11, "jaune"),
            T("jaune_12_a", 12, "jaune")]
           + _fillers(nb_filler))


def _plateau_groupe_7():
    return [[T("rouge_7_a", 7, "rouge"), T("bleu_7_a", 7, "bleu"),
            T("noir_7_a", 7, "noir")]]


@besoin_exact
def test_reserve_tuile_garde_la_quatrieme_tuile_du_groupe():
    """Chevalet assez grand pour que la condition (d) (chevalet après coup
    > SEUIL_FIN_PARTIE_VERIF_FINITION) soit vérifiée : la stratégie change le
    coup, garde jaune 7, et ne pose que la suite jaune 10-11-12."""
    niveaux.BRIDAGES["Champion du Monde"] = _bridage_reserve_seule()
    try:
        etat = _etat(_chevalet_reserve(nb_filler=5), plateau=_plateau_groupe_7())
        taille_main = len(etat["joueurs"][1]["chevalet"])
        assert taille_main == 9
        coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")
    finally:
        niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
            niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"jaune_10_a", "jaune_11_a", "jaune_12_a"}
    assert "jaune_7_a" not in coup["ids_tuiles"]
    assert coup["solveur"] == ia.SOLVEUR_RESERVE_TUILE
    info = coup["reserve_tuile_info"]
    assert info["declenchee"] is True
    assert info["choisi"] is True
    assert info["nb_tuiles_gardees"] == 1
    assert info["id_tuile_gardee"] == "jaune_7_a"


@besoin_exact
def test_reserve_tuile_chevalet_moins_de_6_decision_inchangee():
    """Même position, mais avec un chevalet de moins de 6 tuiles (condition
    (d) : chevalet après coup resterait ≤ SEUIL_FIN_PARTIE_VERIF_FINITION) —
    la stratégie ne change rien, même décision qu'avec le solveur seul."""
    niveaux.BRIDAGES["Champion du Monde"] = _bridage_reserve_seule()
    try:
        etat = _etat(_chevalet_reserve(nb_filler=1), plateau=_plateau_groupe_7())
        taille_main = len(etat["joueurs"][1]["chevalet"])
        assert taille_main < 6
        attendu = ia.jouer_niveau_expert(etat, 1)
        coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")
    finally:
        niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
            niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == set(attendu["ids_tuiles"])
    assert coup["reserve_tuile_info"]["choisi"] is False


@besoin_exact
def test_reserve_tuile_coup_qui_vide_la_main_joue_tel_quel():
    """Un coup qui vide la main gagne la partie : jamais modifié par la
    stratégie, quelle que soit la taille du chevalet (condition (e))."""
    niveaux.BRIDAGES["Champion du Monde"] = _bridage_reserve_seule()
    try:
        etat = _etat([T("rouge_7_a", 7, "rouge"), T("bleu_7_a", 7, "bleu"),
                     T("noir_7_a", 7, "noir")])
        coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")
    finally:
        niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
            niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_7_a", "bleu_7_a", "noir_7_a"}
    # Jamais soumis à la stratégie : aucune annotation ajoutée.
    assert "reserve_tuile_info" not in coup


@besoin_exact
def test_reserve_tuile_desactivee_decision_identique_a_avant():
    """Stratégie désactivée (registre par défaut, #228) : décision
    identique à celle du solveur seul, aucune annotation ajoutée."""
    etat = _etat(_chevalet_reserve(nb_filler=5), plateau=_plateau_groupe_7())
    attendu = ia.jouer_niveau_expert(etat, 1)
    coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == set(attendu["ids_tuiles"])
    assert "reserve_tuile_info" not in coup


@besoin_exact
def test_expert_inchange_meme_position():
    """Expert n'a jamais accès à ``reserve_tuile`` (registre, #228/#229) :
    même décision avec ou sans la stratégie forcée pour Champion du Monde
    uniquement."""
    etat = _etat(_chevalet_reserve(nb_filler=5), plateau=_plateau_groupe_7(),
                niveau="Expert")
    attendu = ia.jouer_niveau_expert(etat, 1)

    niveaux.BRIDAGES["Champion du Monde"] = _bridage_reserve_seule()
    try:
        coup = ia.jouer_niveau_bride(etat, 1, "Expert")
    finally:
        niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
            niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == set(attendu["ids_tuiles"])
    assert "reserve_tuile_info" not in coup
