"""Vérification de finition en fin de partie — étape 1 de la brique « Deux
tours » (issue #221).

Positions de test fixes (point 6 de l'issue), construites à la main, chacune
avec sa réponse attendue. Hypothèse assumée partout (voir docstring de
``moteur/verification_finition.py``) : l'adversaire ne touche pas au tapis
entre les deux tours.

**Remarque méthodologique, documentée après expérimentation (#221)** : dans
ce moteur, un coup peut librement recomposer tout le plateau en un seul tour
(seule contrainte : ne perdre aucune tuile déjà posée). Il en découle qu'un
coup A, PROUVÉ optimal (nombre de tuiles posées maximal), qui ne vide pas le
chevalet ne peut JAMAIS avoir un candidat qui permette de finir au tour
suivant (sans quoi A aurait lui-même déjà pu finir CE tour en combinant les
deux coups en un seul — vérifié par construction dans plusieurs variantes de
la position « 3 jaune coincé » pendant cette issue). Le mécanisme ne peut
donc réellement changer le coup joué que lorsque le coup marqué comme venant
du modèle exact n'a PAS été prouvé optimal (budget de temps serré) — les
positions qui testent ``appliquee_autre_coup``/une partie des cas où
``candidats[0]`` suffit utilisent donc un coup « A » fabriqué à la main
(``monkeypatch`` de ``resoudre_exact`` côté ``ia.py`` UNIQUEMENT, jamais côté
``verification_finition.py`` — la vérification elle-même reste réelle,
jamais simulée) pour représenter ce cas réel, plutôt que de prétendre que le
solveur naturel se tromperait sans raison.
"""

import time

from rummikub.moteur import ia, verification_finition as vf
from rummikub.moteur import niveaux
from rummikub.moteur.ia import (
    jouer_niveau_bride, jouer_niveau_expert, _coup_sans_rearrangement,
    _verifier_finition_fin_de_partie, SOLVEUR_EXACT, SOLVEUR_RECHERCHE,
    SOLVEUR_AVANCE,
)


def T(id_, v, c, j=False):
    return {"id": id_, "valeur": v, "couleur": c, "est_joker": j}


def _etat(plateau, chevalet, niveau="Champion du Monde"):
    return {
        "joueurs": [
            {"nom": "Humain", "est_ia": False, "niveau": None,
             "chevalet": [], "mise_initiale_faite": True},
            {"nom": "Bot", "est_ia": True, "niveau": niveau,
             "chevalet": chevalet, "mise_initiale_faite": True},
        ],
        "plateau": plateau,
        "config": {"nb_manches": 1, "valeur_joker_penalite": 30,
                   "mise_initiale_min": 30},
        "index_joueur_actuel": 1,
    }


# --------------------------------------------------------------------------- #
# 1. Hors fin de partie : chevalet plus grand que N → décision identique
# --------------------------------------------------------------------------- #

def test_hors_fin_de_partie_decision_inchangee():
    etat = _etat(
        plateau=[[T("jaune_1_a", 1, "jaune"), T("jaune_2_a", 2, "jaune"),
                 T("jaune_3_a", 3, "jaune"), T("joker_1", None, None, True)]],
        chevalet=[T("jaune_5_a", 5, "jaune"), T("rouge_7_a", 7, "rouge"),
                 T("bleu_7_a", 7, "bleu"), T("rouge_9_a", 9, "rouge"),
                 T("bleu_9_a", 9, "bleu"), T("noir_9_a", 9, "noir")],
    )
    assert len(etat["joueurs"][1]["chevalet"]) > niveaux.SEUIL_FIN_PARTIE_VERIF_FINITION
    attendu = jouer_niveau_expert(etat, 1)
    obtenu = jouer_niveau_bride(etat, 1, "Champion du Monde", rng=_Rng(0.999))
    assert obtenu["action"] == "jouer"
    assert set(obtenu["ids_tuiles"]) == set(attendu["ids_tuiles"])
    assert obtenu.get("verif_finition") == vf.NON_APPLICABLE


# --------------------------------------------------------------------------- #
# 2. Le meilleur coup vide déjà le chevalet : jamais de vérification
# --------------------------------------------------------------------------- #

