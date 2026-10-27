"""Tests des cinq niveaux d'IA."""

import json
from pathlib import Path

import pytest

from rummikub.moteur.ia import (
    jouer_ia, jouer_niveau_avance, jouer_niveau_expert,
    jouer_niveau_facile, jouer_niveau_intermediaire, NIVEAUX_IA,
    BUDGET_TEMPS_EXPERT,
)
from rummikub.moteur.partie import creer_partie, _plateau_vers_dict
from rummikub.moteur.validation import valider_plateau
from rummikub.moteur.tuiles import tuile_depuis_dict, Tuile
from rummikub.moteur.solveur import resoudre_coup, BudgetDepasse, mesurer_perturbation

_DONNEES = Path(__file__).resolve().parent / "donnees"


def _partie_2j(niveau="Débutant"):
    return creer_partie(
        [{"nom": "Humain", "est_ia": False, "niveau": None},
         {"nom": "Bot", "est_ia": True, "niveau": niveau}],
        {"nb_manches": 1, "valeur_joker_penalite": 30,
         "mise_initiale_min": 30})


def test_ia_debutant_ne_plante_pas():
    etat = _partie_2j("Débutant")
    etat["index_joueur_actuel"] = 1
    res = jouer_ia(etat, 1)
    assert res["action"] in ("jouer", "piocher", "passer")


def test_tous_niveaux_ne_plantent_pas():
    for n in NIVEAUX_IA:
        etat = _partie_2j(n)
        etat["index_joueur_actuel"] = 1
        res = jouer_ia(etat, 1)
        assert res["action"] in ("jouer", "piocher", "passer"), \
            f"Niveau {n} a retourné action invalide"


def test_debutant_action_valide():
    etat = _partie_2j("Débutant")
    etat["index_joueur_actuel"] = 1
    res = jouer_ia(etat, 1)
    assert "action" in res and "ids_tuiles" in res


def test_expert_action_valide():
    etat = _partie_2j("Expert")
    etat["index_joueur_actuel"] = 1
    res = jouer_ia(etat, 1)
    assert res["action"] in ("jouer", "piocher", "passer")


def test_ia_jouer_coup_valide():
    """Si l'IA choisit 'jouer', le plateau proposé doit être valide."""
    for n in NIVEAUX_IA:
        etat = _partie_2j(n)
        etat["index_joueur_actuel"] = 1
        etat["joueurs"][1]["mise_initiale_faite"] = True
        res = jouer_ia(etat, 1)
        if res["action"] == "jouer" and res["nouveau_plateau"]:
            plateau = [[tuile_depuis_dict(d) for d in c]
                       for c in res["nouveau_plateau"]]
            r = valider_plateau(plateau)
            assert r["valide"], f"Niveau {n} : plateau IA invalide"


def _etat_avec_joker_recuperable(niveau):
    """Plateau : suite rouge 4-5-(joker=6).

    Chevalet du bot : un rouge 6 (pour reprendre le joker), un noir 9 et un
    bleu 9 (ne forment un groupe complet qu'avec le joker libéré), et un
    rouge 7 qui permettrait l'extension la plus simple sans toucher au
    joker — c'est ce dernier coup, moins intéressant, que jouent Facile et
    Intermédiaire.
    """
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "rouge_4_a", "valeur": 4, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_5_a", "valeur": 5, "couleur": "rouge", "est_joker": False},
        {"id": "joker_1", "valeur": None, "couleur": None, "est_joker": True},
    ]]
    bot["chevalet"] = [
        {"id": "rouge_6_b", "valeur": 6, "couleur": "rouge", "est_joker": False},
        {"id": "noir_9_a", "valeur": 9, "couleur": "noir", "est_joker": False},
        {"id": "bleu_9_a", "valeur": 9, "couleur": "bleu", "est_joker": False},
        {"id": "rouge_7_a", "valeur": 7, "couleur": "rouge", "est_joker": False},
    ]
    return etat


def test_avance_prefere_recuperer_le_joker():
    """Avancé compare le coup évident à la récupération du joker et choisit
    la seconde, nettement meilleure ici (4 tuiles posées contre 1)."""
    etat = _etat_avec_joker_recuperable("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {
        "rouge_6_b", "noir_9_a", "bleu_9_a", "rouge_7_a"}
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]


def test_expert_prefere_recuperer_le_joker():
    etat = _etat_avec_joker_recuperable("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {
        "rouge_6_b", "noir_9_a", "bleu_9_a", "rouge_7_a"}


def test_facile_ne_recupere_pas_le_joker():
    """Facile/Intermédiaire restent inchangés : extension évidente (rouge 7)
    sans tenter d'échanger le joker du plateau."""
    etat = _etat_avec_joker_recuperable("Facile")
    coup = jouer_niveau_facile(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_7_a"}


def test_intermediaire_ne_recupere_pas_le_joker():
    etat = _etat_avec_joker_recuperable("Intermédiaire")
    coup = jouer_niveau_intermediaire(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_7_a"}


def _etat_avec_joker_detachable(niveau):
    """Plateau : suite rouge 3-4-(joker=5).

    Chevalet du bot : un rouge 2 (allonge l'AUTRE bout, rendant 3-4 seul
    valide une fois le joker détaché), un noir 9 et un bleu 9 (ne forment un
    groupe complet qu'avec le joker libéré), et un rouge 6 qui permet
    d'étendre la suite directement après le joker sans le détacher — Facile
    et Intermédiaire se contentent d'étendre les deux bouts (rouge 2 et
    rouge 6, 2 tuiles) sans jamais toucher au joker.
    """
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "rouge_3_a", "valeur": 3, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_4_a", "valeur": 4, "couleur": "rouge", "est_joker": False},
        {"id": "joker_1", "valeur": None, "couleur": None, "est_joker": True},
    ]]
    bot["chevalet"] = [
        {"id": "rouge_2_a", "valeur": 2, "couleur": "rouge", "est_joker": False},
        {"id": "noir_9_a", "valeur": 9, "couleur": "noir", "est_joker": False},
        {"id": "bleu_9_a", "valeur": 9, "couleur": "bleu", "est_joker": False},
        {"id": "rouge_6_a", "valeur": 6, "couleur": "rouge", "est_joker": False},
    ]
    return etat


def test_avance_detache_le_joker_en_bout_de_suite():
    """Avancé compare l'extension évidente au détachement du joker libéré
    par l'extension de l'autre bout, et choisit ce dernier, meilleur ici
    (3 tuiles posées contre 2)."""
    etat = _etat_avec_joker_detachable("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_2_a", "noir_9_a", "bleu_9_a"}
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]


def test_expert_detache_le_joker_en_bout_de_suite():
    etat = _etat_avec_joker_detachable("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_2_a", "noir_9_a", "bleu_9_a"}


