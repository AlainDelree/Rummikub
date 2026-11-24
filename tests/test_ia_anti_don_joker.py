"""Tests de la gestion du joker (issue #253 — REMPLACE la règle d'attente de
#252) : joker en main utile, joker libre évité, joker repris camouflé,
échange facultatif et échange différé. Voir docs/contexte/
ia_anti_don_joker.md pour la définition complète et l'arbre de décision."""

from rummikub.moteur import niveaux as _niveaux
from rummikub.moteur.ia import (
    jouer_niveau_bride, jokers_libres_sur_plateau, jokers_rendus_libres_par_coup,
    _joker_en_reserve,
)
from rummikub.moteur.partie import (
    creer_partie, plateau_depuis_dict, tuile_depuis_dict,
)


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


def _bot(niveau, plateau, chevalet, mise_initiale_faite=True):
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = mise_initiale_faite
    etat["plateau"] = plateau
    bot["chevalet"] = chevalet
    return etat


# --------------------------------------------------------------------------- #
# Définition d'un joker LIBRE (#253) — mesure pure, sans décision de jeu
# --------------------------------------------------------------------------- #

def test_joker_en_bout_de_suite_de_4_est_libre():
    """Suite rouge 7-8-9-(joker=10) : retirer le joker laisse 7-8-9, valide
    seule (3 tuiles) — libre SANS aucune tuile de remplacement."""
    plateau = plateau_depuis_dict([[
        _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
        _t("rouge_9_a", 9, "rouge"), _t("joker_1", est_joker=True),
    ]])
    assert jokers_libres_sur_plateau(plateau) == {"joker_1"}


def test_joker_dans_un_groupe_de_4_est_libre():
    """Groupe (5 rouge, 5 bleu, 5 noir, joker) : retirer le joker laisse un
    groupe de 3 valide — libre sans aucune tuile."""
    plateau = plateau_depuis_dict([[
        _t("rouge_5_a", 5, "rouge"), _t("bleu_5_a", 5, "bleu"),
        _t("noir_5_a", 5, "noir"), _t("joker_1", est_joker=True),
    ]])
    assert jokers_libres_sur_plateau(plateau) == {"joker_1"}


def test_joker_interieur_d_une_longue_suite_scindee_est_libre():
    """Suite rouge 1-2-3-(joker=4)-5-6-7 : le joker se scinde en deux suites
    valides (1-2-3 et 5-6-7) — libre sans aucune tuile."""
    plateau = plateau_depuis_dict([[
        _t("rouge_1_a", 1, "rouge"), _t("rouge_2_a", 2, "rouge"),
        _t("rouge_3_a", 3, "rouge"), _t("joker_1", est_joker=True),
        _t("rouge_5_a", 5, "rouge"), _t("rouge_6_a", 6, "rouge"),
        _t("rouge_7_a", 7, "rouge"),
    ]])
    assert jokers_libres_sur_plateau(plateau) == {"joker_1"}


def test_joker_au_milieu_d_une_suite_de_3_n_est_pas_libre():
    """Suite rouge 7-(joker=8)-9 : le retirer laisse 7 et 9 disjoints (aucun
    n'atteint 3 tuiles) — pas libre."""
    plateau = plateau_depuis_dict([[
        _t("rouge_7_a", 7, "rouge"), _t("joker_1", est_joker=True),
        _t("rouge_9_a", 9, "rouge"),
    ]])
    assert jokers_libres_sur_plateau(plateau) == set()


def test_joker_au_milieu_d_une_suite_de_4_n_est_pas_libre():
    """Suite rouge 6-7-(joker=8)-9 : le joker est STRICTEMENT intérieur mais
    la suite ne compte que 4 tuiles (la scission milieu exige au moins 7) —
    pas libre."""
    plateau = plateau_depuis_dict([[
        _t("rouge_6_a", 6, "rouge"), _t("rouge_7_a", 7, "rouge"),
        _t("joker_1", est_joker=True), _t("rouge_9_a", 9, "rouge"),
    ]])
    assert jokers_libres_sur_plateau(plateau) == set()


def test_joker_dans_un_groupe_de_3_n_est_pas_libre():
    """Groupe (5 rouge, 5 bleu, joker) : le retirer ferait tomber le groupe
    à 2 tuiles, sous le minimum — pas libre."""
    plateau = plateau_depuis_dict([[
        _t("rouge_5_a", 5, "rouge"), _t("bleu_5_a", 5, "bleu"),
        _t("joker_1", est_joker=True),
    ]])
    assert jokers_libres_sur_plateau(plateau) == set()


def test_joker_deja_libre_avant_le_coup_n_est_pas_nouveau():
    """Laisser en place un joker déjà libre AVANT le coup n'est pas rendu
    libre PAR ce coup (même nuance qu'en #252)."""
    etat = _bot("Expert",
               plateau=[[
                   _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
                   _t("rouge_9_a", 9, "rouge"), _t("joker_1", est_joker=True),
               ]],
               chevalet=[_t("noir_2_a", 2, "noir")])
    coup = {"ids_tuiles": [], "nouveau_plateau": etat["plateau"]}
    assert jokers_rendus_libres_par_coup(etat, 1, coup) == set()


# --------------------------------------------------------------------------- #
# Point 1 — joker « en réserve » : test complet (#254)
# --------------------------------------------------------------------------- #

