"""Tests du regroupement des fichiers d'une même partie reprise et de la
déduction de la mise initiale à travers la reprise (issue #202) :
``persistance/parties_liees.py`` + ``persistance/coups_rates.py``.

Scénarios couverts :
  - deux fichiers d'une même partie (le joueur a fait sa mise initiale dans le
    premier, le second commence juste après la reprise) : une fois reliés, les
    décisions du second fichier sont classées « après la mise initiale » et le
    solveur reçoit le bon drapeau — alors qu'analysé seul, le second fichier
    les classerait à tort « avant la mise initiale » ;
  - historique de début manquant : les décisions dont l'état de mise initiale
    est indéterminable sont exclues du calcul et comptées à part ;
  - utilisation directe de la clé ``mises_initiales`` du journal (#202+).
"""

from rummikub.persistance import coups_rates as CR
from rummikub.persistance import parties_liees as PL


def _tuile(id_, valeur, couleur, est_joker=False):
    return {"id": id_, "valeur": valeur, "couleur": couleur, "est_joker": est_joker}


def _joueur(nom, est_ia, niveau=None):
    return {"nom": nom, "est_ia": est_ia, "niveau": niveau}


def _action(tour, auteur_index, action, nb_tuiles_posees=0, mains=None,
            plateau=None, mises_initiales=None, termine=False, gagnant_index=None):
    a = {
        "horodatage": "2026-10-26T10:00:00", "action": action, "tour": tour,
        "joueur_actuel": None, "auteur_index": auteur_index,
        "nb_tuiles_posees": nb_tuiles_posees, "termine": termine,
        "gagnant_index": gagnant_index,
        "mains_joueurs": mains if mains is not None else [],
        "plateau": plateau if plateau is not None else [],
        "pioche": [], "sac_restant": 0,
    }
    if mises_initiales is not None:
        a["mises_initiales"] = mises_initiales
    return a


# Chevalet du Bot : rouge 4 (prolonge rouge 1-2-3), plus deux tuiles isolées —
# après la mise, poser rouge 4 est un coup à 1 tuile ; avant la mise, aucune
# ouverture à 30 points n'est possible (pas de coup).
_MAIN_BOT = [_tuile("rouge_4_a", 4, "rouge"),
             _tuile("bleu_9_a", 9, "bleu"),
             _tuile("jaune_2_a", 2, "jaune")]
_PLATEAU_R123 = [[_tuile("rouge_1_a", 1, "rouge"),
                  _tuile("rouge_2_a", 2, "rouge"),
                  _tuile("rouge_3_a", 3, "rouge")]]
_JOUEURS = [_joueur("Alain", False), _joueur("Bot", True, "Expert")]


def _fichier_A(avec_cle=False):
    """Début de partie : le Bot (idx 1) fait sa mise initiale au tour 2."""
    mains_debut = [{"nom": "Alain", "tuiles": []}, {"nom": "Bot", "tuiles": _MAIN_BOT}]
    kw = {}
    actions = [
        _action(1, 0, "pose", nb_tuiles_posees=3, mains=mains_debut, plateau=[],
                mises_initiales=[True, False] if avec_cle else None),
        _action(2, 1, "pose", nb_tuiles_posees=3, mains=mains_debut, plateau=_PLATEAU_R123,
                mises_initiales=[True, True] if avec_cle else None),
        _action(3, 0, "pioche", mains=mains_debut, plateau=_PLATEAU_R123,
                mises_initiales=[True, True] if avec_cle else None),
    ]
    return {"partie_id": "partie_X", "debut": "2026-10-26T10:00:00",
            "joueurs": _JOUEURS, "actions": actions}


def _fichier_B(avec_cle=False, partie_id="partie_X", debut="2026-10-26T11:00:00"):
    """Reprise : le Bot pioche au tour 5 alors que rouge 4 prolongerait la
    suite rouge déjà posée. B commence par une action du joueur 0 (pour que la
    décision du Bot au tour 5 soit reconstituable même B analysé seul)."""
    mains = [{"nom": "Alain", "tuiles": []}, {"nom": "Bot", "tuiles": _MAIN_BOT}]
    actions = [
        _action(4, 0, "pioche", mains=mains, plateau=_PLATEAU_R123,
                mises_initiales=[True, True] if avec_cle else None),
        _action(5, 1, "pioche", mains=mains, plateau=_PLATEAU_R123,
                mises_initiales=[True, True] if avec_cle else None),
    ]
    return {"partie_id": partie_id, "debut": debut, "joueurs": _JOUEURS, "actions": actions}


