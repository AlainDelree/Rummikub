"""Tests des extensions de l'analyse des coups ratés (issue #193, suite de
#188) : poses sous-optimales, budget nécessaire, analyse d'un joueur humain,
technique de la « réserve » — voir ``persistance/coups_rates.py``.

Le fichier historique ``test_coups_rates.py`` (#188) reste inchangé : les
fonctions qu'il teste (``extraire_decisions_ia``, ``analyser_decision``,
``calculer_resume``, ``top_coups_rates``) ne changent pas de comportement.
"""

import json
from pathlib import Path

import pytest

from rummikub.persistance import coups_rates as CR

_DONNEES = Path(__file__).resolve().parent / "donnees"


def _tuile(id_, valeur, couleur, est_joker=False):
    return {"id": id_, "valeur": valeur, "couleur": couleur, "est_joker": est_joker}


def _joueur(nom, est_ia, niveau=None):
    return {"nom": nom, "est_ia": est_ia, "niveau": niveau}


def _action(tour, auteur_index, action, nb_tuiles_posees=0,
           mains_joueurs=None, plateau=None):
    return {
        "horodatage": "2026-10-20T10:00:00",
        "action": action,
        "tour": tour,
        "joueur_actuel": None,
        "auteur_index": auteur_index,
        "nb_tuiles_posees": nb_tuiles_posees,
        "termine": False,
        "gagnant_index": None,
        "mains_joueurs": mains_joueurs if mains_joueurs is not None else [],
        "plateau": plateau if plateau is not None else [],
        "pioche": [],
        "sac_restant": 0,
    }


# --------------------------------------------------------------------------- #
# extraire_toutes_decisions : poses comprises, dédoublonnage après annulation.
# --------------------------------------------------------------------------- #

def _journal_pose_sous_optimale_humain():
    """Alain (idx 0) pose UNE tuile (rouge_4) alors que rouge_4 ET rouge_5
    prolongeraient tous les deux la suite rouge 1-2-3 déjà posée (le solveur
    en trouve deux)."""
    rouge4 = _tuile("rouge_4_a", 4, "rouge")
    rouge5 = _tuile("rouge_5_a", 5, "rouge")
    bleu9 = _tuile("bleu_9_a", 9, "bleu")
    main_avant = [rouge4, rouge5, bleu9]
    main_apres = [rouge5, bleu9]
    plateau = [[_tuile("rouge_1_a", 1, "rouge"), _tuile("rouge_2_a", 2, "rouge"),
               _tuile("rouge_3_a", 3, "rouge")]]
    actions = [
        _action(1, 0, "pose", nb_tuiles_posees=3,
               mains_joueurs=[{"nom": "Alain", "tuiles": main_avant},
                              {"nom": "Bot", "tuiles": []}],
               plateau=[]),
        _action(2, 0, "pose", nb_tuiles_posees=1,
               mains_joueurs=[{"nom": "Alain", "tuiles": main_apres},
                              {"nom": "Bot", "tuiles": []}],
               plateau=plateau),
    ]
    return {"partie_id": "h1", "debut": "2026-10-20T10:00:00",
            "joueurs": [_joueur("Alain", False), _joueur("Bot", True, "Expert")],
            "actions": actions}


def test_extraire_toutes_decisions_capture_les_poses():
    data = _journal_pose_sous_optimale_humain()
    decisions = CR.extraire_decisions_joueur(data, "Alain")
    assert len(decisions) == 1
    d = decisions[0]
    assert d["action"] == "pose"
    assert d["nb_tuiles_jouees"] == 1
    assert d["ids_tuiles_reelles"] == ["rouge_4_a"]


