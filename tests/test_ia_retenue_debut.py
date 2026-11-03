"""Tests de la stratégie ``retenue_debut`` (issue #229, hypothèse H1) :
plafonner le nombre de tuiles posées par tour pendant les premiers tours qui
suivent la propre ouverture du joueur.

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
    return [T(f"{_COULEURS[i % 4]}_{depart + i}_f", depart + i, _COULEURS[i % 4])
           for i in range(n)]


def _historique_ouverture(idx, tours_depuis_ouverture):
    """Historique minimal : une ouverture (points > 0) au tour 1 pour
    ``idx``, suivie de ``tours_depuis_ouverture`` tours (points = 0, comme
    une pioche — le type d'action réelle ne compte pas pour le compteur,
    seul le nombre de tours importe, voir
    ``ia._nb_tours_joueur_depuis_ouverture``)."""
    historique = [{"joueur_index": idx, "points": 30, "tour": 1}]
    for t in range(2, 2 + tours_depuis_ouverture):
        historique.append({"joueur_index": idx, "points": 0, "tour": t})
    return historique


def _etat(chevalet, plateau, tours_depuis_ouverture=0,
         mise_initiale_faite=True, niveau="Champion du Monde"):
    return {
        "joueurs": [
            {"nom": "Humain", "est_ia": False, "niveau": None,
             "chevalet": [], "mise_initiale_faite": True},
            {"nom": "Bot", "est_ia": True, "niveau": niveau,
             "chevalet": chevalet, "mise_initiale_faite": mise_initiale_faite},
        ],
        "plateau": plateau,
        "config": {"nb_manches": 1, "valeur_joker_penalite": 30,
                   "mise_initiale_min": 30},
        "index_joueur_actuel": 1,
        "historique": _historique_ouverture(1, tours_depuis_ouverture),
        "tour_numero": 10 + tours_depuis_ouverture,
    }


def _bridage_retenue_seule():
    return niveaux.bridage_champion_personnalise(["retenue_debut"])


def _plateau_suite_rouge(n=3):
    return [[T(f"rouge_{v}_a", v, "rouge") for v in range(1, n + 1)]]


def _chevalet_extension(n_extension, n_filler):
    """``n_extension`` tuiles qui prolongent la suite rouge du plateau +
    ``n_filler`` tuiles de remplissage sans combinaison possible."""
    extension = [T(f"rouge_{v}_a", v, "rouge") for v in range(4, 4 + n_extension)]
    return extension + _fillers(n_filler)


def _restaurer():
    niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
        niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)


@besoin_exact
def test_retenue_debut_plafond_respecte_pendant_la_fenetre():
    """Dans la fenêtre (tours écoulés < TOURS_RETENUE_DEBUT), tapis < seuil,
    chevalet > 8 : le coup est plafonné à POSE_MAX_DEBUT tuiles, même si le
    solveur pourrait en poser davantage."""
    niveaux.BRIDAGES["Champion du Monde"] = _bridage_retenue_seule()
    try:
        etat = _etat(_chevalet_extension(n_extension=3, n_filler=6),
                    _plateau_suite_rouge(), tours_depuis_ouverture=0)
        taille_main = len(etat["joueurs"][1]["chevalet"])
        assert taille_main > 8
        attendu = ia.jouer_niveau_expert(etat, 1)
        assert len(attendu["ids_tuiles"]) > niveaux.POSE_MAX_DEBUT
        coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")
    finally:
        _restaurer()

    assert coup["action"] == "jouer"
    assert len(coup["ids_tuiles"]) == niveaux.POSE_MAX_DEBUT
    assert coup["solveur"] == ia.SOLVEUR_RETENUE_DEBUT
    info = coup["retenue_debut_info"]
    assert info["declenchee"] is True
    assert info["choisi"] is True
    assert info["nb_tuiles_posees"] == niveaux.POSE_MAX_DEBUT


@besoin_exact
def test_retenue_debut_aucun_effet_apres_la_fenetre():
    """Au-delà de TOURS_RETENUE_DEBUT tours depuis l'ouverture : même
    décision qu'avec le solveur seul."""
    niveaux.BRIDAGES["Champion du Monde"] = _bridage_retenue_seule()
    try:
        etat = _etat(_chevalet_extension(n_extension=3, n_filler=6),
                    _plateau_suite_rouge(),
                    tours_depuis_ouverture=niveaux.TOURS_RETENUE_DEBUT)
        attendu = ia.jouer_niveau_expert(etat, 1)
        coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")
    finally:
        _restaurer()

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == set(attendu["ids_tuiles"])
    assert coup["retenue_debut_info"]["declenchee"] is False