def test_joker_en_reserve_dechu_par_groupe4_deja_complet():
    """Suite rouge 3-4-(joker_1=5) : le joker n'est pas déjà libre (bout
    d'une suite de 3 seulement). Un groupe de 4 DÉJÀ COMPLET ailleurs sur
    le plateau (rouge_5/bleu_5/noir_5/jaune_5) peut perdre n'importe quelle
    tuile réelle (groupe de 3 valide restant) ; le rouge_5 ainsi libéré
    correspond EXACTEMENT au joker_1 (même recombinaison que
    ``_jokers_liberables_par_reduction_groupe4``, SANS aucune tuile de
    main) : la tuile de remplacement devient donc disponible par un pur
    déplacement de l'autre exemplaire visible — PAS en réserve, même si
    l'unique autre exemplaire de rouge_5 est bien visible sur le plateau
    (#254, point 1 — #253 ne détectait pas cette recombinaison, qui ne fait
    pourtant partie d'aucune des 3 voies de ``jokers_libres_sur_plateau``)."""
    plateau = plateau_depuis_dict([[
        _t("rouge_3_a", 3, "rouge"), _t("rouge_4_a", 4, "rouge"),
        _t("joker_1", est_joker=True),
    ], [
        _t("rouge_5_a", 5, "rouge"), _t("bleu_5_a", 5, "bleu"),
        _t("noir_5_a", 5, "noir"), _t("jaune_5_a", 5, "jaune"),
    ]])
    assert "joker_1" not in jokers_libres_sur_plateau(plateau)  # pas déjà libre
    rec = {"joker": plateau[0][2],
          "remplacement": tuile_depuis_dict(_t("rouge_5_hand", 5, "rouge"))}
    assert _joker_en_reserve(plateau, rec) is False


def test_joker_en_reserve_tient_si_le_groupe_n_est_pas_deja_a_4():
    """Voisin de ``test_joker_en_reserve_dechu_par_groupe4_deja_complet`` :
    le groupe n'a que 3 tuiles (``jaune_5`` retirée), pas 4 — la réduction
    de ``_jokers_liberables_par_reduction_groupe4`` exige soit un groupe
    DÉJÀ à 4, soit une tuile de MAIN pour le compléter (chevalet vide ici,
    donc aucun candidat) : aucune recombinaison du plateau seul ne libère
    joker_1 — toujours en réserve."""
    plateau = plateau_depuis_dict([[
        _t("rouge_3_a", 3, "rouge"), _t("rouge_4_a", 4, "rouge"),
        _t("joker_1", est_joker=True),
    ], [
        _t("rouge_5_a", 5, "rouge"), _t("bleu_5_a", 5, "bleu"),
        _t("noir_5_a", 5, "noir"),
    ]])
    rec = {"joker": plateau[0][2],
          "remplacement": tuile_depuis_dict(_t("rouge_5_hand", 5, "rouge"))}
    assert _joker_en_reserve(plateau, rec) is True


# --------------------------------------------------------------------------- #
# Point 3 — joker en main UTILE
# --------------------------------------------------------------------------- #

def test_joker_en_main_utile_est_joue():
    """Avec le joker : rouge 7-8-(joker=9) [2 réelles] + bleu 5-6-7 [3
    réelles] = 5 tuiles réelles. Sans aucun joker : seule bleu 5-6-7 est
    jouable (rouge 7-8 seuls ne forment rien) = 3 réelles. 5 > 3 : utile,
    joué tel quel (noir_2 isolé empêche de vider la main)."""
    etat = _bot("Expert", plateau=[], chevalet=[
        _t("joker_1", est_joker=True),
        _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
        _t("bleu_5_a", 5, "bleu"), _t("bleu_6_a", 6, "bleu"),
        _t("bleu_7_a", 7, "bleu"), _t("noir_2_a", 2, "noir"),
    ])
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {
        "joker_1", "rouge_7_a", "rouge_8_a", "bleu_5_a", "bleu_6_a", "bleu_7_a"}
    assert coup["joker"]["jokers_main_gardes"] == 0


def test_joker_en_main_non_utile_est_garde():
    """Avec le joker : rouge 7-8-9-(joker=10), 3 réelles (le joker n'ajoute
    QUE lui-même). Sans aucun joker : rouge 7-8-9 seule, 3 réelles aussi.
    3 == 3 (égalité) : PAS utile, le joker est gardé et seule la suite de 3
    est jouée (noir_2 isolé empêche de vider la main)."""
    etat = _bot("Expert", plateau=[], chevalet=[
        _t("joker_1", est_joker=True),
        _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
        _t("rouge_9_a", 9, "rouge"), _t("noir_2_a", 2, "noir"),
    ])
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_7_a", "rouge_8_a", "rouge_9_a"}
    assert coup["joker"]["jokers_main_gardes"] == 1


def test_joker_rend_l_ouverture_possible_est_joue():
    """Mise initiale NON faite. Avec le joker : rouge 11-12-(joker=13) = 36
    points (≥ 30), 2 réelles. Sans aucun joker : rouge 11-12 seules
    n'atteignent aucune mise initiale (0 réelle jouée). 2 > 0 : utile —
    l'ouverture est rendue possible PAR le joker."""
    etat = _bot("Expert", plateau=[], chevalet=[
        _t("joker_1", est_joker=True),
        _t("rouge_11_a", 11, "rouge"), _t("rouge_12_a", 12, "rouge"),
        _t("noir_2_a", 2, "noir"),
    ], mise_initiale_faite=False)
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"joker_1", "rouge_11_a", "rouge_12_a"}
    assert coup["joker"]["jokers_main_gardes"] == 0


# --------------------------------------------------------------------------- #
# Point 4 (#254) — deux jokers de main évalués SÉPARÉMENT (REMPLACE
# l'évaluation collective de #253, point 3)
# --------------------------------------------------------------------------- #