def test_extraire_toutes_decisions_dedoublonne_apres_annulation():
    """Une pose annulée puis rejouée réutilise le même numéro de tour (voir
    bilan.py) : seule la DERNIÈRE occurrence doit être conservée, et l'état
    « avant » doit être reconstitué depuis l'action juste avant la version
    FINALE (ici l'annulation, qui restaure l'état de début de tour)."""
    main_debut_tour = [_tuile("rouge_4_a", 4, "rouge"), _tuile("bleu_9_a", 9, "bleu")]
    actions = [
        _action(1, 0, "pose", nb_tuiles_posees=1,
               mains_joueurs=[{"nom": "Alain", "tuiles": main_debut_tour},
                              {"nom": "Bot", "tuiles": []}],
               plateau=[]),
        # Tentative malheureuse (tour 2), puis annulée.
        _action(2, 0, "pose", nb_tuiles_posees=1,
               mains_joueurs=[{"nom": "Alain", "tuiles": [_tuile("bleu_9_a", 9, "bleu")]},
                              {"nom": "Bot", "tuiles": []}],
               plateau=[]),
        _action(2, 0, "annulation",
               mains_joueurs=[{"nom": "Alain", "tuiles": main_debut_tour},
                              {"nom": "Bot", "tuiles": []}],
               plateau=[]),
        # Rejoué différemment, toujours tour 2 (tour_numero restauré par
        # annuler_tour) : c'est CETTE version qui doit compter.
        _action(2, 0, "passe",
               mains_joueurs=[{"nom": "Alain", "tuiles": main_debut_tour},
                              {"nom": "Bot", "tuiles": []}],
               plateau=[]),
    ]
    data = {"partie_id": "h2", "debut": "2026-10-20T10:00:00",
            "joueurs": [_joueur("Alain", False), _joueur("Bot", True, "Expert")],
            "actions": actions}
    decisions = CR.extraire_decisions_joueur(data, "Alain")
    # Seule la décision de tour 2 doit apparaître (la pose de tour 1 n'a pas
    # d'état précédent exploitable ici, elle est de toute façon la première
    # action du journal).
    assert [d["tour"] for d in decisions] == [2]
    assert decisions[0]["action"] == "passe"


# --------------------------------------------------------------------------- #
# analyser_decision_complete : classification pose/pioche/passe.
# --------------------------------------------------------------------------- #

def _decision_pose_factice(nb_jouees=1, ids_reelles=None):
    return {"tour": 10, "niveau": "Expert", "nom": "Bot", "action": "pose",
            "nb_tuiles_jouees": nb_jouees, "ids_tuiles_reelles": ids_reelles or ["a"],
            "moment": "apres_mise", "idx": 1, "etat": {}}


def test_pose_sous_optimale_quand_le_solveur_fait_mieux(monkeypatch):
    def faux_resoudre(etat, idx, budget_temps):
        return {"action": "jouer", "ids_tuiles": ["a", "b", "c"], "nouveau_plateau": []}
    monkeypatch.setattr(CR, "resoudre_coup", faux_resoudre)

    r = CR.analyser_decision_complete(_decision_pose_factice(nb_jouees=1, ids_reelles=["a"]))
    assert r["pose_sous_optimale"] is True
    assert r["coup_rate"] is False
    assert r["joueur_bat_solveur"] is False
    assert r["nb_tuiles_manquantes"] == 2
    assert r["nb_tuiles_excedentaires"] == 0


def test_joueur_bat_solveur_quand_le_joueur_pose_plus(monkeypatch):
    def faux_resoudre(etat, idx, budget_temps):
        return {"action": "jouer", "ids_tuiles": ["a"], "nouveau_plateau": []}
    monkeypatch.setattr(CR, "resoudre_coup", faux_resoudre)

    r = CR.analyser_decision_complete(
        _decision_pose_factice(nb_jouees=3, ids_reelles=["a", "b", "c"]))
    assert r["joueur_bat_solveur"] is True
    assert r["pose_sous_optimale"] is False
    assert r["nb_tuiles_excedentaires"] == 2
    assert r["nb_tuiles_manquantes"] == 0


def test_pose_au_maximum_ne_signale_rien(monkeypatch):
    def faux_resoudre(etat, idx, budget_temps):
        return {"action": "jouer", "ids_tuiles": ["a"], "nouveau_plateau": []}
    monkeypatch.setattr(CR, "resoudre_coup", faux_resoudre)

    r = CR.analyser_decision_complete(_decision_pose_factice(nb_jouees=1, ids_reelles=["a"]))
    assert r["pose_sous_optimale"] is False
    assert r["joueur_bat_solveur"] is False


def test_pose_inconclusive_ne_classe_dans_aucune_categorie(monkeypatch):
    def faux_resoudre(etat, idx, budget_temps):
        raise CR.BudgetDepasse()
    monkeypatch.setattr(CR, "resoudre_coup", faux_resoudre)

    r = CR.analyser_decision_complete(_decision_pose_factice(nb_jouees=1))
    assert r["inconclusif"] is True
    assert r["pose_sous_optimale"] is False
    assert r["joueur_bat_solveur"] is False
    assert r["nb_tuiles_manquantes"] is None


# --------------------------------------------------------------------------- #
# calculer_resume_complet
# --------------------------------------------------------------------------- #