# --------------------------------------------------------------------------- #
# Regroupement (parties_liees).
# --------------------------------------------------------------------------- #

def test_grouper_deux_fichiers_meme_partie_id():
    journaux = [{"nom": "partie_20261026_110000.json", "data": _fichier_B()},
                {"nom": "partie_20261026_100000.json", "data": _fichier_A()}]
    groupes = PL.grouper_journaux(journaux)
    assert len(groupes) == 1
    # Classés dans l'ordre chronologique (debut), A avant B.
    noms = [item["nom"] for item in groupes[0]]
    assert noms == ["partie_20261026_100000.json", "partie_20261026_110000.json"]


def test_grouper_repli_sans_partie_id_par_continuite_des_tours():
    """Identifiant absent : reliés par mêmes joueurs + continuité des tours."""
    a = _fichier_A()
    b = _fichier_B()
    a["partie_id"] = None
    b["partie_id"] = None
    journaux = [{"nom": "partie_20261026_100000.json", "data": a},
                {"nom": "partie_20261026_110000.json", "data": b}]
    groupes = PL.grouper_journaux(journaux)
    assert len(groupes) == 1


def test_grouper_deux_parties_distinctes_memes_joueurs_non_reliees():
    """Deux parties complètes entre les mêmes joueurs, chacune débutant au
    tour 1, ne doivent PAS être reliées (le second fichier commence au début,
    pas en reprise)."""
    a = _fichier_A()
    b = _fichier_A()  # repart au tour 1 -> nouvelle partie.
    a["partie_id"] = None
    b["partie_id"] = None
    journaux = [{"nom": "partie_20261026_100000.json", "data": a},
                {"nom": "partie_20261026_120000.json", "data": b}]
    groupes = PL.grouper_journaux(journaux)
    assert len(groupes) == 2


def test_fusionner_concatene_les_actions():
    journaux = [{"nom": "a.json", "data": _fichier_A()},
                {"nom": "b.json", "data": _fichier_B()}]
    parties = PL.fusionner_journaux(journaux)
    assert len(parties) == 1
    p = parties[0]
    assert len(p["data"]["actions"]) == 5   # 3 de A + 2 de B.
    assert p["debut_present"] is True       # A commence au tour 1.
    assert p["fichiers"] == ["a.json", "b.json"]


# --------------------------------------------------------------------------- #
# Déduction de la mise initiale à travers la reprise (point 2).
# --------------------------------------------------------------------------- #

def test_fichier_reprise_seul_classe_a_tort_avant_mise():
    """Référence : le second fichier analysé SEUL croit la mise non faite."""
    decisions = CR.extraire_decisions_ia_toutes(_fichier_B())
    tour5 = [d for d in decisions if d["tour"] == 5 and d["idx"] == 1]
    assert len(tour5) == 1
    assert tour5[0]["moment"] == "avant_mise"


def test_fichiers_relies_classent_apres_mise_sans_cle():
    """Reliés (repli #188, sans la clé mises_initiales) : la pose du Bot dans
    le premier fichier est visible -> tour 5 classé « après la mise »."""
    journaux = [{"nom": "a.json", "data": _fichier_A()},
                {"nom": "b.json", "data": _fichier_B()}]
    p = PL.fusionner_journaux(journaux)[0]
    decisions = CR.extraire_decisions_ia_toutes(p["data"], p["debut_present"])
    tour5 = [d for d in decisions if d["tour"] == 5 and d["idx"] == 1]
    assert len(tour5) == 1
    assert tour5[0]["moment"] == "apres_mise"


def test_fichiers_relies_avec_cle_mises_initiales():
    """Reliés en utilisant directement la clé ``mises_initiales`` (#202+)."""
    journaux = [{"nom": "a.json", "data": _fichier_A(avec_cle=True)},
                {"nom": "b.json", "data": _fichier_B(avec_cle=True)}]
    p = PL.fusionner_journaux(journaux)[0]
    decisions = CR.extraire_decisions_ia_toutes(p["data"], p["debut_present"])
    tour5 = [d for d in decisions if d["tour"] == 5 and d["idx"] == 1][0]
    assert tour5["moment"] == "apres_mise"
    assert tour5["mise_initiale_inconnue"] is False


