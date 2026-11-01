"""Tests du rapport de ``scripts/comparer_niveaux_ia.py`` affiné par l'issue
#223 : causes de repli d'Expert SÉPARÉES (point 2) et statuts de vérification
de finition plus fins (point 4). Construit des résumés synthétiques (plutôt
que de rejouer une campagne complète) pour isoler l'affichage de la
simulation — la campagne elle-même (chemin de production, #223 point 3) est
couverte par ``tests/test_verification_finition.py``."""

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from rummikub.moteur import verification_finition as vf  # noqa: E402

import comparer_niveaux_ia as M  # noqa: E402


def _resume_minimal(**overrides) -> dict:
    base = {
        "niveau_a": "Avancé", "niveau_b": "Expert", "nb_manches": 1,
        "stats_verif_finition": {}, "victoires": {"A": 0, "B": 0},
        "matchs_nuls": 0, "matchs_decides": 0,
        "cumul_par_camp": {"A": [], "B": []},
        "fins": {"chevalet_vide": 0, "pioche_vide": 0, "garde_fou": 0},
        "penalites_perdant": [], "tuiles_perdant": [], "tours_decidees": [],
        "temps_par_niveau": {"Expert": [0.1] * 10},
        "coups_invalides_total": 0, "coups_tuiles_disparues_total": 0,
        "anomalies_conservation_total": 0,
        "replis_expert": {"budget_depasse": 0, "deps_absentes": 0, "autre": 0},
        "aucun_coup_expert": 0,
        "perturbations_expert": [], "preferer_simple": True,
        "eval_a": "off", "eval_b": "off", "nb_donnes": 1, "nb_parties": 2,
        "sans_exact": False,
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# Point 2 : causes de repli séparées + avertissement si deps absentes
# --------------------------------------------------------------------------- #

def test_rapport_separe_les_trois_causes_de_repli(capsys):
    resume = _resume_minimal(replis_expert={
        "budget_depasse": 3, "deps_absentes": 0, "autre": 0})
    M.afficher_rapport(resume)
    sortie = capsys.readouterr().out
    assert "budget de temps réellement dépassé" in sortie
    assert "solveur exact indisponible (dépendances absentes)" in sortie
    assert "coup légitimement impossible" not in sortie


def test_rapport_avertit_si_deps_absentes_pendant_la_campagne(capsys):
    resume = _resume_minimal(replis_expert={
        "budget_depasse": 0, "deps_absentes": 4, "autre": 0})
    M.afficher_rapport(resume)
    sortie = capsys.readouterr().out
    assert "ATTENTION" in sortie
    assert "4/10" in sortie


def test_rapport_sans_deps_absentes_pas_d_avertissement(capsys):
    resume = _resume_minimal(replis_expert={
        "budget_depasse": 0, "deps_absentes": 0, "autre": 0})
    M.afficher_rapport(resume)
    sortie = capsys.readouterr().out
    assert "ATTENTION" not in sortie


def test_rapport_affiche_aucun_coup_possible_separement(capsys):
    resume = _resume_minimal(aucun_coup_expert=7)
    M.afficher_rapport(resume)
    sortie = capsys.readouterr().out
    assert "Aucun coup possible (cas légitime" in sortie
    assert "7/10" in sortie


def test_rapport_entete_dependances():
    resume = _resume_minimal()
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        M.afficher_rapport(resume)
    sortie = buf.getvalue()
    assert sys.executable in sortie


# --------------------------------------------------------------------------- #
# Point 4 : les sept statuts de finition, affichés séparément
# --------------------------------------------------------------------------- #

def test_rapport_affiche_les_sept_statuts_separement(capsys):
    stats = {code: i + 1 for i, code in enumerate((
        vf.NON_APPLICABLE, vf.PAS_DE_COUP_A_COMPARER, vf.SOLVEUR_NON_EXACT,
        vf.BUDGET_EPUISE, vf.APPLIQUEE_MEILLEUR_SUFFIT,
        vf.APPLIQUEE_AUCUN_CANDIDAT, vf.APPLIQUEE_AUTRE_COUP))}
    resume = _resume_minimal(stats_verif_finition=stats)
    M.afficher_rapport(resume)
    sortie = capsys.readouterr().out
    for code in stats:
        assert vf.LIBELLES[code] in sortie
    # Les deux statuts auparavant confondus sous un même libellé (#223,
    # point 3 du contexte) doivent apparaître comme deux lignes DISTINCTES.
    assert vf.LIBELLES[vf.APPLIQUEE_MEILLEUR_SUFFIT] != \
        vf.LIBELLES[vf.APPLIQUEE_AUCUN_CANDIDAT]


def test_frequence_activation_exclut_les_statuts_non_executes():
    """La fréquence d'activation ne doit porter que sur les tours où la
    vérification a RÉELLEMENT tourné (pas sur les replis amont)."""
    stats = {
        vf.NON_APPLICABLE: 100,          # jamais consulté le solveur
        vf.PAS_DE_COUP_A_COMPARER: 50,   # idem
        vf.SOLVEUR_NON_EXACT: 20,        # idem
        vf.APPLIQUEE_AUTRE_COUP: 3,
        vf.APPLIQUEE_AUCUN_CANDIDAT: 7,
    }
    resume = _resume_minimal(stats_verif_finition=stats)
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        M.afficher_rapport(resume)
    sortie = buf.getvalue()
    # tentés = 3 + 7 = 10 (exclut les 170 replis amont) ; changés = 3.
    assert "3/10" in sortie