def test_calculer_resume_complet_distingue_poses_et_pioches():
    resultats = [
        {"niveau": "Expert", "moment": "apres_mise", "action": "pose",
        "coup_rate": False, "pose_sous_optimale": True, "joueur_bat_solveur": False,
        "nb_tuiles_manquantes": 2, "budget_limite": False, "inconclusif": False},
        {"niveau": "Expert", "moment": "apres_mise", "action": "pioche",
        "coup_rate": True, "pose_sous_optimale": False, "joueur_bat_solveur": False,
        "nb_tuiles_manquantes": 1, "budget_limite": True, "inconclusif": False},
        {"niveau": "Expert", "moment": "apres_mise", "action": "pioche",
        "coup_rate": False, "pose_sous_optimale": False, "joueur_bat_solveur": False,
        "nb_tuiles_manquantes": None, "budget_limite": None, "inconclusif": True},
    ]
    resume = CR.calculer_resume_complet(resultats)
    bucket = resume["Expert"]["apres_mise"]
    assert bucket["decisions"] == 3
    assert bucket["poses_sous_optimales"] == 1
    assert bucket["tuiles_manquantes_poses"] == 2
    assert bucket["pioche_passe_ratees"] == 1
    assert bucket["budget_limite"] == 1
    assert bucket["inconclusifs"] == 1


# --------------------------------------------------------------------------- #
# budget_necessaire / repartition_budget_necessaire
# --------------------------------------------------------------------------- #

def test_budget_necessaire_plus_petit_budget_suffisant(monkeypatch):
    appels = []
    def faux_resoudre(etat, idx, budget_temps):
        appels.append(budget_temps)
        nb = 3 if budget_temps >= 6.0 else 1
        return {"action": "jouer", "ids_tuiles": ["a", "b", "c"][:nb], "nouveau_plateau": []}
    monkeypatch.setattr(CR, "resoudre_coup", faux_resoudre)

    decision = {"etat": {}, "idx": 0}
    assert CR.budget_necessaire(decision, nb_tuiles_cible=3) == 6.0
    # N'a pas testé les budgets au-delà du premier qui suffit.
    assert appels == [1.5, 3.0, 6.0]


def test_budget_necessaire_indetermine_si_aucun_budget_ne_suffit(monkeypatch):
    def faux_resoudre(etat, idx, budget_temps):
        return {"action": "jouer", "ids_tuiles": ["a"], "nouveau_plateau": []}
    monkeypatch.setattr(CR, "resoudre_coup", faux_resoudre)

    decision = {"etat": {}, "idx": 0}
    assert CR.budget_necessaire(decision, nb_tuiles_cible=5) is None


def test_repartition_budget_necessaire():
    rep = CR.repartition_budget_necessaire([1.5, 1.5, 6.0, None, 10.0])
    assert rep[1.5] == 2
    assert rep[6.0] == 1
    assert rep[10.0] == 1
    assert rep[3.0] == 0
    assert rep["indetermine"] == 1


# --------------------------------------------------------------------------- #
# detecter_reserves_joueur / resume_joueur_humain (données synthétiques).
# --------------------------------------------------------------------------- #

def _d(tour, action, ids_main_avant, ids_reelles):
    return {"tour": tour, "nom": "Alain", "action": action,
            "ids_tuiles_reelles": ids_reelles, "idx": 0, "moment": "apres_mise",
            "etat": {"joueurs": [{"chevalet": [_tuile(i, 1, "rouge") for i in ids_main_avant]}]}}


def _r(coup_rate=False, pose_sous_optimale=False, joueur_bat_solveur=False,
       ids_tuiles_solveur=None, inconclusif=False, nb_tuiles_reel=0, nb_tuiles_solveur=0):
    return {"coup_rate": coup_rate, "pose_sous_optimale": pose_sous_optimale,
            "joueur_bat_solveur": joueur_bat_solveur,
            "ids_tuiles_solveur": ids_tuiles_solveur or [],
            "inconclusif": inconclusif, "nb_tuiles_manquantes": 0,
            "nb_tuiles_excedentaires": 0, "nb_tuiles_reel": nb_tuiles_reel,
            "nb_tuiles_solveur": nb_tuiles_solveur}


def test_detecter_reserve_reussie():
    """Tour 1 : le joueur pose 1 tuile ("a") alors que le solveur en trouve
    2 ("a", "b") — "b" reste en main. Tour 2 : "b" est posée. Réserve
    réussie, ne doit PAS apparaître comme pose sous-optimale."""
    decisions = [
        _d(1, "pose", ["a", "b"], ["a"]),
        _d(2, "pose", ["b"], ["b"]),
    ]
    resultats = [
        {**_r(pose_sous_optimale=True, ids_tuiles_solveur=["a", "b"]),
         "nb_tuiles_manquantes": 1},
        _r(nb_tuiles_reel=1, nb_tuiles_solveur=1),
    ]
    reserves = CR.detecter_reserves_joueur(decisions, resultats)
    assert len(reserves["reserves_reussies"]) == 1
    assert reserves["reserves_reussies"][0]["tuiles"] == ["b"]
    assert reserves["reserves_perdues"] == []
    assert reserves["indices_a_exclure"] == {0}

    resume = CR.resume_joueur_humain(decisions, resultats, reserves)
    assert resume["coups_peut_etre_rates"] == []
    assert len(resume["reserves_reussies"]) == 1