def test_facile_ne_detache_pas_le_joker():
    """Facile/Intermédiaire restent inchangés : étendent les deux bouts de
    la suite (rouge 2 et rouge 6) sans jamais détacher le joker du plateau,
    qui reste coincé entre les tuiles réelles."""
    etat = _etat_avec_joker_detachable("Facile")
    coup = jouer_niveau_facile(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_2_a", "rouge_6_a"}


def test_intermediaire_ne_detache_pas_le_joker():
    etat = _etat_avec_joker_detachable("Intermédiaire")
    coup = jouer_niveau_intermediaire(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_2_a", "rouge_6_a"}


def _etat_avec_deux_jokers_recuperables(niveau):
    """Plateau avec DEUX jokers récupérables par échange direct, sur deux
    suites distinctes (régression #169).

    Chevalet du bot : rouge 6 et bleu 9 (une tuile de reprise par joker),
    plus noir 2/jaune 2/noir 3/jaune 3 qui, seuls, ne forment aucune
    combinaison valide (2 couleurs par valeur seulement). Sans récupérer
    ET replacer les DEUX jokers dans le même coup (noir 2 + noir 3 +
    joker + joker formant une suite 1-2-3-4 en noir), l'IA ne peut rien
    jouer du tout ici : aucune extension ni combinaison simple n'existe.
    """
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [
        [
            {"id": "rouge_4_a", "valeur": 4, "couleur": "rouge", "est_joker": False},
            {"id": "rouge_5_a", "valeur": 5, "couleur": "rouge", "est_joker": False},
            {"id": "joker_1", "valeur": None, "couleur": None, "est_joker": True},
        ],
        [
            {"id": "bleu_7_a", "valeur": 7, "couleur": "bleu", "est_joker": False},
            {"id": "bleu_8_a", "valeur": 8, "couleur": "bleu", "est_joker": False},
            {"id": "joker_2", "valeur": None, "couleur": None, "est_joker": True},
        ],
    ]
    bot["chevalet"] = [
        {"id": "rouge_6_b", "valeur": 6, "couleur": "rouge", "est_joker": False},
        {"id": "bleu_9_a", "valeur": 9, "couleur": "bleu", "est_joker": False},
        {"id": "noir_2_a", "valeur": 2, "couleur": "noir", "est_joker": False},
        {"id": "jaune_2_a", "valeur": 2, "couleur": "jaune", "est_joker": False},
        {"id": "noir_3_a", "valeur": 3, "couleur": "noir", "est_joker": False},
        {"id": "jaune_3_a", "valeur": 3, "couleur": "jaune", "est_joker": False},
    ]
    return etat


def test_avance_recupere_les_deux_jokers_a_la_fois():
    """Régression #169 : deux jokers récupérables par échange direct sur
    deux suites distinctes doivent être récupérés dans le MÊME coup, et
    pas seulement l'un des deux (seule façon de jouer ici)."""
    etat = _etat_avec_deux_jokers_recuperables("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] == "jouer"
    assert {"rouge_6_b", "bleu_9_a"} <= set(coup["ids_tuiles"])
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]
    combo_rouge = next(c for c in plateau
                       if any(t.id == "rouge_6_b" for t in c))
    combo_bleu = next(c for c in plateau
                      if any(t.id == "bleu_9_a" for t in c))
    assert not any(t.est_joker for t in combo_rouge)
    assert not any(t.est_joker for t in combo_bleu)


def test_expert_recupere_les_deux_jokers_a_la_fois():
    etat = _etat_avec_deux_jokers_recuperables("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert {"rouge_6_b", "bleu_9_a"} <= set(coup["ids_tuiles"])


def _etat_avec_reduction_groupe4(niveau):
    """Reprend l'exemple de l'issue #180 : un groupe de trois 11 (bleu,
    jaune, noir) plus le 11 rouge de la main devient un groupe de quatre ;
    le 11 noir libéré correspond exactement au joker d'une suite noire
    10-joker-12-13 présente ailleurs sur le plateau.

    Chevalet du bot : 11 rouge (complète le groupe à 4 et libère le 11
    noir), 1 et 2 noirs (pour rejouer le joker libéré dans une nouvelle
    suite 1-2-3(joker) noire) — sans cette combinaison, l'IA ne peut rien
    jouer d'autre ici.
    """
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [
        [
            {"id": "bleu_11_a", "valeur": 11, "couleur": "bleu", "est_joker": False},
            {"id": "jaune_11_a", "valeur": 11, "couleur": "jaune", "est_joker": False},
            {"id": "noir_11_a", "valeur": 11, "couleur": "noir", "est_joker": False},
        ],
        [
            {"id": "noir_10_a", "valeur": 10, "couleur": "noir", "est_joker": False},
            {"id": "joker_1", "valeur": None, "couleur": None, "est_joker": True},
            {"id": "noir_12_a", "valeur": 12, "couleur": "noir", "est_joker": False},
            {"id": "noir_13_a", "valeur": 13, "couleur": "noir", "est_joker": False},
        ],
    ]
    bot["chevalet"] = [
        {"id": "rouge_11_a", "valeur": 11, "couleur": "rouge", "est_joker": False},
        {"id": "noir_1_a", "valeur": 1, "couleur": "noir", "est_joker": False},
        {"id": "noir_2_a", "valeur": 2, "couleur": "noir", "est_joker": False},
    ]
    return etat


def test_avance_libere_une_tuile_de_groupe4_pour_echanger_un_joker():
    """Issue #180 : Avancé complète le groupe à 4 (11 rouge), libère le 11
    noir, l'échange contre le joker noir, et rejoue ce dernier dans une
    nouvelle suite 1-2-3(joker) noire — seule façon de poser les 3 tuiles
    de la main ici."""
    etat = _etat_avec_reduction_groupe4("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_11_a", "noir_1_a", "noir_2_a"}
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]
    combo_groupe = next(c for c in plateau
                        if any(t.id == "rouge_11_a" for t in c))
    assert len(combo_groupe) == 3
    assert not any(t.id == "noir_11_a" for t in combo_groupe)
    assert not any(t.est_joker for c in plateau for t in c
                   if any(tt.id == "noir_10_a" for tt in c))


def test_expert_libere_une_tuile_de_groupe4_pour_echanger_un_joker():
    etat = _etat_avec_reduction_groupe4("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_11_a", "noir_1_a", "noir_2_a"}


def test_facile_ne_libere_pas_de_tuile_de_groupe4():
    """Facile/Intermédiaire restent inchangés : complète le groupe à 4 avec
    le 11 rouge sans jamais tenter d'échanger un joker ailleurs."""
    etat = _etat_avec_reduction_groupe4("Facile")
    coup = jouer_niveau_facile(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_11_a"}


def _etat_avec_tuile_interieure_liberable(niveau):
    """Issue #181 : suite rouge 1-2-3-4-5-6-7 ; le chevalet du bot a un 4
    bleu et un 4 jaune. Retirer le 4 rouge (position intérieure) laisse
    deux suites valides (1-2-3 et 5-6-7) et libère une tuile qui forme avec
    la main le groupe de 4 (rouge/bleu/jaune)."""
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "rouge_1_a", "valeur": 1, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_2_a", "valeur": 2, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_3_a", "valeur": 3, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_4_a", "valeur": 4, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_5_a", "valeur": 5, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_6_a", "valeur": 6, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_7_a", "valeur": 7, "couleur": "rouge", "est_joker": False},
    ]]
    bot["chevalet"] = [
        {"id": "bleu_4_a", "valeur": 4, "couleur": "bleu", "est_joker": False},
        {"id": "jaune_4_a", "valeur": 4, "couleur": "jaune", "est_joker": False},
    ]
    return etat


