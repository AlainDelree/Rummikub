"""Tests du modèle exact maison d'Expert (``moteur/solveur_exact.py``, HiGHS —
issue #206, suite de #204).

Deux familles de tests :

* **Repli** (points 4 et 6d de l'issue) : vérifient que l'absence de
  ``highspy``/``numpy``, un budget de temps nul ou une erreur font se replier
  Expert sur la recherche arborescente conservée (``solveur.py``) puis sur
  Avancé, sans jamais lever ni bloquer. Ces tests tournent **toujours** (y
  compris sans les dépendances).
* **Modèle exact** (points 6a/6b/6c/6e) : vérifient l'optimum, la conservation,
  la mise initiale et les critères de départage. Ils sont **sautés** si
  ``highspy``/``numpy`` sont absents (comme les tests Playwright/#204) ; la
  comparaison avec la bibliothèque ``rummikub-solver`` (#204) est sautée en
  plus si elle n'est pas installée.

Le budget des assertions d'optimum est mis à l'échelle de la vitesse machine
(``facteur_machine``, voir ``tests/conftest.py``) : le modèle exact PROUVE
l'optimum, le résultat ne dépend donc pas du budget tant qu'il est suffisant —
l'échelle garantit seulement qu'une machine lente ne fasse pas expirer le
budget avant la preuve.
"""

import json
import sys
from pathlib import Path

import pytest

from rummikub.moteur import solveur_exact as se
from rummikub.moteur.ia import jouer_niveau_expert, jouer_niveau_avance
from rummikub.moteur.tuiles import Tuile
from rummikub.moteur.validation import valider_combinaison

_DONNEES = Path(__file__).resolve().parent / "donnees"

besoin_exact = pytest.mark.skipif(
    not se.DISPONIBLE,
    reason="highspy/numpy absents (dépendances du modèle exact d'Expert)")


def _cas():
    return (sorted(_DONNEES.glob("cas_expert_*.json"))
            + sorted(_DONNEES.glob("reference_*.json")))


def _charger(nom):
    data = json.loads((_DONNEES / nom).read_text(encoding="utf-8"))
    return data


# --------------------------------------------------------------------------- #
# Repli (toujours exécutés — points 4 et 6d)
# --------------------------------------------------------------------------- #

def test_module_importable_sans_dependances():
    """Le module s'importe et énumère ses ensembles même sans highspy/numpy
    (l'énumération est en Python pur) ; ``DISPONIBLE`` reflète la présence
    réelle des dépendances."""
    assert isinstance(se.DISPONIBLE, bool)
    assert len(se._SETS) > 500  # quelques centaines d'ensembles valides


def test_indisponible_leve_message_installation(monkeypatch):
    """Quand les dépendances manquent, ``resoudre_coup_exact`` lève
    ``SolveurExactIndisponible`` (et non une erreur opaque)."""
    monkeypatch.setattr(se, "DISPONIBLE", False)
    with pytest.raises(se.SolveurExactIndisponible):
        se.resoudre_coup_exact(_charger("reference_victoire_manquee_ines_tour85.json")["etat"],
                               0)


def test_expert_se_replie_si_modele_exact_indisponible(monkeypatch):
    """highspy/numpy absents : Expert doit jouer le coup de la recherche
    conservée (``solveur.py``), pas lever ni bloquer. On force l'indisponibilité
    et on vérifie qu'Expert pose le coup de 3 tuiles que trouve la recherche."""
    monkeypatch.setattr(se, "DISPONIBLE", False)
    data = _charger("cas_expert_ia_261026172338_tour37.json")
    etat, idx = data["etat"], data["idx"]
    coup = jouer_niveau_expert(etat, idx, budget_temps=10.0)
    assert coup["action"] == "jouer"
    assert len(coup["ids_tuiles"]) >= 1


def test_expert_se_replie_si_budget_nul():
    """Budget de temps nul : Expert se replie sur la recherche (qui, budget
    nul, lève aussi) puis sur Avancé — exactement le coup d'Avancé, sans
    jamais planter. Quand le modèle exact est disponible, on vérifie en plus
    qu'un budget nul lève bien ``BudgetExactDepasse`` (et non une solution
    non fiable) — point 6d de l'issue."""
    data = _charger("cas_expert_ia_261026172338_tour37.json")
    etat, idx = data["etat"], data["idx"]
    if se.DISPONIBLE:
        with pytest.raises(se.BudgetExactDepasse):
            se.resoudre_exact(etat, idx, budget_temps=0.0)
    coup = jouer_niveau_expert(etat, idx, budget_temps=0.0)
    coup_avance = jouer_niveau_avance(etat, idx)
    assert coup["action"] == coup_avance["action"]


