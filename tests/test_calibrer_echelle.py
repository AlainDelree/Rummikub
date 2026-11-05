"""Tests rapides de ``scripts/calibrer_echelle.py`` (issue #240) : lecture des
réglages (valides et invalides), verdict et calcul d'Elo sur des chiffres
fabriqués, reprise sur une mini-série avec interruption simulée, et refus de
mélanger deux jeux de réglages dans un même dossier. Aucune longue simulation
ici — budget du solveur et garde-fou de tours minuscules, au plus 2 donnes."""

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import calibrer_echelle as M  # noqa: E402
from rummikub.moteur import niveaux as _niveaux  # noqa: E402

_BUDGET_RAPIDE = 0.02
_MAX_TOURS_RAPIDE = 10


def _main_worker(args: list[str]) -> int:
    return M.main(["calibrer_echelle.py", *args, "--_worker"])


# --------------------------------------------------------------------------- #
# Lecture des réglages — valides
# --------------------------------------------------------------------------- #

def test_parser_reglage_valide_entier():
    niveau, bridage = M.parser_reglage("Facile=2/0.30")
    assert niveau == "Facile"
    assert bridage == _niveaux.Bridage(perturbation_max=2, taux_oubli=0.30)


def test_parser_reglage_valide_inf():
    niveau, bridage = M.parser_reglage("Avancé=inf/0.05")
    assert niveau == "Avancé"
    assert bridage.perturbation_max is None
    assert bridage.taux_oubli == 0.05


@pytest.mark.parametrize("texte", ["none/0", "illimite/0", "illimité/0", "∞/0"])
def test_parser_reglage_synonymes_illimite(texte):
    niveau, bridage = M.parser_reglage(f"Expert={texte}")
    assert bridage.perturbation_max is None


def test_parser_candidats_valide():
    niveau, candidats = M.parser_candidats("Avancé=inf/0.03,inf/0.06,inf/0.10")
    assert niveau == "Avancé"
    assert candidats == [
        _niveaux.Bridage(perturbation_max=None, taux_oubli=0.03),
        _niveaux.Bridage(perturbation_max=None, taux_oubli=0.06),
        _niveaux.Bridage(perturbation_max=None, taux_oubli=0.10),
    ]


def test_parser_paire_valide():
    assert M.parser_paire("Débutant:Expert") == ("Débutant", "Expert")


# --------------------------------------------------------------------------- #
# Lecture des réglages — invalides
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("texte", [
    "Facile:2/0.30",            # pas de « = »
    "Inconnu=2/0.30",           # niveau inexistant
    "Facile=2",                 # pas de « / »
    "Facile=abc/0.30",          # perturbation non entière
    "Facile=-1/0.30",           # perturbation négative
    "Facile=2/1.5",             # oubli hors de [0, 1]
    "Facile=2/bas",             # oubli non numérique
])
def test_parser_reglage_invalide(texte):
    with pytest.raises(ValueError):
        M.parser_reglage(texte)


@pytest.mark.parametrize("texte", [
    "Avancé:inf/0.03",          # pas de « = »
    "Inconnu=inf/0.03",         # niveau inexistant
    "Avancé=inf",               # pas de « / »
    "Avancé=",                  # aucun candidat
])
def test_parser_candidats_invalide(texte):
    with pytest.raises(ValueError):
        M.parser_candidats(texte)


@pytest.mark.parametrize("texte", ["Débutant", "Débutant-Expert", "Inconnu:Expert"])
def test_parser_paire_invalide(texte):
    with pytest.raises(ValueError):
        M.parser_paire(texte)


# --------------------------------------------------------------------------- #
# Verdict et Elo sur des chiffres fabriqués
# --------------------------------------------------------------------------- #

def test_verdict_dans_la_cible():
    assert M.verdict_cible(0.65, 0.60, 0.70) == "dans la cible"
    assert M.verdict_cible(0.60, 0.60, 0.70) == "dans la cible"
    assert M.verdict_cible(0.70, 0.60, 0.70) == "dans la cible"


def test_verdict_trop_faible():
    assert "trop faible" in M.verdict_cible(0.50, 0.60, 0.70)


def test_verdict_trop_fort():
    assert "trop fort" in M.verdict_cible(0.85, 0.60, 0.70)


def test_elo_depuis_taux_symetrique():
    # 75 victoires sur 100 : écart positif ; l'inverse (25/100) donne
    # exactement l'opposé par symétrie de la correction de continuité.
    elo_fort = M.elo_depuis_taux(75, 100)
    elo_faible = M.elo_depuis_taux(25, 100)
    assert elo_fort > 0
    assert elo_faible < 0
    assert elo_fort == pytest.approx(-elo_faible)


def test_elo_depuis_taux_aucune_partie():
    assert M.elo_depuis_taux(0, 0) is None


def test_elo_depuis_taux_100_pour_cent_fini_grace_a_la_correction():
    # 10 victoires sur 10 : sans correction de continuité, p=1 → Elo infini.
    elo = M.elo_depuis_taux(10, 10)
    assert elo is not None
    assert elo > 0
    import math
    assert math.isfinite(elo)


