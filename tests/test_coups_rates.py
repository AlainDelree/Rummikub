"""Tests de détection des « coups ratés » de l'IA à partir des journaux de
parties (issue #188, suite de #185) : voir
``persistance/coups_rates.py``."""

import pytest

from rummikub.persistance import coups_rates as CR


# --------------------------------------------------------------------------- #
# Fixtures : journaux fabriqués à la main.
# --------------------------------------------------------------------------- #

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


def _journal_coup_rate_apres_mise():
    """Le bot (idx 1), mise initiale déjà faite, pioche alors qu'un rouge 4
    de son chevalet prolonge la suite rouge 1-2-3 déjà posée."""
    rouge4 = _tuile("rouge_4_a", 4, "rouge")
    bleu9 = _tuile("bleu_9_a", 9, "bleu")
    jaune2 = _tuile("jaune_2_a", 2, "jaune")
    main_bot = [rouge4, bleu9, jaune2]
    actions = [
        _action(1, 0, "pose", nb_tuiles_posees=3,
               mains_joueurs=[{"nom": "Alain", "tuiles": []},
                              {"nom": "Bot", "tuiles": main_bot}],
               plateau=[]),
        _action(2, 1, "pose", nb_tuiles_posees=3,
               mains_joueurs=[{"nom": "Alain", "tuiles": []},
                              {"nom": "Bot", "tuiles": main_bot}],
               plateau=[[_tuile("rouge_1_a", 1, "rouge"),
                        _tuile("rouge_2_a", 2, "rouge"),
                        _tuile("rouge_3_a", 3, "rouge")]]),
        _action(3, 1, "pioche"),
    ]
    return {"partie_id": "t1", "debut": "2026-10-20T10:00:00",
            "joueurs": [_joueur("Alain", False), _joueur("Bot", True, "Avancé")],
            "actions": actions}


def _journal_pioche_justifiee():
    """Le bot (idx 1), mise initiale déjà faite, pioche avec un chevalet qui
    ne permet réellement aucune combinaison (plateau vide, 3 tuiles isolées
    de couleurs et valeurs toutes différentes)."""
    main_bot = [_tuile("rouge_1_a", 1, "rouge"),
               _tuile("bleu_5_a", 5, "bleu"),
               _tuile("jaune_9_a", 9, "jaune")]
    actions = [
        _action(1, 0, "pose", nb_tuiles_posees=3,
               mains_joueurs=[{"nom": "Alain", "tuiles": []},
                              {"nom": "Bot", "tuiles": main_bot}],
               plateau=[]),
        _action(2, 1, "pose", nb_tuiles_posees=3,
               mains_joueurs=[{"nom": "Alain", "tuiles": []},
                              {"nom": "Bot", "tuiles": main_bot}],
               plateau=[]),
        _action(3, 1, "pioche"),
    ]
    return {"partie_id": "t2", "debut": "2026-10-20T10:00:00",
            "joueurs": [_joueur("Alain", False), _joueur("Bot", True, "Expert")],
            "actions": actions}


def _journal_coup_rate_avant_mise():
    """Le bot (idx 1) n'a encore jamais posé (pas de mise initiale faite) et
    pioche alors que rouge 10-11-12 (33 points) ouvrirait la partie."""
    main_bot = [_tuile("rouge_10_a", 10, "rouge"),
               _tuile("rouge_11_a", 11, "rouge"),
               _tuile("rouge_12_a", 12, "rouge")]
    actions = [
        _action(1, 0, "pioche",
               mains_joueurs=[{"nom": "Alain", "tuiles": []},
                              {"nom": "Bot", "tuiles": main_bot}],
               plateau=[]),
        _action(2, 1, "pioche"),
    ]
    return {"partie_id": "t3", "debut": "2026-10-20T10:00:00",
            "joueurs": [_joueur("Alain", False), _joueur("Bot", True, "Intermédiaire")],
            "actions": actions}