def test_detecter_reserve_perdue():
    """Même début, mais au tour suivant "b" n'est PAS jouée (reste en main
    ou n'est plus posable) : réserve perdue, toujours exclue des coups
    ratés."""
    decisions = [
        _d(1, "pose", ["a", "b"], ["a"]),
        _d(2, "pioche", ["b"], []),
    ]
    resultats = [
        {**_r(pose_sous_optimale=True, ids_tuiles_solveur=["a", "b"]),
         "nb_tuiles_manquantes": 1},
        _r(),
    ]
    reserves = CR.detecter_reserves_joueur(decisions, resultats)
    assert reserves["reserves_reussies"] == []
    assert len(reserves["reserves_perdues"]) == 1
    assert reserves["reserves_perdues"][0]["tuiles"] == ["b"]
    assert reserves["indices_a_exclure"] == {0}


def test_solveur_bat_jamais_confondu_avec_une_reserve():
    decisions = [_d(1, "pose", ["a", "b", "c"], ["a", "b", "c"])]
    resultats = [_r(joueur_bat_solveur=True, ids_tuiles_solveur=["a"],
                    nb_tuiles_reel=3, nb_tuiles_solveur=1)]
    reserves = CR.detecter_reserves_joueur(decisions, resultats)
    assert reserves["indices_a_exclure"] == set()
    resume = CR.resume_joueur_humain(decisions, resultats, reserves)
    assert len(resume["solveur_bat"]) == 1


# --------------------------------------------------------------------------- #
# Validation sur un cas de référence connu (point 4 de l'issue #193) —
# fabrique un journal où la décision réelle de l'IA est « pose d'UNE tuile »
# alors que le solveur, avec un budget généreux, en trouve 3 (tour 57 de
# Bruno, voir tests/donnees/cas_expert_bruno_tour57.json et l'issue #188).
# Robuste au temps de calcul de la machine (voir issue, point 4) : un
# budget TRÈS généreux (15 s, grande marge au-dessus du temps observé en
# développement) pour le cas « détecté », un budget délibérément minuscule
# pour le cas « pas détecté — correctement signalé comme inconclusif ».
# --------------------------------------------------------------------------- #

def _decision_bruno_pose_une_tuile():
    cas = json.loads((_DONNEES / "cas_expert_bruno_tour57.json").read_text(encoding="utf-8"))
    chevalet = cas["etat"]["joueurs"][cas["idx"]]["chevalet"]
    tuile_posee = chevalet[-1]["id"]  # "rouge_11_b" : fait bien partie du
    # coup optimal à 3 tuiles (rouge_11_b, jaune_8_a, jaune_13_a).
    return {
        "tour": 57, "niveau": "Expert", "nom": "Bruno", "action": "pose",
        "nb_tuiles_jouees": 1, "ids_tuiles_reelles": [tuile_posee],
        "moment": "apres_mise", "idx": cas["idx"], "etat": cas["etat"],
    }, cas["attendu_min_tuiles"]


def test_cas_reference_bruno_detecte_avec_budget_suffisant():
    decision, attendu = _decision_bruno_pose_une_tuile()
    r = CR.analyser_decision_complete(decision, budget_genereux=15.0)
    assert r["inconclusif"] is False
    assert r["pose_sous_optimale"] is True
    assert r["nb_tuiles_solveur"] == attendu
    assert r["nb_tuiles_manquantes"] == attendu - 1


def test_cas_reference_bruno_budget_trop_court_signale_inconclusif():
    """Avec un budget délibérément trop court pour ce cas (voir l'issue :
    non résolu à 1,5 s/3 s/6 s sur la machine de référence), l'outil ne doit
    JAMAIS conclure « pas de coup raté » — seulement « inconclusif », pour
    ne pas sous-compter les coups ratés à tort (point 3 de l'issue)."""
    decision, _ = _decision_bruno_pose_une_tuile()
    r = CR.analyser_decision_complete(decision, budget_genereux=0.05)
    assert r["inconclusif"] is True
    assert r["pose_sous_optimale"] is False
    assert r["coup_rate"] is False
