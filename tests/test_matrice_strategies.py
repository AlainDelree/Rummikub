"""Tests de l'outil de matrice de comparaisons de stratégies (issue #228,
point 7) : plans (ablation/complet/personnalisé), fusion de résumés,
lecture tolérante d'une ligne incomplète, et une MINI-SÉRIE de deux
configurations de deux donnes chacune — y compris une interruption simulée
puis une reprise qui ne rejoue pas les parties déjà écrites, et le refus de
reprendre si le commit a changé.

``comparer_niveaux_ia.comparer`` est REMPLACÉ par un faux générateur de
résultats déterministe (``_FauxComparer``) : ce fichier teste l'INFRA-
STRUCTURE de la matrice (plans, reprise, checkpoint, résumé), jamais le
moteur de jeu lui-même (couvert par ses propres tests) — conformément à
CONTEXTE.md §7, aucune campagne longue n'est rejouée ici."""

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import matrice_strategies as M  # noqa: E402


# --------------------------------------------------------------------------- #
# Faux ``comparer_niveaux_ia.comparer`` — déterministe, écrit ligne par
# ligne avec flush (comme le vrai), et peut simuler une panne EN PLEIN
# MILIEU d'une donne (après la première des deux lignes d'ordre miroir).
# --------------------------------------------------------------------------- #

class _FauxComparer:
    def __init__(self):
        self.appels = 0
        self.panne_apres_n_lignes = None
        self.lignes_ecrites = 0

    def __call__(self, niveau_a, niveau_b, nb_donnes, seed, max_tours,
                nb_manches=1, preferer_simple=True, eval_a="off", eval_b="off",
                sans_exact=False, export_resultats=None, export_trace=None,
                budget_temps=None, donnes_debut=0, donnes_fin=None,
                mode_fichier="w"):
        self.appels += 1
        fin = nb_donnes if donnes_fin is None else donnes_fin
        f = (open(export_resultats, mode_fichier, encoding="utf-8")
            if export_resultats else None)
        victoires = {"A": 0, "B": 0}
        n_jouees = 0
        try:
            for i in range(donnes_debut, fin):
                for ordre in (["A", "B"], ["B", "A"]):
                    if (self.panne_apres_n_lignes is not None
                            and self.lignes_ecrites >= self.panne_apres_n_lignes):
                        raise RuntimeError("panne simulée (#228, test de reprise)")
                    gagnant = "A" if (i + (ordre[0] == "B")) % 2 == 0 else "B"
                    victoires[gagnant] += 1
                    if f:
                        f.write(json.dumps({
                            "donne": i + 1, "ordre": ordre,
                            "niveau_a": niveau_a, "niveau_b": niveau_b,
                            "vainqueur_camp": gagnant, "arretee_garde_fou": False,
                            "score_a": 10, "score_b": -10,
                            "strategies_changees": {"verif_finition": False,
                                                    "garde_joker": False},
                        }, ensure_ascii=False) + "\n")
                        f.flush()
                        self.lignes_ecrites += 1
                n_jouees += 1
        finally:
            if f:
                f.close()
        return {
            "niveau_a": niveau_a, "niveau_b": niveau_b, "nb_manches": nb_manches,
            "stats_verif_finition": {"appliquee_meilleur_suffit": n_jouees * 2},
            "stats_garde_joker": {}, "parties_garde_joker": [],
            "victoires": victoires, "matchs_nuls": 0, "matchs_decides": n_jouees * 2,
            "cumul_par_camp": {"A": [10] * (n_jouees * 2), "B": [-10] * (n_jouees * 2)},
            "fins": {"chevalet_vide": n_jouees * 2, "pioche_vide": 0, "garde_fou": 0},
            "penalites_perdant": [], "tuiles_perdant": [], "tours_decidees": [],
            "temps_par_niveau": {}, "coups_invalides_total": 0,
            "coups_tuiles_disparues_total": 0, "anomalies_conservation_total": 0,
            "replis_expert": {"budget_depasse": 0, "deps_absentes": 0, "autre": 0},
            "aucun_coup_expert": 0, "perturbations_expert": [],
            "preferer_simple": preferer_simple, "eval_a": eval_a, "eval_b": eval_b,
            "nb_donnes": nb_donnes, "nb_donnes_jouees": n_jouees,
            "nb_parties": n_jouees * 2, "sans_exact": sans_exact,
            "valeur_joker_penalite": 30,
        }


@pytest.fixture
def faux_comparer(monkeypatch):
    faux = _FauxComparer()
    monkeypatch.setattr(M.cni, "comparer", faux)
    return faux


def _argv(dossier, **extra):
    base = ["matrice_strategies.py", "--dossier", str(dossier),
           "--niveau-a", "Avancé", "--niveau-b", "Expert",
           "--donnes", "2", "--seed", "0", "--plan", "ablation",
           "--strategies", "garde_joker"]
    for k, v in extra.items():
        base += [f"--{k.replace('_', '-')}", str(v)] if v is not True else [f"--{k.replace('_', '-')}"]
    return base


