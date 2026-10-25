"""Tests des cinq niveaux d'IA."""

from rummikub.moteur.ia import (
    jouer_ia, jouer_niveau_avance, jouer_niveau_expert,
    jouer_niveau_facile, jouer_niveau_intermediaire, NIVEAUX_IA,
)
from rummikub.moteur.partie import creer_partie
from rummikub.moteur.validation import valider_plateau
from rummikub.moteur.tuiles import tuile_depuis_dict


def _partie_2j(niveau="Débutant"):
    return creer_partie(
        [{"nom": "Humain", "est_ia": False, "niveau": None},
         {"nom": "Bot", "est_ia": True, "niveau": niveau}],
        {"nb_manches": 1, "valeur_joker_penalite": 30,
         "mise_initiale_min": 30})


def test_ia_debutant_ne_plante_pas():
    etat = _partie_2j("Débutant")
    etat["index_joueur_actuel"] = 1
    res = jouer_ia(etat, 1)
    assert res["action"] in ("jouer", "piocher", "passer")


def test_tous_niveaux_ne_plantent_pas():
    for n in NIVEAUX_IA:
        etat = _partie_2j(n)
        etat["index_joueur_actuel"] = 1
        res = jouer_ia(etat, 1)
        assert res["action"] in ("jouer", "piocher", "passer"), \
            f"Niveau {n} a retourné action invalide"


def test_debutant_action_valide():
    etat = _partie_2j("Débutant")
    etat["index_joueur_actuel"] = 1
    res = jouer_ia(etat, 1)
    assert "action" in res and "ids_tuiles" in res


def test_expert_action_valide():
    etat = _partie_2j("Expert")
    etat["index_joueur_actuel"] = 1
    res = jouer_ia(etat, 1)
    assert res["action"] in ("jouer", "piocher", "passer")


def test_ia_jouer_coup_valide():
    """Si l'IA choisit 'jouer', le plateau proposé doit être valide."""
    for n in NIVEAUX_IA:
        etat = _partie_2j(n)
        etat["index_joueur_actuel"] = 1
        etat["joueurs"][1]["mise_initiale_faite"] = True
        res = jouer_ia(etat, 1)
        if res["action"] == "jouer" and res["nouveau_plateau"]:
            plateau = [[tuile_depuis_dict(d) for d in c]
                       for c in res["nouveau_plateau"]]
            r = valider_plateau(plateau)
            assert r["valide"], f"Niveau {n} : plateau IA invalide"


def _etat_avec_joker_recuperable(niveau):
    """Plateau : suite rouge 4-5-(joker=6).

    Chevalet du bot : un rouge 6 (pour reprendre le joker), un noir 9 et un
    bleu 9 (ne forment un groupe complet qu'avec le joker libéré), et un
    rouge 7 qui permettrait l'extension la plus simple sans toucher au
    joker — c'est ce dernier coup, moins intéressant, que jouent Facile et
    Intermédiaire.
    """
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "rouge_4_a", "valeur": 4, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_5_a", "valeur": 5, "couleur": "rouge", "est_joker": False},
        {"id": "joker_1", "valeur": None, "couleur": None, "est_joker": True},
    ]]
    bot["chevalet"] = [
        {"id": "rouge_6_b", "valeur": 6, "couleur": "rouge", "est_joker": False},
        {"id": "noir_9_a", "valeur": 9, "couleur": "noir", "est_joker": False},
        {"id": "bleu_9_a", "valeur": 9, "couleur": "bleu", "est_joker": False},
        {"id": "rouge_7_a", "valeur": 7, "couleur": "rouge", "est_joker": False},
    ]
    return etat


def test_avance_prefere_recuperer_le_joker():
    """Avancé compare le coup évident à la récupération du joker et choisit
    la seconde, nettement meilleure ici (4 tuiles posées contre 1)."""
    etat = _etat_avec_joker_recuperable("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {
        "rouge_6_b", "noir_9_a", "bleu_9_a", "rouge_7_a"}
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]


def test_expert_prefere_recuperer_le_joker():
    etat = _etat_avec_joker_recuperable("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {
        "rouge_6_b", "noir_9_a", "bleu_9_a", "rouge_7_a"}