def test_deux_jokers_en_main_un_seul_utile_est_joue():
    """Main : joker_1, joker_2, rouge_7, rouge_8, noir_5, noir_6, noir_7,
    bleu_2 (isolée, empêche de vider la main). rouge_7-8 ne forme rien SANS
    AUCUN joker (2 tuiles seulement) : UN SEUL joker, combiné à rouge_7-8,
    est UTILE (rouge_7-8-(joker=9), 2 réelles, contre 0 sans lui). noir_5-
    6-7 est DÉJÀ une suite valide à 3 tuiles réelles SANS aucun joker : y
    ajouter un second joker (en bout, 4e tuile) n'apporte AUCUNE tuile
    réelle de plus (3 == 3) — ce second joker N'EST PAS utile. Les deux
    jokers étant INTERCHANGEABLES pour le solveur, PEU IMPORTE lequel des
    deux (joker_1 ou joker_2) finit assigné à quelle place : exactement UN
    SEUL doit être posé, l'autre gardé. Sous #253 (évaluation collective),
    les DEUX auraient été jugés utiles ensemble (5 réel avec les deux
    contre 3 sans AUCUN des deux) et le second aurait été posé pour rien —
    c'est exactement le bug que corrige #254, point 4."""
    etat = _bot("Expert", plateau=[], chevalet=[
        _t("joker_1", est_joker=True), _t("joker_2", est_joker=True),
        _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
        _t("noir_5_a", 5, "noir"), _t("noir_6_a", 6, "noir"),
        _t("noir_7_a", 7, "noir"), _t("bleu_2_a", 2, "bleu"),
    ])
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "jouer"
    ids = set(coup["ids_tuiles"])
    assert ids & {"joker_1", "joker_2"} and len(ids & {"joker_1", "joker_2"}) == 1
    assert ids - {"joker_1", "joker_2"} == {
        "rouge_7_a", "rouge_8_a", "noir_5_a", "noir_6_a", "noir_7_a"}
    assert coup["joker"]["jokers_main_gardes"] == 1


def test_deux_jokers_en_main_tous_deux_utiles_sont_joues():
    """Voisin du test précédent : ``noir_7_a`` est retiré, ``noir_5_a`` et
    ``noir_6_a`` ne forment donc plus une suite à 3 tuiles SANS joker (2
    tuiles seulement). Les deux paires (rouge 7-8 et noir 5-6) ont chacune
    BESOIN d'un joker pour être posées du tout, mais un seul joker ne peut
    servir qu'à UNE paire à la fois : retirer séparément joker_1 OU joker_2
    laisse chaque fois l'AUTRE joker disponible pour sauver une seule paire
    (2 réelles, contre 4 réelles avec les deux) — chacun est donc UTILE
    individuellement, et les deux sont posés."""
    etat = _bot("Expert", plateau=[], chevalet=[
        _t("joker_1", est_joker=True), _t("joker_2", est_joker=True),
        _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
        _t("noir_5_a", 5, "noir"), _t("noir_6_a", 6, "noir"),
        _t("bleu_2_a", 2, "bleu"),
    ])
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {
        "joker_1", "rouge_7_a", "rouge_8_a",
        "joker_2", "noir_5_a", "noir_6_a"}
    assert coup["joker"]["jokers_main_gardes"] == 0


# --------------------------------------------------------------------------- #
# Exception absolue : un coup gagnant est TOUJOURS joué (avec ou sans joker)
# --------------------------------------------------------------------------- #

def test_coup_gagnant_avec_joker_toujours_joue():
    etat = _bot("Expert", plateau=[], chevalet=[
        _t("joker_1", est_joker=True),
        _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
    ])
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"joker_1", "rouge_7_a", "rouge_8_a"}
    assert "joker" not in coup


def test_coup_gagnant_sans_joker_toujours_joue():
    etat = _bot("Expert", plateau=[], chevalet=[
        _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
        _t("rouge_9_a", 9, "rouge"),
    ])
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_7_a", "rouge_8_a", "rouge_9_a"}
    assert "joker" not in coup


# --------------------------------------------------------------------------- #
# Point 4 — joker LIBRE évité (remplace la pioche bornée de #252)
# --------------------------------------------------------------------------- #

def test_evite_le_coup_qui_rend_un_joker_libre_en_posant_moins_de_tuiles():
    """Plateau : suite rouge 7-8-(joker=9) (pas libre, 2 tuiles restantes
    seulement). Jouer rouge_6 de la main l'étendrait en 6-7-8-(joker=9), 4
    tuiles — le joker deviendrait libre (reste 6-7-8, 3 tuiles). Une
    alternative existe (bleu 5-6-7, 3 tuiles, sans toucher au plateau) :
    elle est préférée, au prix d'une tuile en moins."""
    etat = _bot("Expert",
               plateau=[[
                   _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
                   _t("joker_1", est_joker=True),
               ]],
               chevalet=[
                   _t("rouge_6_a", 6, "rouge"),
                   _t("bleu_5_a", 5, "bleu"), _t("bleu_6_a", 6, "bleu"),
                   _t("bleu_7_a", 7, "bleu"), _t("noir_2_a", 2, "noir"),
               ])
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"bleu_5_a", "bleu_6_a", "bleu_7_a"}
    assert coup["joker"]["joker_libre_declenche"] is True
    assert coup["joker"]["joker_libre_evite"] is True
    assert coup["joker"]["joker_libre_pioche"] is False


