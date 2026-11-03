"""Tests directs de la brique « Sorties » (issue #231, anciennement « tuiles
vivantes ») : ``moteur/sorties.py`` — calcul SANS passer par ``ia.py`` ni le
solveur exact (point 7 de l'issue)."""

from rummikub.moteur import sorties


def T(id_, v, c, j=False):
    return {"id": id_, "valeur": v, "couleur": c, "est_joker": j}


def _etat(chevalet, plateau=None, pioche_taille=20):
    return {
        "joueurs": [
            {"nom": "Humain", "chevalet": []},
            {"nom": "Bot", "chevalet": chevalet},
        ],
        "plateau": plateau or [],
        "pioche": [T(f"f{i}", 1, "rouge") for i in range(pioche_taille)],
    }


# --------------------------------------------------------------------------- #
# Point 7 : une paire qui se complète par une seule tuile encore disponible
# contre une paire isolée — la première a le score le plus élevé.
# --------------------------------------------------------------------------- #

def test_paire_qui_se_complete_a_un_meilleur_score_qu_une_paire_isolee():
    chevalet_complete = [T("rouge_5_a", 5, "rouge"), T("rouge_6_a", 6, "rouge")]
    chevalet_isole = [T("rouge_5_a", 5, "rouge"), T("bleu_9_a", 9, "bleu")]

    sorties_completes = sorties.sorties_chevalet(chevalet_complete, [])
    assert sorties_completes == {("rouge", 4), ("rouge", 7), ("joker", None)}
    assert sorties.sorties_chevalet(chevalet_isole, []) == set()

    score_complete = sorties.score_chevalet(
        chevalet_complete, [], _etat(chevalet_complete), 1)
    score_isole = sorties.score_chevalet(
        chevalet_isole, [], _etat(chevalet_isole), 1)

    assert score_isole == 0.0
    assert score_complete > score_isole


# --------------------------------------------------------------------------- #
# Point 7 : une sortie dont tous les exemplaires sont connus (donc
# indisponibles) ne compte pas dans le score.
# --------------------------------------------------------------------------- #

def test_sortie_aux_exemplaires_tous_connus_ne_compte_pas():
    # red_5/blue_5 (chevalet) se complètent par jaune_5 ou noir_5, plus le
    # joker — mais les DEUX exemplaires de jaune_5 et de noir_5 sont déjà sur
    # le tapis (deux groupes de 3), et les DEUX jokers sont déjà en main :
    # toutes les sorties identifiées sont donc indisponibles.
    chevalet = [T("rouge_5_a", 5, "rouge"), T("bleu_5_a", 5, "bleu"),
               T("joker_1", None, "rouge", True), T("joker_2", None, "noir", True)]
    plateau = [
        [T("jaune_5_a", 5, "jaune"), T("noir_5_a", 5, "noir"), T("rouge_5_b", 5, "rouge")],
        [T("jaune_5_b", 5, "jaune"), T("noir_5_b", 5, "noir"), T("bleu_5_b", 5, "bleu")],
    ]

    cles = sorties.sorties_chevalet(chevalet, plateau)
    assert {("jaune", 5), ("noir", 5)} <= cles

    score = sorties.score_chevalet(chevalet, plateau, _etat(chevalet, plateau), 1)
    assert score == 0.0


def test_sorties_chevalet_groupe_couleurs_differentes():
    chevalet = [T("rouge_7_a", 7, "rouge"), T("bleu_7_a", 7, "bleu")]
    assert sorties.sorties_chevalet(chevalet, []) == {
        ("jaune", 7), ("noir", 7), ("joker", None)}


def test_sorties_chevalet_paire_espacee_d_une():
    chevalet = [T("rouge_5_a", 5, "rouge"), T("rouge_7_a", 7, "rouge")]
    assert sorties.sorties_chevalet(chevalet, []) == {
        ("rouge", 6), ("joker", None)}


def test_sorties_chevalet_jokers_exclus_de_la_regle_de_paire():
    """Un joker du chevalet ne forme jamais, seul, la moitié d'une paire
    (il n'a ni couleur ni valeur propres) — seules les tuiles RÉELLES du
    chevalet participent à la règle de paire."""
    chevalet = [T("joker_1", None, "rouge", True), T("rouge_5_a", 5, "rouge")]
    assert sorties.sorties_chevalet(chevalet, []) == set()


def test_sorties_rattachement_prolonge_une_suite_du_tapis():
    plateau = [[T("rouge_10_a", 10, "rouge"), T("rouge_11_a", 11, "rouge"),
               T("rouge_12_a", 12, "rouge")]]
    assert sorties.sorties_chevalet([], plateau) == {
        ("rouge", 9), ("rouge", 13), ("joker", None)}


def test_sorties_rattachement_complete_un_groupe_de_trois():
    plateau = [[T("rouge_7_a", 7, "rouge"), T("bleu_7_a", 7, "bleu"),
               T("jaune_7_a", 7, "jaune")]]
    assert sorties.sorties_chevalet([], plateau) == {
        ("noir", 7), ("joker", None)}


def test_sorties_rattachement_groupe_complet_sans_sortie():
    """Un groupe déjà à 4 tuiles ne peut plus être complété (plafond du
    jeu)."""
    plateau = [[T("rouge_7_a", 7, "rouge"), T("bleu_7_a", 7, "bleu"),
               T("jaune_7_a", 7, "jaune"), T("noir_7_a", 7, "noir")]]
    assert sorties.sorties_chevalet([], plateau) == set()
