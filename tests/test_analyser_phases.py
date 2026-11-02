"""Tests de ``scripts/analyser_phases.py`` (issue #226) : définition des
phases (cas aux bornes, où le seuil N change la classification), et analyse
sur de petits fichiers de trace fabriqués à la main (pas de campagne longue
rejouée dans ces tests — voir CONTEXTE.md §7, même principe)."""

import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import analyser_phases as AP  # noqa: E402


# --------------------------------------------------------------------------- #
# Définition des phases — cas aux bornes (point 3 de l'issue)
# --------------------------------------------------------------------------- #

def _ligne_tour(chevalet_avant, ouvert_avant, **kwargs):
    base = {"chevalet_avant": chevalet_avant, "ouvert_avant": ouvert_avant}
    base.update(kwargs)
    return base


def test_prologue_quel_que_soit_le_chevalet_si_pas_encore_ouvert():
    # Même avec un petit chevalet, pas encore ouvert => prologue (le seuil
    # de fin de partie ne s'applique qu'APRÈS l'ouverture, §13/#226).
    ligne = _ligne_tour(chevalet_avant=3, ouvert_avant=False)
    assert AP.phase_du_tour(ligne, seuil=5) == "prologue"
    assert AP.phase_du_tour(ligne, seuil=6) == "prologue"


def test_borne_exacte_du_seuil_est_fin():
    ligne = _ligne_tour(chevalet_avant=5, ouvert_avant=True)
    assert AP.phase_du_tour(ligne, seuil=5) == "fin"


def test_juste_au_dessus_du_seuil_est_developpement():
    ligne = _ligne_tour(chevalet_avant=6, ouvert_avant=True)
    assert AP.phase_du_tour(ligne, seuil=5) == "developpement"


def test_le_seuil_change_la_classification_du_meme_tour():
    """Cas central demandé par l'issue : un même tour (chevalet de 6 tuiles,
    déjà ouvert) est classé différemment selon le seuil choisi — c'est ce qui
    permet de changer N à l'analyse sans relancer de campagne."""
    ligne = _ligne_tour(chevalet_avant=6, ouvert_avant=True)
    assert AP.phase_du_tour(ligne, seuil=5) == "developpement"
    assert AP.phase_du_tour(ligne, seuil=6) == "fin"


# --------------------------------------------------------------------------- #
# Analyse sur un petit fichier de trace fabriqué à la main
# --------------------------------------------------------------------------- #

def _tour(donne, ordre, manche, tour, idx, camp, niveau, chevalet_avant,
         ouvert_avant, action, chevalet_apres, ouvert_apres,
         nb_tuiles_posees=0, points_poses=0, taille_pioche_avant=70,
         joker_en_main_avant=False):
    return {
        "donne": donne, "ordre": ordre, "niveau_a": "X", "niveau_b": "Y",
        "type": "tour", "manche": manche, "tour": tour, "camp": camp,
        "niveau": niveau, "index_joueur": idx,
        "chevalet_avant": chevalet_avant, "chevalet_apres": chevalet_apres,
        "ouvert_avant": ouvert_avant, "ouvert_apres": ouvert_apres,
        "action": action, "nb_tuiles_posees": nb_tuiles_posees,
        "points_poses": points_poses,
        "taille_pioche_avant": taille_pioche_avant,
        "joker_en_main_avant": joker_en_main_avant,
    }


def _resultat(donne, ordre, manche, vainqueur_camp, perdant_camp,
             tuiles_restantes_perdant, fin, tours):
    return {
        "donne": donne, "ordre": ordre, "niveau_a": "X", "niveau_b": "Y",
        "type": "resultat", "manche": manche,
        "vainqueur_camp": vainqueur_camp, "vainqueur_niveau": "X",
        "perdant_camp": perdant_camp, "perdant_niveau": "Y",
        "tuiles_restantes_perdant": tuiles_restantes_perdant, "fin": fin,
        "tours": tours,
    }


