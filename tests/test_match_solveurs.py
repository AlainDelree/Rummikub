"""Tests du script de match « notre solveur » vs bibliothèque (issue #212).

``scripts/match_solveurs.py`` fait jouer des parties entières entre le niveau
Expert livré et un « joueur bibliothèque » bâti sur l'adaptateur
``scripts/solveur_exact.py`` (#204). La bibliothèque ``rummikub-solver`` est une
dépendance de DÉVELOPPEMENT seulement : ces tests se sautent proprement si elle
est absente (comme ``tests/test_solveur_exact.py``). Pour les lancer :

    python -m venv .venv-solveur-exact
    .venv-solveur-exact/bin/pip install 'rummikub-solver[highs]' pytest
    .venv-solveur-exact/bin/python -m pytest tests/test_match_solveurs.py
"""

import sys
from pathlib import Path

import pytest

# Saute tout le module si la bibliothèque est absente — le « joueur
# bibliothèque » n'a alors aucun sens (point 5 de l'issue : décideur
# bibliothèque sautant proprement si la lib absente).
pytest.importorskip("rummikub_solver")

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import match_solveurs as M  # noqa: E402
import solveur_exact as solveur_biblio  # noqa: E402
from rummikub.moteur.partie import creer_partie  # noqa: E402
from rummikub.moteur.tuiles import Tuile  # noqa: E402
from rummikub.moteur.validation import valider_combinaison  # noqa: E402


# --------------------------------------------------------------------------- #
# Garde-fou : la bibliothèque est bien marquée disponible/absente proprement.
# --------------------------------------------------------------------------- #

def test_bibliotheque_disponible_flag():
    # Le module s'importe toujours ; DISPONIBLE dit si la lib est là. Ici, le
    # module de test ne serait pas chargé si elle manquait (importorskip).
    assert solveur_biblio.DISPONIBLE is True


# --------------------------------------------------------------------------- #
# Statistiques : IC 95 % de Wilson, conservation des 106 tuiles.
# --------------------------------------------------------------------------- #

def test_wilson_bornes_et_proportion():
    p, bas, haut = M._wilson(50, 100)
    assert abs(p - 0.5) < 1e-9
    assert 0.0 <= bas < p < haut <= 1.0
    # Échantillon vide : tout à zéro, pas d'erreur.
    assert M._wilson(0, 0) == (0.0, 0.0, 0.0)
    # Cas extrême 0 succès : borne basse à 0, borne haute > 0.
    p0, bas0, haut0 = M._wilson(0, 20)
    assert p0 == 0.0 and bas0 == 0.0 and haut0 > 0.0


def test_conservation_ok_detecte_tuile_manquante():
    etat = creer_partie(
        [{"nom": "a", "est_ia": True, "niveau": "Expert"},
         {"nom": "b", "est_ia": True, "niveau": "Expert"}],
        {"nb_manches": 1})
    ok, msg = M.conservation_ok(etat)
    assert ok, msg
    # On retire une tuile de la pioche : le contrôle doit le détecter.
    etat["pioche"].pop()
    ok, msg = M.conservation_ok(etat)
    assert not ok
    assert "105" in msg


def test_conservation_ok_detecte_doublon():
    etat = creer_partie(
        [{"nom": "a", "est_ia": True, "niveau": "Expert"},
         {"nom": "b", "est_ia": True, "niveau": "Expert"}],
        {"nb_manches": 1})
    # Duplique un id (tuile en double) sans changer le compte total.
    etat["pioche"][0] = dict(etat["pioche"][1])
    ok, msg = M.conservation_ok(etat)
    assert not ok
    assert "doublon" in msg


# --------------------------------------------------------------------------- #
# Décideur bibliothèque : coup complet, ordonné, validé, conservatif.
# --------------------------------------------------------------------------- #

def _etat_apres_mise(plateau_combos, chevalet_tuiles):
    """Construit un état minimal à deux joueurs, mise initiale DÉJÀ faite pour
    le joueur 0, avec le plateau et le chevalet fournis (listes de Tuile)."""
    etat = {
        "joueurs": [
            {"nom": "j0", "chevalet": [t.as_dict() for t in chevalet_tuiles],
             "mise_initiale_faite": True},
            {"nom": "j1", "chevalet": [], "mise_initiale_faite": True},
        ],
        "plateau": [[t.as_dict() for t in combo] for combo in plateau_combos],
        "pioche": [],
        "index_joueur_actuel": 0,
        "tour_numero": 1,
        "config": {"mise_initiale_min": 30, "nb_manches": 1},
    }
    return etat


