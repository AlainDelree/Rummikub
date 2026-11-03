"""Tests de la stratégie ``placement_joker`` (issue #232) : pour un coup qui
pose un joker du chevalet, à nombre de tuiles posées égal, préférer le
placement le moins exposé à une reprise par l'adversaire.

Deux niveaux de test, même convention que ``tests/test_sorties.py``/
``tests/test_ia_chances_prochain_tour.py`` :

1. la brique de calcul (``_types_remplacement_joker``/``_exposition_coup_
   joker``), testée DIRECTEMENT sur des dicts construits à la main — évite
   de dépendre du modèle exact pour les cas où seule l'exposition compte
   (le solveur complet, à perturbation illimitée, peut toujours trouver un
   réarrangement global plus rentable qu'un plateau construit à la main —
   voir CONTEXTE.md §13, point sur les limites de construction de position) ;
2. la stratégie bout-en-bout (``ia.jouer_niveau_bride``), sur une position
   SANS tapis (aucun réarrangement possible) où le dilemme porte uniquement
   sur l'usage du joker (une suite OU une série, jamais les deux à la fois,
   puisqu'un seul joker est disponible)."""

import pytest

from rummikub.moteur import ia, niveaux
from rummikub.moteur import solveur_exact as se

besoin_exact = pytest.mark.skipif(
    not se.DISPONIBLE,
    reason="highspy/numpy absents (dépendances du modèle exact d'Expert)")


def T(id_, v, c, j=False):
    return {"id": id_, "valeur": v, "couleur": c, "est_joker": j}


# --------------------------------------------------------------------------- #
# Brique directe : règles de remplacement (point 1 de l'issue, CONTEXTE.md
# §13) et exposition (point 3).
# --------------------------------------------------------------------------- #

def test_types_remplacement_suite_milieu_une_seule_valeur():
    combo = [T("rouge_5_a", 5, "rouge"), T("joker_1", None, "noir", j=True),
             T("rouge_7_a", 7, "rouge")]
    assert ia._types_remplacement_joker(combo, 1) == [("rouge", 6)]


def test_types_remplacement_suite_bout_une_seule_valeur_aussi():
    """Ce moteur ne distingue PAS le joker en bout de suite du joker au
    milieu (CONTEXTE.md §13, point 1) : les deux donnent UNE seule valeur
    de remplacement, déduite de la position — contrairement à l'intuition
    de l'énoncé de l'issue (deux valeurs voisines pour le cas « bout »)."""
    combo = [T("rouge_5_a", 5, "rouge"), T("rouge_6_a", 6, "rouge"),
             T("joker_1", None, "noir", j=True)]
    assert ia._types_remplacement_joker(combo, 2) == [("rouge", 7)]


def test_types_remplacement_groupe_deux_couleurs_manquantes():
    combo = [T("rouge_5_a", 5, "rouge"), T("bleu_5_a", 5, "bleu"),
             T("joker_1", None, "noir", j=True)]
    assert set(ia._types_remplacement_joker(combo, 2)) == {
        ("jaune", 5), ("noir", 5)}


def test_types_remplacement_combinaison_de_quatre_hors_scope():
    """Une combinaison de 4 tuiles ou plus peut libérer le joker SANS
    remplacement (CONTEXTE.md §8) : hors de portée de cette stratégie,
    jamais mesurée (point 3 de l'issue)."""
    combo = [T("rouge_5_a", 5, "rouge"), T("bleu_5_a", 5, "bleu"),
             T("jaune_5_a", 5, "jaune"), T("joker_1", None, "noir", j=True)]
    assert ia._types_remplacement_joker(combo, 3) is None


def test_exposition_suite_milieu_deux_exemplaires_inconnus():
    etat = {"joueurs": [{"chevalet": [
        T("rouge_5_a", 5, "rouge"), T("rouge_7_a", 7, "rouge"),
        T("joker_1", None, "noir", j=True)]}], "pioche": []}
    coup = {"ids_tuiles": ["rouge_5_a", "rouge_7_a", "joker_1"],
           "nouveau_plateau": [[
               T("rouge_5_a", 5, "rouge"),
               T("joker_1", None, "noir", j=True),
               T("rouge_7_a", 7, "rouge")]]}
    score, info = ia._exposition_coup_joker(etat, 0, coup)
    assert score == 2
    assert info["details"][0]["types"] == [("rouge", 6)]