def test_distances_elo_a_expert_chaine_adjacente():
    aretes = {
        ("Avancé", "Expert"): 0.0,
        ("Intermédiaire", "Avancé"): 150.0,
        ("Facile", "Intermédiaire"): 150.0,
        ("Débutant", "Facile"): 150.0,
    }
    distances = M._distances_elo_a_expert(aretes)
    assert distances["Expert"] == 0.0
    assert distances["Avancé"] == pytest.approx(0.0)
    assert distances["Intermédiaire"] == pytest.approx(-150.0)
    assert distances["Facile"] == pytest.approx(-300.0)
    assert distances["Débutant"] == pytest.approx(-450.0)


def test_distances_elo_a_expert_chaine_rompue():
    # Paire Facile-Intermédiaire manquante : Facile et Débutant non calculables.
    aretes = {
        ("Avancé", "Expert"): 0.0,
        ("Intermédiaire", "Avancé"): 150.0,
    }
    distances = M._distances_elo_a_expert(aretes)
    assert "Intermédiaire" in distances
    assert "Facile" not in distances
    assert "Débutant" not in distances


def test_distances_elo_a_expert_arete_directe_preferee():
    # Une mesure DIRECTE Débutant:Expert ne dépend d'aucune chaîne adjacente.
    aretes = {("Débutant", "Expert"): 600.0}
    distances = M._distances_elo_a_expert(aretes)
    assert distances["Débutant"] == pytest.approx(-600.0)


# --------------------------------------------------------------------------- #
# Reprise après interruption (mini-série de deux donnes)
# --------------------------------------------------------------------------- #

def test_reprise_ne_rejoue_pas_les_donnes_completes(tmp_path):
    dossier = tmp_path / "calib"
    code1 = _main_worker([
        "--dossier", str(dossier), "--paire", "Débutant:Facile",
        "--donnes", "1", "--seed", "0", "--max-tours", str(_MAX_TOURS_RAPIDE),
        "--budget-solveur", str(_BUDGET_RAPIDE),
    ])
    assert code1 == M.CODE_TERMINE
    chemin = dossier / "resultats_Debutant_vs_Facile.jsonl"
    contenu_1 = chemin.read_text(encoding="utf-8")
    assert len(contenu_1.strip().splitlines()) == 2  # 1 donne = 2 parties miroir

    # Relance sur le MÊME dossier avec davantage de donnes : prolonge la
    # série sans rejouer la donne déjà complète (simule une reprise après
    # interruption : la commande d'origine, coupée après 1 donne, continue).
    code2 = _main_worker([
        "--dossier", str(dossier), "--paire", "Débutant:Facile",
        "--donnes", "2", "--seed", "0", "--max-tours", str(_MAX_TOURS_RAPIDE),
        "--budget-solveur", str(_BUDGET_RAPIDE),
    ])
    assert code2 == M.CODE_TERMINE
    contenu_2 = chemin.read_text(encoding="utf-8")
    lignes_2 = contenu_2.strip().splitlines()
    assert len(lignes_2) == 4  # 2 donnes = 4 parties miroir
    # Les deux premières lignes (donne 1) n'ont pas été rejouées.
    assert lignes_2[0] == contenu_1.strip().splitlines()[0]
    assert lignes_2[1] == contenu_1.strip().splitlines()[1]


def test_reprise_tronque_une_donne_incomplete_par_coupure_brutale(tmp_path):
    dossier = tmp_path / "calib"
    dossier.mkdir()
    chemin = dossier / "resultats_Debutant_vs_Facile.jsonl"
    # Donne 1 complète (2 lignes) + donne 2 INCOMPLÈTE (1 seule ligne, comme
    # une coupure brutale en plein milieu) : doit être rejouée en entier.
    enregs = [
        {"donne": 1, "ordre": ["A", "B"], "niveau_a": "Débutant",
         "niveau_b": "Facile", "vainqueur_camp": "B", "arretee_garde_fou": False,
         "score_a": -5, "score_b": 5},
        {"donne": 1, "ordre": ["B", "A"], "niveau_a": "Débutant",
         "niveau_b": "Facile", "vainqueur_camp": "A", "arretee_garde_fou": False,
         "score_a": 5, "score_b": -5},
        {"donne": 2, "ordre": ["A", "B"], "niveau_a": "Débutant",
         "niveau_b": "Facile", "vainqueur_camp": "B", "arretee_garde_fou": False,
         "score_a": -3, "score_b": 3},
    ]
    chemin.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in enregs) + "\n",
        encoding="utf-8")

    nb_complet = M._tronquer_si_necessaire(chemin)
    assert nb_complet == 1
    lignes = chemin.read_text(encoding="utf-8").strip().splitlines()
    assert len(lignes) == 2  # la donne 2 incomplète a été retirée


def test_statut_sans_serie_echoue_proprement(tmp_path):
    code = M.commande_statut(tmp_path / "inexistant")
    assert code == 1


