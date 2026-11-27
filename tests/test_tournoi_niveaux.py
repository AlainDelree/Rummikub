"""Tests rapides de ``scripts/tournoi_niveaux.py`` (issue #276) : rotation
des sièges, classement sur égalité, agrégation des statistiques sur un jeu
de données fabriqué à la main, reprise après interruption, noms de niveaux
sans accent, et un essai de bout en bout très court.

Jamais de vrai niveau LENT en boucle : les niveaux réels utilisés ici
(Débutant/Facile) ont leur réglage remplacé par celui, RAPIDE, de la
fixture ``niveau_debutant_rapide``/``BRIDAGE_DEBUTANT_RAPIDE`` de
``tests/conftest.py`` (perturbation 0 → jamais de recours au solveur
exact), restauré automatiquement par le filet de sécurité autouse
``_bridages_restaures``. Les propriétés GÉNÉRALES (rotation, classement,
agrégation, reprise) sont testées sur des données fabriquées à la main,
sans dépendre des réglages calibrés d'un niveau."""

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import tournoi_niveaux as M  # noqa: E402
from rummikub.moteur import niveaux as _niveaux  # noqa: E402

_MAX_TOURS_RAPIDE = 300
_RAPIDE = _niveaux.Bridage(perturbation_max=0, taux_oubli=0.0,
                          eviter_don_joker=False)


def _rendre_rapide(monkeypatch, *niveaux):
    for niveau in niveaux:
        monkeypatch.setitem(_niveaux.BRIDAGES, niveau, _RAPIDE)


# --------------------------------------------------------------------------- #
# Noms de niveaux : accent-insensibles, nom inconnu refusé
# --------------------------------------------------------------------------- #

def test_resoudre_niveau_sans_accent():
    assert M.resoudre_niveau("Avance") == "Avancé"
    assert M.resoudre_niveau("INTERMEDIAIRE") == "Intermédiaire"
    assert M.resoudre_niveau("  Expert ") == "Expert"


def test_resoudre_niveau_inconnu_liste_les_noms_valides():
    try:
        M.resoudre_niveau("Inconnu")
        assert False, "devait lever ValueError"
    except ValueError as exc:
        for niveau in M.NIVEAUX_DEFAUT:
            assert niveau in str(exc)


def test_parser_niveaux_accepte_les_noms_sans_accent():
    assert M.parser_niveaux("Expert,Avance,Intermediaire,Facile") == [
        "Expert", "Avancé", "Intermédiaire", "Facile"]


def test_parser_niveaux_refuse_moins_de_deux():
    try:
        M.parser_niveaux("Expert")
        assert False, "devait lever ValueError"
    except ValueError:
        pass


def test_parser_niveaux_refuse_plus_de_quatre():
    try:
        M.parser_niveaux("Expert,Avance,Intermediaire,Facile,Debutant")
        assert False, "devait lever ValueError"
    except ValueError:
        pass


def test_parser_niveaux_refuse_un_doublon():
    try:
        M.parser_niveaux("Expert,Expert")
        assert False, "devait lever ValueError"
    except ValueError:
        pass


# --------------------------------------------------------------------------- #
# Rotation des sièges (issue #276, point 3)
# --------------------------------------------------------------------------- #

def test_rotation_couvre_les_quatre_sieges():
    niveaux = ["Expert", "Avancé", "Intermédiaire", "Facile"]
    vus_par_siege = [set() for _ in range(4)]
    for r in range(4):
        rot = M.rotation(niveaux, r)
        assert len(rot) == 4
        for siege, niveau in enumerate(rot):
            vus_par_siege[siege].add(niveau)
    # Chaque siège a vu chacun des quatre niveaux exactement une fois.
    assert all(vu == set(niveaux) for vu in vus_par_siege)
    # Chaque rotation est bien une permutation complète (aucun niveau
    # dédoublé ni oublié dans une même rotation).
    for r in range(4):
        assert sorted(M.rotation(niveaux, r)) == sorted(niveaux)


def test_rotation_deux_niveaux():
    niveaux = ["Débutant", "Facile"]
    assert M.rotation(niveaux, 0) == ["Débutant", "Facile"]
    assert M.rotation(niveaux, 1) == ["Facile", "Débutant"]


# --------------------------------------------------------------------------- #
# Classement : correct et STABLE en cas de scores égaux (issue #276, point 4)
# --------------------------------------------------------------------------- #

def test_places_depuis_scores_sans_egalite():
    assert M.places_depuis_scores([10, 5, 2, -3]) == [1.0, 2.0, 3.0, 4.0]


def test_places_depuis_scores_egalite_partagee():
    # 2e et 3e places à égalité (score 5) : place moyenne 2.5 partagée.
    assert M.places_depuis_scores([10, 5, 5, 2]) == [1.0, 2.5, 2.5, 4.0]


def test_places_depuis_scores_egalite_totale():
    assert M.places_depuis_scores([3, 3, 3, 3]) == [2.5, 2.5, 2.5, 2.5]


