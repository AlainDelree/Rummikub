"""Tests de la stratégie ``petits_chiffres`` (issue #230, hypothèse H4) :
garder les petites tuiles (valeur ≤ ``niveaux.VALEUR_MAX_PETITS``) en main
pour bloquer l'adversaire — un ex-champion du monde néerlandais (Matthijs
Delvers, 2026) conseille de garder les petites tuiles comme les 3.

Positions de test fixes (point 6 de l'issue), construites à la main — même
convention que ``tests/test_ia_reserve_tuile.py`` (préfixe ``_f`` pour les
tuiles de remplissage, valeurs toutes distinctes, aucune combinaison
possible ni entre elles ni avec le reste de la main)."""

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


def _bridage_petits_chiffres_seule():
    return niveaux.bridage_champion_personnalise(["petits_chiffres"])


def _bridage_petits_chiffres_tolerant():
    """Même stratégie, avec la variante tolérante (``ECART_TUILES_PETITS``)
    activée pour la durée du test — restaurée par l'appelant."""
    return niveaux.bridage_champion_personnalise(["petits_chiffres"])


# --------------------------------------------------------------------------- #
# Critère de départage (point 2) : deux groupes de taille égale (3 tuiles),
# l'un de petite valeur (3), l'autre de grande valeur (9), qui se disputent
# le SEUL joker du chevalet (un seul des deux est donc posable) — plateau
# vide, donc perturbation strictement à égalité (0,0) pour les deux options,
# quel que soit le choix : seul le critère ``petits_chiffres`` (ou, sans
# lui, les points posés, qui favorisent déjà la grande valeur) décide.
# --------------------------------------------------------------------------- #

def _chevalet_dilemme(nb_filler):
    return ([T("rouge_3_a", 3, "rouge"), T("bleu_3_a", 3, "bleu"),
            T("rouge_9_a", 9, "rouge"), T("bleu_9_a", 9, "bleu"),
            T("joker_1", None, "noir", j=True)]
           + _fillers(nb_filler))


@besoin_exact
def test_petits_chiffres_garde_la_petite_tuile_en_main():
    """Chevalet assez grand pour que la stratégie s'applique (> seuil de fin
    de partie) : avec ``petits_chiffres`` seule, le coup choisi pose le
    groupe de 9 (joker + les deux 9) et garde les deux 3 en main."""
    niveaux.BRIDAGES["Champion du Monde"] = _bridage_petits_chiffres_seule()
    try:
        etat = _etat(_chevalet_dilemme(nb_filler=5))
        taille_main = len(etat["joueurs"][1]["chevalet"])
        assert taille_main > niveaux.SEUIL_FIN_PARTIE_VERIF_FINITION
        coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")
    finally:
        niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
            niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_9_a", "bleu_9_a", "joker_1"}
    assert "rouge_3_a" not in coup["ids_tuiles"]
    assert "bleu_3_a" not in coup["ids_tuiles"]


@besoin_exact
def test_petits_chiffres_desactivee_decision_identique_a_avant():
    """Stratégie désactivée (registre par défaut, #228) : décision identique
    à celle du solveur seul (aucun changement de comportement sans elle)."""
    etat = _etat(_chevalet_dilemme(nb_filler=5))
    attendu = ia.jouer_niveau_expert(etat, 1)
    coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == set(attendu["ids_tuiles"])
    assert "petits_chiffres_info" not in coup


@besoin_exact
def test_expert_inchange_meme_position():
    """Expert n'a jamais accès à ``petits_chiffres`` (registre, #228/#230) :
    même décision avec ou sans la stratégie forcée pour Champion du Monde
    uniquement."""
    etat = _etat(_chevalet_dilemme(nb_filler=5), niveau="Expert")
    attendu = ia.jouer_niveau_expert(etat, 1)

    niveaux.BRIDAGES["Champion du Monde"] = _bridage_petits_chiffres_seule()
    try:
        coup = ia.jouer_niveau_bride(etat, 1, "Expert")
    finally:
        niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
            niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == set(attendu["ids_tuiles"])
    assert "petits_chiffres_info" not in coup


# --------------------------------------------------------------------------- #
# Limite (point 4) : chevalet plus petit que le seuil de fin de partie —
# décision inchangée, même avec la stratégie forcée.
# --------------------------------------------------------------------------- #

@besoin_exact
def test_petits_chiffres_chevalet_petit_decision_inchangee():
    niveaux.BRIDAGES["Champion du Monde"] = _bridage_petits_chiffres_seule()
    try:
        etat = _etat(_chevalet_dilemme(nb_filler=0))
        taille_main = len(etat["joueurs"][1]["chevalet"])
        assert taille_main <= niveaux.SEUIL_FIN_PARTIE_VERIF_FINITION
        attendu = ia.jouer_niveau_expert(etat, 1)
        coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")
    finally:
        niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
            niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == set(attendu["ids_tuiles"])
    assert "petits_chiffres_info" not in coup


# --------------------------------------------------------------------------- #
# Coup gagnant jamais modifié (point 4, condition (e) de la brique #221).
# --------------------------------------------------------------------------- #