def test_pioche_sans_compteur_ni_limite_si_seul_coup_laisse_un_joker_libre():
    """Même plateau, mais SEULE option : étendre avec rouge_6 (pas
    d'alternative). L'IA pioche plutôt que de laisser le joker libre —
    SANS compteur ni limite (contrairement à #252) : répété deux fois de
    suite sur le MÊME état, elle pioche encore la seconde fois."""
    etat = _bot("Expert",
               plateau=[[
                   _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
                   _t("joker_1", est_joker=True),
               ]],
               chevalet=[_t("rouge_6_a", 6, "rouge"), _t("noir_2_a", 2, "noir")])

    coup1 = jouer_niveau_bride(etat, 1, "Expert")
    assert coup1["action"] == "piocher"
    assert coup1["joker"]["joker_libre_pioche"] is True

    coup2 = jouer_niveau_bride(etat, 1, "Expert")
    assert coup2["action"] == "piocher"
    assert coup2["joker"]["joker_libre_pioche"] is True


# --------------------------------------------------------------------------- #
# Point 5 (#254) — pioche vide : jouer plutôt que passer sans fin
# --------------------------------------------------------------------------- #

def test_joue_malgre_joker_libre_si_pioche_vide():
    """Même plateau/main que ``test_pioche_sans_compteur_ni_limite_si_seul_
    coup_laisse_un_joker_libre`` (SEULE option : étendre avec rouge_6,
    joker_1 devient libre ; aucune alternative), mais la pioche est VIDE —
    passer n'apporterait rien de mieux (elle resterait vide au tour
    suivant) : l'IA joue le coup malgré le joker libre, plutôt que de
    passer indéfiniment (#254, point 5 — remplace, dans ce seul cas, la
    règle « piocher plutôt que de laisser un joker libre »)."""
    etat = _bot("Expert",
               plateau=[[
                   _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
                   _t("joker_1", est_joker=True),
               ]],
               chevalet=[_t("rouge_6_a", 6, "rouge"), _t("noir_2_a", 2, "noir")])
    etat["pioche"] = []

    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_6_a"}
    assert coup["joker"]["joker_libre_declenche"] is True
    assert coup["joker"]["joker_libre_evite"] is False
    assert coup["joker"]["joker_libre_pioche"] is False
    assert coup["joker"]["joker_libre_force_pioche_vide"] is True


def test_pioche_encore_si_pioche_non_vide_meme_scenario():
    """Voisin EXACT du test précédent (même plateau/main), mais avec une
    pioche NON vide (cas normal) : reproduit ``test_pioche_sans_compteur_
    ni_limite_si_seul_coup_laisse_un_joker_libre`` — l'IA pioche, ne joue
    PAS le coup qui laisse le joker libre."""
    etat = _bot("Expert",
               plateau=[[
                   _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
                   _t("joker_1", est_joker=True),
               ]],
               chevalet=[_t("rouge_6_a", 6, "rouge"), _t("noir_2_a", 2, "noir")])
    assert etat["pioche"]  # non vide par construction normale de la partie

    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "piocher"
    assert coup["joker"]["joker_libre_force_pioche_vide"] is False


# --------------------------------------------------------------------------- #
# Point 5/6 — échange facultatif (reprise, camouflage, décision)
# --------------------------------------------------------------------------- #

def test_echange_facultatif_repris_et_camoufle_en_position_non_libre():
    """Échange rouge_6 contre le joker de la suite rouge 4-5-(joker=6) ; le
    joker libéré est reposé avec noir_2+jaune_2 (groupe de 3, PAS libre) —
    utilisé avec la main, donc camouflage via la main elle-même (bleu_9
    isolé empêche de vider la main). Le second rouge_6 (``rouge_6_b``) sur
    le plateau écarte la réserve (#253 point 6) : échange immédiat."""
    etat = _bot("Expert",
               plateau=[[
                   _t("rouge_4_a", 4, "rouge"), _t("rouge_5_a", 5, "rouge"),
                   _t("joker_1", est_joker=True),
               ], [
                   _t("rouge_6_b", 6, "rouge"), _t("bleu_6_a", 6, "bleu"),
                   _t("noir_6_a", 6, "noir"),
               ]],
               chevalet=[
                   _t("rouge_6_a", 6, "rouge"),
                   _t("noir_2_a", 2, "noir"), _t("jaune_2_a", 2, "jaune"),
                   _t("bleu_9_a", 9, "bleu"),
               ])
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_6_a", "noir_2_a", "jaune_2_a"}
    plateau_apres = plateau_depuis_dict(coup["nouveau_plateau"])
    assert "joker_1" not in jokers_libres_sur_plateau(plateau_apres)
    assert coup["joker"]["echange_differe"] is False


def test_echange_facultatif_non_repris_si_seul_endroit_est_libre():
    """Même échange (rouge_6), mais la SEULE façon de reposer le joker
    libéré est de l'étendre en bout de la suite noire 3-4-5 (noir
    3-4-5-(joker=6)), toujours libre. Aucun autre placement n'existe
    (bleu_9 isolé). L'IA ne reprend PAS le joker (ni ne joue rouge_6) —
    faute d'alternative, elle pioche."""
    etat = _bot("Expert",
               plateau=[[
                   _t("rouge_4_a", 4, "rouge"), _t("rouge_5_a", 5, "rouge"),
                   _t("joker_1", est_joker=True),
               ], [
                   _t("noir_3_a", 3, "noir"), _t("noir_4_a", 4, "noir"),
                   _t("noir_5_a", 5, "noir"),
               ]],
               chevalet=[_t("rouge_6_a", 6, "rouge"), _t("bleu_9_a", 9, "bleu")])
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "piocher"