def test_exposition_nulle_les_deux_remplacants_sont_connus():
    """Les deux couleurs manquantes du groupe sont déjà visibles au tapis
    (4 exemplaires comptés) : exposition nulle — l'adversaire ne peut pas
    reprendre ce joker (point 3 de l'issue)."""
    chevalet = [T("rouge_9_a", 9, "rouge"), T("bleu_9_a", 9, "bleu"),
               T("joker_1", None, "noir", j=True)]
    nouveau_plateau = [
        [T("rouge_9_a", 9, "rouge"), T("bleu_9_a", 9, "bleu"),
         T("joker_1", None, "noir", j=True)],
        [T("jaune_9_a", 9, "jaune"), T("jaune_10_a", 10, "jaune"),
         T("jaune_11_a", 11, "jaune")],
        [T("jaune_9_b", 9, "jaune"), T("jaune_10_b", 10, "jaune"),
         T("jaune_11_b", 11, "jaune")],
        [T("noir_9_a", 9, "noir"), T("noir_10_a", 10, "noir"),
         T("noir_11_a", 11, "noir")],
        [T("noir_9_b", 9, "noir"), T("noir_10_b", 10, "noir"),
         T("noir_11_b", 11, "noir")],
    ]
    etat = {"joueurs": [{"chevalet": chevalet}], "pioche": []}
    coup = {"ids_tuiles": ["rouge_9_a", "bleu_9_a", "joker_1"],
           "nouveau_plateau": nouveau_plateau}
    score, info = ia._exposition_coup_joker(etat, 0, coup)
    assert score == 0
    assert info["exclu"] is False


def test_exposition_exclue_si_je_detiens_la_tuile_de_remplacement():
    """Nuance d'Alain (point 4 de l'issue) : si notre main contient encore,
    APRÈS le coup, la tuile qui remplacerait le joker, ce placement est
    exclu du critère — un bon joueur jouerait cette tuile plutôt que le
    joker."""
    chevalet = [T("rouge_5_a", 5, "rouge"), T("rouge_7_a", 7, "rouge"),
               T("joker_1", None, "noir", j=True), T("rouge_6_b", 6, "rouge")]
    coup = {"ids_tuiles": ["rouge_5_a", "rouge_7_a", "joker_1"],
           "nouveau_plateau": [[
               T("rouge_5_a", 5, "rouge"),
               T("joker_1", None, "noir", j=True),
               T("rouge_7_a", 7, "rouge")]]}
    etat = {"joueurs": [{"chevalet": chevalet}], "pioche": []}
    score, info = ia._exposition_coup_joker(etat, 0, coup)
    assert info["exclu"] is True


def test_exposition_aucun_joker_pose_renvoie_none():
    chevalet = [T("rouge_5_a", 5, "rouge"), T("rouge_6_a", 6, "rouge"),
               T("rouge_7_a", 7, "rouge")]
    coup = {"ids_tuiles": ["rouge_5_a", "rouge_6_a", "rouge_7_a"],
           "nouveau_plateau": [chevalet]}
    etat = {"joueurs": [{"chevalet": chevalet}], "pioche": []}
    score, info = ia._exposition_coup_joker(etat, 0, coup)
    assert score is None
    assert info["a_pose_un_joker"] is False


# --------------------------------------------------------------------------- #
# Stratégie bout-en-bout (``jouer_niveau_bride``) — position SANS tapis, où
# le dilemme ne porte que sur l'usage du joker (point 4 de l'issue : critère
# de départage à nombre de tuiles posées égal).
#
# Main : {rouge_12, bleu_12} (série de 12, forte en points, 36 pts avec le
# joker) et {rouge_1, rouge_3} (suite 1-J(2)-3, faible en points, 6 pts) se
# disputent le SEUL joker du chevalet — un seul des deux est donc posable,
# les deux posent 3 tuiles. Sans la stratégie, le solveur préfère la série
# (le plus de points, départage existant, #8bis) ; avec la stratégie,
# l'exposition de la série (deux couleurs manquantes à la valeur 12, jamais
# vues : 4 exemplaires inconnus) est supérieure à celle de la suite (une
# seule valeur manquante, rouge 2 : 2 exemplaires inconnus) — la stratégie
# préfère donc la suite.
# --------------------------------------------------------------------------- #

def _chevalet_dilemme(nb_filler=0):
    base = [T("rouge_12_a", 12, "rouge"), T("bleu_12_a", 12, "bleu"),
           T("rouge_1_a", 1, "rouge"), T("rouge_3_a", 3, "rouge"),
           T("joker_1", None, "noir", j=True)]
    couleurs = ("rouge", "bleu", "jaune", "noir")
    for i in range(nb_filler):
        base.append(T(f"{couleurs[i % 4]}_{20 + i}_f", 20 + i, couleurs[i % 4]))
    return base