def test_coup_gagnant_jamais_verifie():
    etat = _etat(
        plateau=[],
        chevalet=[T("rouge_7_a", 7, "rouge"), T("bleu_7_a", 7, "bleu"),
                 T("noir_7_a", 7, "noir")],
    )
    coup = jouer_niveau_bride(etat, 1, "Champion du Monde", rng=_Rng(0.0))
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_7_a", "bleu_7_a", "noir_7_a"}
    assert "verif_finition" not in coup


# --------------------------------------------------------------------------- #
# 3. Fin de partie, avec joker, mais aucun candidat ne permet de finir
# --------------------------------------------------------------------------- #

def _etat_sans_issue():
    return _etat(
        plateau=[[T("jaune_1_a", 1, "jaune"), T("jaune_2_a", 2, "jaune"),
                 T("jaune_3_a", 3, "jaune"), T("joker_1", None, None, True)]],
        chevalet=[T("jaune_5_a", 5, "jaune"), T("rouge_7_a", 7, "rouge"),
                 T("bleu_7_a", 7, "bleu"), T("rouge_9_a", 9, "rouge"),
                 T("bleu_9_a", 9, "bleu")],
    )


def test_aucun_candidat_naturel_ne_permet_de_finir():
    etat = _etat_sans_issue()
    assert len(etat["joueurs"][1]["chevalet"]) <= niveaux.SEUIL_FIN_PARTIE_VERIF_FINITION
    attendu = jouer_niveau_expert(etat, 1)
    assert attendu["action"] == "jouer"
    assert len(attendu["ids_tuiles"]) < len(etat["joueurs"][1]["chevalet"])

    obtenu = jouer_niveau_bride(etat, 1, "Champion du Monde", rng=_Rng(0.999))
    assert obtenu["action"] == "jouer"
    assert set(obtenu["ids_tuiles"]) == set(attendu["ids_tuiles"])
    assert obtenu.get("verif_finition") == vf.APPLIQUEE_SANS_CHANGEMENT


def test_sans_joker_decision_verifiee():
    """Cas sans joker du tout sur le plateau : la vérification s'exécute (fin
    de partie, Champion du Monde) sans jamais planter, et ne change rien
    puisqu'aucun candidat ne fait mieux que le meilleur coup du solveur."""
    etat = _etat(
        plateau=[[T("rouge_4_a", 4, "rouge"), T("rouge_5_a", 5, "rouge"),
                 T("rouge_6_a", 6, "rouge")]],
        chevalet=[T("rouge_7_a", 7, "rouge"), T("bleu_1_a", 1, "bleu"),
                 T("noir_13_a", 13, "noir")],
    )
    attendu = jouer_niveau_expert(etat, 1)
    assert attendu["action"] == "jouer"
    assert set(attendu["ids_tuiles"]) == {"rouge_7_a"}  # seule tuile jouable

    obtenu = jouer_niveau_bride(etat, 1, "Champion du Monde", rng=_Rng(0.999))
    assert set(obtenu["ids_tuiles"]) == {"rouge_7_a"}
    assert obtenu.get("verif_finition") == vf.APPLIQUEE_SANS_CHANGEMENT


# --------------------------------------------------------------------------- #
# 4/5/6. Décision de verification_finition.verifier(), avec l'oracle « peut
# finir au tour suivant » REMPLACÉ par une réponse contrôlée (monkeypatch de
# ``_peut_finir_au_tour_suivant`` SEULEMENT) — isole ici la LOGIQUE de
# décision (ordre de vérification, préférence au premier candidat à égalité,
# repli si rien ne finit) de la question, déjà couverte par de vraies
# positions ailleurs dans ce fichier (tests 1 et 3), de savoir si le solveur
# exact trouve correctement la réponse sur un plateau réel. Voir la remarque
# méthodologique en tête de fichier : avec un coup A PROUVÉ optimal, aucun
# candidat ne peut jamais finir là où A échoue (propriété de ce moteur) — ces
# trois tests contrôlent donc directement la réponse de l'oracle plutôt que
# de chercher une position où le solveur se tromperait sans raison.
# --------------------------------------------------------------------------- #

def _etat_quatre_candidats():
    return _etat(
        plateau=[],
        chevalet=[T("jaune_5_a", 5, "jaune"), T("rouge_7_a", 7, "rouge"),
                 T("bleu_7_a", 7, "bleu"), T("noir_7_a", 7, "noir")],
    )