def test_echange_facultatif_repris_si_le_coup_fait_gagner():
    """Même structure, mais la main entière se résume à rouge_6 : jouer
    l'échange vide le chevalet et gagne la partie — joué malgré tout, même
    si le seul reposition possible (noir 3-4-5-(joker=6)) est libre."""
    etat = _bot("Expert",
               plateau=[[
                   _t("rouge_4_a", 4, "rouge"), _t("rouge_5_a", 5, "rouge"),
                   _t("joker_1", est_joker=True),
               ], [
                   _t("noir_3_a", 3, "noir"), _t("noir_4_a", 4, "noir"),
                   _t("noir_5_a", 5, "noir"),
               ]],
               chevalet=[_t("rouge_6_a", 6, "rouge")])
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_6_a"}
    assert "joker" not in coup


# --------------------------------------------------------------------------- #
# Point 6 — échange différé (réserve)
# --------------------------------------------------------------------------- #

def _etat_echange_en_reserve(niveau="Expert"):
    """Échange rouge_6 contre le joker de rouge 4-5-(joker=6). L'autre
    rouge_6 (``rouge_6_b``) est visible sur le plateau (réserve, #253 point
    6). Le joker libéré, une fois rouge_6 échangé, ne peut être reposé que
    par extension PURE (sans tuile de main) sur noir 8-9-10 ou le groupe
    rouge_6_b/bleu_6/noir_6 — jamais avec la main. ``noir_3`` complète le
    groupe rouge/bleu/jaune_3 (4 couleurs, aucune place pour le joker) :
    c'est l'« autre coup » que l'IA joue normalement pendant l'attente.
    ``bleu_9`` isolé (inutilisable) évite que jouer rouge_6+noir_3 ne vide
    le chevalet (ce qui déclencherait l'exception absolue du coup gagnant
    avant même d'atteindre la gestion du joker, docs/contexte/
    ia_anti_don_joker.md §3)."""
    return _bot(niveau,
               plateau=[[
                   _t("rouge_4_a", 4, "rouge"), _t("rouge_5_a", 5, "rouge"),
                   _t("joker_1", est_joker=True),
               ], [
                   _t("rouge_6_b", 6, "rouge"), _t("bleu_6_a", 6, "bleu"),
                   _t("noir_6_a", 6, "noir"),
               ], [
                   _t("noir_8_a", 8, "noir"), _t("noir_9_a", 9, "noir"),
                   _t("noir_10_a", 10, "noir"),
               ], [
                   _t("rouge_3_a", 3, "rouge"), _t("bleu_3_a", 3, "bleu"),
                   _t("jaune_3_a", 3, "jaune"),
               ]],
               chevalet=[_t("rouge_6_a", 6, "rouge"), _t("noir_3_a", 3, "noir"),
                        _t("bleu_9_a", 9, "bleu")])


def test_echange_differe_jusqu_a_trois_tours_puis_fait():
    etat = _etat_echange_en_reserve()

    coup1 = jouer_niveau_bride(etat, 1, "Expert")
    assert coup1["action"] == "jouer"
    assert set(coup1["ids_tuiles"]) == {"noir_3_a"}
    assert coup1["joker"]["echange_differe"] is True
    assert coup1["joker"]["echange_differe_pioche"] is False
    assert etat["joueurs"][1][_niveaux.CLE_ATTENTE_ECHANGE_DIFFERE] == {"joker_1": 1}

    coup2 = jouer_niveau_bride(etat, 1, "Expert")
    assert set(coup2["ids_tuiles"]) == {"noir_3_a"}
    assert etat["joueurs"][1][_niveaux.CLE_ATTENTE_ECHANGE_DIFFERE] == {"joker_1": 2}

    coup3 = jouer_niveau_bride(etat, 1, "Expert")
    assert set(coup3["ids_tuiles"]) == {"noir_3_a"}
    assert etat["joueurs"][1][_niveaux.CLE_ATTENTE_ECHANGE_DIFFERE] == {"joker_1": 3}

    # Quatrième décision (LIMITE_ECHANGE_DIFFERE=3 atteinte) : le point 6
    # cesse de différer (compteur remis à 0) et tente de jouer l'échange —
    # mais celui-ci est désormais SOUMIS au point 4 (#254, point 2) : la
    # seule reposition possible du joker libéré (extension pure sur noir
    # 8-9-10, ou sur le groupe rouge_6_b/bleu_6/noir_6) est TOUJOURS libre
    # (bout de suite ≥4, ou groupe de 4) ; une alternative SANS l'échange
    # existe (noir_3_a seul, sans toucher au plateau) — elle est prise à sa
    # place, le joker reste sur le tapis (il est « en réserve », donc cela
    # ne coûte rien). L'échange n'est donc PAS fait ce tour-ci non plus.
    coup4 = jouer_niveau_bride(etat, 1, "Expert")
    assert coup4["action"] == "jouer"
    assert set(coup4["ids_tuiles"]) == {"noir_3_a"}
    assert coup4["joker"]["echange_differe"] is False
    assert coup4["joker"]["joker_libre_evite"] is True
    assert etat["joueurs"][1].get(_niveaux.CLE_ATTENTE_ECHANGE_DIFFERE) == {}