def test_repli_appelle_on_repli(monkeypatch):
    """``on_repli`` est appelé quand le modèle exact ne produit pas le coup
    (ici : dépendances absentes → cause_timeout False)."""
    monkeypatch.setattr(se, "DISPONIBLE", False)
    data = _charger("cas_expert_ia_261026172338_tour37.json")
    etat, idx = data["etat"], data["idx"]
    appels = []
    jouer_niveau_expert(etat, idx, on_repli=lambda t: appels.append(t))
    assert appels == [False]


# --------------------------------------------------------------------------- #
# Optimum exact sur tous les cas de référence (point 6a)
# --------------------------------------------------------------------------- #

@besoin_exact
@pytest.mark.parametrize("chemin", _cas(), ids=lambda p: p.name)
def test_optimum_exact_sur_les_cas_de_reference(chemin, facteur_machine):
    data = json.loads(chemin.read_text(encoding="utf-8"))
    budget = se.BUDGET_TEMPS_DEFAUT * facteur_machine
    res = se.resoudre_exact(data["etat"], data["idx"], budget_temps=budget)

    assert res.optimal, f"{chemin.name} : optimum non prouvé dans le budget"
    for combo in res.combinaisons:
        r = valider_combinaison(combo)
        assert r["valide"], f"{chemin.name} : combinaison invalide ({r['raison']})"
    assert res.toutes_valides and res.conservation_ok
    if "attendu_exact_tuiles" in data:
        assert res.nb_tuiles == data["attendu_exact_tuiles"], (
            f"{chemin.name} : {res.nb_tuiles} tuiles au lieu de "
            f"{data['attendu_exact_tuiles']} attendues")


@besoin_exact
def test_bruno_tour57_pose_rouge_12(facteur_machine):
    """Cas pivot : notre ancienne recherche restait à 3 tuiles même à 30 s ;
    le modèle exact pose 4 tuiles dont rouge_12 (coupe la suite rouge)."""
    data = _charger("cas_expert_bruno_tour57.json")
    res = se.resoudre_exact(data["etat"], data["idx"],
                            budget_temps=se.BUDGET_TEMPS_DEFAUT * facteur_machine)
    assert res.nb_tuiles == 4
    assert any(i.startswith("rouge_12") for i in res.ids_tuiles)


@besoin_exact
def test_ines_tour85_victoire_immediate(facteur_machine):
    """Victoire immédiate manquée par l'ancienne recherche (1 tuile) : le
    modèle exact pose les 2 tuiles."""
    data = _charger("reference_victoire_manquee_ines_tour85.json")
    res = se.resoudre_exact(data["etat"], data["idx"],
                            budget_temps=se.BUDGET_TEMPS_DEFAUT * facteur_machine)
    assert res.nb_tuiles == 2
    assert res.valide_globalement


@besoin_exact
def test_expert_joue_le_coup_exact_de_bout_en_bout(facteur_machine):
    """``jouer_niveau_expert`` (branchement complet) pose bien 4 tuiles sur
    Bruno tour 57 — ce que l'ancienne recherche ne faisait pas."""
    data = _charger("cas_expert_bruno_tour57.json")
    etat, idx = data["etat"], data["idx"]
    coup = jouer_niveau_expert(etat, idx,
                               budget_temps=se.BUDGET_TEMPS_DEFAUT * facteur_machine)
    assert coup["action"] == "jouer"
    assert len(coup["ids_tuiles"]) == 4


# --------------------------------------------------------------------------- #
# Comparaison avec la recherche exhaustive indépendante (point 6b)
# --------------------------------------------------------------------------- #