def _journal_ancien_format():
    """Format d'avant #185 : joueurs = liste de noms (pas de est_ia/niveau).
    Doit être ignoré proprement (aucune décision IA identifiable)."""
    return {"partie_id": "old1", "debut": "2026-01-01T08:00:00",
            "joueurs": ["Alain", "Bot"],
            "actions": [
                {"horodatage": "2026-01-01T08:00:00", "action": "pose", "tour": 1,
                "mains_joueurs": [], "plateau": [], "pioche": [], "sac_restant": 50},
                {"horodatage": "2026-01-01T08:00:10", "action": "pioche", "tour": 2,
                "auteur_index": 1, "mains_joueurs": [], "plateau": [], "pioche": [],
                "sac_restant": 49},
            ]}


def _journal_champs_manquants():
    """Format récent (joueurs normalisés) mais action précédente sans
    ``plateau``/``mains_joueurs`` (coupure/écriture incomplète) : doit être
    ignoré proprement plutôt que de lever une exception."""
    return {"partie_id": "old2", "debut": "2026-01-01T08:00:00",
            "joueurs": [_joueur("Alain", False), _joueur("Bot", True, "Expert")],
            "actions": [
                {"horodatage": "2026-01-01T08:00:00", "action": "pose", "tour": 1,
                "auteur_index": 0},
                {"horodatage": "2026-01-01T08:00:10", "action": "pioche", "tour": 2,
                "auteur_index": 1},
            ]}


# --------------------------------------------------------------------------- #
# extraire_decisions_ia
# --------------------------------------------------------------------------- #

def test_extraire_decisions_entree_invalide():
    assert CR.extraire_decisions_ia("pas un dict") == []
    assert CR.extraire_decisions_ia({"actions": "pas une liste"}) == []
    assert CR.extraire_decisions_ia({"actions": []}) == []
    # Une seule action : pas d'état précédent, rien à reconstituer.
    assert CR.extraire_decisions_ia(
        {"joueurs": [_joueur("Bot", True, "Expert")],
         "actions": [_action(1, 0, "pioche")]}) == []


def test_extraire_decisions_ancien_format_ignore_proprement():
    assert CR.extraire_decisions_ia(_journal_ancien_format()) == []


def test_extraire_decisions_champs_manquants_ignore_proprement():
    assert CR.extraire_decisions_ia(_journal_champs_manquants()) == []


def test_extraire_decisions_premiere_action_ignoree():
    """La première action d'un journal ne peut jamais être reconstituée :
    une pioche en tour 1 ne doit jamais apparaître dans les décisions."""
    data = _journal_coup_rate_apres_mise()
    decisions = CR.extraire_decisions_ia(data)
    assert all(d["tour"] != 1 for d in decisions)


def test_extraire_decisions_moment_apres_mise():
    decisions = CR.extraire_decisions_ia(_journal_coup_rate_apres_mise())
    assert len(decisions) == 1
    d = decisions[0]
    assert d["moment"] == "apres_mise"
    assert d["niveau"] == "Avancé"
    assert d["nom"] == "Bot"
    assert d["action"] == "pioche"
    assert d["etat"]["joueurs"][1]["mise_initiale_faite"] is True


def test_extraire_decisions_moment_avant_mise():
    decisions = CR.extraire_decisions_ia(_journal_coup_rate_avant_mise())
    assert len(decisions) == 1
    d = decisions[0]
    assert d["moment"] == "avant_mise"
    assert d["etat"]["joueurs"][1]["mise_initiale_faite"] is False


# --------------------------------------------------------------------------- #
# analyser_decision / analyser_journal (intégration réelle avec le solveur).
# --------------------------------------------------------------------------- #

def test_coup_rate_detecte_apres_mise():
    resultats = CR.analyser_journal(_journal_coup_rate_apres_mise(),
                                    budget_genereux=2.0)
    assert len(resultats) == 1
    r = resultats[0]
    assert r["coup_rate"] is True
    assert r["nb_tuiles"] == 1
    assert r["moment"] == "apres_mise"
    # Pas de notion de points d'ouverture une fois la mise initiale faite.
    assert r["points_ouverture"] is None


def test_pioche_justifiee_aucun_coup_rate():
    resultats = CR.analyser_journal(_journal_pioche_justifiee(),
                                    budget_genereux=2.0)
    assert len(resultats) == 1
    r = resultats[0]
    assert r["coup_rate"] is False
    assert r["nb_tuiles"] is None


