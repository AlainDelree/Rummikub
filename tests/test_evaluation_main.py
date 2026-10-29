"""Tests de l'évaluation de la main restante d'Expert (issue #211,
``moteur/evaluation_main.py`` + son intégration au modèle exact).

Trois familles (point 6 de l'issue) :

* **Évaluation sur mains fabriquées** : doublons, tuiles de bord (1/13 vs 2/12
  vs milieu), tuiles isolées, joker, et poids des points selon le nombre de
  manches — ces tests tournent TOUJOURS (pur Python, sans dépendance).
* **Propriété « l'évaluation ne change JAMAIS le nombre de tuiles posées »**
  sur des positions fabriquées et sur les cas de référence — sautés si
  ``highspy``/``numpy`` sont absents (comme ``test_solveur_exact_maison.py``).
* **Départage effectif** : sur une position fabriquée, l'évaluation choisit,
  à nombre de tuiles égal, le coup qui laisse la meilleure main (exemple
  d'Alice, CONTEXTE.md §13).
"""

import json
from pathlib import Path

import pytest

from rummikub.moteur import evaluation_main as em
from rummikub.moteur import solveur_exact as se
from rummikub.moteur.solveur_exact import resoudre_exact
from rummikub.moteur.tuiles import Tuile

_DONNEES = Path(__file__).resolve().parent / "donnees"

besoin_exact = pytest.mark.skipif(
    not se.DISPONIBLE,
    reason="highspy/numpy absents (dépendances du modèle exact d'Expert)")


def _t(valeur, couleur, suffixe=""):
    return Tuile(f"{couleur}{valeur}{suffixe}", valeur, couleur)


def _joker(suffixe=""):
    return Tuile(f"J{suffixe}", None, "noir", est_joker=True)


# --------------------------------------------------------------------------- #
# Primitives de bord
# --------------------------------------------------------------------------- #

def test_nb_suites_trois():
    # 1 et 13 : une seule suite de trois ; 2 et 12 : deux ; milieu : trois.
    assert em.nb_suites_trois(1) == 1
    assert em.nb_suites_trois(13) == 1
    assert em.nb_suites_trois(2) == 2
    assert em.nb_suites_trois(12) == 2
    for v in range(3, 12):
        assert em.nb_suites_trois(v) == 3


def test_penalite_bord_graduee():
    # Les bords 1/13 pénalisés plus que 2/12, eux-mêmes plus que le milieu.
    assert em.penalite_bord(1) == em.penalite_bord(13) == 2
    assert em.penalite_bord(2) == em.penalite_bord(12) == 1
    assert em.penalite_bord(7) == 0
    assert em.penalite_bord(1) > em.penalite_bord(2) > em.penalite_bord(7)


# --------------------------------------------------------------------------- #
# Évaluation sur mains fabriquées
# --------------------------------------------------------------------------- #

def test_doublons_comptes():
    # Une paire identique = 1 doublon ; deux paires = 2.
    assert em.nb_doublons([_t(5, "rouge", "a"), _t(5, "rouge", "b")]) == 1
    assert em.nb_doublons([_t(5, "rouge", "a"), _t(5, "bleu", "b")]) == 0
    main = [_t(5, "rouge", "a"), _t(5, "rouge", "b"),
            _t(9, "bleu", "a"), _t(9, "bleu", "b")]
    assert em.nb_doublons(main) == 2


def test_doublon_penalise():
    cfg = em.ConfigEvaluation(active=True, doublons=True, bords=False,
                              points=False)
    avec = [_t(5, "rouge", "a"), _t(5, "rouge", "b")]
    sans = [_t(5, "rouge", "a"), _t(6, "bleu", "b")]
    assert em.evaluer_main(avec, cfg) > em.evaluer_main(sans, cfg)
    assert em.evaluer_main(avec, cfg) == cfg.poids_doublon


def test_bord_penalise_plus_que_milieu():
    cfg = em.ConfigEvaluation(active=True, doublons=False, bords=True,
                              points=False)
    bord = [_t(1, "rouge"), _t(13, "bleu")]
    milieu = [_t(7, "rouge"), _t(8, "bleu")]
    assert em.evaluer_main(bord, cfg) > em.evaluer_main(milieu, cfg)
    assert em.evaluer_main(milieu, cfg) == 0


def test_tuiles_isolees():
    # 1 rouge isolé (pas de 2 rouge ni d'autre 1) ; les 7 et 8 rouge voisins.
    main = [_t(1, "rouge"), _t(7, "rouge"), _t(8, "rouge")]
    isolees = em.tuiles_isolees(main)
    assert [t.valeur for t in isolees] == [1]
    # Un doublon n'est jamais isolé (même valeur présente deux fois).
    paire = [_t(1, "rouge", "a"), _t(1, "rouge", "b")]
    assert em.tuiles_isolees(paire) == []
    # Même valeur, autre couleur → non isolé.
    groupe = [_t(1, "rouge"), _t(1, "bleu")]
    assert em.tuiles_isolees(groupe) == []
    # Le joker n'est jamais isolé.
    assert em.tuiles_isolees([_joker()]) == []


