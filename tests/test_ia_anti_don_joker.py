"""Tests de la règle anti-don de joker (issue #252) : Intermédiaire, Avancé et
Expert ne doivent plus poser, ni laisser en place après leur coup, un joker
que l'adversaire peut reprendre facilement — voir docs/contexte/
ia_anti_don_joker.md pour la définition complète."""

from rummikub.moteur import niveaux as _niveaux
from rummikub.moteur.ia import (
    jouer_niveau_bride, jokers_offerts_sur_plateau, jokers_offerts_par_coup,
)
from rummikub.moteur.partie import creer_partie, plateau_depuis_dict
from rummikub.moteur.tuiles import tuile_depuis_dict


class _RngFixe:
    """RNG factice : ``random()`` renvoie toujours ``valeur`` (ici, pour
    empêcher l'oubli de façon déterministe — repris de tests/test_niveaux.py)."""
    def __init__(self, valeur):
        self.valeur = valeur

    def random(self):
        return self.valeur


def _partie_2j(niveau):
    return creer_partie(
        [{"nom": "Humain", "est_ia": False, "niveau": None},
         {"nom": "Bot", "est_ia": True, "niveau": niveau}],
        {"nb_manches": 1, "valeur_joker_penalite": 30, "mise_initiale_min": 30})


def _t(id_, valeur=None, couleur=None, est_joker=False):
    return {"id": id_, "valeur": valeur, "couleur": couleur, "est_joker": est_joker}


# --------------------------------------------------------------------------- #
# Détection d'un joker offert (mesure pure, sans décision de jeu)
# --------------------------------------------------------------------------- #

def test_joker_en_bout_de_suite_avec_remplacement_inconnu_est_offert():
    plateau = plateau_depuis_dict([[
        _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
        _t("joker_1", est_joker=True),
    ]])
    offerts = jokers_offerts_sur_plateau(plateau, [])
    assert offerts == {"joker_1"}


def test_joker_sans_tuile_de_remplacement_inconnue_n_est_pas_offert():
    """Joker au MILIEU d'une suite (une seule voie de reprise, l'échange
    direct) dont les DEUX exemplaires du type manquant sont déjà visibles
    (un sur le plateau, un en main) : aucune tuile de remplacement cachée,
    donc pas offert."""
    plateau = plateau_depuis_dict([
        [_t("rouge_7_a", 7, "rouge"), _t("joker_1", est_joker=True),
         _t("rouge_9_a", 9, "rouge")],
        [_t("rouge_8_a", 8, "rouge"), _t("bleu_8_a", 8, "bleu"),
         _t("noir_8_a", 8, "noir")],
    ])
    chevalet = [tuile_depuis_dict(_t("rouge_8_b", 8, "rouge"))]
    offerts = jokers_offerts_sur_plateau(plateau, chevalet)
    assert offerts == set()


def test_joker_deja_offert_avant_le_coup_n_est_pas_un_nouveau_don():
    """Laisser en place un joker déjà offert AVANT le coup n'est pas un
    cadeau fait par CE coup (nuance d'Alain, #252)."""
    etat = _partie_2j("Expert")
    etat["index_joueur_actuel"] = 1
    etat["plateau"] = [[
        _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
        _t("joker_1", est_joker=True),
    ]]
    etat["joueurs"][1]["chevalet"] = [_t("noir_2_a", 2, "noir")]
    # Coup qui ne touche pas à la suite existante (le joker y reste).
    coup = {"ids_tuiles": [], "nouveau_plateau": etat["plateau"]}
    assert jokers_offerts_par_coup(etat, 1, coup) == set()


# --------------------------------------------------------------------------- #
# Décision de jeu (Expert, Avancé, Intermédiaire)
# --------------------------------------------------------------------------- #

def _etat_gift_evitable(niveau):
    """Meilleur coup (6 tuiles) : suite rouge 7-8-(joker=9, remplacement
    rouge 6 ou rouge 9 inconnu) + suite bleue 5-6-7 (sans joker, 3 tuiles).
    Alternative sans don (3 tuiles, en retirant le joker) : la suite bleue
    seule. ``noir_2`` isolée empêche ce coup de 6 tuiles de vider la main
    (sinon l'exception absolue du coup gagnant s'appliquerait avant même
    d'atteindre la règle anti-don, §13)."""
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = []
    bot["chevalet"] = [
        _t("joker_1", est_joker=True),
        _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
        _t("bleu_5_a", 5, "bleu"), _t("bleu_6_a", 6, "bleu"),
        _t("bleu_7_a", 7, "bleu"), _t("noir_2_a", 2, "noir"),
    ]
    return etat