def test_echange_differe_force_et_joue_si_pioche_vide_et_aucune_alternative():
    """Variante de ``test_echange_differe_jusqu_a_trois_tours_puis_fait`` où
    l'« autre coup » (noir_3) n'est PAS disponible (chevalet réduit à
    rouge_6_a seul) : après 3 tours de pioche comptée (#254, point 3), le
    4e appel force — le point 4 ne trouve ÉVIDEMMENT aucune alternative
    (aucune autre tuile en main) ; si la pioche est VIDE, l'échange est
    joué quand même (#254, point 5) plutôt que de passer sans fin."""
    etat = _bot("Expert",
               plateau=[[
                   _t("rouge_4_a", 4, "rouge"), _t("rouge_5_a", 5, "rouge"),
                   _t("joker_1", est_joker=True),
               ], [
                   _t("rouge_6_b", 6, "rouge"), _t("bleu_6_a", 6, "bleu"),
                   _t("noir_6_a", 6, "noir"),
               ]],
               chevalet=[_t("rouge_6_a", 6, "rouge"), _t("bleu_9_a", 9, "bleu")])

    for n in (1, 2, 3):
        coup = jouer_niveau_bride(etat, 1, "Expert")
        assert coup["action"] == "piocher"
        assert etat["joueurs"][1][_niveaux.CLE_ATTENTE_ECHANGE_DIFFERE] == {
            "joker_1": n}

    # Voisin (limite pas encore atteinte, pioche non vide) : comportement
    # inchangé ci-dessus (3 pioches comptées). Au 4e appel, limite atteinte
    # : si la pioche N'EST PAS vide, point 4 pioche encore (sans compteur
    # ni limite, "mieux vaut le laisser sur le tapis", #254 point 2).
    coup4_pioche_dispo = jouer_niveau_bride(etat, 1, "Expert")
    assert coup4_pioche_dispo["action"] == "piocher"
    assert etat["joueurs"][1].get(_niveaux.CLE_ATTENTE_ECHANGE_DIFFERE) == {}

    # Au tour suivant (nouveau cycle, compteur reparti de 0), si la pioche
    # est VIDE : l'échange est joué (#254, point 5).
    for n in (1, 2, 3):
        jouer_niveau_bride(etat, 1, "Expert")
    etat["pioche"] = []
    coup_force = jouer_niveau_bride(etat, 1, "Expert")
    assert coup_force["action"] == "jouer"
    assert set(coup_force["ids_tuiles"]) == {"rouge_6_a"}
    # Forcé par la limite du point 6 (délai expiré) ET par le point 5 (pioche
    # vide, aucune alternative trouvée par le point 4) : les deux drapeaux
    # correspondent à des déclencheurs différents (voir
    # ``_appliquer_echange_differe``/``_appliquer_joker_libre``) ; ici c'est
    # le second qui a effectivement décidé de jouer malgré le joker libre.
    assert coup_force["joker"]["joker_libre_force_pioche_vide"] is True
    assert etat["joueurs"][1].get(_niveaux.CLE_ATTENTE_ECHANGE_DIFFERE) == {}


def test_echange_differe_limite_a_deux_tours_si_adversaire_faible():
    etat = _etat_echange_en_reserve()
    # Adversaire (index 0) à moins de 5 tuiles (nombre de tuiles seulement).
    etat["joueurs"][0]["chevalet"] = [
        _t("bleu_1_a", 1, "bleu"), _t("bleu_2_a", 2, "bleu"),
        _t("bleu_3_b", 3, "bleu")]

    coup1 = jouer_niveau_bride(etat, 1, "Expert")
    assert set(coup1["ids_tuiles"]) == {"noir_3_a"}
    assert etat["joueurs"][1][_niveaux.CLE_ATTENTE_ECHANGE_DIFFERE] == {"joker_1": 1}

    coup2 = jouer_niveau_bride(etat, 1, "Expert")
    assert set(coup2["ids_tuiles"]) == {"noir_3_a"}
    assert etat["joueurs"][1][_niveaux.CLE_ATTENTE_ECHANGE_DIFFERE] == {"joker_1": 2}

    # Troisième décision (LIMITE_ECHANGE_DIFFERE_ADVERSAIRE_FAIBLE=2
    # atteinte) : comme au 4e tour de ``test_echange_differe_jusqu_a_trois_
    # tours_puis_fait``, le point 4 trouve une alternative (noir_3_a seul)
    # à la place de l'échange forcé, qui laisserait un joker libre (#254,
    # point 2) : le joker reste en réserve sur le tapis.
    coup3 = jouer_niveau_bride(etat, 1, "Expert")
    assert coup3["action"] == "jouer"
    assert set(coup3["ids_tuiles"]) == {"noir_3_a"}
    assert coup3["joker"]["joker_libre_evite"] is True
    assert etat["joueurs"][1].get(_niveaux.CLE_ATTENTE_ECHANGE_DIFFERE) == {}


def test_echange_fait_aussitot_si_joker_utilisable_avec_la_main():
    """Variante de ``test_echange_facultatif_repris_et_camoufle...`` : la
    réserve tient (second rouge_6 visible), mais le joker libéré EST
    utilisable avec la main (noir_2+jaune_2) — fait aussitôt, jamais
    différé."""
    etat = _bot("Expert",
               plateau=[[
                   _t("rouge_4_a", 4, "rouge"), _t("rouge_5_a", 5, "rouge"),
                   _t("joker_1", est_joker=True),
               ], [
                   _t("rouge_6_b", 6, "rouge"), _t("bleu_6_a", 6, "bleu"),
                   _t("noir_6_a", 6, "noir"),
               ]],
               chevalet=[
                   _t("rouge_6_a", 6, "rouge"),
                   _t("noir_2_a", 2, "noir"), _t("jaune_2_a", 2, "jaune"),
                   _t("bleu_9_a", 9, "bleu"),
               ])
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "jouer"
    assert "rouge_6_a" in coup["ids_tuiles"]
    assert coup["joker"]["echange_differe"] is False