def _etat(chevalet, niveau="Champion du Monde"):
    return {
        "joueurs": [
            {"nom": "Humain", "est_ia": False, "niveau": None,
             "chevalet": [], "mise_initiale_faite": True},
            {"nom": "Bot", "est_ia": True, "niveau": niveau,
             "chevalet": chevalet, "mise_initiale_faite": True},
        ],
        "plateau": [],
        "pioche": [],
        "config": {"nb_manches": 1, "valeur_joker_penalite": 30,
                  "mise_initiale_min": 30},
        "index_joueur_actuel": 1,
        "historique": [],
    }


def _bridage_placement_joker_seule():
    return niveaux.bridage_champion_personnalise(["placement_joker"])


@besoin_exact
def test_sans_la_strategie_le_solveur_prefere_la_serie_la_plus_rentable():
    """Confirme le point de départ du dilemme (le départage EXISTANT, sans
    la stratégie, choisit la série) — sinon le test suivant ne démontrerait
    rien."""
    etat = _etat(_chevalet_dilemme())
    coup = ia.jouer_niveau_expert(etat, 1)
    assert set(coup["ids_tuiles"]) == {"rouge_12_a", "bleu_12_a", "joker_1"}


@besoin_exact
def test_placement_joker_choisit_le_placement_le_moins_expose():
    niveaux.BRIDAGES["Champion du Monde"] = _bridage_placement_joker_seule()
    try:
        etat = _etat(_chevalet_dilemme())
        coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")
    finally:
        niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
            niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_1_a", "rouge_3_a", "joker_1"}
    assert coup["solveur"] == ia.SOLVEUR_PLACEMENT_JOKER
    info = coup["placement_joker_info"]
    assert info["declenchee"] is True
    assert info["choisi"] is True
    assert info["exposition_avant"] == 4
    assert info["meilleure_exposition"] == 2


@besoin_exact
def test_placement_joker_desactivee_decision_identique_a_avant():
    etat = _etat(_chevalet_dilemme())
    attendu = ia.jouer_niveau_expert(etat, 1)
    coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == set(attendu["ids_tuiles"])
    assert "placement_joker_info" not in coup


@besoin_exact
def test_expert_inchange_meme_position():
    """Expert n'a jamais accès à ``placement_joker`` (registre, #228/#232) :
    même décision avec ou sans la stratégie forcée pour Champion du Monde
    uniquement."""
    etat = _etat(_chevalet_dilemme(), niveau="Expert")
    attendu = ia.jouer_niveau_expert(etat, 1)

    niveaux.BRIDAGES["Champion du Monde"] = _bridage_placement_joker_seule()
    try:
        coup = ia.jouer_niveau_bride(etat, 1, "Expert")
    finally:
        niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
            niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == set(attendu["ids_tuiles"])
    assert "placement_joker_info" not in coup


@besoin_exact
def test_coup_sans_joker_aucun_effet():
    """Un coup qui ne pose aucun joker n'est jamais modifié (point 4 de
    l'issue : « sans effet quand le coup ne pose pas de joker »)."""
    niveaux.BRIDAGES["Champion du Monde"] = _bridage_placement_joker_seule()
    try:
        etat = _etat([T("rouge_5_a", 5, "rouge"), T("rouge_6_a", 6, "rouge"),
                     T("rouge_7_a", 7, "rouge"), T("bleu_12_a", 12, "bleu")])
        coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")
    finally:
        niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
            niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_5_a", "rouge_6_a", "rouge_7_a"}
    info = coup["placement_joker_info"]
    assert info["declenchee"] is False
    assert info["choisi"] is False


@besoin_exact
def test_coup_qui_vide_la_main_joue_tel_quel():
    niveaux.BRIDAGES["Champion du Monde"] = _bridage_placement_joker_seule()
    try:
        etat = _etat([T("rouge_5_a", 5, "rouge"),
                     T("joker_1", None, "noir", j=True),
                     T("rouge_7_a", 7, "rouge")])
        coup = ia.jouer_niveau_bride(etat, 1, "Champion du Monde")
    finally:
        niveaux.BRIDAGES["Champion du Monde"] = niveaux.bridage_champion_personnalise(
            niveaux.STRATEGIES_CHAMPION_PAR_DEFAUT)

    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_5_a", "joker_1", "rouge_7_a"}
    assert "placement_joker_info" not in coup