def test_facile_ne_recupere_pas_le_joker():
    """Facile/Intermédiaire restent inchangés : extension évidente (rouge 7)
    sans tenter d'échanger le joker du plateau."""
    etat = _etat_avec_joker_recuperable("Facile")
    coup = jouer_niveau_facile(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_7_a"}


def test_intermediaire_ne_recupere_pas_le_joker():
    etat = _etat_avec_joker_recuperable("Intermédiaire")
    coup = jouer_niveau_intermediaire(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_7_a"}


def _etat_avec_joker_detachable(niveau):
    """Plateau : suite rouge 3-4-(joker=5).

    Chevalet du bot : un rouge 2 (allonge l'AUTRE bout, rendant 3-4 seul
    valide une fois le joker détaché), un noir 9 et un bleu 9 (ne forment un
    groupe complet qu'avec le joker libéré), et un rouge 6 qui permet
    d'étendre la suite directement après le joker sans le détacher — Facile
    et Intermédiaire se contentent d'étendre les deux bouts (rouge 2 et
    rouge 6, 2 tuiles) sans jamais toucher au joker.
    """
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "rouge_3_a", "valeur": 3, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_4_a", "valeur": 4, "couleur": "rouge", "est_joker": False},
        {"id": "joker_1", "valeur": None, "couleur": None, "est_joker": True},
    ]]
    bot["chevalet"] = [
        {"id": "rouge_2_a", "valeur": 2, "couleur": "rouge", "est_joker": False},
        {"id": "noir_9_a", "valeur": 9, "couleur": "noir", "est_joker": False},
        {"id": "bleu_9_a", "valeur": 9, "couleur": "bleu", "est_joker": False},
        {"id": "rouge_6_a", "valeur": 6, "couleur": "rouge", "est_joker": False},
    ]
    return etat


def test_avance_detache_le_joker_en_bout_de_suite():
    """Avancé compare l'extension évidente au détachement du joker libéré
    par l'extension de l'autre bout, et choisit ce dernier, meilleur ici
    (3 tuiles posées contre 2)."""
    etat = _etat_avec_joker_detachable("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_2_a", "noir_9_a", "bleu_9_a"}
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]


def test_expert_detache_le_joker_en_bout_de_suite():
    etat = _etat_avec_joker_detachable("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_2_a", "noir_9_a", "bleu_9_a"}