def test_avance_scinde_une_suite_pour_liberer_une_tuile_interieure():
    """Avancé retire le 4 rouge en milieu de suite, scindant la suite en
    deux (1-2-3 et 5-6-7), pour former le groupe des 4 avec la main."""
    etat = _etat_avec_tuile_interieure_liberable("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"bleu_4_a", "jaune_4_a"}
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]
    assert len(plateau) == 3
    groupe_4 = next(c for c in plateau if any(t.id == "bleu_4_a" for t in c))
    assert {t.id for t in groupe_4} == {"rouge_4_a", "bleu_4_a", "jaune_4_a"}


def test_expert_scinde_une_suite_pour_liberer_une_tuile_interieure():
    etat = _etat_avec_tuile_interieure_liberable("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"bleu_4_a", "jaune_4_a"}


def test_facile_ne_scinde_pas_une_suite_en_son_milieu():
    """Non-régression : Facile/Intermédiaire ne savent pas scinder une
    suite en son milieu (seuls Avancé/Expert le tentent) — avec seulement
    deux tuiles de valeur 4 en main, aucun coup n'est jouable."""
    etat = _etat_avec_tuile_interieure_liberable("Facile")
    coup = jouer_niveau_facile(etat, 1)
    assert coup["action"] != "jouer"


def _etat_avec_joker_interieur_liberable(niveau):
    """Issue #181 : suite bleue 3-4-5-(joker)-7-8-9 ; le chevalet du bot a
    un 12 rouge et un 12 jaune. Retirer le joker (position intérieure)
    laisse deux suites valides (3-4-5 et 7-8-9) et libère un joker rejoué
    avec la main dans un groupe de 12 (rouge/jaune/joker)."""
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "bleu_3_a", "valeur": 3, "couleur": "bleu", "est_joker": False},
        {"id": "bleu_4_a", "valeur": 4, "couleur": "bleu", "est_joker": False},
        {"id": "bleu_5_a", "valeur": 5, "couleur": "bleu", "est_joker": False},
        {"id": "joker_1", "valeur": None, "couleur": None, "est_joker": True},
        {"id": "bleu_7_a", "valeur": 7, "couleur": "bleu", "est_joker": False},
        {"id": "bleu_8_a", "valeur": 8, "couleur": "bleu", "est_joker": False},
        {"id": "bleu_9_a", "valeur": 9, "couleur": "bleu", "est_joker": False},
    ]]
    bot["chevalet"] = [
        {"id": "rouge_12_a", "valeur": 12, "couleur": "rouge", "est_joker": False},
        {"id": "jaune_12_a", "valeur": 12, "couleur": "jaune", "est_joker": False},
    ]
    return etat


def test_avance_scinde_une_suite_pour_liberer_un_joker_interieur():
    """Avancé retire le joker en milieu de suite, scindant la suite en deux
    (3-4-5 et 7-8-9), et rejoue le joker libéré dans un nouveau groupe de 12
    avec la main — seule façon de jouer les deux tuiles de la main ici."""
    etat = _etat_avec_joker_interieur_liberable("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_12_a", "jaune_12_a"}
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]
    assert len(plateau) == 3
    groupe_12 = next(c for c in plateau
                     if any(t.id == "rouge_12_a" for t in c))
    assert any(t.est_joker for t in groupe_12)
    assert not any(t.est_joker for c in plateau for t in c
                   if not any(tt.id == "rouge_12_a" for tt in c))


def test_expert_scinde_une_suite_pour_liberer_un_joker_interieur():
    etat = _etat_avec_joker_interieur_liberable("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_12_a", "jaune_12_a"}


def test_avance_ne_scinde_pas_une_suite_trop_courte():
    """Suite rouge 3-4-5-6-7 (longueur 5) : retirer la tuile centrale (5)
    laisserait deux parties de longueur 2, invalides — trop courte pour
    être scindée en son milieu, même si la main a de quoi former un groupe
    avec la tuile centrale (5 bleu / 5 jaune). Le coup ne doit pas être
    proposé."""
    etat = _partie_2j("Avancé")
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "rouge_3_a", "valeur": 3, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_4_a", "valeur": 4, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_5_a", "valeur": 5, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_6_a", "valeur": 6, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_7_a", "valeur": 7, "couleur": "rouge", "est_joker": False},
    ]]
    bot["chevalet"] = [
        {"id": "bleu_5_a", "valeur": 5, "couleur": "bleu", "est_joker": False},
        {"id": "jaune_5_a", "valeur": 5, "couleur": "jaune", "est_joker": False},
    ]
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] != "jouer"


# --------------------------------------------------------------------------- #
# Issue #182 : non-régression de la scission en BOUT de suite (cas #134,
# jamais couvert par un test unitaire avant la généralisation #181).
# --------------------------------------------------------------------------- #

def _etat_avec_fin_de_suite_liberable(niveau):
    """Suite rouge 4-5-6-7 ; le chevalet du bot a un 7 bleu et un 7 jaune.
    Détacher le 7 rouge (dernière tuile, position en BOUT) laisse la suite
    4-5-6 valide seule, et libère une tuile qui forme avec la main le
    groupe de trois 7 (rouge/bleu/jaune)."""
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "rouge_4_a", "valeur": 4, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_5_a", "valeur": 5, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_6_a", "valeur": 6, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_7_a", "valeur": 7, "couleur": "rouge", "est_joker": False},
    ]]
    bot["chevalet"] = [
        {"id": "bleu_7_a", "valeur": 7, "couleur": "bleu", "est_joker": False},
        {"id": "jaune_7_a", "valeur": 7, "couleur": "jaune", "est_joker": False},
    ]
    return etat


def test_avance_scinde_une_suite_pour_liberer_sa_derniere_tuile():
    """Avancé détache le 7 rouge en fin de suite ; 4-5-6 reste valide et le
    groupe de trois 7 est posé."""
    etat = _etat_avec_fin_de_suite_liberable("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"bleu_7_a", "jaune_7_a"}
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]
    assert len(plateau) == 2
    suite_restante = next(c for c in plateau
                          if any(t.id == "rouge_4_a" for t in c))
    assert {t.id for t in suite_restante} == {
        "rouge_4_a", "rouge_5_a", "rouge_6_a"}
    groupe_7 = next(c for c in plateau if any(t.id == "bleu_7_a" for t in c))
    assert {t.id for t in groupe_7} == {"rouge_7_a", "bleu_7_a", "jaune_7_a"}


def test_expert_scinde_une_suite_pour_liberer_sa_derniere_tuile():
    etat = _etat_avec_fin_de_suite_liberable("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"bleu_7_a", "jaune_7_a"}


def _etat_avec_debut_de_suite_liberable(niveau):
    """Suite rouge 4-5-6-7 ; le chevalet du bot a un 4 bleu et un 4 jaune.
    Détacher le 4 rouge (première tuile, position en BOUT) laisse la suite
    5-6-7 valide seule, et libère une tuile qui forme avec la main le
    groupe de trois 4 (rouge/bleu/jaune)."""
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "rouge_4_a", "valeur": 4, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_5_a", "valeur": 5, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_6_a", "valeur": 6, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_7_a", "valeur": 7, "couleur": "rouge", "est_joker": False},
    ]]
    bot["chevalet"] = [
        {"id": "bleu_4_a", "valeur": 4, "couleur": "bleu", "est_joker": False},
        {"id": "jaune_4_a", "valeur": 4, "couleur": "jaune", "est_joker": False},
    ]
    return etat