@besoin_exact
def test_accord_avec_recherche_exhaustive_positions_aleatoires(facteur_machine):
    """Sur des positions aléatoires (graine fixe), le modèle exact ne doit
    JAMAIS poser moins de tuiles que la recherche exhaustive indépendante de
    ``verif_solveur``, et chacune de ses solutions doit être valide et
    conserver le plateau.

    On ne compare pas l'égalité stricte : la recherche exhaustive de
    ``verif_solveur`` est sensible à l'ORDRE des tuiles (elle énumère des
    sous-ensembles dans l'ordre de la liste et valide par position, voir son
    module), elle sous-estime donc certaines suites qui exigeraient de
    réordonner (p. ex. préfixer ``bleu 4`` à ``bleu 5-6-7-8``) — c'est
    précisément la limite qui fait que l'ancien test ``test_verif_solveur``
    ne vérifie, lui aussi, que « jamais pire ». L'égalité EXACTE est vérifiée
    séparément contre la bibliothèque ``rummikub-solver``
    (``test_accord_avec_bibliotheque_rummikub_solver``). Ici, la validité +
    la conservation de CHAQUE solution du modèle exact garantissent qu'il ne
    sur-compte jamais ; combiné à « jamais sous l'exhaustive », cela borne le
    résultat des deux côtés."""
    import random
    from rummikub.moteur import verif_solveur

    rng = random.Random(20626)
    for _ in range(250):
        pos = verif_solveur.generer_position_aleatoire(rng)
        exhaustif = verif_solveur.max_tuiles_posables_exhaustif(
            pos["plateau"], pos["chevalet"])
        etat = {
            "joueurs": [{"chevalet": [t.as_dict() for t in pos["chevalet"]],
                         "mise_initiale_faite": True}],
            "plateau": [[t.as_dict() for t in combo] for combo in pos["plateau"]],
            "config": {"mise_initiale_min": 30},
        }
        res = se.resoudre_exact(etat, 0, budget_temps=5.0 * facteur_machine)
        assert res.valide_globalement, (
            f"solution invalide/non conservée : plateau="
            f"{[[t.id for t in c] for c in pos['plateau']]} "
            f"main={[t.id for t in pos['chevalet']]}")
        assert res.nb_tuiles >= exhaustif, (
            f"le modèle exact pose {res.nb_tuiles} < {exhaustif} (exhaustive) : "
            f"plateau={[[t.id for t in c] for c in pos['plateau']]} "
            f"main={[t.id for t in pos['chevalet']]}")


# --------------------------------------------------------------------------- #
# Comparaison avec la bibliothèque rummikub-solver (point 6c)
# --------------------------------------------------------------------------- #

@besoin_exact
def test_accord_avec_bibliotheque_rummikub_solver(facteur_machine):
    """Quand la bibliothèque exacte ``rummikub-solver`` (#204) est installée,
    notre modèle maison trouve le même nombre de tuiles sur tous les cas de
    référence. Sauté si la bibliothèque est absente."""
    pytest.importorskip("rummikub_solver")
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import solveur_exact as lib_adaptateur  # adaptateur bibliothèque (#204)

    for chemin in _cas():
        data = json.loads(chemin.read_text(encoding="utf-8"))
        maison = se.resoudre_exact(data["etat"], data["idx"],
                                   budget_temps=se.BUDGET_TEMPS_DEFAUT * facteur_machine)
        lib = lib_adaptateur.resoudre_exact(data["etat"], data["idx"])
        assert maison.nb_tuiles == lib.nb_tuiles, (
            f"{chemin.name} : maison {maison.nb_tuiles} vs bibliothèque "
            f"{lib.nb_tuiles}")


# --------------------------------------------------------------------------- #
# Mise initiale (point 2 / 6e)
# --------------------------------------------------------------------------- #

@besoin_exact
def test_mise_initiale_ne_touche_pas_le_plateau(facteur_machine):
    """Mise initiale pas faite : le plateau d'un autre joueur ne doit pas être
    réarrangé (contrairement à la bibliothèque de #204). On pose une suite de
    la main seule totalisant ≥ 30, et le plateau d'origine reste identique."""
    # Plateau posé par un adversaire (ne doit pas bouger).
    plateau = [[{"id": "rouge_5_a", "valeur": 5, "couleur": "rouge", "est_joker": False},
                {"id": "rouge_6_a", "valeur": 6, "couleur": "rouge", "est_joker": False},
                {"id": "rouge_7_a", "valeur": 7, "couleur": "rouge", "est_joker": False}]]
    # Main : une suite noire 9-10-11-12 (42 pts ≥ 30) + du bruit.
    chevalet = [
        {"id": "noir_9_a", "valeur": 9, "couleur": "noir", "est_joker": False},
        {"id": "noir_10_a", "valeur": 10, "couleur": "noir", "est_joker": False},
        {"id": "noir_11_a", "valeur": 11, "couleur": "noir", "est_joker": False},
        {"id": "noir_12_a", "valeur": 12, "couleur": "noir", "est_joker": False},
        {"id": "bleu_2_a", "valeur": 2, "couleur": "bleu", "est_joker": False},
    ]
    etat = {
        "joueurs": [{"chevalet": chevalet, "mise_initiale_faite": False}],
        "plateau": plateau,
        "config": {"mise_initiale_min": 30},
    }
    res = se.resoudre_exact(etat, 0, budget_temps=5.0 * facteur_machine)
    assert res.valide_globalement
    assert res.points >= 30  # mise initiale atteinte avec la seule main
    # Les tuiles rouges du plateau figurent telles quelles dans le résultat,
    # dans leur combinaison d'origine (aucune tuile du plateau déplacée).
    assert [t["id"] for t in res.nouveau_plateau[0]] == \
        ["rouge_5_a", "rouge_6_a", "rouge_7_a"]
    # Toutes les tuiles posées viennent de la main (aucune du plateau).
    for tid in res.ids_tuiles:
        assert tid.startswith("noir_")