# --------------------------------------------------------------------------- #
# Refus de mélanger deux jeux de réglages dans un même dossier
# --------------------------------------------------------------------------- #

def test_refuse_de_melanger_deux_jeux_de_reglages(tmp_path, capsys):
    dossier = tmp_path / "calib"
    code1 = _main_worker([
        "--dossier", str(dossier), "--reglage", "Facile=1/0.30",
        "--paire", "Débutant:Facile", "--donnes", "1", "--seed", "0",
        "--max-tours", str(_MAX_TOURS_RAPIDE),
        "--budget-solveur", str(_BUDGET_RAPIDE),
    ])
    assert code1 == M.CODE_TERMINE
    chemin = dossier / "resultats_Debutant_vs_Facile.jsonl"
    contenu_avant = chemin.read_text(encoding="utf-8")

    code2 = _main_worker([
        "--dossier", str(dossier), "--reglage", "Facile=2/0.30",
        "--paire", "Débutant:Facile", "--donnes", "1", "--seed", "0",
        "--max-tours", str(_MAX_TOURS_RAPIDE),
        "--budget-solveur", str(_BUDGET_RAPIDE),
    ])
    assert code2 == 1
    erreur = capsys.readouterr().err
    assert "réglages DIFFÉRENTS" in erreur
    # Le fichier déjà écrit n'a pas été touché par la tentative refusée.
    assert chemin.read_text(encoding="utf-8") == contenu_avant


def test_prolongation_de_donnes_est_autorisee(tmp_path):
    dossier = tmp_path / "calib"
    _main_worker([
        "--dossier", str(dossier), "--paire", "Débutant:Facile",
        "--donnes", "1", "--seed", "0", "--max-tours", str(_MAX_TOURS_RAPIDE),
        "--budget-solveur", str(_BUDGET_RAPIDE),
    ])
    code = _main_worker([
        "--dossier", str(dossier), "--paire", "Débutant:Facile",
        "--donnes", "2", "--seed", "0", "--max-tours", str(_MAX_TOURS_RAPIDE),
        "--budget-solveur", str(_BUDGET_RAPIDE),
    ])
    assert code == M.CODE_TERMINE
    reglages = json.loads((dossier / "reglages.json").read_text(encoding="utf-8"))
    assert reglages["donnes"] == 2


# --------------------------------------------------------------------------- #
# Campagne complète (rapide) : rapport lisible, statut
# --------------------------------------------------------------------------- #

def test_campagne_complete_ecrit_un_rapport_lisible(tmp_path):
    dossier = tmp_path / "calib"
    code = _main_worker([
        "--dossier", str(dossier), "--paire", "Débutant:Facile",
        "--donnes", "2", "--seed", "0", "--max-tours", str(_MAX_TOURS_RAPIDE),
        "--budget-solveur", str(_BUDGET_RAPIDE),
    ])
    assert code == M.CODE_TERMINE
    rapport = (dossier / "rapport.txt").read_text(encoding="utf-8")
    assert "Débutant vs Facile" in rapport
    assert "TERMINÉ NORMALEMENT" in rapport
    assert "[2/2d]" in rapport


def test_statut_lit_sans_rejouer(tmp_path, capsys):
    dossier = tmp_path / "calib"
    _main_worker([
        "--dossier", str(dossier), "--paire", "Débutant:Facile",
        "--donnes", "1", "--seed", "0", "--max-tours", str(_MAX_TOURS_RAPIDE),
        "--budget-solveur", str(_BUDGET_RAPIDE),
    ])
    chemin = dossier / "resultats_Debutant_vs_Facile.jsonl"
    avant = chemin.read_text(encoding="utf-8")

    code = M.main(["calibrer_echelle.py", "--dossier", str(dossier), "--statut"])
    assert code == 0
    sortie = capsys.readouterr().out
    assert "Débutant vs Facile" in sortie
    assert chemin.read_text(encoding="utf-8") == avant  # inchangé


# --------------------------------------------------------------------------- #
# Options incompatibles / invalides détectées par le CLI
# --------------------------------------------------------------------------- #

def test_paire_et_candidats_incompatibles(tmp_path):
    with pytest.raises(SystemExit) as exc:
        M.main(["calibrer_echelle.py", "--dossier", str(tmp_path),
               "--paire", "Débutant:Facile",
               "--candidats", "Avancé=inf/0.03", "--contre", "Expert"])
    assert exc.value.code == 2


def test_candidats_sans_contre_refuse(tmp_path):
    with pytest.raises(SystemExit) as exc:
        M.main(["calibrer_echelle.py", "--dossier", str(tmp_path),
               "--candidats", "Avancé=inf/0.03"])
    assert exc.value.code == 2


def test_cible_basse_superieure_a_haute_refuse(tmp_path):
    with pytest.raises(SystemExit) as exc:
        M.main(["calibrer_echelle.py", "--dossier", str(tmp_path),
               "--cible-basse", "0.8", "--cible-haute", "0.6"])
    assert exc.value.code == 2