def test_avance_scinde_une_suite_pour_liberer_sa_premiere_tuile():
    """Avancé détache le 4 rouge en début de suite ; 5-6-7 reste valide et
    le groupe de trois 4 est posé."""
    etat = _etat_avec_debut_de_suite_liberable("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"bleu_4_a", "jaune_4_a"}
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]
    assert len(plateau) == 2
    suite_restante = next(c for c in plateau
                          if any(t.id == "rouge_5_a" for t in c))
    assert {t.id for t in suite_restante} == {
        "rouge_5_a", "rouge_6_a", "rouge_7_a"}
    groupe_4 = next(c for c in plateau if any(t.id == "bleu_4_a" for t in c))
    assert {t.id for t in groupe_4} == {"rouge_4_a", "bleu_4_a", "jaune_4_a"}


def test_expert_scinde_une_suite_pour_liberer_sa_premiere_tuile():
    etat = _etat_avec_debut_de_suite_liberable("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"bleu_4_a", "jaune_4_a"}


def _etat_avec_suite_trop_courte_en_bout(niveau):
    """Suite rouge 5-6-7 (longueur 3, le minimum) ; le chevalet du bot a un
    7 bleu et un 7 jaune. Détacher le 7 rouge en bout laisserait 5-6 seul
    (longueur 2), invalide — trop courte pour être scindée, même en bout."""
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "rouge_5_a", "valeur": 5, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_6_a", "valeur": 6, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_7_a", "valeur": 7, "couleur": "rouge", "est_joker": False},
    ]]
    bot["chevalet"] = [
        {"id": "bleu_7_a", "valeur": 7, "couleur": "bleu", "est_joker": False},
        {"id": "jaune_7_a", "valeur": 7, "couleur": "jaune", "est_joker": False},
    ]
    return etat


def test_avance_ne_scinde_pas_une_suite_de_trois_tuiles_en_bout():
    """Non-régression : une suite au minimum légal (3 tuiles) ne peut pas
    être scindée en bout, la partie restante (2 tuiles) étant invalide."""
    etat = _etat_avec_suite_trop_courte_en_bout("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] != "jouer"


def test_expert_ne_scinde_pas_une_suite_de_trois_tuiles_en_bout():
    etat = _etat_avec_suite_trop_courte_en_bout("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] != "jouer"


def _etat_avec_joker_en_bout_de_suite(niveau):
    """Suite rouge 4-5-6-(joker=7) ; le chevalet du bot a un 7 bleu et un 7
    jaune — même valeur que celle représentée par le joker, mais pas la même
    couleur (rouge), donc pas d'échange direct possible (#169) ; et aucune
    tuile pour étendre l'autre bout, donc pas de détachement par extension
    (cf. :func:`_jokers_detachables_par_extension`). Le joker étant en bout
    de suite, par le mécanisme de scission (#134/#181) il n'est PAS
    détachable : seule une tuile réelle peut être la tuile « libre » retirée
    (cf. note CONTEXTE.md §8). Aucun coup ne doit donc être proposé ici."""
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "rouge_4_a", "valeur": 4, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_5_a", "valeur": 5, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_6_a", "valeur": 6, "couleur": "rouge", "est_joker": False},
        {"id": "joker_1", "valeur": None, "couleur": None, "est_joker": True},
    ]]
    bot["chevalet"] = [
        {"id": "bleu_7_a", "valeur": 7, "couleur": "bleu", "est_joker": False},
        {"id": "jaune_7_a", "valeur": 7, "couleur": "jaune", "est_joker": False},
    ]
    return etat


def test_avance_ne_detache_pas_un_joker_en_bout_de_suite_par_scission():
    """Non-régression : un joker en bout de suite n'est pas détaché par le
    mécanisme de scission (#134/#181), contrairement à une tuile réelle."""
    etat = _etat_avec_joker_en_bout_de_suite("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] != "jouer"


def test_expert_trouve_un_groupe_pour_le_joker_en_bout_de_suite():
    """Issue #186 : contrairement à Avancé (tactiques locales, non-régression
    ci-dessus), le solveur de réarrangement global d'Expert trouve ICI un
    coup légitimement meilleur que « ne rien jouer » : la suite rouge
    4-5-6-(joker) redevient la suite 4-5-6 (toujours valide, 3 tuiles) et le
    joker libéré forme un NOUVEAU groupe de 7 avec les deux tuiles de la
    main (bleu/jaune/joker = 7) — aucune des deux ne correspond à la
    couleur/valeur de la tactique de scission (qui ne s'applique de toute
    façon pas à un joker en bout), mais le réarrangement global n'a pas
    cette limite. Conformément à la consigne de l'issue #186 (tâche 6), ce
    test remplace l'ancien `test_expert_ne_detache_pas_un_joker_en_bout_de_
    suite_par_scission`, devenu faux pour de bonnes raisons — voir le
    rapport de clôture #186."""
    etat = _etat_avec_joker_en_bout_de_suite("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"bleu_7_a", "jaune_7_a"}
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]
    suite_restante = next(c for c in plateau
                          if any(t.id == "rouge_4_a" for t in c))
    assert {t.id for t in suite_restante} == {
        "rouge_4_a", "rouge_5_a", "rouge_6_a"}
    groupe_7 = next(c for c in plateau if any(t.id == "bleu_7_a" for t in c))
    assert any(t.est_joker for t in groupe_7)


def test_avance_ne_scinde_pas_en_bout_sans_mise_initiale_faite():
    """Non-régression : sans mise initiale faite, la scission en bout de
    suite n'est pas proposée (même configuration que la scission en fin de
    suite, mais `mise_initiale_faite` à False)."""
    etat = _etat_avec_fin_de_suite_liberable("Avancé")
    etat["joueurs"][1]["mise_initiale_faite"] = False
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] != "jouer"


def test_expert_ne_scinde_pas_en_bout_sans_mise_initiale_faite():
    etat = _etat_avec_fin_de_suite_liberable("Expert")
    etat["joueurs"][1]["mise_initiale_faite"] = False
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] != "jouer"


def _etat_avec_groupe4_joker_sans_remplacement(niveau):
    """Issue #183 : groupe plateau de trois 9 (rouge, bleu, jaune) plus un
    joker (groupe de 4 valide). Retirer le joker laisse les trois 9 seuls,
    toujours un groupe valide — sans aucune tuile de remplacement. Chevalet
    du bot : 12 rouge et 12 jaune, pour rejouer le joker libéré dans un
    nouveau groupe de 12 (rouge/jaune/joker)."""
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "rouge_9_a", "valeur": 9, "couleur": "rouge", "est_joker": False},
        {"id": "bleu_9_a", "valeur": 9, "couleur": "bleu", "est_joker": False},
        {"id": "jaune_9_a", "valeur": 9, "couleur": "jaune", "est_joker": False},
        {"id": "joker_1", "valeur": None, "couleur": None, "est_joker": True},
    ]]
    bot["chevalet"] = [
        {"id": "rouge_12_a", "valeur": 12, "couleur": "rouge", "est_joker": False},
        {"id": "jaune_12_a", "valeur": 12, "couleur": "jaune", "est_joker": False},
    ]
    return etat


