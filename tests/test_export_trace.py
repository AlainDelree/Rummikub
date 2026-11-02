"""Tests de la trace brute par tour de ``scripts/comparer_niveaux_ia.py``
(``--export-trace``, issue #226) : mesure PURE qui ne doit jamais changer le
déroulement d'une partie, désactivée par défaut.

Une partie courte (Débutant contre Débutant, rapide) est jouée via
``comparer_niveaux_ia.comparer`` pour vérifier que les lignes écrites sont
cohérentes avec l'état réel du moteur (ne rejoue jamais une campagne
longue — voir CONTEXTE.md §7, même principe appliqué ici)."""

import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import comparer_niveaux_ia as M  # noqa: E402

ACTIONS_VALIDES = {"pose", "pioche", "passe"}


def _lire_jsonl(chemin):
    with open(chemin, encoding="utf-8") as f:
        return [json.loads(ligne) for ligne in f if ligne.strip()]


def test_sans_export_trace_aucun_fichier_ni_changement(tmp_path):
    """Option désactivée par défaut : ``comparer`` fonctionne à l'identique
    sans jamais créer de fichier quand ``export_trace`` n'est pas fourni."""
    resume = M.comparer("Débutant", "Débutant", nb_donnes=1, seed=1,
                        max_tours=300)
    assert resume["nb_donnes"] == 1
    assert not list(tmp_path.iterdir())


def test_trace_une_partie_courte_lignes_coherentes_et_resultat(tmp_path):
    chemin = tmp_path / "trace.jsonl"
    resume = M.comparer("Débutant", "Débutant", nb_donnes=1, seed=1,
                        max_tours=300, export_trace=str(chemin))
    lignes = _lire_jsonl(chemin)
    assert lignes, "la trace ne doit pas être vide"

    tours = [l for l in lignes if l["type"] == "tour"]
    resultats = [l for l in lignes if l["type"] == "resultat"]
    assert tours, "au moins un tour doit être tracé"
    # 1 donne x 2 (miroir) = 2 matchs d'une manche chacun : une ligne de
    # résultat par manche effectivement terminée (cf. #203 pour la notion de
    # manche). Ici aucun garde-fou n'est attendu (parties courtes, Débutant).
    assert len(resultats) == 2

    for l in tours:
        assert l["action"] in ACTIONS_VALIDES
        assert isinstance(l["ouvert_avant"], bool)
        assert isinstance(l["ouvert_apres"], bool)
        assert l["chevalet_avant"] >= 0
        assert l["chevalet_apres"] >= 0
        assert l["nb_tuiles_posees"] >= 0
        assert l["points_poses"] >= 0
        assert l["taille_pioche_avant"] >= 0
        assert isinstance(l["joker_en_main_avant"], bool)
        if l["action"] == "pose":
            assert l["nb_tuiles_posees"] > 0
            assert l["chevalet_apres"] == l["chevalet_avant"] - l["nb_tuiles_posees"]
        else:
            assert l["nb_tuiles_posees"] == 0
            assert l["points_poses"] == 0
        if l["action"] == "passe":
            assert l["chevalet_apres"] == l["chevalet_avant"]
        if l["action"] == "pioche":
            assert l["chevalet_apres"] >= l["chevalet_avant"]
        # Une fois ouvert, un joueur reste ouvert (pas de retour en arrière).
        if l["ouvert_avant"]:
            assert l["ouvert_apres"]

    # Monotonie de l'ouverture par joueur, à travers tous ses tours triés.
    for cle, groupe in _grouper_par_manche_et_joueur(tours):
        groupe.sort(key=lambda l: l["tour"])
        deja_ouvert = False
        for l in groupe:
            if deja_ouvert:
                assert l["ouvert_avant"] is True
            deja_ouvert = deja_ouvert or l["ouvert_apres"]

    for r in resultats:
        assert r["vainqueur_niveau"] == "Débutant"
        assert r["perdant_niveau"] == "Débutant"
        assert r["vainqueur_camp"] in r["ordre"]
        assert r["perdant_camp"] in r["ordre"]
        assert r["vainqueur_camp"] != r["perdant_camp"]
        assert r["tuiles_restantes_perdant"] >= 0
        assert r["fin"] in ("chevalet_vide", "pioche_vide")
        assert r["tours"] > 0


def _grouper_par_manche_et_joueur(tours):
    groupes = {}
    for l in tours:
        cle = (l["donne"], tuple(l["ordre"]), l["manche"], l["index_joueur"])
        groupes.setdefault(cle, []).append(l)
    return groupes.items()


def test_export_trace_independant_de_export_resultats(tmp_path):
    """Les deux exports peuvent être utilisés ensemble ou séparément, sans
    interférer (issue #226, point 1 : indépendance explicitement demandée)."""
    chemin_trace = tmp_path / "trace.jsonl"
    chemin_resultats = tmp_path / "resultats.jsonl"
    M.comparer("Débutant", "Débutant", nb_donnes=1, seed=2, max_tours=300,
              export_trace=str(chemin_trace),
              export_resultats=str(chemin_resultats))
    assert chemin_trace.exists()
    assert chemin_resultats.exists()
    lignes_resultats = _lire_jsonl(chemin_resultats)
    assert len(lignes_resultats) == 2  # un par match (miroir), cf. #225.