def test_places_depuis_scores_est_stable():
    scores = [8, 8, 1, -1]
    assert M.places_depuis_scores(scores) == M.places_depuis_scores(scores)


# --------------------------------------------------------------------------- #
# Agrégation des statistiques sur un jeu de données fabriqué à la main
# --------------------------------------------------------------------------- #

def _enregistrement(donne, rotation_, niveaux_par_siege, scores, fin="chevalet_vide"):
    return {
        "donne": donne, "rotation": rotation_,
        "niveaux_par_siege": niveaux_par_siege,
        "scores_par_siege": scores, "tours": 10, "fin": fin,
        "decidee": fin != "limite_tours",
        "anomalies": [], "temps_par_niveau": {},
    }


def _jeu_fabrique():
    # 2 donnes, 2 rotations chacune (X/Y). Donne 1 : X gagne nettement aux
    # deux sièges. Donne 2 : égalité stricte des scores aux deux rotations.
    return [
        _enregistrement(1, 0, ["X", "Y"], [10, -10]),
        _enregistrement(1, 1, ["Y", "X"], [-10, 10]),
        _enregistrement(2, 0, ["X", "Y"], [5, 5], fin="manche_bloquee"),
        _enregistrement(2, 1, ["Y", "X"], [5, 5], fin="manche_bloquee"),
    ]


def test_stats_par_niveau_sur_jeu_fabrique():
    stats = M.stats_par_niveau(_jeu_fabrique(), ["X", "Y"])

    assert stats["X"]["manches_jouees"] == 4
    assert stats["X"]["victoires"] == 4  # gagne net 2x, et à égalité 2x
    assert stats["X"]["taux_victoire"] == 1.0
    assert stats["X"]["place_moyenne"] == 1.25  # (1+1+1.5+1.5)/4
    assert stats["X"]["score_moyen"] == 7.5  # (10+10+5+5)/4

    assert stats["Y"]["manches_jouees"] == 4
    assert stats["Y"]["victoires"] == 2  # seulement les 2 égalités
    assert stats["Y"]["taux_victoire"] == 0.5
    assert stats["Y"]["place_moyenne"] == 1.75  # (2+2+1.5+1.5)/4
    assert stats["Y"]["score_moyen"] == -2.5  # (-10-10+5+5)/4


def test_matrice_qui_bat_qui_sur_jeu_fabrique():
    matrice = M.matrice_qui_bat_qui(_jeu_fabrique(), ["X", "Y"])
    taux_xy, n_xy = matrice[("X", "Y")]
    taux_yx, n_yx = matrice[("Y", "X")]
    assert n_xy == n_yx == 4
    assert taux_xy == 0.75  # 2 victoires nettes + 2 x 0.5 (égalités)
    assert taux_yx == 0.25
    assert taux_xy + taux_yx == 1.0


def test_victoires_par_siege_sur_jeu_fabrique():
    comptes, n = M.victoires_par_siege(_jeu_fabrique(), 2)
    assert n == 4
    # Données fabriquées symétriques : aucun biais de siège.
    assert comptes == [3, 3]


def test_repartition_fins_sur_jeu_fabrique():
    fins = M.repartition_fins(_jeu_fabrique())
    assert fins == {"chevalet_vide": 2, "manche_bloquee": 2, "limite_tours": 0}


# --------------------------------------------------------------------------- #
# Intervalle de Wilson : bornes toujours dans [0, 1], symétrie à 50 %
# --------------------------------------------------------------------------- #

def test_intervalle_wilson_aucune_manche():
    assert M.intervalle_wilson(0, 0) == (0.0, 0.0, 0.0)


def test_intervalle_wilson_bornes_dans_0_1():
    for victoires, total in [(0, 10), (10, 10), (5, 10), (1, 3)]:
        taux, basse, haute = M.intervalle_wilson(victoires, total)
        assert 0.0 <= basse <= taux <= haute <= 1.0


def test_intervalle_wilson_symetrique_a_moitie():
    taux, basse, haute = M.intervalle_wilson(5, 10)
    assert taux == 0.5
    assert abs((basse + haute) / 2 - 0.5) < 1e-9


# --------------------------------------------------------------------------- #
# Reprise après interruption : pas de rejoue, pas de doublon
# --------------------------------------------------------------------------- #

def test_purger_donnes_incompletes_tronque_une_donne_en_plein_milieu(tmp_path):
    dossier = tmp_path / "tournoi"
    dossier.mkdir()
    chemin = M.fichier_resultats(dossier, 0)
    enregs = [
        _enregistrement(1, 0, ["X", "Y"], [10, -10]),
        _enregistrement(1, 1, ["Y", "X"], [-10, 10]),
        _enregistrement(2, 0, ["X", "Y"], [5, 5]),  # donne 2 INCOMPLÈTE
        # (rotation 1 de la donne 2 manque : coupure brutale simulée)
    ]
    M._ecrire_jsonl_atomique(chemin, enregs)

    completes = M._purger_donnes_incompletes(chemin, n_rotations=2)
    assert completes == {1}
    lignes = chemin.read_text(encoding="utf-8").strip().splitlines()
    assert len(lignes) == 2  # la donne 2 incomplète a été retirée