def _manche_fabriquee():
    """Manche à 2 joueurs (idx 0 = camp A = futur vainqueur, idx 1 = camp B =
    futur perdant), construite à la main — voir le calcul de référence dans
    le rapport de clôture de l'issue #226 pour le détail tour par tour."""
    ordre = ["A", "B"]
    lignes = [
        _tour(1, ordre, 1, 1, 0, "A", "X", 14, False, "pioche", 15, False),
        _tour(1, ordre, 1, 2, 1, "B", "Y", 14, False, "pose", 9, True,
             nb_tuiles_posees=5, points_poses=32),
        _tour(1, ordre, 1, 3, 0, "A", "X", 15, False, "pose", 11, True,
             nb_tuiles_posees=4, points_poses=31),
        _tour(1, ordre, 1, 4, 1, "B", "Y", 9, True, "pioche", 10, True),
        _tour(1, ordre, 1, 5, 0, "A", "X", 11, True, "pose", 5, True,
             nb_tuiles_posees=6, points_poses=40),
        _tour(1, ordre, 1, 6, 1, "B", "Y", 10, True, "pioche", 11, True),
        _tour(1, ordre, 1, 7, 0, "A", "X", 5, True, "pose", 3, True,
             nb_tuiles_posees=2, points_poses=10),
        _tour(1, ordre, 1, 8, 1, "B", "Y", 11, True, "pioche", 12, True),
        _tour(1, ordre, 1, 9, 0, "A", "X", 3, True, "pose", 0, True,
             nb_tuiles_posees=3, points_poses=15),
    ]
    resultat = _resultat(1, ordre, 1, "A", "B", 12, "chevalet_vide", 9)
    return lignes + [resultat]


def test_analyser_manche_fabriquee_seuil_5():
    lignes = _manche_fabriquee()
    resume = AP.analyser(lignes, seuil=5)

    assert resume["nb_manches"] == 1
    assert resume["manches_ignorees"] == 0

    # Gagnant (idx 0, camp A) : prologue = tours 1 et 3 (ouverture au tour 3,
    # chevalet_avant=15 à ce moment, 1 pioche avant) ; développement = tour 5
    # (chevalet_avant=11 > 5) ; fin = tours 7 et 9 (chevalet_avant <= 5).
    assert resume["tour_ouverture"]["gagnant"]["moyenne"] == 3
    assert resume["chevalet_a_ouverture"]["gagnant"]["moyenne"] == 15
    assert resume["pioches_avant_ouverture"]["gagnant"]["moyenne"] == 1
    assert sum(resume["duree_phase"]["gagnant"]["prologue"]) == 2
    assert sum(resume["duree_phase"]["gagnant"]["developpement"]) == 1
    assert sum(resume["duree_phase"]["gagnant"]["fin"]) == 2
    assert sum(resume["tuiles_posees_phase"]["gagnant"]["fin"]) == 5  # 2 + 3

    # Perdant (idx 1, camp B) : ouvre dès son premier tour (tour 2) ; ne
    # descend jamais à <= 5 tuiles avant la fin de la manche => jamais en
    # phase Fin.
    assert resume["tour_ouverture"]["perdant"]["moyenne"] == 2
    assert resume["chevalet_a_ouverture"]["perdant"]["moyenne"] == 14
    assert resume["pioches_avant_ouverture"]["perdant"]["moyenne"] == 0
    assert sum(resume["duree_phase"]["perdant"]["fin"]) == 0
    assert sum(resume["duree_phase"]["perdant"]["developpement"]) == 3

    # (a) Fin du prologue : idx 0 ouvre en second (tour 3), avec 11 tuiles
    # contre 9 pour idx 1 (déjà ouvert) => idx 1 en avance (écart 2) ; le
    # vainqueur final (idx 0) n'était PAS en avance à ce moment.
    fp = resume["cp_fin_prologue"]
    assert fp["n"] == 1
    assert fp["leader_gagne"] == 0
    assert fp["egalites"] == 0
    assert fp["ecarts"] == [2]

    # (b) Entrée en phase Fin : un seul événement (idx 0 au tour 7, avec 5
    # tuiles contre 11 pour idx 1 à ce moment) => idx 0 en avance (écart 6),
    # et idx 0 gagne effectivement la manche.
    ef = resume["cp_entree_fin"]
    assert ef["n"] == 1
    assert ef["leader_gagne"] == 1
    assert ef["egalites"] == 0
    assert ef["ecarts"] == [6]