def test_avance_libere_un_joker_de_groupe4_sans_remplacement():
    """Issue #183 : Avancé retire le joker du groupe de 9 (réduit à 3,
    toujours valide, aucune tuile de remplacement) et le rejoue dans un
    nouveau groupe de 12 avec la main — seule façon de jouer les deux
    tuiles de la main ici."""
    etat = _etat_avec_groupe4_joker_sans_remplacement("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_12_a", "jaune_12_a"}
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]
    groupe_9 = next(c for c in plateau if any(t.id == "rouge_9_a" for t in c))
    assert len(groupe_9) == 3
    assert not any(t.est_joker for t in groupe_9)
    groupe_12 = next(c for c in plateau
                     if any(t.id == "rouge_12_a" for t in c))
    assert any(t.est_joker for t in groupe_12)


def test_expert_libere_un_joker_de_groupe4_sans_remplacement():
    etat = _etat_avec_groupe4_joker_sans_remplacement("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_12_a", "jaune_12_a"}


def test_facile_ne_libere_pas_le_joker_de_groupe4():
    """Non-régression : Facile/Intermédiaire ne savent pas retirer un joker
    d'un groupe de 4 sans remplacement (seuls Avancé/Expert le tentent) —
    avec seulement deux tuiles de valeur 12 en main et un groupe de 4 déjà
    plein sur le plateau, aucun coup n'est jouable."""
    etat = _etat_avec_groupe4_joker_sans_remplacement("Facile")
    coup = jouer_niveau_facile(etat, 1)
    assert coup["action"] != "jouer"


def test_avance_ne_reduit_pas_un_groupe_de_3_avec_joker():
    """Un groupe de SEULEMENT 3 tuiles (2 réelles + 1 joker) ne peut pas
    perdre son joker : il ne resterait que 2 tuiles réelles, insuffisant
    pour un groupe valide. La réduction sans remplacement ne s'applique
    qu'aux groupes de 4 ; ici, le coup ne doit pas être proposé."""
    etat = _partie_2j("Avancé")
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "rouge_9_a", "valeur": 9, "couleur": "rouge", "est_joker": False},
        {"id": "bleu_9_a", "valeur": 9, "couleur": "bleu", "est_joker": False},
        {"id": "joker_1", "valeur": None, "couleur": None, "est_joker": True},
    ]]
    bot["chevalet"] = [
        {"id": "rouge_12_a", "valeur": 12, "couleur": "rouge", "est_joker": False},
        {"id": "jaune_12_a", "valeur": 12, "couleur": "jaune", "est_joker": False},
    ]
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] != "jouer"


# --------------------------------------------------------------------------- #
# Issue #186 : solveur de réarrangement global du plateau (niveau Expert).
# --------------------------------------------------------------------------- #

def _etat_demantelement_courte_suite(niveau):
    """Issue #175 : suite noire 5-(joker=6)-7 (3 tuiles, le minimum). Le
    chevalet contient bleu_5/jaune_5 et bleu_7/jaune_7 (pour recomposer
    chacune des deux tuiles réelles démantelées en un nouveau groupe) et
    bleu_9/jaune_9 (pour le joker, isolé une fois les deux tuiles réelles
    retirées de la suite, dans un troisième groupe). Aucune tactique locale
    existante (#148 à #183) ne couvre ce cas : elles ne retirent jamais
    DEUX tuiles réelles d'une même combinaison en un seul coup. Seul le
    solveur de réarrangement global (#186) le trouve."""
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "noir_5_a", "valeur": 5, "couleur": "noir", "est_joker": False},
        {"id": "joker_1", "valeur": None, "couleur": None, "est_joker": True},
        {"id": "noir_7_a", "valeur": 7, "couleur": "noir", "est_joker": False},
    ]]
    bot["chevalet"] = [
        {"id": "bleu_5_a", "valeur": 5, "couleur": "bleu", "est_joker": False},
        {"id": "jaune_5_a", "valeur": 5, "couleur": "jaune", "est_joker": False},
        {"id": "bleu_7_a", "valeur": 7, "couleur": "bleu", "est_joker": False},
        {"id": "jaune_7_a", "valeur": 7, "couleur": "jaune", "est_joker": False},
        {"id": "bleu_9_a", "valeur": 9, "couleur": "bleu", "est_joker": False},
        {"id": "jaune_9_a", "valeur": 9, "couleur": "jaune", "est_joker": False},
    ]
    return etat


def test_expert_demantele_completement_une_courte_suite_avec_joker():
    """Issue #175 : le solveur pose les 6 tuiles de la main en démantelant
    complètement la suite noire — chacune de ses deux tuiles réelles
    recomposée dans un nouveau groupe, le joker isolé et libéré dans un
    troisième groupe."""
    etat = _etat_demantelement_courte_suite("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {
        "bleu_5_a", "jaune_5_a", "bleu_7_a", "jaune_7_a", "bleu_9_a", "jaune_9_a"}
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]
    assert len(plateau) == 3
    groupe_5 = next(c for c in plateau if any(t.id == "bleu_5_a" for t in c))
    groupe_7 = next(c for c in plateau if any(t.id == "bleu_7_a" for t in c))
    groupe_9 = next(c for c in plateau if any(t.id == "bleu_9_a" for t in c))
    assert {t.id for t in groupe_5} == {"noir_5_a", "bleu_5_a", "jaune_5_a"}
    assert {t.id for t in groupe_7} == {"noir_7_a", "bleu_7_a", "jaune_7_a"}
    assert any(t.est_joker for t in groupe_9)


def test_avance_ne_demantele_pas_une_courte_suite_avec_joker():
    """Non-régression : Avancé (tactiques locales) ne trouve PAS ce coup —
    voir CONTEXTE.md §8, cas identifié mais non implémenté avant #186."""
    etat = _etat_demantelement_courte_suite("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] != "jouer"


def test_expert_ouvre_avec_une_combinaison_qui_atteint_la_mise_minimale():
    """Mise initiale pas faite (#186, tâche 2) : seule la main compte (le
    plateau n'est pas touché), le solveur doit choisir une combinaison
    atteignant au moins le minimum requis (30 points par défaut)."""
    etat = _partie_2j("Expert")
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["chevalet"] = [
        {"id": "rouge_13_a", "valeur": 13, "couleur": "rouge", "est_joker": False},
        {"id": "bleu_13_a", "valeur": 13, "couleur": "bleu", "est_joker": False},
        {"id": "jaune_13_a", "valeur": 13, "couleur": "jaune", "est_joker": False},
        {"id": "noir_1_a", "valeur": 1, "couleur": "noir", "est_joker": False},
    ]
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_13_a", "bleu_13_a", "jaune_13_a"}
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]


def test_expert_n_ouvre_pas_sous_le_minimum_de_la_mise_initiale():
    """Si aucune combinaison possible depuis la main n'atteint le minimum
    requis (ici 3 points : groupe de trois 1), Expert ne doit pas jouer."""
    etat = _partie_2j("Expert")
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["chevalet"] = [
        {"id": "rouge_1_a", "valeur": 1, "couleur": "rouge", "est_joker": False},
        {"id": "bleu_1_a", "valeur": 1, "couleur": "bleu", "est_joker": False},
        {"id": "jaune_1_a", "valeur": 1, "couleur": "jaune", "est_joker": False},
    ]
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] in ("piocher", "passer")