def test_facile_ne_detache_pas_le_joker():
    """Facile/Intermédiaire restent inchangés : étendent les deux bouts de
    la suite (rouge 2 et rouge 6) sans jamais détacher le joker du plateau,
    qui reste coincé entre les tuiles réelles."""
    etat = _etat_avec_joker_detachable("Facile")
    coup = jouer_niveau_facile(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_2_a", "rouge_6_a"}


def test_intermediaire_ne_detache_pas_le_joker():
    etat = _etat_avec_joker_detachable("Intermédiaire")
    coup = jouer_niveau_intermediaire(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_2_a", "rouge_6_a"}


def _etat_avec_deux_jokers_recuperables(niveau):
    """Plateau avec DEUX jokers récupérables par échange direct, sur deux
    suites distinctes (régression #169).

    Chevalet du bot : rouge 6 et bleu 9 (une tuile de reprise par joker),
    plus noir 2/jaune 2/noir 3/jaune 3 qui, seuls, ne forment aucune
    combinaison valide (2 couleurs par valeur seulement). Sans récupérer
    ET replacer les DEUX jokers dans le même coup (noir 2 + noir 3 +
    joker + joker formant une suite 1-2-3-4 en noir), l'IA ne peut rien
    jouer du tout ici : aucune extension ni combinaison simple n'existe.
    """
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [
        [
            {"id": "rouge_4_a", "valeur": 4, "couleur": "rouge", "est_joker": False},
            {"id": "rouge_5_a", "valeur": 5, "couleur": "rouge", "est_joker": False},
            {"id": "joker_1", "valeur": None, "couleur": None, "est_joker": True},
        ],
        [
            {"id": "bleu_7_a", "valeur": 7, "couleur": "bleu", "est_joker": False},
            {"id": "bleu_8_a", "valeur": 8, "couleur": "bleu", "est_joker": False},
            {"id": "joker_2", "valeur": None, "couleur": None, "est_joker": True},
        ],
    ]
    bot["chevalet"] = [
        {"id": "rouge_6_b", "valeur": 6, "couleur": "rouge", "est_joker": False},
        {"id": "bleu_9_a", "valeur": 9, "couleur": "bleu", "est_joker": False},
        {"id": "noir_2_a", "valeur": 2, "couleur": "noir", "est_joker": False},
        {"id": "jaune_2_a", "valeur": 2, "couleur": "jaune", "est_joker": False},
        {"id": "noir_3_a", "valeur": 3, "couleur": "noir", "est_joker": False},
        {"id": "jaune_3_a", "valeur": 3, "couleur": "jaune", "est_joker": False},
    ]
    return etat


def test_avance_recupere_les_deux_jokers_a_la_fois():
    """Régression #169 : deux jokers récupérables par échange direct sur
    deux suites distinctes doivent être récupérés dans le MÊME coup, et
    pas seulement l'un des deux (seule façon de jouer ici)."""
    etat = _etat_avec_deux_jokers_recuperables("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] == "jouer"
    assert {"rouge_6_b", "bleu_9_a"} <= set(coup["ids_tuiles"])
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]
    combo_rouge = next(c for c in plateau
                       if any(t.id == "rouge_6_b" for t in c))
    combo_bleu = next(c for c in plateau
                      if any(t.id == "bleu_9_a" for t in c))
    assert not any(t.est_joker for t in combo_rouge)
    assert not any(t.est_joker for t in combo_bleu)


def test_expert_recupere_les_deux_jokers_a_la_fois():
    etat = _etat_avec_deux_jokers_recuperables("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert {"rouge_6_b", "bleu_9_a"} <= set(coup["ids_tuiles"])


def _etat_avec_reduction_groupe4(niveau):
    """Reprend l'exemple de l'issue #180 : un groupe de trois 11 (bleu,
    jaune, noir) plus le 11 rouge de la main devient un groupe de quatre ;
    le 11 noir libéré correspond exactement au joker d'une suite noire
    10-joker-12-13 présente ailleurs sur le plateau.

    Chevalet du bot : 11 rouge (complète le groupe à 4 et libère le 11
    noir), 1 et 2 noirs (pour rejouer le joker libéré dans une nouvelle
    suite 1-2-3(joker) noire) — sans cette combinaison, l'IA ne peut rien
    jouer d'autre ici.
    """
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [
        [
            {"id": "bleu_11_a", "valeur": 11, "couleur": "bleu", "est_joker": False},
            {"id": "jaune_11_a", "valeur": 11, "couleur": "jaune", "est_joker": False},
            {"id": "noir_11_a", "valeur": 11, "couleur": "noir", "est_joker": False},
        ],
        [
            {"id": "noir_10_a", "valeur": 10, "couleur": "noir", "est_joker": False},
            {"id": "joker_1", "valeur": None, "couleur": None, "est_joker": True},
            {"id": "noir_12_a", "valeur": 12, "couleur": "noir", "est_joker": False},
            {"id": "noir_13_a", "valeur": 13, "couleur": "noir", "est_joker": False},
        ],
    ]
    bot["chevalet"] = [
        {"id": "rouge_11_a", "valeur": 11, "couleur": "rouge", "est_joker": False},
        {"id": "noir_1_a", "valeur": 1, "couleur": "noir", "est_joker": False},
        {"id": "noir_2_a", "valeur": 2, "couleur": "noir", "est_joker": False},
    ]
    return etat


def test_avance_libere_une_tuile_de_groupe4_pour_echanger_un_joker():
    """Issue #180 : Avancé complète le groupe à 4 (11 rouge), libère le 11
    noir, l'échange contre le joker noir, et rejoue ce dernier dans une
    nouvelle suite 1-2-3(joker) noire — seule façon de poser les 3 tuiles
    de la main ici."""
    etat = _etat_avec_reduction_groupe4("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_11_a", "noir_1_a", "noir_2_a"}
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]
    combo_groupe = next(c for c in plateau
                        if any(t.id == "rouge_11_a" for t in c))
    assert len(combo_groupe) == 3
    assert not any(t.id == "noir_11_a" for t in combo_groupe)
    assert not any(t.est_joker for c in plateau for t in c
                   if any(tt.id == "noir_10_a" for tt in c))


def test_expert_libere_une_tuile_de_groupe4_pour_echanger_un_joker():
    etat = _etat_avec_reduction_groupe4("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_11_a", "noir_1_a", "noir_2_a"}


def test_facile_ne_libere_pas_de_tuile_de_groupe4():
    """Facile/Intermédiaire restent inchangés : complète le groupe à 4 avec
    le 11 rouge sans jamais tenter d'échanger un joker ailleurs."""
    etat = _etat_avec_reduction_groupe4("Facile")
    coup = jouer_niveau_facile(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_11_a"}


def _etat_avec_tuile_interieure_liberable(niveau):
    """Issue #181 : suite rouge 1-2-3-4-5-6-7 ; le chevalet du bot a un 4
    bleu et un 4 jaune. Retirer le 4 rouge (position intérieure) laisse
    deux suites valides (1-2-3 et 5-6-7) et libère une tuile qui forme avec
    la main le groupe de 4 (rouge/bleu/jaune)."""
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "rouge_1_a", "valeur": 1, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_2_a", "valeur": 2, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_3_a", "valeur": 3, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_4_a", "valeur": 4, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_5_a", "valeur": 5, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_6_a", "valeur": 6, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_7_a", "valeur": 7, "couleur": "rouge", "est_joker": False},
    ]]
    bot["chevalet"] = [
        {"id": "bleu_4_a", "valeur": 4, "couleur": "bleu", "est_joker": False},
        {"id": "jaune_4_a", "valeur": 4, "couleur": "jaune", "est_joker": False},
    ]
    return etat