# --------------------------------------------------------------------------- #
# Plans
# --------------------------------------------------------------------------- #

def test_plan_ablation_structure_et_reference():
    configs, reference = M.construire_plan_ablation(["verif_finition", "garde_joker"])
    noms = [c["nom"] for c in configs]
    assert noms == [
        "temoin_sans_strategie",
        "champion_avec_verif_finition_seule", "champion_avec_garde_joker_seule",
        "champion_complet_sans_verif_finition", "champion_complet_sans_garde_joker",
        "champion_complet",
    ]
    assert reference == "champion_complet"
    assert configs[0]["strategies_champion"] == []
    assert configs[-1]["strategies_champion"] == ["verif_finition", "garde_joker"]


def test_plan_complet_toutes_les_combinaisons():
    configs, reference = M.construire_plan_complet(["verif_finition", "garde_joker"])
    assert len(configs) == 4  # 2^2
    tailles = sorted(len(c["strategies_champion"]) for c in configs)
    assert tailles == [0, 1, 1, 2]
    assert reference == "champion_verif_finition_garde_joker"


def test_plan_personnalise_depuis_fichier(tmp_path):
    chemin = tmp_path / "plan.json"
    chemin.write_text(json.dumps({"configurations": [
        {"nom": "a", "strategies_champion": []},
        {"nom": "b", "strategies_champion": ["garde_joker"], "reference": True},
    ]}), encoding="utf-8")
    configs, reference = M.charger_plan_personnalise(str(chemin))
    assert [c["nom"] for c in configs] == ["a", "b"]
    assert reference == "b"


def test_plan_personnalise_nom_duplique_leve(tmp_path):
    chemin = tmp_path / "plan.json"
    chemin.write_text(json.dumps([
        {"nom": "a", "strategies_champion": []},
        {"nom": "a", "strategies_champion": ["garde_joker"]},
    ]), encoding="utf-8")
    with pytest.raises(ValueError, match="dupliqué"):
        M.charger_plan_personnalise(str(chemin))


def test_plan_personnalise_strategie_inconnue_leve(tmp_path):
    chemin = tmp_path / "plan.json"
    chemin.write_text(json.dumps([{"nom": "a", "strategies_champion": ["bidon"]}]),
                      encoding="utf-8")
    with pytest.raises(ValueError):
        M.charger_plan_personnalise(str(chemin))


# --------------------------------------------------------------------------- #
# Lecture tolérante d'une ligne incomplète
# --------------------------------------------------------------------------- #

def test_lire_lignes_tolerant_ignore_la_derniere_ligne_corrompue(tmp_path):
    chemin = tmp_path / "f.jsonl"
    chemin.write_text('{"a": 1}\n{"a": 2}\n{"a": 3, "incompl', encoding="utf-8")
    lignes = M._lire_lignes_tolerant(chemin)
    assert lignes == [{"a": 1}, {"a": 2}]