def _oracle_fixe(reponses):
    """Fausse ``_peut_finir_au_tour_suivant`` : ``reponses`` associe un
    ensemble d'``ids_tuiles`` (frozenset) à la réponse à renvoyer pour le
    coup qui pose exactement ces tuiles."""
    def _faux(etat, idx, coup, budget_temps):
        return reponses[frozenset(coup["ids_tuiles"])]
    return _faux


def test_verifier_choisit_le_candidat_qui_permet_de_finir(monkeypatch):
    etat = _etat_quatre_candidats()
    idx = 1
    coup_a = {"action": "jouer", "ids_tuiles": ["rouge_7_a", "bleu_7_a"],
             "nouveau_plateau": [[T("rouge_7_a", 7, "rouge"),
                                  T("bleu_7_a", 7, "bleu"),
                                  T("noir_7_a", 7, "noir")]]}
    coup_b = {"action": "jouer", "ids_tuiles": ["jaune_5_a"],
             "nouveau_plateau": [[T("jaune_5_a", 5, "jaune")]]}
    monkeypatch.setattr(vf, "_peut_finir_au_tour_suivant", _oracle_fixe({
        frozenset(coup_a["ids_tuiles"]): False,
        frozenset(coup_b["ids_tuiles"]): True,
    }))
    deadline = time.monotonic() + 5.0
    coup_choisi, statut = vf.verifier(etat, idx, [coup_a, coup_b], deadline)
    assert statut == vf.APPLIQUEE_AUTRE_COUP
    assert set(coup_choisi["ids_tuiles"]) == set(coup_b["ids_tuiles"])


def test_verifier_garde_le_meilleur_coup_si_lui_seul_permet_de_finir(monkeypatch):
    etat = _etat_quatre_candidats()
    idx = 1
    coup_a = {"action": "jouer", "ids_tuiles": ["rouge_7_a", "bleu_7_a"],
             "nouveau_plateau": [[T("rouge_7_a", 7, "rouge"),
                                  T("bleu_7_a", 7, "bleu"),
                                  T("noir_7_a", 7, "noir")]]}
    coup_b = {"action": "jouer", "ids_tuiles": ["jaune_5_a"],
             "nouveau_plateau": [[T("jaune_5_a", 5, "jaune")]]}
    monkeypatch.setattr(vf, "_peut_finir_au_tour_suivant", _oracle_fixe({
        frozenset(coup_a["ids_tuiles"]): True,
        frozenset(coup_b["ids_tuiles"]): False,
    }))
    deadline = time.monotonic() + 5.0
    coup_choisi, statut = vf.verifier(etat, idx, [coup_a, coup_b], deadline)
    assert statut == vf.APPLIQUEE_SANS_CHANGEMENT
    assert set(coup_choisi["ids_tuiles"]) == set(coup_a["ids_tuiles"])


def test_verifier_egalite_prefere_le_premier_candidat(monkeypatch):
    """Si A et B permettent TOUS les deux de finir au tour suivant, A (le
    meilleur coup du solveur, toujours en premier dans la liste) est
    préféré — point 4 de l'issue."""
    etat = _etat_quatre_candidats()
    idx = 1
    coup_a = {"action": "jouer", "ids_tuiles": ["rouge_7_a", "bleu_7_a"],
             "nouveau_plateau": [[T("rouge_7_a", 7, "rouge"),
                                  T("bleu_7_a", 7, "bleu"),
                                  T("noir_7_a", 7, "noir")]]}
    coup_b = {"action": "jouer", "ids_tuiles": ["jaune_5_a"],
             "nouveau_plateau": [[T("jaune_5_a", 5, "jaune")]]}
    monkeypatch.setattr(vf, "_peut_finir_au_tour_suivant", _oracle_fixe({
        frozenset(coup_a["ids_tuiles"]): True,
        frozenset(coup_b["ids_tuiles"]): True,
    }))
    deadline = time.monotonic() + 5.0
    coup_choisi, statut = vf.verifier(etat, idx, [coup_a, coup_b], deadline)
    assert statut == vf.APPLIQUEE_SANS_CHANGEMENT
    assert set(coup_choisi["ids_tuiles"]) == set(coup_a["ids_tuiles"])