def _manche_bordure():
    """Manche minimale où le tour décisif (tour 3, chevalet_avant=6, déjà
    ouvert) tombe exactement sur la frontière entre seuil 5 et seuil 6 —
    démontre, à travers ``analyser`` (pas seulement ``phase_du_tour``), que
    changer N à l'analyse change le résultat sans rejouer la moindre
    partie (point 3 de l'issue #226)."""
    ordre = ["A", "B"]
    lignes = [
        _tour(1, ordre, 1, 1, 0, "A", "X", 14, False, "pose", 6, True,
             nb_tuiles_posees=8, points_poses=32),
        _tour(1, ordre, 1, 2, 1, "B", "Y", 14, False, "pose", 6, True,
             nb_tuiles_posees=8, points_poses=32),
        _tour(1, ordre, 1, 3, 0, "A", "X", 6, True, "pose", 0, True,
             nb_tuiles_posees=6, points_poses=20),
    ]
    resultat = _resultat(1, ordre, 1, "A", "B", 6, "chevalet_vide", 3)
    return lignes + [resultat]


def test_le_seuil_change_la_phase_du_tour_decisif_dans_analyser():
    lignes = _manche_bordure()
    resume_5 = AP.analyser(lignes, seuil=5)
    resume_6 = AP.analyser(lignes, seuil=6)
    # seuil 5 : chevalet_avant=6 > 5 => développement.
    assert sum(resume_5["duree_phase"]["gagnant"]["developpement"]) == 1
    assert sum(resume_5["duree_phase"]["gagnant"]["fin"]) == 0
    # seuil 6 : chevalet_avant=6 <= 6 => fin.
    assert sum(resume_6["duree_phase"]["gagnant"]["developpement"]) == 0
    assert sum(resume_6["duree_phase"]["gagnant"]["fin"]) == 1


def test_manche_sans_resultat_est_ignoree():
    lignes = _manche_fabriquee()
    lignes_sans_resultat = [l for l in lignes if l["type"] == "tour"]
    resume = AP.analyser(lignes_sans_resultat, seuil=5)
    assert resume["nb_manches"] == 0
    assert resume["manches_ignorees"] == 1


def test_charger_trace_fichier_fabrique(tmp_path):
    chemin = tmp_path / "trace.jsonl"
    lignes = _manche_fabriquee()
    with open(chemin, "w", encoding="utf-8") as f:
        for l in lignes:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")
    relues = AP.charger_trace(chemin)
    assert relues == lignes


def test_rapport_ne_plante_pas(capsys):
    resume = AP.analyser(_manche_fabriquee(), seuil=5)
    AP.afficher_rapport(resume)
    sortie = capsys.readouterr().out
    assert "ANALYSE PAR PHASES" in sortie


# --------------------------------------------------------------------------- #
# Analyse PAR NIVEAU (issue #228, point 4) — dans ``_manche_fabriquee``, le
# niveau "X" joue toujours l'index 0 (futur gagnant) et "Y" toujours l'index
# 1 (futur perdant) : les résultats par niveau doivent donc reproduire
# exactement les résultats par rôle déjà vérifiés par
# ``test_analyser_manche_fabriquee_seuil_5`` ci-dessus.
# --------------------------------------------------------------------------- #