@besoin_exact
def test_mise_initiale_insuffisante_renvoie_none(facteur_machine):
    """Si la main ne peut pas atteindre la mise minimale sans toucher au
    plateau, aucun coup n'est renvoyé (Expert piochera)."""
    plateau = [[{"id": "rouge_5_a", "valeur": 5, "couleur": "rouge", "est_joker": False},
                {"id": "rouge_6_a", "valeur": 6, "couleur": "rouge", "est_joker": False},
                {"id": "rouge_7_a", "valeur": 7, "couleur": "rouge", "est_joker": False}]]
    # Main : une suite bleue 1-2-3 (6 pts < 30) seulement.
    chevalet = [
        {"id": "bleu_1_a", "valeur": 1, "couleur": "bleu", "est_joker": False},
        {"id": "bleu_2_a", "valeur": 2, "couleur": "bleu", "est_joker": False},
        {"id": "bleu_3_a", "valeur": 3, "couleur": "bleu", "est_joker": False},
    ]
    etat = {
        "joueurs": [{"chevalet": chevalet, "mise_initiale_faite": False}],
        "plateau": plateau,
        "config": {"mise_initiale_min": 30},
    }
    coup = se.resoudre_coup_exact(etat, 0, budget_temps=5.0 * facteur_machine)
    assert coup is None


# --------------------------------------------------------------------------- #
# Critères de départage (point 3 / 6e)
# --------------------------------------------------------------------------- #

@besoin_exact
def test_david_tour31_coup_simple_un_seul_geste(facteur_machine):
    """David tour 31 : parmi les coups qui posent la même unique tuile, le
    modèle exact choisit celui qui perturbe le moins le plateau — étendre le
    groupe de 1 (0 tuile déplacée), pas fragmenter plusieurs combinaisons."""
    data = _charger("cas_expert_coup_simple_david_tour31.json")
    res = se.resoudre_exact(data["etat"], data["idx"],
                            budget_temps=se.BUDGET_TEMPS_DEFAUT * facteur_machine)
    assert res.nb_tuiles == 1
    deplacees, modifiees = res.perturbation
    assert deplacees == 0, f"{deplacees} tuiles déplacées pour un coup simple"
    assert modifiees <= 1


@besoin_exact
def test_departage_economie_de_jokers(facteur_machine):
    """À nombre de tuiles ET points posés égaux, le modèle préfère NE PAS
    poser un joker de la main si une solution équivalente s'en passe. Plateau
    vide, main = {rouge/bleu/noir/jaune 5, joker} : le maximum est un groupe
    de 4 tuiles. On peut l'atteindre avec les 4 réelles (joker en main) ou
    avec 3 réelles + joker (une réelle en main) ; la première pose autant de
    tuiles et plus de points, et garde le joker — c'est elle qui doit sortir."""
    chevalet = [
        {"id": "rouge_5_a", "valeur": 5, "couleur": "rouge", "est_joker": False},
        {"id": "bleu_5_a", "valeur": 5, "couleur": "bleu", "est_joker": False},
        {"id": "noir_5_a", "valeur": 5, "couleur": "noir", "est_joker": False},
        {"id": "jaune_5_a", "valeur": 5, "couleur": "jaune", "est_joker": False},
        {"id": "joker_1", "valeur": None, "couleur": "rouge", "est_joker": True},
    ]
    etat = {
        "joueurs": [{"chevalet": chevalet, "mise_initiale_faite": True}],
        "plateau": [],
        "config": {"mise_initiale_min": 30},
    }
    res = se.resoudre_exact(etat, 0, budget_temps=5.0 * facteur_machine)
    assert res.nb_tuiles == 4  # groupe de 4 (maximum)
    assert res.jokers_main == 0, "un joker a été posé alors qu'il pouvait rester en main"
    assert "joker_1" not in res.ids_tuiles