def test_echange_fait_aussitot_si_pas_en_reserve():
    """Aucun second rouge_6 visible : pas en réserve (#253 point 6) — le
    joker libéré n'a nulle part où aller sauf extension pure (pas libre à
    camoufler ici car la seule extension disponible — noir 8-9-10 — rend le
    joker libre ; puisqu'il n'est pas en réserve, point 4 (général) décide
    seul : ici, aucune alternative n'existe, donc pioche."""
    etat = _bot("Expert",
               plateau=[[
                   _t("rouge_4_a", 4, "rouge"), _t("rouge_5_a", 5, "rouge"),
                   _t("joker_1", est_joker=True),
               ], [
                   _t("noir_8_a", 8, "noir"), _t("noir_9_a", 9, "noir"),
                   _t("noir_10_a", 10, "noir"),
               ]],
               chevalet=[_t("rouge_6_a", 6, "rouge"), _t("bleu_9_a", 9, "bleu")])
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "piocher"


def test_compteur_differe_retire_quand_la_reserve_cesse():
    """Un compteur d'attente déjà présent pour un joker qui n'est plus en
    réserve (p. ex. le plateau a été recomposé) est retiré, même si ce
    joker n'est pas concerné par le coup de ce tour."""
    etat = _etat_echange_en_reserve()
    etat["joueurs"][1][_niveaux.CLE_ATTENTE_ECHANGE_DIFFERE] = {"joker_1": 2}
    # Retire le second rouge_6 : la réserve cesse (plus personne d'autre ne
    # peut être exclu de détenir la tuile de remplacement).
    etat["plateau"][1] = [
        _t("bleu_6_a", 6, "bleu"), _t("noir_6_a", 6, "noir"),
        _t("jaune_6_a", 6, "jaune"),
    ]
    jouer_niveau_bride(etat, 1, "Expert")
    assert etat["joueurs"][1].get(_niveaux.CLE_ATTENTE_ECHANGE_DIFFERE) == {}


def test_echange_differe_ne_passe_pas_le_tour_sauf_coup_unique():
    """Pendant le différé, l'IA joue normalement son autre coup (noir_3,
    voir ``_etat_echange_en_reserve``) — ce n'est pas un tour passé. Si
    l'échange est le SEUL coup possible, elle pioche — et ``#254`` (point 3)
    CORRIGE #253 : ce tour de pioche compte désormais dans la limite
    d'attente (#253 ne le comptait pas, permettant une attente sans
    limite)."""
    etat = _etat_echange_en_reserve()
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "jouer"  # pas un tour passé

    etat_seul_coup = _bot("Expert",
                         plateau=[[
                             _t("rouge_4_a", 4, "rouge"), _t("rouge_5_a", 5, "rouge"),
                             _t("joker_1", est_joker=True),
                         ], [
                             _t("rouge_6_b", 6, "rouge"), _t("bleu_6_a", 6, "bleu"),
                             _t("noir_6_a", 6, "noir"),
                         ], [
                             _t("noir_8_a", 8, "noir"), _t("noir_9_a", 9, "noir"),
                             _t("noir_10_a", 10, "noir"),
                         ]],
                         chevalet=[_t("rouge_6_a", 6, "rouge"),
                                  _t("bleu_2_a", 2, "bleu")])
    coup_seul = jouer_niveau_bride(etat_seul_coup, 1, "Expert")
    assert coup_seul["action"] == "piocher"
    assert etat_seul_coup["joueurs"][1].get(
        _niveaux.CLE_ATTENTE_ECHANGE_DIFFERE) == {"joker_1": 1}


# --------------------------------------------------------------------------- #
# Point 7 (#254) — débarras du joker inutile en fin de match multi-manches
# --------------------------------------------------------------------------- #

def _pioche_factice(n):
    return [_t(f"pioche_{i}") for i in range(n)]


def _etat_joker_non_utile_fin_match(nb_manches, tuiles_adversaire, taille_pioche):
    """Même scénario que ``test_joker_en_main_non_utile_est_garde`` (joker
    non utile : rouge 7-8-9-(joker) n'ajoute aucune tuile réelle), avec un
    match/une pioche/un adversaire paramétrables pour tester les 3 seuils
    du point 7."""
    etat = _bot("Expert", plateau=[], chevalet=[
        _t("joker_1", est_joker=True),
        _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
        _t("rouge_9_a", 9, "rouge"), _t("noir_2_a", 2, "noir"),
    ])
    etat["config"]["nb_manches"] = nb_manches
    etat["joueurs"][0]["chevalet"] = [
        _t(f"adv_{i}", 1, "bleu") for i in range(tuiles_adversaire)]
    etat["pioche"] = _pioche_factice(taille_pioche)
    return etat


def test_joker_inutile_debarrasse_en_fin_de_match_multi_manches():
    """Match à 2 manches, adversaire à AU PLUS 2 tuiles (ici 2), pioche à
    STRICTEMENT MOINS de 30 tuiles (ici 10) : les trois conditions du point
    7 sont réunies — le joker, normalement gardé (voir ``test_joker_en_
    main_non_utile_est_garde``, nb_manches=1), est posé quand même (une
    pose existait déjà pour lui dans le coup de base, même sans gain)."""
    etat = _etat_joker_non_utile_fin_match(
        nb_manches=2, tuiles_adversaire=2, taille_pioche=10)
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {
        "joker_1", "rouge_7_a", "rouge_8_a", "rouge_9_a"}
    assert coup["joker"]["jokers_main_gardes"] == 0
    assert coup["joker"]["jokers_debarrasses_fin_match"] == 1