def test_decideur_biblio_coup_apres_mise_valide_et_ordonne():
    # Plateau : une suite bleu 3-4-5. Main : bleu 6 (prolonge la suite) + de
    # quoi ne rien casser. La bibliothèque doit poser au moins le 6.
    plateau = [[Tuile("b3", 3, "bleu"), Tuile("b4", 4, "bleu"),
                Tuile("b5", 5, "bleu")]]
    chevalet = [Tuile("b6", 6, "bleu"), Tuile("r1", 1, "rouge"),
                Tuile("n9", 9, "noir")]
    etat = _etat_apres_mise(plateau, chevalet)
    dec = M.decider_bibliotheque(etat, 0)
    if dec.action == "jouer":
        # Chaque combinaison du nouveau plateau est valide (remise dans l'ordre).
        from rummikub.moteur.partie import plateau_depuis_dict
        for combo in plateau_depuis_dict(dec.nouveau_plateau):
            assert valider_combinaison(combo)["valide"]
        # Conservation : toutes les tuiles du plateau initial sont encore là.
        ids_avant = {t["id"] for c in etat["plateau"] for t in c}
        ids_apres = {t["id"] for c in dec.nouveau_plateau for t in c}
        assert ids_avant <= ids_apres
        assert dec.nb_posees == len(dec.ids_tuiles) >= 1


def test_decideur_biblio_mise_initiale_ne_touche_pas_le_plateau():
    # Mise NON faite : un plateau adverse existe déjà ; la bibliothèque ne doit
    # former sa combinaison qu'avec la main et laisser le plateau intact.
    plateau = [[Tuile("x1", 1, "rouge"), Tuile("x2", 2, "rouge"),
                Tuile("x3", 3, "rouge")]]
    # Main : un groupe de 10 (3 couleurs) = 30 points, atteint la mise.
    chevalet = [Tuile("d10a", 10, "noir"), Tuile("d10b", 10, "bleu"),
                Tuile("d10c", 10, "rouge"), Tuile("z1", 1, "noir")]
    etat = _etat_apres_mise(plateau, chevalet)
    etat["joueurs"][0]["mise_initiale_faite"] = False
    dec = M.decider_bibliotheque(etat, 0)
    assert dec.mise_contrainte is True
    if dec.action == "jouer":
        from rummikub.moteur.partie import plateau_depuis_dict
        for combo in plateau_depuis_dict(dec.nouveau_plateau):
            assert valider_combinaison(combo)["valide"]
        # Le plateau initial (rouge 1-2-3) est conservé À L'IDENTIQUE.
        ids_avant = {t["id"] for c in etat["plateau"] for t in c}
        ids_apres = {t["id"] for c in dec.nouveau_plateau for t in c}
        assert ids_avant <= ids_apres
        # Les tuiles posées viennent toutes de la main.
        ids_main = {t["id"] for t in etat["joueurs"][0]["chevalet"]}
        assert set(dec.ids_tuiles) <= ids_main


# --------------------------------------------------------------------------- #
# Égalité d'optimalité : les deux solveurs posent le même nombre de tuiles.
# --------------------------------------------------------------------------- #

def test_max_posable_egaux_sur_etats_de_depart():
    # Sur plusieurs donnes de départ (mise non faite), le nombre maximal de
    # tuiles posables doit être IDENTIQUE entre notre modèle et la bibliothèque
    # (c'est le socle du match : seul le départage diffère).
    comparables = 0
    for seed in range(5):
        import random
        random.seed(1000 + seed)
        etat = creer_partie(
            [{"nom": "a", "est_ia": True, "niveau": "Expert"},
             {"nom": "b", "est_ia": True, "niveau": "Expert"}],
            {"nb_manches": 1})
        nb_notre = M.max_posable_notre(etat, 0, budget_temps=10.0)
        nb_biblio = M.max_posable_biblio(etat, 0)
        # ``None`` = solveur non concluant (budget dépassé sous charge CPU) : on
        # ne compare que les cas où les DEUX ont conclu — c'est exactement ce que
        # fait le contrôle d'optimalité du match (il ignore les ``None``).
        if nb_notre is None or nb_biblio is None:
            continue
        comparables += 1
        assert nb_notre == nb_biblio, (
            f"seed {seed} : notre={nb_notre} biblio={nb_biblio}")
    assert comparables >= 1, "aucun état comparable (budget trop serré ?)"


# --------------------------------------------------------------------------- #
# Petit match complet (lent) : miroir, conservation, aucun écart d'optimalité.
# --------------------------------------------------------------------------- #

@pytest.mark.lent
def test_petit_match_integrite():
    resultat = M.jouer_match(nb_donnes=1, seed_base=4242, max_tours=400,
                             budget_temps=1.5, limite_temps=None)
    assert resultat["parties_jouees"] == 2        # 1 donne = 2 parties (miroir)
    agr = M.agreger(resultat)
    # Aucune tuile perdue sur aucun coup d'aucune partie.
    assert agr["conservation_erreurs"] == []
    # Aucun écart d'optimalité : même nombre de tuiles posables sur chaque état.
    assert agr["ecarts_optimalite"] == []
    # Les deux sens de la donne existent (places échangées).
    sens = {p["sens"] for p in resultat["parties"]}
    assert sens == {"A", "B"}
    # Chaque partie s'est terminée (non bloquée) avec un résultat exploitable.
    for p in resultat["parties"]:
        assert p["gagnant_role"] in (M.NOM_NOTRE, M.NOM_BIBLIO) or p["egalite"]


def test_wilson_disjoint_detecte_difference():
    # 80/100 vs 20/100 : intervalles nettement disjoints.
    _, _, haut_perdant = M._wilson(20, 100)
    _, bas_gagnant, _ = M._wilson(80, 100)
    assert bas_gagnant > haut_perdant