def test_poids_points_selon_manches():
    # Poids des points quasi nul en 1 manche, non nul à partir de 2.
    main = [_t(13, "rouge"), _t(12, "bleu")]
    cfg1 = em.depuis_preset("complet", nb_manches=1)
    cfg3 = em.depuis_preset("complet", nb_manches=3)
    assert cfg1.poids_points_effectif() == em.POIDS_POINTS_1_MANCHE
    assert cfg3.poids_points_effectif() == em.POIDS_POINTS_N_MANCHES
    assert em.POIDS_POINTS_N_MANCHES > em.POIDS_POINTS_1_MANCHE
    # À critères bords/doublons identiques, la main vaut plus cher en 3 manches
    # (les points comptent), pas en 1 manche.
    assert em.evaluer_main(main, cfg3) > em.evaluer_main(main, cfg1)


def test_poids_points_force_par_preset():
    main = [_t(10, "rouge")]
    for nom, attendu in (("points-nul", 0), ("points-faible", 1),
                         ("points-moyen", 3), ("points-fort", 8)):
        cfg = em.depuis_preset(nom)
        assert cfg.poids_points_effectif() == attendu
        assert em.evaluer_main(main, cfg) == attendu * 10


def test_joker_non_penalise_par_defaut():
    cfg = em.depuis_preset("complet")
    assert em.evaluer_main([_joker()], cfg) == 0


def test_preset_inconnu_leve():
    with pytest.raises(ValueError):
        em.depuis_preset("n-existe-pas")


def test_preset_position():
    assert em.depuis_preset("complet").position == "apres_simplicite"
    assert em.depuis_preset("complet-avant").avant_simplicite is True
    assert em.depuis_preset("complet-apres").avant_simplicite is False


def test_defaut_desactive():
    # Réglage d'Expert par défaut : évaluation désactivée (point 4 de l'issue —
    # n'activer que ce dont le gain est démontré). Garde-fou contre une
    # activation par inadvertance.
    assert em.DEFAUT.active is False


# --------------------------------------------------------------------------- #
# Intégration au modèle exact
# --------------------------------------------------------------------------- #

def _etat(chevalet, plateau=None, nb_manches=1, mise_faite=True):
    return {
        "joueurs": [{
            "chevalet": [t.as_dict() for t in chevalet],
            "mise_initiale_faite": mise_faite,
        }],
        "plateau": [[t.as_dict() for t in combo] for combo in (plateau or [])],
        "config": {"nb_manches": nb_manches, "mise_initiale_min": 30},
    }


@besoin_exact
def test_eval_ne_change_pas_nb_tuiles_positions_fabriquees():
    """Propriété centrale (#211, point 2) : quelle que soit la configuration
    d'évaluation, le nombre de tuiles posées reste celui du modèle de base."""
    positions = [
        # Exemple d'Alice : 1-2-3 rouge OU groupe de 3 → 3 tuiles dans les deux.
        [_t(1, "rouge"), _t(2, "rouge", "a"), _t(2, "rouge", "b"),
         _t(3, "rouge"), _t(3, "bleu"), _t(3, "noir")],
        # Main riche : plusieurs combinaisons possibles.
        [_t(4, "rouge"), _t(5, "rouge"), _t(6, "rouge"), _t(7, "rouge"),
         _t(10, "bleu"), _t(10, "rouge"), _t(10, "noir"), _t(1, "jaune"),
         _t(13, "jaune")],
        # Main pauvre (rien de posable).
        [_t(1, "rouge"), _t(5, "bleu"), _t(9, "noir")],
    ]
    presets = ["off", "complet", "doublons", "bords", "points-faible",
               "points-fort", "complet-avant"]
    for chevalet in positions:
        for nb_manches in (1, 3):
            etat = _etat(chevalet, nb_manches=nb_manches)
            base = resoudre_exact(etat, 0, budget_temps=5.0,
                                  eval_config=em.depuis_preset("off")).nb_tuiles
            for p in presets:
                cfg = em.depuis_preset(p, nb_manches)
                r = resoudre_exact(etat, 0, budget_temps=5.0, eval_config=cfg)
                assert r.nb_tuiles == base, (p, nb_manches, chevalet)
                assert r.valide_globalement


@besoin_exact
def test_eval_ne_change_pas_nb_tuiles_cas_reference():
    """Les cas de référence (``cas_expert_*.json``) conservent le nombre de
    tuiles obtenu, quelle que soit l'évaluation (point 5 de l'issue)."""
    for chemin in sorted(_DONNEES.glob("cas_expert_*.json")):
        data = json.loads(chemin.read_text(encoding="utf-8"))
        etat = data.get("etat", data)
        idx = etat.get("index_joueur_actuel", 0)
        base = resoudre_exact(etat, idx, budget_temps=5.0,
                              eval_config=em.depuis_preset("off")).nb_tuiles
        for p in ("complet", "doublons", "bords", "points-fort", "complet-avant"):
            cfg = em.depuis_preset(p, etat.get("config", {}).get("nb_manches", 1))
            r = resoudre_exact(etat, idx, budget_temps=5.0, eval_config=cfg)
            assert r.nb_tuiles == base, (chemin.name, p)