def test_expert_aucun_coup_possible():
    """Aucune combinaison ne peut être formée ni étendue : Expert doit se
    replier sur pioche (ou passe si la pioche est vide), jamais planter ni
    renvoyer un coup invalide."""
    etat = _partie_2j("Expert")
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "rouge_4_a", "valeur": 4, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_5_a", "valeur": 5, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_6_a", "valeur": 6, "couleur": "rouge", "est_joker": False},
    ]]
    bot["chevalet"] = [
        {"id": "bleu_1_a", "valeur": 1, "couleur": "bleu", "est_joker": False},
        {"id": "jaune_9_a", "valeur": 9, "couleur": "jaune", "est_joker": False},
        {"id": "noir_12_a", "valeur": 12, "couleur": "noir", "est_joker": False},
    ]
    assert resoudre_coup(etat, 1, budget_temps=1.0) is None
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] in ("piocher", "passer")


def test_expert_se_replie_sur_avance_si_budget_depasse():
    """Issue #186 (tâche 3/6) : avec un budget de temps nul, le solveur
    doit lever BudgetDepasse dès la recherche ; Expert se replie alors sur
    exactement le coup que jouerait Avancé, sans jamais planter."""
    etat = _etat_avec_reduction_groupe4("Expert")
    with pytest.raises(BudgetDepasse):
        resoudre_coup(etat, 1, budget_temps=0.0)

    coup_replie = jouer_niveau_expert(etat, 1, budget_temps=0.0)
    coup_avance = jouer_niveau_avance(etat, 1)
    assert coup_replie["action"] == coup_avance["action"] == "jouer"
    assert set(coup_replie["ids_tuiles"]) == set(coup_avance["ids_tuiles"])


# --------------------------------------------------------------------------- #
# Issue #187 : le solveur ne doit jamais faire disparaître une combinaison
# déjà posée (par un autre joueur) tant que la mise initiale n'est pas
# faite — avant ce correctif, le plateau était simplement ignoré, y compris
# dans le résultat renvoyé.
# --------------------------------------------------------------------------- #

def _etat_plateau_non_vide_sans_mise_initiale(niveau):
    """Reproduit le scénario constaté en jeu (#187) : un groupe de 12 déjà
    posé par un autre joueur (joker_1 + rouge_12_a + noir_12_a), et le bot
    courant qui n'a pas encore fait sa mise initiale mais peut l'ouvrir
    avec une suite en main."""
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = False
    etat["plateau"] = [[
        {"id": "joker_1", "valeur": None, "couleur": None, "est_joker": True},
        {"id": "rouge_12_a", "valeur": 12, "couleur": "rouge", "est_joker": False},
        {"id": "noir_12_a", "valeur": 12, "couleur": "noir", "est_joker": False},
    ]]
    bot["chevalet"] = [
        {"id": "bleu_11_a", "valeur": 11, "couleur": "bleu", "est_joker": False},
        {"id": "bleu_12_a", "valeur": 12, "couleur": "bleu", "est_joker": False},
        {"id": "bleu_13_a", "valeur": 13, "couleur": "bleu", "est_joker": False},
    ]
    return etat


def test_expert_conserve_le_plateau_quand_la_mise_initiale_n_est_pas_faite():
    """Avec un plateau non vide (posé par un autre joueur) et la mise
    initiale pas encore faite, le solveur ne doit jamais faire disparaître
    la combinaison déjà posée, même s'il ne peut légalement pas la
    toucher (règle du jeu : interdiction de retoucher le plateau avant sa
    propre mise initiale) — et le nombre total de tuiles doit être
    conservé (plateau + main restante == plateau + main de départ)."""
    etat = _etat_plateau_non_vide_sans_mise_initiale("Expert")
    bot = etat["joueurs"][1]
    ids_avant = ({tt["id"] for combo in etat["plateau"] for tt in combo}
                | {tt["id"] for tt in bot["chevalet"]})

    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"

    nouveau_plateau = [[tuile_depuis_dict(d) for d in c]
                       for c in coup["nouveau_plateau"]]
    assert valider_plateau(nouveau_plateau)["valide"]

    combos_ids = [{tt.id for tt in combo} for combo in nouveau_plateau]
    assert {"joker_1", "rouge_12_a", "noir_12_a"} in combos_ids, \
        "la combinaison déjà posée a disparu du plateau (#187)"

    ids_apres = ({tt.id for combo in nouveau_plateau for tt in combo}
                | ({tt["id"] for tt in bot["chevalet"]}
                   - set(coup["ids_tuiles"])))
    assert ids_apres == ids_avant, "des tuiles ont disparu (ou sont apparues)"

    # Le coup doit aussi passer le garde-fou central de jouer_tour (#187).
    from rummikub.moteur.partie import jouer_tour
    res = jouer_tour(etat, coup["ids_tuiles"], coup["nouveau_plateau"])
    assert res["ok"], res.get("erreur")


def test_expert_conserve_plusieurs_combinaisons_du_plateau_sans_mise_initiale():
    """Comme ci-dessus, mais avec PLUSIEURS combinaisons déjà présentes sur
    le plateau : aucune ne doit disparaître ni être altérée."""
    etat = _partie_2j("Expert")
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = False
    combo1 = [
        {"id": "joker_1", "valeur": None, "couleur": None, "est_joker": True},
        {"id": "rouge_12_a", "valeur": 12, "couleur": "rouge", "est_joker": False},
        {"id": "noir_12_a", "valeur": 12, "couleur": "noir", "est_joker": False},
    ]
    combo2 = [
        {"id": "jaune_1_a", "valeur": 1, "couleur": "jaune", "est_joker": False},
        {"id": "jaune_2_a", "valeur": 2, "couleur": "jaune", "est_joker": False},
        {"id": "jaune_3_a", "valeur": 3, "couleur": "jaune", "est_joker": False},
        {"id": "jaune_4_a", "valeur": 4, "couleur": "jaune", "est_joker": False},
    ]
    etat["plateau"] = [combo1, combo2]
    bot["chevalet"] = [
        {"id": "bleu_11_a", "valeur": 11, "couleur": "bleu", "est_joker": False},
        {"id": "bleu_12_a", "valeur": 12, "couleur": "bleu", "est_joker": False},
        {"id": "bleu_13_a", "valeur": 13, "couleur": "bleu", "est_joker": False},
    ]
    ids_avant = ({tt["id"] for tt in combo1} | {tt["id"] for tt in combo2}
                | {tt["id"] for tt in bot["chevalet"]})

    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"

    nouveau_plateau = [[tuile_depuis_dict(d) for d in c]
                       for c in coup["nouveau_plateau"]]
    combos_ids = [{tt.id for tt in combo} for combo in nouveau_plateau]
    assert {"joker_1", "rouge_12_a", "noir_12_a"} in combos_ids
    assert {"jaune_1_a", "jaune_2_a", "jaune_3_a", "jaune_4_a"} in combos_ids

    ids_apres = ({tt.id for combo in nouveau_plateau for tt in combo}
                | ({tt["id"] for tt in bot["chevalet"]}
                   - set(coup["ids_tuiles"])))
    assert ids_apres == ids_avant


# --------------------------------------------------------------------------- #
# Issue #190 (suite de #187) : plateau chargé (70 tuiles, 19 combinaisons)
# où le solveur ne trouvait RIEN en 1,5 s (repli total sur Avancé) alors
# qu'un coup de 3 tuiles existe — voir ``tests/donnees/cas_expert_budget_
# tour81.json`` et le rapport de clôture #190 pour l'analyse (combinatoire
# du gel des combinaisons, ordre d'exploration, backtracking).
# --------------------------------------------------------------------------- #