def test_analyser_par_niveau_reproduit_les_roles_de_la_manche_fabriquee():
    resume = AP.analyser_par_niveau(_manche_fabriquee(), seuil=5)
    assert resume["niveaux"] == ["X", "Y"]

    assert resume["duree_phase"]["X"]["prologue"] == 2
    assert resume["duree_phase"]["X"]["developpement"] == 1
    assert resume["duree_phase"]["X"]["fin"] == 2
    assert resume["tuiles_posees_phase"]["X"]["fin"] == 5  # 2 + 3

    assert resume["duree_phase"]["Y"]["prologue"] == 1
    assert resume["duree_phase"]["Y"]["developpement"] == 3
    assert resume["duree_phase"]["Y"]["fin"] == 0


def test_analyser_par_niveau_sur_trace_vide():
    resume = AP.analyser_par_niveau([], seuil=5)
    assert resume["niveaux"] == []


def test_rapport_par_niveau_ne_plante_pas(capsys):
    resume = AP.analyser_par_niveau(_manche_fabriquee(), seuil=5)
    AP.afficher_rapport_par_niveau(resume)
    sortie = capsys.readouterr().out
    assert "ANALYSE PAR NIVEAU" in sortie
    assert "X" in sortie and "Y" in sortie


# --------------------------------------------------------------------------- #
# Comparaison de deux traces, PAR PHASE (issue #228, point 4)
# --------------------------------------------------------------------------- #

def test_comparer_traces_identiques_delta_nul():
    resume = AP.analyser(_manche_fabriquee(), seuil=5)
    diffs = AP.comparer_traces(resume, resume)
    for role in ("gagnant", "perdant"):
        for ph in AP.PHASES:
            assert diffs[role][ph]["delta_duree"] == 0
            assert diffs[role][ph]["delta_tuiles_par_tour"] == 0
            assert diffs[role][ph]["delta_freq_pioche"] == 0


def test_comparer_traces_detecte_une_difference():
    lignes_1 = _manche_fabriquee()
    lignes_2 = [dict(l) for l in lignes_1]
    # Le gagnant pose une tuile de plus lors de son dernier tour de phase
    # Fin (tour 9) dans la deuxième trace — la différence doit ressortir
    # côté gagnant, phase Fin, jamais ailleurs.
    for l in lignes_2:
        if l.get("type") == "tour" and l.get("tour") == 9:
            l["nb_tuiles_posees"] += 1
    resume_1 = AP.analyser(lignes_1, seuil=5)
    resume_2 = AP.analyser(lignes_2, seuil=5)
    diffs = AP.comparer_traces(resume_1, resume_2)
    assert diffs["gagnant"]["fin"]["delta_tuiles_par_tour"] > 0
    assert diffs["perdant"]["fin"]["delta_tuiles_par_tour"] == 0
    assert diffs["gagnant"]["prologue"]["delta_tuiles_par_tour"] == 0


def test_afficher_comparaison_ne_plante_pas(capsys):
    resume = AP.analyser(_manche_fabriquee(), seuil=5)
    diffs = AP.comparer_traces(resume, resume)
    AP.afficher_comparaison(diffs, "trace1.jsonl", "trace2.jsonl")
    sortie = capsys.readouterr().out
    assert "COMPARAISON PAR PHASE" in sortie
    assert "trace1.jsonl" in sortie and "trace2.jsonl" in sortie


def test_cli_par_niveau_et_comparer(tmp_path, capsys):
    chemin = tmp_path / "trace.jsonl"
    with open(chemin, "w", encoding="utf-8") as f:
        for l in _manche_fabriquee():
            f.write(json.dumps(l, ensure_ascii=False) + "\n")
    code = AP.main(["analyser_phases.py", str(chemin), "--par-niveau",
                    "--comparer", str(chemin)])
    assert code == 0
    sortie = capsys.readouterr().out
    assert "ANALYSE PAR NIVEAU" in sortie
    assert "COMPARAISON PAR PHASE" in sortie
    assert "seuil N = 5" in sortie