# --------------------------------------------------------------------------- #
# 7/8. Intégration complète (jouer_niveau_bride), avec le même oracle
# contrôlé, pour vérifier le CÂBLAGE de bout en bout (seuil de taille de
# main, lecture du mécanisme « exact », génération des candidats via
# ``_coup_sans_rearrangement``, pose de la clé de journal) plutôt que la
# position elle-même.
# --------------------------------------------------------------------------- #

def test_integration_appliquee_autre_coup_via_jouer_niveau_bride(monkeypatch):
    etat = _etat_sans_issue()  # exact et sans-réarrangement y diffèrent réellement
    idx = 1
    coup_sans_rearr = _coup_sans_rearrangement(etat, idx)
    assert coup_sans_rearr["action"] == "jouer"

    coup_exact = jouer_niveau_expert(etat, idx)
    assert coup_exact.get("solveur") == SOLVEUR_EXACT
    assert vf.coups_differents(coup_exact, coup_sans_rearr)

    monkeypatch.setattr(vf, "_peut_finir_au_tour_suivant", _oracle_fixe({
        frozenset(coup_exact["ids_tuiles"]): False,
        frozenset(coup_sans_rearr["ids_tuiles"]): True,
    }))

    coup = jouer_niveau_bride(etat, idx, "Champion du Monde", rng=_Rng(0.999))
    assert coup["action"] == "jouer"
    assert coup.get("verif_finition") == vf.APPLIQUEE_AUTRE_COUP
    assert set(coup["ids_tuiles"]) == set(coup_sans_rearr["ids_tuiles"])


def test_budget_deja_epuise_pendant_verification():
    etat = _etat_sans_issue()
    idx = 1
    coup = jouer_niveau_expert(etat, idx)
    assert coup.get("solveur") == SOLVEUR_EXACT
    taille_main = len(etat["joueurs"][idx]["chevalet"])
    deadline_deja_passee = time.monotonic() - 1.0
    coup_final, statut = _verifier_finition_fin_de_partie(
        etat, idx, coup, taille_main, deadline_deja_passee)
    assert statut == vf.BUDGET_EPUISE
    assert set(coup_final["ids_tuiles"]) == set(coup["ids_tuiles"])


# --------------------------------------------------------------------------- #
# 9. Repli sans highspy/numpy : même comportement qu'avant #221
# --------------------------------------------------------------------------- #

def test_repli_sans_dependances_verif_finition(monkeypatch):
    monkeypatch.setattr("rummikub.moteur.solveur_exact.DISPONIBLE", False)
    etat = _etat_sans_issue()
    coup = jouer_niveau_bride(etat, 1, "Champion du Monde", rng=_Rng(0.999))
    assert coup["action"] in ("jouer", "piocher", "passer")
    if coup["action"] == "jouer":
        assert coup.get("solveur") in (SOLVEUR_RECHERCHE, SOLVEUR_AVANCE)
        assert coup.get("verif_finition") == vf.BUDGET_EPUISE


# --------------------------------------------------------------------------- #
# 10/11. Niveaux non concernés : Avancé inchangé, interrupteur par niveau
# --------------------------------------------------------------------------- #

def test_niveau_avance_non_affecte():
    etat = _etat_sans_issue()
    attendu = jouer_niveau_expert(etat, 1)
    obtenu = jouer_niveau_bride(etat, 1, "Avancé", rng=_Rng(0.999))
    assert set(obtenu["ids_tuiles"]) == set(attendu["ids_tuiles"])
    assert "verif_finition" not in obtenu


def test_interrupteur_par_niveau(monkeypatch):
    """Couper l'interrupteur de Champion du Monde retombe exactement sur le
    comportement d'avant #221 (aucune vérification tentée)."""
    monkeypatch.setitem(
        niveaux.BRIDAGES, "Champion du Monde",
        niveaux.Bridage(perturbation_max=None, taux_oubli=0.0,
                        verif_finition=False))
    etat = _etat_sans_issue()
    attendu = jouer_niveau_expert(etat, 1)
    obtenu = jouer_niveau_bride(etat, 1, "Champion du Monde", rng=_Rng(0.999))
    assert set(obtenu["ids_tuiles"]) == set(attendu["ids_tuiles"])
    assert "verif_finition" not in obtenu


class _Rng:
    """RNG factice (voir tests/test_niveaux.py) : ``random()`` constant."""
    def __init__(self, valeur):
        self.valeur = valeur

    def random(self):
        return self.valeur