def test_lire_lignes_tolerant_leve_si_ligne_interieure_corrompue(tmp_path):
    chemin = tmp_path / "f.jsonl"
    chemin.write_text('{"a": 1}\nPAS_DU_JSON\n{"a": 3}\n', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        M._lire_lignes_tolerant(chemin)


def test_lire_lignes_tolerant_fichier_absent(tmp_path):
    assert M._lire_lignes_tolerant(tmp_path / "absent.jsonl") == []


# --------------------------------------------------------------------------- #
# Fusion de résumés
# --------------------------------------------------------------------------- #

def test_fusionner_resumes_additionne_les_compteurs():
    a = {"matchs_decides": 2, "victoires": {"A": 1, "B": 1},
        "tuiles_perdant": [3], "stats_verif_finition": {"appliquee_meilleur_suffit": 1},
        "nb_parties": 2}
    b = {"matchs_decides": 2, "victoires": {"A": 2, "B": 0},
        "tuiles_perdant": [5], "stats_verif_finition": {"appliquee_meilleur_suffit": 1},
        "nb_parties": 2}
    fusion = M._fusionner_resumes(a, b)
    assert fusion["matchs_decides"] == 4
    assert fusion["victoires"] == {"A": 3, "B": 1}
    assert fusion["tuiles_perdant"] == [3, 5]
    assert fusion["stats_verif_finition"]["appliquee_meilleur_suffit"] == 2
    assert fusion["nb_parties"] == 4


# --------------------------------------------------------------------------- #
# Mini-série (point 7) : deux configurations, deux donnes chacune
# --------------------------------------------------------------------------- #

def test_mini_serie_complete_de_bout_en_bout(tmp_path, faux_comparer):
    dossier = tmp_path / "serie"
    code = M.main(_argv(dossier))
    assert code == 0

    description = M._lire_json(dossier / "description.json")
    assert description["fin"] is not None
    noms = [c["nom"] for c in description["configurations"]]
    assert noms == ["temoin_sans_strategie", "champion_avec_garde_joker_seule",
                    "champion_complet_sans_garde_joker", "champion_complet"]

    for nom in noms:
        chk = M._lire_json(dossier / nom / "checkpoint.json")
        assert chk["donnes_completees"] == 2
        assert chk["termine"] is True
        lignes = M._lire_lignes_tolerant(dossier / nom / "resultats.jsonl")
        assert len(lignes) == 4  # 2 donnes x 2 ordres

    resume_texte = (dossier / "resume.txt").read_text(encoding="utf-8")
    assert "champion_complet" in resume_texte
    assert "RÉFÉRENCE" in resume_texte


def test_statut_sur_serie_terminee(tmp_path, faux_comparer, capsys):
    dossier = tmp_path / "serie"
    M.main(_argv(dossier))
    capsys.readouterr()
    code = M.afficher_statut(dossier)
    assert code == 0
    sortie = capsys.readouterr().out
    assert "4/4" in sortie
    assert "TERMINÉE" in sortie


def test_interruption_simulee_puis_reprise_ne_rejoue_rien(tmp_path, faux_comparer):
    """Panne en PLEIN MILIEU de la deuxième configuration : la première
    ligne du deuxième ordre miroir de la première donne n'est jamais écrite
    (1 ligne isolée dans le fichier). Relancer la MÊME commande doit : (1)
    abandonner cette ligne isolée, (2) reprendre exactement à cette donne
    (jamais rejouer la première ligne déjà écrite), (3) ne jamais rejouer
    les configurations déjà terminées."""
    dossier = tmp_path / "serie"

    # La 1ʳᵉ config (temoin_sans_strategie) écrit 4 lignes (2 donnes) avant
    # la panne, déclenchée sur la 5ᵉ ligne écrite (1ʳᵉ ligne de la 2ᵉ config).
    faux_comparer.panne_apres_n_lignes = 5
    with pytest.raises(RuntimeError, match="panne simulée"):
        M.main(_argv(dossier))

    chemin_temoin = dossier / "temoin_sans_strategie" / "resultats.jsonl"
    assert len(M._lire_lignes_tolerant(chemin_temoin)) == 4
    chk_temoin = M._lire_json(dossier / "temoin_sans_strategie" / "checkpoint.json")
    assert chk_temoin["termine"] is True

    chemin_gj = dossier / "champion_avec_garde_joker_seule" / "resultats.jsonl"
    lignes_gj_avant = M._lire_lignes_tolerant(chemin_gj)
    assert len(lignes_gj_avant) == 1  # la panne a coupé APRÈS cette ligne
    contenu_brut_avant = chemin_gj.read_text(encoding="utf-8")

    # Reprise : plus de panne, même commande exactement.
    faux_comparer.panne_apres_n_lignes = None
    faux_comparer.lignes_ecrites = 0
    code = M.main(_argv(dossier))
    assert code == 0

    # La ligne déjà écrite avant la panne n'a pas été réécrite : la trouve
    # identique en tête du fichier final (jamais rejouée).
    lignes_gj_apres = M._lire_lignes_tolerant(chemin_gj)
    assert len(lignes_gj_apres) == 4
    assert lignes_gj_apres[0] == lignes_gj_avant[0]
    assert contenu_brut_avant.splitlines()[0] in chemin_gj.read_text(encoding="utf-8")

    # La 1ʳᵉ config, déjà terminée avant la panne, n'a JAMAIS été rejouée
    # (le faux comparateur n'a pas été réinvoqué sur elle : 4 lignes pile).
    assert len(M._lire_lignes_tolerant(chemin_temoin)) == 4

    for nom in ("champion_complet_sans_garde_joker", "champion_complet"):
        chk = M._lire_json(dossier / nom / "checkpoint.json")
        assert chk["donnes_completees"] == 2
        assert chk["termine"] is True


def test_refuse_de_reprendre_si_le_commit_a_change(tmp_path, faux_comparer, monkeypatch):
    dossier = tmp_path / "serie"
    monkeypatch.setattr(M, "_commit_code", lambda: "COMMIT_1")
    assert M.main(_argv(dossier)) == 0

    monkeypatch.setattr(M, "_commit_code", lambda: "COMMIT_2")
    # La série est déjà entièrement jouée : seule la vérification du commit,
    # faite AVANT tout travail par configuration, nous intéresse ici.
    code = M.main(_argv(dossier))
    assert code == 1

    # Avec l'option explicite, la reprise est autorisée.
    code = M.main(_argv(dossier, forcer_reprise_commit_different=True))
    assert code == 0
    description = M._lire_json(dossier / "description.json")
    assert description["commit_depart"] == "COMMIT_1"  # jamais réécrit en douce


def test_controle_rapide_necrit_pas_dans_le_dossier(tmp_path, faux_comparer, capsys):
    dossier = tmp_path / "serie"
    code = M.main(_argv(dossier, controle_rapide=2))
    assert code == 0
    assert not (dossier / "description.json").is_file()
    sortie = capsys.readouterr().out
    assert "Contrôle rapide" in sortie