@besoin_exact
def test_retenue_debut_aucun_effet_avant_ouverture():
    """Mise initiale pas encore faite (pose d'ouverture elle-même, ou
    tour antérieur) : aucun effet, décision identique au solveur seul."""
    niveaux.BRIDAGES["Champion du Monde"] = _bridage_retenue_seule()
    try:
        chevalet = [T("rouge_8_a", 8, "rouge"), T("rouge_9_a", 9, "rouge"),
                   T("rouge_10_a", 10, "rouge"), T("rouge_11_a", 11, "rouge"),
                   T("rouge_12_a", 12, "rouge")] + _fillers(5)
        etat = _etat(chevalet, plateau=[], tours_depuis_ouverture=0,
                    mise_initiale_faite=False)
        attendu = ia.jouer_niveau_expert(etat, 1)
        coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")
    finally:
        _restaurer()

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == set(attendu["ids_tuiles"])
    assert coup["retenue_debut_info"]["declenchee"] is False


@besoin_exact
def test_retenue_debut_aucun_coup_dans_le_plafond_joue_le_coup_normal():
    """Si aucune combinaison ne tient dans le plafond (ici : il faut au
    moins 3 tuiles pour toute nouvelle combinaison, le plateau est vide),
    le coup normal est joué tel quel — jamais une pioche alors qu'un coup
    existe (contrainte de l'issue)."""
    niveaux.BRIDAGES["Champion du Monde"] = _bridage_retenue_seule()
    try:
        chevalet = ([T("rouge_1_a", 1, "rouge"), T("rouge_2_a", 2, "rouge"),
                    T("rouge_3_a", 3, "rouge")] + _fillers(6))
        etat = _etat(chevalet, plateau=[], tours_depuis_ouverture=0)
        taille_main = len(etat["joueurs"][1]["chevalet"])
        assert taille_main > 8
        attendu = ia.jouer_niveau_expert(etat, 1)
        assert len(attendu["ids_tuiles"]) == 3 > niveaux.POSE_MAX_DEBUT
        coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")
    finally:
        _restaurer()

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == set(attendu["ids_tuiles"])
    info = coup["retenue_debut_info"]
    assert info["declenchee"] is True
    assert info["choisi"] is False


@besoin_exact
def test_retenue_debut_desactivee_decision_identique_a_avant():
    """Stratégie désactivée (registre par défaut, #228) : décision
    identique à celle du solveur seul, aucune annotation ajoutée."""
    etat = _etat(_chevalet_extension(n_extension=3, n_filler=6),
                _plateau_suite_rouge(), tours_depuis_ouverture=0)
    attendu = ia.jouer_niveau_expert(etat, 1)
    coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == set(attendu["ids_tuiles"])
    assert "retenue_debut_info" not in coup


@besoin_exact
def test_expert_inchange_meme_position():
    """Expert n'a jamais accès à ``retenue_debut`` (registre, #228/#229) :
    même décision avec ou sans la stratégie forcée pour Champion du Monde
    uniquement."""
    etat = _etat(_chevalet_extension(n_extension=3, n_filler=6),
                _plateau_suite_rouge(), tours_depuis_ouverture=0,
                niveau="Expert")
    attendu = ia.jouer_niveau_expert(etat, 1)

    niveaux.BRIDAGES["Champion du Monde"] = _bridage_retenue_seule()
    try:
        coup = ia.jouer_niveau_bride(etat, 1, "Expert")
    finally:
        _restaurer()

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == set(attendu["ids_tuiles"])
    assert "retenue_debut_info" not in coup