@besoin_exact
def test_eval_depart_departage_exemple_alice():
    """Exemple d'Alice (CONTEXTE.md §13, piste 2) : main
    ``1r 2r 2r 3r 3b 3n``. Sans évaluation, Expert peut poser le groupe
    ``3r 3b 3n`` (laisse le doublon ``2r``) ; avec évaluation, il préfère la
    suite ``1-2-3 rouge`` qui fait partir un ``2r`` (doublon) ET le ``1`` (bord).
    Les deux posent 3 tuiles."""
    chevalet = [_t(1, "rouge"), _t(2, "rouge", "a"), _t(2, "rouge", "b"),
                _t(3, "rouge"), _t(3, "bleu"), _t(3, "noir")]
    etat = _etat(chevalet)
    r_off = resoudre_exact(etat, 0, budget_temps=5.0,
                           eval_config=em.depuis_preset("off"))
    r_eval = resoudre_exact(etat, 0, budget_temps=5.0,
                            eval_config=em.depuis_preset("complet"))
    assert r_off.nb_tuiles == r_eval.nb_tuiles == 3

    def main_restante(res):
        poses = set(res.ids_tuiles)
        return em.evaluer_main(
            [t for t in chevalet if t.id not in poses],
            em.depuis_preset("complet"))

    # L'évaluation laisse une main au moins aussi bonne (pénalité ≤) que le
    # coup de base, et strictement meilleure sur cet exemple.
    assert main_restante(r_eval) <= main_restante(r_off)
    # La suite 1-2-3 rouge a bien été posée : le 1 rouge est parti.
    assert any(t.valeur == 1 and t.couleur == "rouge"
               for combo in r_eval.combinaisons for t in combo)


# --------------------------------------------------------------------------- #
# Journal : mécanisme décideur d'Expert (#211, point 5bis)
# --------------------------------------------------------------------------- #

@besoin_exact
def test_expert_marque_solveur_exact():
    """Un coup décidé par le modèle exact est annoté ``solveur="exact"``."""
    from rummikub.moteur.ia import jouer_niveau_expert, SOLVEUR_EXACT
    chevalet = [_t(1, "rouge"), _t(2, "rouge"), _t(3, "rouge")]
    etat = _etat(chevalet, mise_faite=True)
    etat["joueurs"][0]["niveau"] = "Expert"
    coup = jouer_niveau_expert(etat, 0, budget_temps=5.0)
    assert coup["action"] == "jouer"
    assert coup["solveur"] == SOLVEUR_EXACT


def test_expert_marque_recherche_sans_exact():
    """Mode « sans modèle exact » : le coup vient de la recherche de repli et
    est annoté ``solveur="recherche"`` (ce test tourne même sans highspy)."""
    from rummikub.moteur.ia import jouer_niveau_expert, SOLVEUR_RECHERCHE
    chevalet = [_t(1, "rouge"), _t(2, "rouge"), _t(3, "rouge")]
    etat = _etat(chevalet, mise_faite=True)
    etat["joueurs"][0]["niveau"] = "Expert"
    coup = jouer_niveau_expert(etat, 0, budget_temps=5.0, utiliser_exact=False)
    assert coup["action"] == "jouer"
    assert coup["solveur"] == SOLVEUR_RECHERCHE


def test_journal_enregistre_solveur(tmp_path, monkeypatch):
    """``logger_action(solveur=...)`` écrit la clé ``solveur`` ; elle est omise
    quand ``solveur`` vaut ``None`` (rétrocompatible)."""
    from rummikub import config
    from rummikub.persistance import journal

    monkeypatch.setattr(config, "LOG_PARTIES", True, raising=False)
    monkeypatch.setattr(journal, "_dossier_logs", lambda: tmp_path)
    journal._journaux.clear()

    etat = {"id": "test211", "tour_numero": 1, "manche_numero": 1,
            "index_joueur_actuel": 1,
            "joueurs": [{"nom": "A", "chevalet": []},
                        {"nom": "B", "chevalet": []}],
            "plateau": [], "pioche": []}
    journal.logger_action(etat, "pose", auteur_index=0, nb_tuiles_posees=3,
                          solveur="exact")
    journal.logger_action(etat, "pioche", auteur_index=1)  # pas de solveur

    data = journal._journaux[etat["id"]]["data"]
    assert data["actions"][0]["solveur"] == "exact"
    assert "solveur" not in data["actions"][1]
    journal._journaux.clear()