def test_coup_rate_avant_mise_rapporte_points_ouverture():
    resultats = CR.analyser_journal(_journal_coup_rate_avant_mise(),
                                    budget_genereux=2.0)
    assert len(resultats) == 1
    r = resultats[0]
    assert r["coup_rate"] is True
    assert r["nb_tuiles"] == 3
    assert r["points_ouverture"] == 33


def test_analyser_journal_appelle_le_callback_de_progression():
    appels = []
    CR.analyser_journal(_journal_coup_rate_apres_mise(), budget_genereux=2.0,
                        on_resultat=appels.append)
    assert len(appels) == 1
    assert appels[0]["coup_rate"] is True


# --------------------------------------------------------------------------- #
# Distinction budget de production / budget généreux (Expert uniquement) —
# logique testée par substitution du solveur (indépendante du chronométrage
# réel, qui ne peut pas être garanti déterministe dans un test).
# --------------------------------------------------------------------------- #

def _decision_factice(niveau="Expert", moment="apres_mise"):
    return {"tour": 10, "niveau": niveau, "nom": "Bot", "action": "pioche",
            "moment": moment, "idx": 1, "etat": {}}


def test_budget_limite_quand_seul_le_budget_genereux_trouve(monkeypatch):
    def faux_resoudre(etat, idx, budget_temps):
        if budget_temps >= 5:
            return {"action": "jouer", "ids_tuiles": ["a", "b"], "nouveau_plateau": []}
        return None
    monkeypatch.setattr(CR, "resoudre_coup", faux_resoudre)

    resultat = CR.analyser_decision(_decision_factice(), budget_genereux=10.0,
                                    budget_production=1.5)
    assert resultat["coup_rate"] is True
    assert resultat["nb_tuiles"] == 2
    assert resultat["budget_limite"] is True


def test_pas_de_limite_budget_quand_production_trouve_aussi(monkeypatch):
    def faux_resoudre(etat, idx, budget_temps):
        return {"action": "jouer", "ids_tuiles": ["a"], "nouveau_plateau": []}
    monkeypatch.setattr(CR, "resoudre_coup", faux_resoudre)

    resultat = CR.analyser_decision(_decision_factice(), budget_genereux=10.0,
                                    budget_production=1.5)
    assert resultat["coup_rate"] is True
    assert resultat["budget_limite"] is False


def test_budget_limite_non_calcule_hors_expert(monkeypatch):
    def faux_resoudre(etat, idx, budget_temps):
        return {"action": "jouer", "ids_tuiles": ["a"], "nouveau_plateau": []}
    monkeypatch.setattr(CR, "resoudre_coup", faux_resoudre)

    resultat = CR.analyser_decision(_decision_factice(niveau="Avancé"),
                                    budget_genereux=10.0)
    assert resultat["budget_limite"] is None


def test_decision_inconclusive_si_budget_depasse_sans_rien_trouver(monkeypatch):
    def faux_resoudre(etat, idx, budget_temps):
        raise CR.BudgetDepasse()
    monkeypatch.setattr(CR, "resoudre_coup", faux_resoudre)

    resultat = CR.analyser_decision(_decision_factice(niveau="Débutant"),
                                    budget_genereux=1.0)
    assert resultat["inconclusif"] is True
    assert resultat["coup_rate"] is False


# --------------------------------------------------------------------------- #
# calculer_resume / top_coups_rates.
# --------------------------------------------------------------------------- #

def _resultats_synthetiques():
    return [
        {"tour": 1, "niveau": "Expert", "nom": "Bot", "action": "pioche",
        "moment": "avant_mise", "coup_rate": True, "nb_tuiles": 3,
        "points_ouverture": 33, "budget_limite": False, "inconclusif": False},
        {"tour": 5, "niveau": "Expert", "nom": "Bot", "action": "pioche",
        "moment": "apres_mise", "coup_rate": False, "nb_tuiles": None,
        "points_ouverture": None, "budget_limite": None, "inconclusif": False},
        {"tour": 2, "niveau": "Avancé", "nom": "Bot2", "action": "passe",
        "moment": "apres_mise", "coup_rate": True, "nb_tuiles": 1,
        "points_ouverture": None, "budget_limite": None, "inconclusif": False},
    ]