def test_solveur_recoit_le_bon_drapeau_apres_liaison():
    """Bout en bout avec le vrai solveur : reliés, le tour 5 est un coup raté
    (rouge 4 prolonge la suite) ; le solveur reçoit mise_initiale_faite=True."""
    journaux = [{"nom": "a.json", "data": _fichier_A()},
                {"nom": "b.json", "data": _fichier_B()}]
    p = PL.fusionner_journaux(journaux)[0]
    decisions = CR.extraire_decisions_ia_toutes(p["data"], p["debut_present"])
    tour5 = [d for d in decisions if d["tour"] == 5 and d["idx"] == 1][0]
    assert tour5["etat"]["joueurs"][1]["mise_initiale_faite"] is True
    r = CR.analyser_decision_complete(tour5, budget_genereux=2.0)
    assert r["coup_rate"] is True
    assert r["nb_tuiles_solveur"] >= 1


# --------------------------------------------------------------------------- #
# Historique manquant (point 3).
# --------------------------------------------------------------------------- #

def _fichier_reprise_debut_manquant():
    """Fichier de reprise ancien (sans clé mises_initiales) commençant en plein
    milieu de partie (tour 20) : le Bot n'y a jamais posé, impossible de savoir
    si sa mise initiale est faite."""
    mains = [{"nom": "Alain", "tuiles": []}, {"nom": "Bot", "tuiles": _MAIN_BOT}]
    actions = [
        _action(20, 0, "pioche", mains=mains, plateau=_PLATEAU_R123),
        _action(21, 1, "pioche", mains=mains, plateau=_PLATEAU_R123),
    ]
    return {"partie_id": "partie_Z", "debut": "2026-10-26T20:00:00",
            "joueurs": _JOUEURS, "actions": actions}


def test_debut_manquant_detecte_par_fusion():
    journaux = [{"nom": "z.json", "data": _fichier_reprise_debut_manquant()}]
    p = PL.fusionner_journaux(journaux)[0]
    assert p["debut_present"] is False


def test_decision_mise_initiale_inconnue_exclue():
    journaux = [{"nom": "z.json", "data": _fichier_reprise_debut_manquant()}]
    p = PL.fusionner_journaux(journaux)[0]
    decisions = CR.extraire_decisions_ia_toutes(p["data"], p["debut_present"])
    tour21 = [d for d in decisions if d["tour"] == 21 and d["idx"] == 1][0]
    assert tour21["moment"] == "inconnu"
    assert tour21["mise_initiale_inconnue"] is True

    # L'analyse n'interroge pas le solveur et marque la décision à part.
    r = CR.analyser_decision_complete(tour21, budget_genereux=2.0)
    assert r["mise_initiale_inconnue"] is True
    assert r["coup_rate"] is False
    assert r["inconclusif"] is False


def test_resume_compte_les_inconnues_a_part():
    journaux = [{"nom": "z.json", "data": _fichier_reprise_debut_manquant()}]
    p = PL.fusionner_journaux(journaux)[0]
    decisions = CR.extraire_decisions_ia_toutes(p["data"], p["debut_present"])
    resultats = [CR.analyser_decision_complete(d, budget_genereux=2.0) for d in decisions]
    resume = CR.calculer_resume_complet(resultats)
    assert resume["Expert"]["inconnu"]["decisions"] == 1
    # Aucune décision inconnue n'est comptée avant/après la mise.
    assert "avant_mise" not in resume["Expert"]
    assert "apres_mise" not in resume["Expert"]


def test_debut_present_defaut_conserve_comportement_ancien():
    """Sans regroupement (debut_present par défaut True) : un fichier de reprise
    seul retombe sur l'ancien comportement (supposé « avant la mise »), jamais
    « inconnu » — la détection de l'inconnu passe par la fusion qui calcule
    debut_present (compatibilité des appels directs existants)."""
    decisions = CR.extraire_decisions_ia_toutes(_fichier_reprise_debut_manquant())
    tour21 = [d for d in decisions if d["tour"] == 21 and d["idx"] == 1][0]
    assert tour21["moment"] == "avant_mise"