def _charger_cas_tour81():
    with open(_DONNEES / "cas_expert_budget_tour81.json", encoding="utf-8") as f:
        data = json.load(f)
    return data["etat"], data["idx"]


def _verifier_coup_valide_sans_perte(etat, idx, coup):
    joueur = etat["joueurs"][idx]
    ids_avant = ({tt["id"] for combo in etat.get("plateau", []) for tt in combo}
                | {tt["id"] for tt in joueur["chevalet"]})
    nouveau_plateau = [[tuile_depuis_dict(d) for d in c]
                       for c in coup["nouveau_plateau"]]
    assert valider_plateau(nouveau_plateau)["valide"]
    ids_apres = ({tt.id for combo in nouveau_plateau for tt in combo}
                | ({tt["id"] for tt in joueur["chevalet"]}
                   - set(coup["ids_tuiles"])))
    assert ids_apres == ids_avant, "des tuiles ont disparu (ou sont apparues)"


def test_solveur_plateau_charge_trouve_au_moins_trois_tuiles_avec_gros_budget():
    """Avec un budget confortable (10 s, largement au-dessus du temps
    mesuré en développement — voir rapport #190), le solveur doit retrouver
    au moins le coup de 3 tuiles identifié manuellement sur ce plateau
    (11 noir, 11 noir, 7 rouge), sans jamais perdre de tuile du plateau."""
    etat, idx = _charger_cas_tour81()
    coup = resoudre_coup(etat, idx, budget_temps=10.0)
    assert coup is not None
    assert coup["action"] == "jouer"
    assert len(coup["ids_tuiles"]) >= 3
    _verifier_coup_valide_sans_perte(etat, idx, coup)


def test_solveur_plateau_charge_trouve_un_coup_avec_budget_de_production():
    """Avec le budget de production d'Expert (voir ``BUDGET_TEMPS_EXPERT``
    dans ``moteur/ia.py``), le solveur doit désormais trouver un coup sur ce
    plateau (avant #190, il ne trouvait RIEN et Expert se repliait sur
    Avancé, qui ne pose qu'une tuile). Tolérance de temps large (×6) pour
    ne pas échouer par hasard sur une machine de CI nettement plus lente
    que celle utilisée pour mesurer la cible de production — ce n'est PAS
    un relâchement de l'objectif de vitesse, seulement une marge anti-
    flakiness sur une machine inconnue."""
    etat, idx = _charger_cas_tour81()
    budget_test = BUDGET_TEMPS_EXPERT * 6
    coup = resoudre_coup(etat, idx, budget_temps=budget_test)
    assert coup is not None, (
        f"aucun coup trouvé même avec {budget_test} s (× 6 le budget de "
        f"production de {BUDGET_TEMPS_EXPERT} s) — régression de vitesse "
        f"du solveur sur plateau chargé")
    assert coup["action"] == "jouer"
    # Objectif mesurable de #190 : retrouver au moins le coup de 3 tuiles
    # (le solveur le trouve en ~80 ms en développement, bien avant
    # l'expiration même du seul budget de production à 1.5 s — la marge
    # ×6 ci-dessus protège le TEMPS de la mesure sur une machine lente,
    # pas la qualité attendue du résultat).
    assert len(coup["ids_tuiles"]) >= 3


# --------------------------------------------------------------------------- #
# Issue #194 (suite de #190) : plateau chargé (52 tuiles) où le coup
# optimal à 3 tuiles exige d'enchaîner les reconfigurations à travers la
# quasi-totalité du plateau (tour 57 de Bruno — voir ``tests/donnees/
# cas_expert_bruno_tour57.json`` et le rapport de clôture #194 pour
# l'analyse : avant #194, le solveur ne trouvait RIEN à 1,5 s/3 s, et
# seulement 2 tuiles à 6 s ; il lui fallait 10 s pour atteindre 3 tuiles).
# --------------------------------------------------------------------------- #

def _charger_cas_bruno_tour57():
    with open(_DONNEES / "cas_expert_bruno_tour57.json", encoding="utf-8") as f:
        data = json.load(f)
    return data["etat"], data["idx"], data["attendu_min_tuiles"]


def test_solveur_cascade_joker_trouve_trois_tuiles_avec_gros_budget():
    """Avec un budget confortable (10 s), le solveur doit trouver le coup à
    3 tuiles de ce cas de référence (rouge_11_b, jaune_8_a, jaune_13_a),
    sans jamais perdre de tuile du plateau — qu'il le trouve vite (nouvelle
    stratégie, #194) ou lentement n'est pas ce que ce test vérifie (voir
    ``test_solveur_cascade_joker_trouve_un_coup_avec_budget_de_production``
    ci-dessous pour la vitesse)."""
    etat, idx, attendu = _charger_cas_bruno_tour57()
    coup = resoudre_coup(etat, idx, budget_temps=10.0)
    assert coup is not None
    assert coup["action"] == "jouer"
    assert len(coup["ids_tuiles"]) >= attendu
    _verifier_coup_valide_sans_perte(etat, idx, coup)


def test_solveur_cascade_joker_trouve_un_coup_avec_budget_de_production():
    """Avec le budget de production d'Expert, le solveur doit désormais
    trouver le coup à 3 tuiles de ce cas (avant #194 : rien à 1,5 s, 2
    tuiles seulement à 6 s). Tolérance de temps large (×6, comme pour le
    cas #190 ci-dessus) pour ne pas échouer par hasard sur une machine de
    CI nettement plus lente que celle utilisée pour mesurer la cible de
    production (le solveur trouve ce coup en ~0,15 s en développement avec
    la nouvelle stratégie, #194 — bien avant l'expiration même du seul
    budget de production à 1,5 s)."""
    etat, idx, attendu = _charger_cas_bruno_tour57()
    budget_test = BUDGET_TEMPS_EXPERT * 6
    coup = resoudre_coup(etat, idx, budget_temps=budget_test)
    assert coup is not None, (
        f"aucun coup trouvé même avec {budget_test} s (× 6 le budget de "
        f"production de {BUDGET_TEMPS_EXPERT} s) — régression de vitesse "
        f"du solveur sur ce plateau")
    assert coup["action"] == "jouer"
    assert len(coup["ids_tuiles"]) >= attendu
    _verifier_coup_valide_sans_perte(etat, idx, coup)


# --------------------------------------------------------------------------- #
# Issue #199 (suite de #194) : à nombre de tuiles posées égal, préférer le
# coup le plus simple (celui qui déplace le moins de tuiles du plateau) —
# voir ``tests/donnees/cas_expert_coup_simple_david_tour31.json`` : l'IA
# avait un unique 1 noir à poser, qu'il suffisait d'ajouter au groupe de 1
# (rouge, bleu, jaune) déjà posé pour en faire un groupe de 4 couleurs en un
# seul geste ; avant #199, le solveur pouvait renvoyer n'importe quelle
# solution posant la même tuile, y compris une qui défait et recrée
# plusieurs combinaisons (constaté en jeu : 12 étapes de pas-à-pas pour
# poser une seule tuile).
# --------------------------------------------------------------------------- #