def test_calculer_resume_par_niveau_et_moment():
    resume = CR.calculer_resume(_resultats_synthetiques())

    assert resume["Expert"]["avant_mise"]["decisions"] == 1
    assert resume["Expert"]["avant_mise"]["coups_rates"] == 1
    assert resume["Expert"]["avant_mise"]["pct_rates"] == pytest.approx(1.0)

    assert resume["Expert"]["apres_mise"]["decisions"] == 1
    assert resume["Expert"]["apres_mise"]["coups_rates"] == 0
    assert resume["Expert"]["apres_mise"]["pct_rates"] == pytest.approx(0.0)

    assert resume["Avancé"]["apres_mise"]["coups_rates"] == 1


def test_top_coups_rates_tri_decroissant_exclut_non_rates():
    top = CR.top_coups_rates(_resultats_synthetiques(), n=5)
    assert [r["tour"] for r in top] == [1, 2]


# --------------------------------------------------------------------------- #
# Manches multiples : ne jamais confondre deux manches d'un même match
# (issue #203).
# --------------------------------------------------------------------------- #

def _action_m(manche, tour, auteur_index, action, nb_tuiles_posees=0,
              mains_joueurs=None, plateau=None):
    a = _action(tour, auteur_index, action, nb_tuiles_posees=nb_tuiles_posees,
                mains_joueurs=mains_joueurs, plateau=plateau)
    a["manche"] = manche
    return a


def _journal_deux_manches():
    """Match de 2 manches. Le bot (idx 1) pioche au tour 3 de CHAQUE manche
    (mêmes numéros de tour, les manches repartent de 1). Chaque pioche est
    précédée, DANS SA manche, d'une action qui enregistre l'état à
    reconstituer. La première action de la manche 2 a pour état précédent une
    action de la manche 1 : elle ne doit jamais être reconstituée."""
    main_bot = [_tuile("rouge_1_a", 1, "rouge"),
                _tuile("bleu_5_a", 5, "bleu"),
                _tuile("jaune_9_a", 9, "jaune")]
    mains = [{"nom": "Alain", "tuiles": []}, {"nom": "Bot", "tuiles": main_bot}]
    actions = [
        _action_m(1, 1, 0, "pose", nb_tuiles_posees=3, mains_joueurs=mains),
        _action_m(1, 2, 1, "pose", nb_tuiles_posees=0, mains_joueurs=mains),
        _action_m(1, 3, 1, "pioche", mains_joueurs=mains),
        # Frontière : première action de la manche 2 (état précédent = manche 1).
        _action_m(2, 1, 1, "pioche", mains_joueurs=mains),
        _action_m(2, 2, 0, "pose", nb_tuiles_posees=3, mains_joueurs=mains),
        _action_m(2, 3, 1, "pioche", mains_joueurs=mains),
    ]
    return {"partie_id": "m2", "debut": "2026-10-28T10:00:00",
            "joueurs": [_joueur("Alain", False), _joueur("Bot", True, "Avancé")],
            "actions": actions}


def test_decisions_ia_ne_melangent_pas_deux_manches():
    """`extraire_decisions_ia` saute la première décision d'une manche (son
    état précédent appartient à la manche d'avant, plateau remis à zéro) et
    conserve les décisions des tours identiques des deux manches sans les
    confondre."""
    decisions = CR.extraire_decisions_ia(_journal_deux_manches())
    # 2 pioches reconstituables (tour 3 de chaque manche) ; la pioche de
    # frontière (manche 2, tour 1) est exclue.
    manches_tours = sorted((d.get("tour"),) for d in decisions)
    assert len(decisions) == 2


def test_toutes_decisions_cle_inclut_la_manche():
    """`extraire_toutes_decisions` (via extraire_decisions_ia_toutes) garde les
    décisions de même (tour, idx) dans deux manches distinctes — la clé de
    dédoublonnage inclut la manche (sinon la manche 2 écraserait la manche 1)."""
    decisions = CR.extraire_decisions_ia_toutes(_journal_deux_manches())
    # Tour 3 pioche présent dans les DEUX manches (clé (manche, tour, idx)) ;
    # pose tour 2 manche 2 ; la pioche de frontière (m2, t1) est exclue.
    tours_pioche = [d["tour"] for d in decisions if d["action"] == "pioche"]
    assert tours_pioche.count(3) == 2
    assert all(d.get("manche") in (1, 2) for d in decisions)