def test_expert_evite_le_coup_qui_offre_un_joker_en_posant_moins_de_tuiles():
    etat = _etat_gift_evitable("Expert")
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"bleu_5_a", "bleu_6_a", "bleu_7_a"}
    assert coup["don_joker"]["declenchee"] is True
    assert coup["don_joker"]["evite"] is True


def test_avance_evite_aussi_le_don_de_joker():
    etat = _etat_gift_evitable("Avancé")
    coup = jouer_niveau_bride(etat, 1, "Avancé")
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"bleu_5_a", "bleu_6_a", "bleu_7_a"}


def test_intermediaire_est_soumis_a_la_regle_comme_avance_et_expert():
    etat = _etat_gift_evitable("Intermédiaire")
    coup = jouer_niveau_bride(etat, 1, "Intermédiaire", rng=_RngFixe(0.99))
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"bleu_5_a", "bleu_6_a", "bleu_7_a"}


def test_debutant_et_facile_peuvent_toujours_offrir_un_joker():
    """Débutant et Facile ne sont jamais soumis à la règle (#252) — leur
    bridage ne l'active pas, et ``jouer_niveau_bride`` ne pose même pas
    l'annotation ``don_joker``."""
    for niveau in ("Débutant", "Facile"):
        assert _niveaux.bridage_pour(niveau).eviter_don_joker is False
        etat = _etat_gift_evitable(niveau)
        coup = jouer_niveau_bride(etat, 1, niveau, rng=_RngFixe(0.99))
        if coup.get("action") == "jouer":
            assert "don_joker" not in coup


def test_niveaux_superieurs_ont_la_regle_activee():
    for niveau in ("Intermédiaire", "Avancé", "Expert"):
        assert _niveaux.bridage_pour(niveau).eviter_don_joker is True


# --------------------------------------------------------------------------- #
# Aucune alternative : attente bornée, puis coup forcé
# --------------------------------------------------------------------------- #

def _etat_gift_sans_alternative():
    """Seul coup possible : suite rouge 7-8-(joker=9), un don inévitable
    (remplacement rouge 6/9 inconnu). ``noir_2`` isolée empêche de vider la
    main (sinon l'exception du coup gagnant s'appliquerait)."""
    etat = _partie_2j("Expert")
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = []
    bot["chevalet"] = [
        _t("joker_1", est_joker=True),
        _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
        _t("noir_2_a", 2, "noir"),
    ]
    return etat


def test_pioche_jusqu_a_la_limite_puis_joue_le_coup_malgre_le_don():
    etat = _etat_gift_sans_alternative()

    coup1 = jouer_niveau_bride(etat, 1, "Expert")
    assert coup1["action"] == "piocher"
    assert coup1["don_joker"]["attente"] is True
    assert etat["joueurs"][1][_niveaux.CLE_ATTENTE_DON_JOKER] == 1

    coup2 = jouer_niveau_bride(etat, 1, "Expert")
    assert coup2["action"] == "piocher"
    assert etat["joueurs"][1][_niveaux.CLE_ATTENTE_DON_JOKER] == 2

    # Troisième tour consécutif (LIMITE_ATTENTE_DON_JOKER=2 dépassée) : le
    # coup qui offre le joker est joué malgré tout.
    coup3 = jouer_niveau_bride(etat, 1, "Expert")
    assert coup3["action"] == "jouer"
    assert set(coup3["ids_tuiles"]) == {"joker_1", "rouge_7_a", "rouge_8_a"}
    assert coup3["don_joker"]["force_apres_attente"] is True
    assert etat["joueurs"][1][_niveaux.CLE_ATTENTE_DON_JOKER] == 0


# --------------------------------------------------------------------------- #
# Exception absolue : un coup gagnant est toujours joué
# --------------------------------------------------------------------------- #

def test_coup_gagnant_joue_meme_s_il_offre_un_joker():
    etat = _partie_2j("Expert")
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = []
    # Main = exactement la suite qui offre le joker : la jouer vide le chevalet.
    bot["chevalet"] = [
        _t("joker_1", est_joker=True),
        _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
    ]
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"joker_1", "rouge_7_a", "rouge_8_a"}
    assert "don_joker" not in coup


# --------------------------------------------------------------------------- #
# Drapeau de désactivation (comparer_niveaux_ia.py)
# --------------------------------------------------------------------------- #

def test_regle_desactivee_reproduit_l_ancien_comportement():
    etat = _etat_gift_evitable("Expert")
    coup = jouer_niveau_bride(etat, 1, "Expert", eviter_don_joker=False)
    assert coup["action"] == "jouer"
    # Ancien comportement : le coup le plus riche (6 tuiles), jamais dégradé.
    assert set(coup["ids_tuiles"]) == {
        "joker_1", "rouge_7_a", "rouge_8_a",
        "bleu_5_a", "bleu_6_a", "bleu_7_a"}
    assert "don_joker" not in coup
