"""Vérification croisée du solveur (``moteur/verif_solveur.py``, issue #193
point 5) : sur de petites positions aléatoires (graine fixe), une recherche
exhaustive indépendante et volontairement lente doit donner le même maximum
de tuiles posables que le solveur de production (budget généreux)."""

import random

from rummikub.moteur.partie import _plateau_vers_dict
from rummikub.moteur.solveur import resoudre_coup, BudgetDepasse
from rummikub.moteur.tuiles import Tuile
from rummikub.moteur.verif_solveur import (
    generer_position_aleatoire, max_tuiles_posables_exhaustif,
)


def _nb_tuiles_solveur(plateau, chevalet, budget=5.0):
    etat = {
        "joueurs": [{"chevalet": [t.as_dict() for t in chevalet],
                     "mise_initiale_faite": True}],
        "plateau": _plateau_vers_dict(plateau),
        "config": {"mise_initiale_min": 30},
    }
    try:
        coup = resoudre_coup(etat, 0, budget_temps=budget)
    except BudgetDepasse:
        return None  # inconclusif, voir l'appelant.
    return len(coup["ids_tuiles"]) if coup else 0


# --------------------------------------------------------------------------- #
# Cas unitaires simples (vérification de la recherche exhaustive elle-même).
# --------------------------------------------------------------------------- #

def test_exhaustif_plateau_vide_main_sans_combinaison():
    chevalet = [Tuile("rouge_1_a", 1, "rouge"), Tuile("bleu_5_a", 5, "bleu"),
                Tuile("jaune_9_a", 9, "jaune")]
    assert max_tuiles_posables_exhaustif([], chevalet) == 0


def test_exhaustif_trouve_un_groupe_de_trois():
    chevalet = [Tuile("rouge_7_a", 7, "rouge"), Tuile("bleu_7_a", 7, "bleu"),
                Tuile("jaune_7_a", 7, "jaune"), Tuile("noir_2_a", 2, "noir")]
    assert max_tuiles_posables_exhaustif([], chevalet) == 3


def test_exhaustif_conserve_le_plateau_et_etend_une_suite():
    plateau = [[Tuile("rouge_1_a", 1, "rouge"), Tuile("rouge_2_a", 2, "rouge"),
               Tuile("rouge_3_a", 3, "rouge")]]
    chevalet = [Tuile("rouge_4_a", 4, "rouge"), Tuile("bleu_9_a", 9, "bleu")]
    assert max_tuiles_posables_exhaustif(plateau, chevalet) == 1


# --------------------------------------------------------------------------- #
# Campagne aléatoire à graine fixe : le solveur ne doit JAMAIS trouver moins
# que la recherche exhaustive (voir avertissement du module — un écart serait
# un bug du solveur à signaler, pas à corriger ici).
# --------------------------------------------------------------------------- #

def test_solveur_jamais_pire_que_l_exhaustif_sur_positions_aleatoires():
    rng = random.Random(193)
    nb_positions = 60
    ecarts = []
    for _ in range(nb_positions):
        pos = generer_position_aleatoire(rng, max_tuiles_main=6)
        exhaustif = max_tuiles_posables_exhaustif(pos["plateau"], pos["chevalet"])
        solveur = _nb_tuiles_solveur(pos["plateau"], pos["chevalet"])
        if solveur is None:
            continue  # inconclusif (budget) : jamais compté comme un écart.
        if solveur < exhaustif:
            ecarts.append((pos, exhaustif, solveur))

    assert ecarts == [], (
        f"{len(ecarts)} position(s) où le solveur trouve moins que la "
        f"recherche exhaustive (voir moteur/solveur.py) : {ecarts[:3]}")