@besoin_exact
def test_petits_chiffres_coup_qui_vide_la_main_joue_tel_quel():
    niveaux.BRIDAGES["Champion du Monde"] = _bridage_petits_chiffres_seule()
    try:
        etat = _etat([T("rouge_3_a", 3, "rouge"), T("bleu_3_a", 3, "bleu"),
                     T("noir_3_a", 3, "noir")])
        coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")
    finally:
        niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
            niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_3_a", "bleu_3_a", "noir_3_a"}
    assert "petits_chiffres_info" not in coup


# --------------------------------------------------------------------------- #
# Variante tolérante (point 3) : ECART_TUILES_PETITS == 1 — un coup qui pose
# une tuile de moins peut être préféré s'il évite de poser une petite tuile.
# Même construction que ``test_ia_reserve_tuile`` (groupe de 3 au tapis + 4e
# tuile en main + suite séparée), mais la 4e tuile est PETITE (valeur 3).
# --------------------------------------------------------------------------- #

def _chevalet_tolerant(nb_filler):
    return ([T("jaune_3_a", 3, "jaune"),
            T("jaune_10_a", 10, "jaune"), T("jaune_11_a", 11, "jaune"),
            T("jaune_12_a", 12, "jaune")]
           + _fillers(nb_filler))


def _plateau_groupe_3():
    return [[T("rouge_3_a", 3, "rouge"), T("bleu_3_a", 3, "bleu"),
            T("noir_3_a", 3, "noir")]]


@besoin_exact
def test_petits_chiffres_base_seule_ne_change_pas_un_optimum_unique():
    """Sans la variante tolérante (``ECART_TUILES_PETITS == 0``, défaut) :
    le départage à nombre de tuiles posées égal ne peut PAS réduire le
    nombre de tuiles posées — ``jaune_3`` (petite) reste posée avec la
    suite, car c'est l'unique optimum (4 tuiles, pas de tuile de moins)."""
    niveaux.BRIDAGES["Champion du Monde"] = _bridage_petits_chiffres_seule()
    try:
        assert niveaux.ECART_TUILES_PETITS == 0
        etat = _etat(_chevalet_tolerant(nb_filler=5), plateau=_plateau_groupe_3())
        coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")
    finally:
        niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
            niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {
        "jaune_3_a", "jaune_10_a", "jaune_11_a", "jaune_12_a"}
    info = coup["petits_chiffres_info"]
    assert info["declenchee"] is True
    assert info["choisi"] is False


@besoin_exact
def test_petits_chiffres_variante_tolerante_garde_la_petite_tuile(monkeypatch):
    """Avec ``ECART_TUILES_PETITS == 1`` : le coup qui pose une tuile de
    moins (la suite seule, 3 tuiles) et garde ``jaune_3`` en main est
    préféré au coup qui en pose 4 (dont la petite tuile)."""
    monkeypatch.setattr(niveaux, "ECART_TUILES_PETITS", 1)
    niveaux.BRIDAGES["Champion du Monde"] = _bridage_petits_chiffres_tolerant()
    try:
        etat = _etat(_chevalet_tolerant(nb_filler=5), plateau=_plateau_groupe_3())
        taille_main = len(etat["joueurs"][1]["chevalet"])
        assert taille_main == 9
        coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")
    finally:
        niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
            niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"jaune_10_a", "jaune_11_a", "jaune_12_a"}
    assert "jaune_3_a" not in coup["ids_tuiles"]
    assert coup["solveur"] == ia.SOLVEUR_PETITS_CHIFFRES
    info = coup["petits_chiffres_info"]
    assert info["declenchee"] is True
    assert info["choisi"] is True
    assert info["nb_petites_posees_avant"] == 1
    assert info["nb_petites_posees_apres"] == 0


@besoin_exact
def test_petits_chiffres_variante_tolerante_chevalet_trop_petit_apres_coup(
        monkeypatch):
    """Chevalet au-dessus du seuil AVANT de jouer (stratégie déclenchée),
    mais le candidat laisserait un chevalet ≤ seuil (condition (d) de
    ``_appliquer_petits_chiffres``) : la variante tolérante ne change rien,
    même décision que le solveur seul."""
    monkeypatch.setattr(niveaux, "ECART_TUILES_PETITS", 1)
    niveaux.BRIDAGES["Champion du Monde"] = _bridage_petits_chiffres_tolerant()
    try:
        etat = _etat(_chevalet_tolerant(nb_filler=3), plateau=_plateau_groupe_3())
        taille_main = len(etat["joueurs"][1]["chevalet"])
        assert niveaux.SEUIL_FIN_PARTIE_VERIF_FINITION < taille_main <= 8
        attendu = ia.jouer_niveau_expert(etat, 1)
        coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")
    finally:
        niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
            niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == set(attendu["ids_tuiles"])
    info = coup["petits_chiffres_info"]
    assert info["declenchee"] is True
    assert info["candidat_existe"] is True
    assert info["choisi"] is False
