"""Tests de la description en français + complexité du coup proposé par le
solveur (issue #196, suite de #193) : voir ``persistance/coups_rates.py``
(``decrire_coup``, ``_complexite_coup``, ``_relabeler_tuiles_indiscernables``)
et les champs ``description_solveur``/``description_reel`` ajoutés à
``analyser_decision_complete``.

Trois scénarios de l'issue, sur de petits journaux fabriqués : un coup raté
simple, un coup (pose sous-optimale) complexe avec échange de joker, et un
cas où le joueur bat le solveur (avec comparaison des deux descriptions).
"""

from pathlib import Path

from rummikub.persistance import coups_rates as CR

_DONNEES = Path(__file__).resolve().parent / "donnees"


def _tuile(id_, valeur, couleur, est_joker=False):
    return {"id": id_, "valeur": valeur, "couleur": couleur, "est_joker": est_joker}


def _joueur(nom, est_ia, niveau=None):
    return {"nom": nom, "est_ia": est_ia, "niveau": niveau}


def _action(tour, auteur_index, action, nb_tuiles_posees=0,
           mains_joueurs=None, plateau=None):
    return {
        "horodatage": "2026-10-27T10:00:00",
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
# Scénario 1 : coup raté SIMPLE (IA, journal fabriqué + vrai solveur).
# --------------------------------------------------------------------------- #

def _journal_coup_rate_simple():
    """Bot (Expert) pioche alors qu'il pouvait compléter une suite jaune
    (6-7) avec le 8 jaune de sa main : un coup à une seule tuile, sans
    joker — simple à vue d'humain."""
    plateau = [[_tuile("jaune_6_a", 6, "jaune"), _tuile("jaune_7_a", 7, "jaune")]]
    main_bot = [_tuile("jaune_8_a", 8, "jaune"), _tuile("noir_2_a", 2, "noir")]
    actions = [
        _action(1, 1, "pose", nb_tuiles_posees=1,
               mains_joueurs=[{"nom": "Humain", "tuiles": []},
                              {"nom": "Bot", "tuiles": []}]),
        _action(2, 0, "passe",
               mains_joueurs=[{"nom": "Humain", "tuiles": []},
                              {"nom": "Bot", "tuiles": main_bot}],
               plateau=plateau),
        _action(3, 1, "pioche",
               mains_joueurs=[{"nom": "Humain", "tuiles": []},
                              {"nom": "Bot", "tuiles": main_bot}],
               plateau=plateau),
    ]
    return {"partie_id": "j1", "debut": "2026-10-27T10:00:00",
            "joueurs": [_joueur("Humain", False), _joueur("Bot", True, "Expert")],
            "actions": actions}


def test_coup_rate_simple_decrit_et_classe_simple():
    data = _journal_coup_rate_simple()
    decisions = CR.extraire_decisions_ia_toutes(data)
    assert len(decisions) == 1
    r = CR.analyser_decision_complete(decisions[0], budget_genereux=10.0)

    assert r["coup_rate"] is True
    assert r["nb_tuiles_solveur"] == 1
    desc = r["description_solveur"]
    assert desc is not None
    assert "8 jaune" in desc["texte"]
    assert desc["complexite"]["a_joker"] is False
    assert desc["complexite"]["nb_combinaisons_touchees"] <= 2
    assert desc["complexite"]["categorie"] == "simple"
    # Résumé agrégé : ce coup doit être classé simple pour Expert.
    resume = CR.calculer_resume_complet([r])
    bucket = resume["Expert"]["apres_mise"]
    assert bucket["coups_simples"] == 1
    assert bucket["coups_complexes"] == 0


# --------------------------------------------------------------------------- #
# Scénario 2 : pose sous-optimale COMPLEXE avec échange de joker (monkeypatch
# du solveur, comme ``test_coups_rates_extensions.py``, pour contrôler
# exactement le plateau proposé).
# --------------------------------------------------------------------------- #

def test_pose_sous_optimale_complexe_avec_joker(monkeypatch):
    avant = [[_tuile("rouge_5_a", 5, "rouge"), _tuile("rouge_6_a", 6, "rouge"),
             {"id": "joker_1", "valeur": None, "couleur": "rouge", "est_joker": True}]]
    apres = [
        [_tuile("rouge_5_a", 5, "rouge"), _tuile("rouge_6_a", 6, "rouge"),
         _tuile("rouge_7_a", 7, "rouge")],
        [_tuile("noir_8_a", 8, "noir"), _tuile("jaune_8_a", 8, "jaune"),
         {"id": "joker_1", "valeur": None, "couleur": "rouge", "est_joker": True}],
    ]

    def faux_resoudre(etat, idx, budget_temps):
        return {"action": "jouer",
                "ids_tuiles": ["rouge_7_a", "noir_8_a", "jaune_8_a"],
                "nouveau_plateau": apres}
    monkeypatch.setattr(CR, "resoudre_coup", faux_resoudre)

    decision = {"tour": 5, "niveau": "Expert", "nom": "Bot", "action": "pose",
                "nb_tuiles_jouees": 1, "ids_tuiles_reelles": ["rouge_7_a"],
                "plateau_apres_reel": None, "moment": "apres_mise", "idx": 1,
                "etat": {"joueurs": [{}, {"chevalet": [], "mise_initiale_faite": True}],
                         "plateau": avant, "config": {"mise_initiale_min": 30}}}

    r = CR.analyser_decision_complete(decision, budget_genereux=10.0, budget_production=1.5)

    assert r["pose_sous_optimale"] is True
    assert r["nb_tuiles_manquantes"] == 2
    desc = r["description_solveur"]
    assert desc is not None
    assert "joker" in desc["texte"].lower()
    assert desc["complexite"]["a_joker"] is True
    assert desc["complexite"]["categorie"] == "complexe"

    resume = CR.calculer_resume_complet([r])
    bucket = resume["Expert"]["apres_mise"]
    assert bucket["coups_complexes"] == 1
    assert bucket["coups_simples"] == 0


# --------------------------------------------------------------------------- #
# Scénario 3 : le joueur BAT le solveur — description du coup proposé ET du
# coup réellement joué, pour comparaison.
# --------------------------------------------------------------------------- #

def _journal_joueur_bat_solveur():
    main_avant = [_tuile("rouge_7_a", 7, "rouge"), _tuile("bleu_7_a", 7, "bleu"),
                  _tuile("noir_7_a", 7, "noir")]
    plateau_apres_reel = [[_tuile("rouge_7_a", 7, "rouge"), _tuile("bleu_7_a", 7, "bleu"),
                           _tuile("noir_7_a", 7, "noir")]]
    actions = [
        _action(1, 0, "pose", nb_tuiles_posees=1,
               mains_joueurs=[{"nom": "Alain", "tuiles": []},
                              {"nom": "Bot", "tuiles": []}]),
        _action(2, 0, "passe",
               mains_joueurs=[{"nom": "Alain", "tuiles": main_avant},
                              {"nom": "Bot", "tuiles": []}],
               plateau=[]),
        _action(3, 0, "pose", nb_tuiles_posees=3,
               mains_joueurs=[{"nom": "Alain", "tuiles": []},
                              {"nom": "Bot", "tuiles": []}],
               plateau=plateau_apres_reel),
    ]
    return {"partie_id": "j3", "debut": "2026-10-27T10:00:00",
            "joueurs": [_joueur("Alain", False), _joueur("Bot", True, "Expert")],
            "actions": actions}


def test_joueur_bat_solveur_decrit_propose_et_reel(monkeypatch):
    data = _journal_joueur_bat_solveur()
    decisions = CR.extraire_decisions_joueur(data, "Alain")
    # Tour 2 ("passe", chevalet encore vide à ce stade du journal fabriqué)
    # et tour 3 (la pose à analyser) : seule celle-ci nous intéresse ici.
    assert [d["tour"] for d in decisions] == [2, 3]
    decision = decisions[1]
    assert decision["plateau_apres_reel"] == [
        [_tuile("rouge_7_a", 7, "rouge"), _tuile("bleu_7_a", 7, "bleu"),
         _tuile("noir_7_a", 7, "noir")]]

    # Le solveur (même au budget généreux) ne retrouve que 2 des 3 tuiles.
    def faux_resoudre(etat, idx, budget_temps):
        return {"action": "jouer", "ids_tuiles": ["rouge_7_a", "bleu_7_a"],
                "nouveau_plateau": [[_tuile("rouge_7_a", 7, "rouge"),
                                     _tuile("bleu_7_a", 7, "bleu")]]}
    monkeypatch.setattr(CR, "resoudre_coup", faux_resoudre)

    r = CR.analyser_decision_complete(decision, budget_genereux=10.0)

    assert r["joueur_bat_solveur"] is True
    assert r["nb_tuiles_excedentaires"] == 1
    assert r["description_solveur"] is not None
    assert r["description_reel"] is not None
    assert "7 noir" in r["description_reel"]["texte"]
    assert "groupe de 7" in r["description_reel"]["texte"]

    resume = CR.resume_joueur_humain([decision], [r], {"reserves_reussies": [],
                                                        "reserves_perdues": [],
                                                        "indices_a_exclure": set()})
    assert len(resume["solveur_bat"]) == 1
    entree = resume["solveur_bat"][0]
    assert entree["description_solveur"] is not None
    assert entree["description_reel"] is not None


# --------------------------------------------------------------------------- #
# Régression : le solveur peut échanger les identifiants de deux tuiles
# physiquement indiscernables (même valeur/couleur) sans changement réel —
# moteur/description_coup.py, qui suit chaque identifiant, y lisait un cycle
# de dépendance et plantait (voir ``_relabeler_tuiles_indiscernables``).
# --------------------------------------------------------------------------- #

def test_relabeler_corrige_echange_insignifiant_entre_tuiles_jumelles():
    avant = [
        [_tuile("bleu_1_b", 1, "bleu"), _tuile("bleu_2_a", 2, "bleu"),
         _tuile("bleu_3_a", 3, "bleu")],
        [_tuile("bleu_2_b", 2, "bleu"), _tuile("jaune_2_b", 2, "jaune"),
         _tuile("noir_2_b", 2, "noir")],
    ]
    # Le solveur a reconstruit les deux mêmes combinaisons mais en échangeant
    # les deux tuiles bleu-2 indiscernables entre elles (aucun changement réel).
    apres_brut = [
        [_tuile("bleu_1_b", 1, "bleu"), _tuile("bleu_2_b", 2, "bleu"),
         _tuile("bleu_3_a", 3, "bleu")],
        [_tuile("bleu_2_a", 2, "bleu"), _tuile("jaune_2_b", 2, "jaune"),
         _tuile("noir_2_b", 2, "noir")],
    ]

    corrige = CR._relabeler_tuiles_indiscernables(avant, apres_brut)

    assert [t["id"] for t in corrige[0]] == [t["id"] for t in avant[0]]
    assert [t["id"] for t in corrige[1]] == [t["id"] for t in avant[1]]


def test_relabeler_ne_touche_jamais_une_tuile_posee_depuis_la_main():
    avant = [[_tuile("rouge_13_a", 13, "rouge"), _tuile("bleu_13_b", 13, "bleu"),
             _tuile("jaune_13_b", 13, "jaune")]]
    # jaune_13_a (posé depuis la main) remplace jaune_13_b, libéré ailleurs :
    # un changement RÉEL, même si le contenu (valeur/couleur) se ressemble.
    apres = [[_tuile("rouge_13_a", 13, "rouge"), _tuile("bleu_13_b", 13, "bleu"),
             _tuile("jaune_13_a", 13, "jaune")]]

    corrige = CR._relabeler_tuiles_indiscernables(avant, apres)

    assert corrige == apres


def test_decrire_coup_sur_cas_reference_bruno_ne_plante_pas():
    """Régression bout en bout sur un vrai coup du solveur (budget généreux,
    cas de référence #193) : avant la correction ci-dessus, la combinaison
    d'échange de deux tuiles bleu-2 indiscernables faisait planter
    ``etapes_coup_ia`` (cycle de dépendance, voir sa docstring)."""
    import json
    from rummikub.moteur.solveur import resoudre_coup

    cas = json.loads((_DONNEES / "cas_expert_bruno_tour57.json").read_text(encoding="utf-8"))
    coup = resoudre_coup(cas["etat"], cas["idx"], budget_temps=15.0)
    assert coup is not None

    description = CR.decrire_coup(cas["etat"]["plateau"], coup["nouveau_plateau"], nom="Bruno")

    assert description["texte"]
    assert description["complexite"]["nb_combinaisons_touchees"] >= 3
    assert description["complexite"]["categorie"] == "complexe"


def test_complexite_ignore_un_echange_de_tuiles_identiques():
    """Point 5 de l'issue #197 : ``decrire_coup`` réutilise tel quel
    ``moteur/description_coup.py`` corrigé, donc un échange de tuiles
    identiques (même valeur/couleur) ne compte ni comme une combinaison
    touchée, ni comme une étape du rejeu — un coup qui ne fait QUE cet
    échange, sans rien poser de plus, est classé "simple"."""
    avant = [
        [_tuile("jaune_1_a", 1, "jaune"), _tuile("jaune_2_a", 2, "jaune"),
         _tuile("jaune_3_a", 3, "jaune")],
        [_tuile("jaune_3_b", 3, "jaune"), _tuile("noir_3_a", 3, "noir"),
         _tuile("bleu_3_a", 3, "bleu")],
    ]
    apres = [
        [_tuile("jaune_1_a", 1, "jaune"), _tuile("jaune_2_a", 2, "jaune"),
         _tuile("jaune_3_b", 3, "jaune")],
        [_tuile("jaune_3_a", 3, "jaune"), _tuile("noir_3_a", 3, "noir"),
         _tuile("bleu_3_a", 3, "bleu")],
    ]

    description = CR.decrire_coup(avant, apres)

    assert description["complexite"]["nb_combinaisons_touchees"] == 0
    assert description["complexite"]["nb_etapes"] == 0
    assert description["complexite"]["categorie"] == "simple"