def test_joker_garde_si_match_a_une_seule_manche():
    """Voisin : match à UNE SEULE manche (``nb_manches=1``, défaut) — la
    règle du point 7 ne s'applique JAMAIS, même avec un adversaire à 2
    tuiles et une pioche à 10 tuiles (identique à ``test_joker_en_main_non_
    utile_est_garde``) : perdre avec ou sans joker en main ne change rien
    à une seule manche."""
    etat = _etat_joker_non_utile_fin_match(
        nb_manches=1, tuiles_adversaire=2, taille_pioche=10)
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_7_a", "rouge_8_a", "rouge_9_a"}
    assert coup["joker"]["jokers_main_gardes"] == 1
    assert coup["joker"]["jokers_debarrasses_fin_match"] == 0


def test_joker_garde_si_aucun_adversaire_a_au_plus_deux_tuiles():
    """Voisin (valeur limite) : match à 2 manches, pioche à 10 tuiles, mais
    l'adversaire a 3 tuiles — STRICTEMENT AU-DESSUS du seuil « au plus 2 » :
    le joker reste gardé."""
    etat = _etat_joker_non_utile_fin_match(
        nb_manches=2, tuiles_adversaire=3, taille_pioche=10)
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert set(coup["ids_tuiles"]) == {"rouge_7_a", "rouge_8_a", "rouge_9_a"}
    assert coup["joker"]["jokers_debarrasses_fin_match"] == 0


def test_joker_garde_si_pioche_a_trente_tuiles_exactement():
    """Voisin (valeur limite) : match à 2 manches, adversaire à 2 tuiles,
    mais la pioche contient EXACTEMENT 30 tuiles — pas « strictement moins
    de 30 » : le joker reste gardé."""
    etat = _etat_joker_non_utile_fin_match(
        nb_manches=2, tuiles_adversaire=2, taille_pioche=30)
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert set(coup["ids_tuiles"]) == {"rouge_7_a", "rouge_8_a", "rouge_9_a"}
    assert coup["joker"]["jokers_debarrasses_fin_match"] == 0


def test_joker_debarrasse_si_pioche_a_vingt_neuf_tuiles():
    """Voisin immédiat du précédent, juste sous le seuil (29 < 30) : le
    joker est posé."""
    etat = _etat_joker_non_utile_fin_match(
        nb_manches=2, tuiles_adversaire=2, taille_pioche=29)
    coup = jouer_niveau_bride(etat, 1, "Expert")
    assert set(coup["ids_tuiles"]) == {
        "joker_1", "rouge_7_a", "rouge_8_a", "rouge_9_a"}
    assert coup["joker"]["jokers_debarrasses_fin_match"] == 1


def test_regle_fin_de_match_desactivable_en_simulation():
    """``DEBARRAS_JOKER_FIN_MATCH_ACTIF=False`` désactive la règle entière
    (#254, point 7), même si toutes les conditions numériques sont
    réunies — utilisé par les scripts de simulation."""
    etat = _etat_joker_non_utile_fin_match(
        nb_manches=2, tuiles_adversaire=2, taille_pioche=10)
    ancien = _niveaux.DEBARRAS_JOKER_FIN_MATCH_ACTIF
    _niveaux.DEBARRAS_JOKER_FIN_MATCH_ACTIF = False
    try:
        coup = jouer_niveau_bride(etat, 1, "Expert")
    finally:
        _niveaux.DEBARRAS_JOKER_FIN_MATCH_ACTIF = ancien
    assert set(coup["ids_tuiles"]) == {"rouge_7_a", "rouge_8_a", "rouge_9_a"}
    assert coup["joker"]["jokers_debarrasses_fin_match"] == 0


# --------------------------------------------------------------------------- #
# Débutant/Facile inchangés ; drapeau de désactivation
# --------------------------------------------------------------------------- #

def _etat_gift_evitable(niveau):
    """Reprend le fixture historique de #252 : sous la NOUVELLE définition
    (#253), ce joker (bout d'une suite de 3 tuiles seulement) n'est PAS
    libre — seul sert ici à vérifier que Débutant/Facile, et la règle
    désactivée, jouent bien le coup le plus riche SANS aucune des nouvelles
    vérifications."""
    etat = _bot(niveau, plateau=[], chevalet=[
        _t("joker_1", est_joker=True),
        _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
        _t("bleu_5_a", 5, "bleu"), _t("bleu_6_a", 6, "bleu"),
        _t("bleu_7_a", 7, "bleu"), _t("noir_2_a", 2, "noir"),
    ])
    return etat


def test_debutant_et_facile_inchanges():
    for niveau in ("Débutant", "Facile"):
        assert _niveaux.bridage_pour(niveau).eviter_don_joker is False
        etat = _etat_gift_evitable(niveau)
        coup = jouer_niveau_bride(etat, 1, niveau, rng=_RngFixe(0.99))
        if coup.get("action") == "jouer":
            assert "joker" not in coup


def test_niveaux_superieurs_ont_la_regle_activee():
    for niveau in ("Intermédiaire", "Avancé", "Expert"):
        assert _niveaux.bridage_pour(niveau).eviter_don_joker is True


def test_regle_desactivee_reproduit_le_comportement_d_avant_252():
    etat = _etat_gift_evitable("Expert")
    coup = jouer_niveau_bride(etat, 1, "Expert", eviter_don_joker=False)
    assert coup["action"] == "jouer"
    # Comportement d'avant #252 : le coup le plus riche (6 tuiles), jamais
    # dégradé ni soumis à aucune des règles de #253.
    assert set(coup["ids_tuiles"]) == {
        "joker_1", "rouge_7_a", "rouge_8_a",
        "bleu_5_a", "bleu_6_a", "bleu_7_a"}
    assert "joker" not in coup
