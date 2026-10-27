"""Tests de la correction #201 (suite de #193) : compter les tuiles
RÉELLEMENT posées depuis la main — à partir de la variation de la main
avant/après le coup — plutôt que depuis le champ ``nb_tuiles_posees`` du
journal, qui pour un coup HUMAIN comptait aussi les tuiles du plateau
déplacées ce tour (voir ``persistance/coups_rates.py``, section #201, et
``ui/api.py:jeu_jouer_coup``).
"""

from rummikub.persistance import coups_rates as CR


def _tuile(id_, valeur, couleur, est_joker=False):
    return {"id": id_, "valeur": valeur, "couleur": couleur, "est_joker": est_joker}


def _joueur(nom, est_ia, niveau=None):
    return {"nom": nom, "est_ia": est_ia, "niveau": niveau}


def _action(tour, auteur_index, action, nb_tuiles_posees=0,
           mains_joueurs=None, plateau=None):
    return {
        "horodatage": "2026-10-26T17:23:38",
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
# Cas réel reproduit (rapport de clôture #201) : un journal annonce
# nb_tuiles_posees=18 pour un coup humain, alors que la main ne perd que 4
# tuiles (3 noir, 3 bleu, 7 jaune, 13 jaune — les ids de l'exemple du corps
# de l'issue). L'ancien comptage (champ du journal) aurait fait croire que
# le joueur posait 18 tuiles contre 7 trouvées par le solveur (« joueur bat
# le solveur » de +11) : l'analyse corrigée doit compter 4, et voir au
# contraire une pose sous-optimale (le solveur en trouve 3 de plus).
# --------------------------------------------------------------------------- #

def _journal_posee_vs_deplacee_humain():
    noir3 = _tuile("noir_3_a", 3, "noir")
    bleu3 = _tuile("bleu_3_a", 3, "bleu")
    jaune7 = _tuile("jaune_7_a", 7, "jaune")
    jaune13 = _tuile("jaune_13_a", 13, "jaune")
    reserve = _tuile("rouge_9_a", 9, "rouge")  # reste en main après le coup.
    main_avant = [noir3, bleu3, jaune7, jaune13, reserve]
    main_apres = [reserve]
    actions = [
        _action(65, 0, "pose", nb_tuiles_posees=5,
               mains_joueurs=[{"nom": "Alain", "tuiles": main_avant},
                              {"nom": "Bot", "tuiles": []}],
               plateau=[]),
        # Champ du journal (pré-#201) GONFLÉ par les tuiles du plateau
        # déplacées ce tour : 18, alors que seules 4 tuiles sortent de la
        # main (voir ``ids_tuiles_reelles`` calculé depuis la variation de
        # la main, jamais depuis ce champ).
        _action(66, 0, "pose", nb_tuiles_posees=18,
               mains_joueurs=[{"nom": "Alain", "tuiles": main_apres},
                              {"nom": "Bot", "tuiles": []}],
               plateau=[[noir3], [bleu3], [jaune7, jaune13]]),
    ]
    return {"partie_id": "p1", "debut": "2026-10-26T17:23:38",
            "joueurs": [_joueur("Alain", False), _joueur("Bot", True, "Expert")],
            "actions": actions}


def test_nb_tuiles_jouees_compte_la_main_pas_le_champ_gonfle():
    data = _journal_posee_vs_deplacee_humain()
    decisions = CR.extraire_decisions_joueur(data, "Alain")
    assert len(decisions) == 1
    d = decisions[0]
    assert d["tour"] == 66
    # 4 tuiles réellement sorties de la main, jamais 18 (champ du journal).
    assert d["nb_tuiles_jouees"] == 4
    assert sorted(d["ids_tuiles_reelles"]) == [
        "bleu_3_a", "jaune_13_a", "jaune_7_a", "noir_3_a"]


def test_plus_de_joueur_bat_solveur_apres_correction(monkeypatch):
    """Avec le champ gonflé (18) et un solveur qui trouve 7 tuiles, l'écart
    (7 - 18 = -11) aurait classé ce coup comme « le joueur bat le solveur »
    (reproduit l'écart cité dans le corps de l'issue). Avec le nombre réel
    (4), le même solveur (7 tuiles) classe correctement ce coup comme une
    pose sous-optimale (3 tuiles manquantes), jamais un cas où le solveur
    est battu."""
    def faux_resoudre(etat, idx, budget_temps):
        return {"action": "jouer",
               "ids_tuiles": ["s1", "s2", "s3", "s4", "s5", "s6", "s7"],
               "nouveau_plateau": []}
    monkeypatch.setattr(CR, "resoudre_coup", faux_resoudre)

    data = _journal_posee_vs_deplacee_humain()
    decision = CR.extraire_decisions_joueur(data, "Alain")[0]
    r = CR.analyser_decision_complete(decision)

    assert r["nb_tuiles_reel"] == 4
    assert r["nb_tuiles_solveur"] == 7
    assert r["pose_sous_optimale"] is True
    assert r["joueur_bat_solveur"] is False
    assert r["nb_tuiles_manquantes"] == 3


# --------------------------------------------------------------------------- #
# Journal ANCIEN, écrit avant #201 : ``nb_tuiles_deplacees`` n'existe pas du
# tout (et, ici, ``nb_tuiles_posees`` non plus) — doit rester lisible, le
# comptage ne s'appuyant QUE sur la variation de la main.
# --------------------------------------------------------------------------- #

def _action_format_ancien(tour, auteur_index, action, mains_joueurs, plateau=None):
    """Action sans ``nb_tuiles_posees`` ni ``nb_tuiles_deplacees`` du tout
    (format antérieur à #185/#201)."""
    return {
        "horodatage": "2026-01-01T08:00:00",
        "action": action,
        "tour": tour,
        "joueur_actuel": None,
        "auteur_index": auteur_index,
        "termine": False,
        "gagnant_index": None,
        "mains_joueurs": mains_joueurs,
        "plateau": plateau or [],
        "pioche": [],
        "sac_restant": 0,
    }


def test_journal_ancien_sans_nb_tuiles_deplacees_reste_lisible():
    rouge4 = _tuile("rouge_4_a", 4, "rouge")
    bleu9 = _tuile("bleu_9_a", 9, "bleu")
    main_avant = [rouge4, bleu9]
    main_apres = [bleu9]
    data = {
        "partie_id": "old1", "debut": "2026-01-01T08:00:00",
        "joueurs": [_joueur("Alain", False), _joueur("Bot", True, "Expert")],
        "actions": [
            _action_format_ancien(1, 0, "pose",
                                  [{"nom": "Alain", "tuiles": main_avant},
                                   {"nom": "Bot", "tuiles": []}]),
            _action_format_ancien(2, 0, "pose",
                                  [{"nom": "Alain", "tuiles": main_apres},
                                   {"nom": "Bot", "tuiles": []}]),
        ],
    }
    decisions = CR.extraire_decisions_joueur(data, "Alain")
    assert len(decisions) == 1
    assert decisions[0]["nb_tuiles_jouees"] == 1
    assert decisions[0]["ids_tuiles_reelles"] == ["rouge_4_a"]


# --------------------------------------------------------------------------- #
# Journal d'IA cohérent : pour une IA, ``ids_tuiles`` ne contient jamais que
# des tuiles de la main (voir ``moteur/solveur.py``/``moteur/ia.py``) — le
# nombre recalculé depuis la variation de la main doit coïncider EXACTEMENT
# avec le champ ``nb_tuiles_posees`` déjà présent dans un journal d'IA
# correct.
# --------------------------------------------------------------------------- #

def test_nb_tuiles_jouees_coincide_avec_le_journal_pour_une_ia():
    jaune2 = _tuile("jaune_2_a", 2, "jaune")
    jaune3 = _tuile("jaune_3_a", 3, "jaune")
    jaune4 = _tuile("jaune_4_a", 4, "jaune")
    main_avant = [jaune2, jaune3, jaune4]
    main_apres = []
    data = {
        "partie_id": "ia1", "debut": "2026-10-26T17:23:38",
        "joueurs": [_joueur("Alain", False), _joueur("Bot", True, "Expert")],
        "actions": [
            _action(1, 1, "pose", nb_tuiles_posees=0,
                   mains_joueurs=[{"nom": "Alain", "tuiles": []},
                                  {"nom": "Bot", "tuiles": main_avant}],
                   plateau=[]),
            _action(2, 1, "pose", nb_tuiles_posees=3,
                   mains_joueurs=[{"nom": "Alain", "tuiles": []},
                                  {"nom": "Bot", "tuiles": main_apres}],
                   plateau=[[jaune2, jaune3, jaune4]]),
        ],
    }
    decisions = CR.extraire_decisions_ia_toutes(data)
    assert len(decisions) == 1
    d = decisions[0]
    # Recalculé depuis la main (ids_tuiles_reelles) : coïncide avec le champ
    # nb_tuiles_posees du journal, puisque l'IA ne journalise jamais de
    # tuile déplacée.
    assert d["nb_tuiles_jouees"] == 3
    assert data["actions"][1]["nb_tuiles_posees"] == 3