def test_avance_scinde_une_suite_pour_liberer_une_tuile_interieure():
    """Avancé retire le 4 rouge en milieu de suite, scindant la suite en
    deux (1-2-3 et 5-6-7), pour former le groupe des 4 avec la main."""
    etat = _etat_avec_tuile_interieure_liberable("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"bleu_4_a", "jaune_4_a"}
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]
    assert len(plateau) == 3
    groupe_4 = next(c for c in plateau if any(t.id == "bleu_4_a" for t in c))
    assert {t.id for t in groupe_4} == {"rouge_4_a", "bleu_4_a", "jaune_4_a"}


def test_expert_scinde_une_suite_pour_liberer_une_tuile_interieure():
    etat = _etat_avec_tuile_interieure_liberable("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"bleu_4_a", "jaune_4_a"}


def test_facile_ne_scinde_pas_une_suite_en_son_milieu():
    """Non-régression : Facile/Intermédiaire ne savent pas scinder une
    suite en son milieu (seuls Avancé/Expert le tentent) — avec seulement
    deux tuiles de valeur 4 en main, aucun coup n'est jouable."""
    etat = _etat_avec_tuile_interieure_liberable("Facile")
    coup = jouer_niveau_facile(etat, 1)
    assert coup["action"] != "jouer"


def _etat_avec_joker_interieur_liberable(niveau):
    """Issue #181 : suite bleue 3-4-5-(joker)-7-8-9 ; le chevalet du bot a
    un 12 rouge et un 12 jaune. Retirer le joker (position intérieure)
    laisse deux suites valides (3-4-5 et 7-8-9) et libère un joker rejoué
    avec la main dans un groupe de 12 (rouge/jaune/joker)."""
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "bleu_3_a", "valeur": 3, "couleur": "bleu", "est_joker": False},
        {"id": "bleu_4_a", "valeur": 4, "couleur": "bleu", "est_joker": False},
        {"id": "bleu_5_a", "valeur": 5, "couleur": "bleu", "est_joker": False},
        {"id": "joker_1", "valeur": None, "couleur": None, "est_joker": True},
        {"id": "bleu_7_a", "valeur": 7, "couleur": "bleu", "est_joker": False},
        {"id": "bleu_8_a", "valeur": 8, "couleur": "bleu", "est_joker": False},
        {"id": "bleu_9_a", "valeur": 9, "couleur": "bleu", "est_joker": False},
    ]]
    bot["chevalet"] = [
        {"id": "rouge_12_a", "valeur": 12, "couleur": "rouge", "est_joker": False},
        {"id": "jaune_12_a", "valeur": 12, "couleur": "jaune", "est_joker": False},
    ]
    return etat


def test_avance_scinde_une_suite_pour_liberer_un_joker_interieur():
    """Avancé retire le joker en milieu de suite, scindant la suite en deux
    (3-4-5 et 7-8-9), et rejoue le joker libéré dans un nouveau groupe de 12
    avec la main — seule façon de jouer les deux tuiles de la main ici."""
    etat = _etat_avec_joker_interieur_liberable("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_12_a", "jaune_12_a"}
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]
    assert len(plateau) == 3
    groupe_12 = next(c for c in plateau
                     if any(t.id == "rouge_12_a" for t in c))
    assert any(t.est_joker for t in groupe_12)
    assert not any(t.est_joker for c in plateau for t in c
                   if not any(tt.id == "rouge_12_a" for tt in c))


def test_expert_scinde_une_suite_pour_liberer_un_joker_interieur():
    etat = _etat_avec_joker_interieur_liberable("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_12_a", "jaune_12_a"}