def test_reprise_ne_rejoue_pas_les_donnes_completes(tmp_path, monkeypatch):
    _rendre_rapide(monkeypatch, "Débutant", "Facile")
    dossier = tmp_path / "tournoi"
    dossier.mkdir()
    niveaux = ["Débutant", "Facile"]

    interrompu1 = M.jouer_pour_worker(
        0, dossier, niveaux, donnes_visees=1, nb_processus=1, seed=0,
        max_tours=_MAX_TOURS_RAPIDE, budget_temps=None, deadline=None)
    assert interrompu1 is False
    chemin = M.fichier_resultats(dossier, 0)
    lignes_1 = chemin.read_text(encoding="utf-8").strip().splitlines()
    assert len(lignes_1) == 2  # 1 donne x 2 rotations

    # Relance sur le même dossier avec davantage de donnes : prolonge la
    # campagne sans rejouer la donne déjà complète (simule une reprise
    # après interruption).
    interrompu2 = M.jouer_pour_worker(
        0, dossier, niveaux, donnes_visees=2, nb_processus=1, seed=0,
        max_tours=_MAX_TOURS_RAPIDE, budget_temps=None, deadline=None)
    assert interrompu2 is False
    lignes_2 = chemin.read_text(encoding="utf-8").strip().splitlines()
    assert len(lignes_2) == 4
    assert lignes_2[0] == lignes_1[0]
    assert lignes_2[1] == lignes_1[1]


def test_reprise_ne_cree_pas_de_doublon_apres_troncature(tmp_path, monkeypatch):
    _rendre_rapide(monkeypatch, "Débutant", "Facile")
    dossier = tmp_path / "tournoi"
    dossier.mkdir()
    niveaux = ["Débutant", "Facile"]
    chemin = M.fichier_resultats(dossier, 0)
    # Donne 1 incomplète (coupure brutale) : une seule des deux rotations.
    M._ecrire_jsonl_atomique(chemin, [_enregistrement(1, 0, niveaux, [1, -1])])

    interrompu = M.jouer_pour_worker(
        0, dossier, niveaux, donnes_visees=1, nb_processus=1, seed=0,
        max_tours=_MAX_TOURS_RAPIDE, budget_temps=None, deadline=None)
    assert interrompu is False
    enregs = M._lire_enregistrements(chemin)
    # Exactement 1 donne complète (2 rotations), jamais 3 (pas de doublon
    # de la ligne de rotation 0 déjà écrite avant la coupure simulée).
    assert len(enregs) == 2
    assert sorted(r["rotation"] for r in enregs) == [0, 1]


# --------------------------------------------------------------------------- #
# Essai de bout en bout très court (1 donne, limite de tours minuscule)
# --------------------------------------------------------------------------- #

def test_essai_bout_en_bout_tres_court(tmp_path, monkeypatch):
    _rendre_rapide(monkeypatch, "Débutant", "Facile")
    dossier = tmp_path / "tournoi"
    code = M.main([
        "tournoi_niveaux.py", "--dossier", str(dossier),
        "--niveaux", "Debutant,Facile", "--donnes", "1",
        "--max-tours", "5", "--_worker",
    ])
    assert code == M.CODE_TERMINE
    assert (dossier / "rapport.txt").is_file()
    enregs = M._lire_enregistrements(M.fichier_resultats(dossier, 0))
    assert len(enregs) == 2  # 1 donne x 2 rotations
    assert {r["rotation"] for r in enregs} == {0, 1}


def test_statut_sans_campagne_echoue_proprement(tmp_path):
    assert M.commande_statut(tmp_path / "inexistant") == 1


def test_refuse_de_melanger_deux_campagnes_differentes(tmp_path, capsys, monkeypatch):
    _rendre_rapide(monkeypatch, "Débutant", "Facile")
    dossier = tmp_path / "tournoi"
    code1 = M.main([
        "tournoi_niveaux.py", "--dossier", str(dossier),
        "--niveaux", "Debutant,Facile", "--donnes", "1",
        "--max-tours", str(_MAX_TOURS_RAPIDE), "--seed", "0", "--_worker",
    ])
    assert code1 == M.CODE_TERMINE

    code2 = M.main([
        "tournoi_niveaux.py", "--dossier", str(dossier),
        "--niveaux", "Debutant,Facile", "--donnes", "1",
        "--max-tours", str(_MAX_TOURS_RAPIDE), "--seed", "1", "--_worker",
    ])
    assert code2 == 1
    erreur = capsys.readouterr().err
    assert "réglages DIFFÉRENTS" in erreur