def test_solveur_coup_simple_trouve_et_retient_le_coup_sans_perturbation():
    """Sur le cas réel de David (tour 31), le solveur doit non seulement
    trouver au moins la tuile attendue, mais la poser en touchant au plus
    une seule combinaison du plateau (idéalement le groupe de 1, étendu
    sans qu'aucune tuile ne soit déplacée) — pas en fragmentant/recréant
    plusieurs combinaisons pour le même résultat."""
    with open(_DONNEES / "cas_expert_coup_simple_david_tour31.json",
              encoding="utf-8") as f:
        data = json.load(f)
    etat, idx = data["etat"], data["idx"]
    assert data["coup_simple_existe"]

    coup = resoudre_coup(etat, idx, budget_temps=BUDGET_TEMPS_EXPERT)
    assert coup is not None
    assert coup["action"] == "jouer"
    assert len(coup["ids_tuiles"]) >= data["attendu_min_tuiles"]
    _verifier_coup_valide_sans_perte(etat, idx, coup)

    deplacees, modifiees = mesurer_perturbation(
        etat["plateau"], coup["nouveau_plateau"])
    assert modifiees <= 1, (
        f"le coup touche {modifiees} combinaison(s) du plateau alors qu'un "
        f"coup simple (étendre le groupe de 1) n'en touche qu'une")
    assert deplacees == 0, (
        f"le coup déplace {deplacees} tuile(s) du plateau alors qu'un coup "
        f"simple n'en déplace aucune (il ne fait qu'ajouter la tuile de la "
        f"main au groupe de 1)")


def test_solveur_departage_petit_plateau_fabrique_prefere_la_solution_simple():
    """Reproduction minimale du cas ci-dessus (voir le rapport de clôture
    #199 pour la démarche de réduction) : un groupe de 1 (rouge, bleu,
    jaune) et une suite jaune (2 à 4) sur le plateau ; en main, le 1 noir
    (qui complète le groupe en un seul geste, sans toucher la suite) et un
    12 jaune sans rapport (qui rend la suite jaune « flexible » pour la
    recherche, et donc une seconde solution possible : fragmenter le groupe
    pour reformer la suite en 1-4). Les deux solutions posent la même seule
    tuile (le 1 noir) ; seule la seconde déplace des tuiles du plateau —
    désactiver ``preferer_simple`` retrouve d'ailleurs cette seconde
    solution (vérifié ci-dessous), ce qui confirme que le plateau fabriqué
    crée bien une égalité réelle entre les deux, pas une coïncidence."""
    plateau = [
        [Tuile("rouge_1_a", 1, "rouge"), Tuile("bleu_1_a", 1, "bleu"),
         Tuile("jaune_1_a", 1, "jaune")],
        [Tuile("jaune_2_a", 2, "jaune"), Tuile("jaune_3_a", 3, "jaune"),
         Tuile("jaune_4_a", 4, "jaune")],
    ]
    chevalet = [Tuile("noir_1_a", 1, "noir"), Tuile("jaune_12_a", 12, "jaune")]
    etat = {
        "joueurs": [{"chevalet": [t.as_dict() for t in chevalet],
                     "mise_initiale_faite": True}],
        "plateau": _plateau_vers_dict(plateau),
        "config": {"mise_initiale_min": 30},
    }

    coup = resoudre_coup(etat, 0)
    assert coup is not None and coup["action"] == "jouer"
    assert coup["ids_tuiles"] == ["noir_1_a"]
    deplacees, modifiees = mesurer_perturbation(
        etat["plateau"], coup["nouveau_plateau"])
    assert (deplacees, modifiees) == (0, 1), (
        "le solveur n'a pas retenu la solution simple (étendre le groupe "
        f"de 1) : perturbation mesurée {(deplacees, modifiees)}")

    # Preuve que le plateau fabriqué crée une vraie égalité (et pas un cas
    # où la solution compliquée n'existe simplement pas) : désactiver le
    # critère retrouve l'ancien comportement, qui fragmente le groupe.
    coup_sans_critere = resoudre_coup(etat, 0, preferer_simple=False)
    deplacees_sc, _ = mesurer_perturbation(
        etat["plateau"], coup_sans_critere["nouveau_plateau"])
    assert deplacees_sc > 0


# --------------------------------------------------------------------------- #
# Non-régression (#199) : sur tous les cas de référence existants (dont
# ceux où le solveur n'atteint pas ``attendu_min_tuiles`` même avant #199 —
# cas « coups ratés » gardés comme matériau pour une future issue, pas
# comme objectif de ce correctif), le nouveau critère de départage ne doit
# jamais poser MOINS de tuiles que l'ancien comportement.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("nom_fichier", [
    "cas_expert_budget_tour81.json",
    "cas_expert_bruno_tour57.json",
    "cas_expert_humain_261026172338_tour66.json",
    "cas_expert_humain_261026174101_tour81.json",
    "cas_expert_humain_261026213723_tour65.json",
    "cas_expert_ia_261026172338_tour37.json",
    "cas_expert_ia_261026172338_tour59.json",
])
def test_preferer_simple_ne_pose_jamais_moins_de_tuiles_au_budget_de_production(
        nom_fichier):
    """Au budget de production (celui réellement utilisé en jeu), le
    nouveau réglage ne doit jamais trouver moins de tuiles que l'ancien
    comportement. ``cas_expert_ia_261026172338_tour61.json`` est exclu de
    cette liste et testé séparément ci-dessous, à budget plus large : ce cas
    est nativement à la limite du budget de production même AVANT #199 (le
    solveur n'y trouve souvent rien dans les 1,5s, avec ou sans le nouveau
    critère — un écart d'une fraction de seconde suffit à faire basculer le
    résultat d'un côté ou de l'autre), le comparer à budget de production
    serait un test structurellement instable, pas une mesure de régression."""

    def _nb_tuiles(preferer_simple):
        try:
            coup = resoudre_coup(etat, idx, budget_temps=BUDGET_TEMPS_EXPERT,
                                 preferer_simple=preferer_simple)
        except BudgetDepasse:
            return 0
        return len(coup["ids_tuiles"]) if coup else 0

    with open(_DONNEES / nom_fichier, encoding="utf-8") as f:
        data = json.load(f)
    etat, idx = data["etat"], data["idx"]

    assert _nb_tuiles(True) >= _nb_tuiles(False), (
        f"{nom_fichier} : preferer_simple pose moins de tuiles que l'ancien "
        f"comportement (régression)")


def test_preferer_simple_atteint_le_meme_plafond_sur_le_cas_le_plus_dur():
    """``cas_expert_ia_261026172338_tour61.json`` (cascade de jokers à
    travers tout le plateau, déjà documenté #194 comme à la limite du
    budget de production) : à budget LARGE (12s, assez pour que les deux
    réglages convergent de façon stable vers leur plafond respectif —
    contrairement au budget de production, voir le test ci-dessus), le
    nouveau critère doit atteindre le même plafond que l'ancien
    comportement, pas moins."""
    with open(_DONNEES / "cas_expert_ia_261026172338_tour61.json",
              encoding="utf-8") as f:
        data = json.load(f)
    etat, idx = data["etat"], data["idx"]

    def _nb_tuiles(preferer_simple):
        try:
            coup = resoudre_coup(etat, idx, budget_temps=12.0,
                                 preferer_simple=preferer_simple)
        except BudgetDepasse:
            return 0
        return len(coup["ids_tuiles"]) if coup else 0

    assert _nb_tuiles(True) >= _nb_tuiles(False)