def test_avance_ne_scinde_pas_une_suite_trop_courte():
    """Suite rouge 3-4-5-6-7 (longueur 5) : retirer la tuile centrale (5)
    laisserait deux parties de longueur 2, invalides — trop courte pour
    être scindée en son milieu, même si la main a de quoi former un groupe
    avec la tuile centrale (5 bleu / 5 jaune). Le coup ne doit pas être
    proposé."""
    etat = _partie_2j("Avancé")
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "rouge_3_a", "valeur": 3, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_4_a", "valeur": 4, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_5_a", "valeur": 5, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_6_a", "valeur": 6, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_7_a", "valeur": 7, "couleur": "rouge", "est_joker": False},
    ]]
    bot["chevalet"] = [
        {"id": "bleu_5_a", "valeur": 5, "couleur": "bleu", "est_joker": False},
        {"id": "jaune_5_a", "valeur": 5, "couleur": "jaune", "est_joker": False},
    ]
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] != "jouer"


def _etat_avec_groupe4_joker_sans_remplacement(niveau):
    """Issue #183 : groupe plateau de trois 9 (rouge, bleu, jaune) plus un
    joker (groupe de 4 valide). Retirer le joker laisse les trois 9 seuls,
    toujours un groupe valide — sans aucune tuile de remplacement. Chevalet
    du bot : 12 rouge et 12 jaune, pour rejouer le joker libéré dans un
    nouveau groupe de 12 (rouge/jaune/joker)."""
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "rouge_9_a", "valeur": 9, "couleur": "rouge", "est_joker": False},
        {"id": "bleu_9_a", "valeur": 9, "couleur": "bleu", "est_joker": False},
        {"id": "jaune_9_a", "valeur": 9, "couleur": "jaune", "est_joker": False},
        {"id": "joker_1", "valeur": None, "couleur": None, "est_joker": True},
    ]]
    bot["chevalet"] = [
        {"id": "rouge_12_a", "valeur": 12, "couleur": "rouge", "est_joker": False},
        {"id": "jaune_12_a", "valeur": 12, "couleur": "jaune", "est_joker": False},
    ]
    return etat


def test_avance_libere_un_joker_de_groupe4_sans_remplacement():
    """Issue #183 : Avancé retire le joker du groupe de 9 (réduit à 3,
    toujours valide, aucune tuile de remplacement) et le rejoue dans un
    nouveau groupe de 12 avec la main — seule façon de jouer les deux
    tuiles de la main ici."""
    etat = _etat_avec_groupe4_joker_sans_remplacement("Avancé")
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_12_a", "jaune_12_a"}
    plateau = [[tuile_depuis_dict(d) for d in c]
               for c in coup["nouveau_plateau"]]
    assert valider_plateau(plateau)["valide"]
    groupe_9 = next(c for c in plateau if any(t.id == "rouge_9_a" for t in c))
    assert len(groupe_9) == 3
    assert not any(t.est_joker for t in groupe_9)
    groupe_12 = next(c for c in plateau
                     if any(t.id == "rouge_12_a" for t in c))
    assert any(t.est_joker for t in groupe_12)


def test_expert_libere_un_joker_de_groupe4_sans_remplacement():
    etat = _etat_avec_groupe4_joker_sans_remplacement("Expert")
    coup = jouer_niveau_expert(etat, 1)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_12_a", "jaune_12_a"}


def test_facile_ne_libere_pas_le_joker_de_groupe4():
    """Non-régression : Facile/Intermédiaire ne savent pas retirer un joker
    d'un groupe de 4 sans remplacement (seuls Avancé/Expert le tentent) —
    avec seulement deux tuiles de valeur 12 en main et un groupe de 4 déjà
    plein sur le plateau, aucun coup n'est jouable."""
    etat = _etat_avec_groupe4_joker_sans_remplacement("Facile")
    coup = jouer_niveau_facile(etat, 1)
    assert coup["action"] != "jouer"


def test_avance_ne_reduit_pas_un_groupe_de_3_avec_joker():
    """Un groupe de SEULEMENT 3 tuiles (2 réelles + 1 joker) ne peut pas
    perdre son joker : il ne resterait que 2 tuiles réelles, insuffisant
    pour un groupe valide. La réduction sans remplacement ne s'applique
    qu'aux groupes de 4 ; ici, le coup ne doit pas être proposé."""
    etat = _partie_2j("Avancé")
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = True
    etat["plateau"] = [[
        {"id": "rouge_9_a", "valeur": 9, "couleur": "rouge", "est_joker": False},
        {"id": "bleu_9_a", "valeur": 9, "couleur": "bleu", "est_joker": False},
        {"id": "joker_1", "valeur": None, "couleur": None, "est_joker": True},
    ]]
    bot["chevalet"] = [
        {"id": "rouge_12_a", "valeur": 12, "couleur": "rouge", "est_joker": False},
        {"id": "jaune_12_a", "valeur": 12, "couleur": "jaune", "est_joker": False},
    ]
    coup = jouer_niveau_avance(etat, 1)
    assert coup["action"] != "jouer"
