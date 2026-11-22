import pytest
from rummikub.moteur.tuiles import Tuile, creer_sac, distribuer
from rummikub.moteur.validation import (valider_suite, valider_groupe,
                                         valider_combinaison, valider_plateau)
from rummikub.moteur.partie import (creer_partie, jouer_tour, piocher,
                                     backup_debut_tour, annuler_tour,
                                     passer_tour, nouvelle_manche,
                                     est_fin_partie, normaliser_etat_reprise)


def t(v, c): return Tuile(f"{c}_{v}_a", v, c)
def j(n=1):  return Tuile(f"joker_{n}", None, None, est_joker=True)


def test_sac_106():
    assert len(creer_sac()) == 106


def test_distribution_3_joueurs():
    d = distribuer(creer_sac(), 3)
    assert all(len(c) == 14 for c in d["chevalets"])
    assert len(d["pioche"]) == 106 - 42


def test_distribution_4_joueurs():
    d = distribuer(creer_sac(), 4)
    assert len(d["pioche"]) == 106 - 56


def test_suite_valide():
    r = valider_suite([t(5, "rouge"), t(6, "rouge"), t(7, "rouge")])
    assert r["valide"] and r["points"] == 18


def test_suite_invalide_couleur():
    assert not valider_suite([t(5, "rouge"), t(6, "bleu"), t(7, "rouge")])["valide"]


def test_suite_trop_courte():
    assert not valider_suite([t(5, "rouge"), t(6, "rouge")])["valide"]


def test_suite_avec_joker_interne():
    r = valider_suite([t(5, "rouge"), j(), t(7, "rouge")])
    assert r["valide"] and r["points"] == 18


def test_suite_avec_joker_extension():
    r = valider_suite([t(5, "rouge"), t(6, "rouge"), t(7, "rouge"), j()])
    assert r["valide"] and r["points"] == 5 + 6 + 7 + 8


def test_groupe_valide():
    r = valider_groupe([t(7, "rouge"), t(7, "bleu"), t(7, "jaune")])
    assert r["valide"] and r["points"] == 21


def test_groupe_doublon_couleur():
    assert not valider_groupe([t(7, "rouge"), t(7, "rouge"), t(7, "jaune")])["valide"]


def test_groupe_5_tuiles():
    assert not valider_groupe([t(7, c) for c in ["rouge", "bleu", "jaune", "noir", "rouge"]])["valide"]


def test_groupe_avec_joker():
    r = valider_groupe([t(7, "rouge"), t(7, "bleu"), j()])
    assert r["valide"] and r["points"] == 21


def test_valider_combinaison_suite():
    r = valider_combinaison([t(5, "rouge"), t(6, "rouge"), t(7, "rouge")])
    assert r["valide"] and r["type"] == "suite"


def test_valider_combinaison_groupe():
    r = valider_combinaison([t(7, "rouge"), t(7, "bleu"), t(7, "jaune")])
    assert r["valide"] and r["type"] == "groupe"


def test_valider_combinaison_invalide():
    r = valider_combinaison([t(7, "rouge"), t(9, "rouge")])
    assert not r["valide"] and r["type"] is None


def test_valider_plateau_valide():
    r = valider_plateau([[t(5, "rouge"), t(6, "rouge"), t(7, "rouge")]])
    assert r["valide"] and r["erreurs"] == []


def test_valider_plateau_invalide():
    r = valider_plateau([[t(7, "rouge"), t(9, "rouge")]])
    assert not r["valide"]


def test_creer_partie_106_tuiles():
    etat = creer_partie(
        [{"nom": "A", "est_ia": False}, {"nom": "B", "est_ia": True, "niveau": "Facile"}],
        {"nb_manches": 1, "valeur_joker_penalite": 30, "mise_initiale_min": 30})
    total = (sum(len(j["chevalet"]) for j in etat["joueurs"])
             + len(etat["pioche"]))
    assert total == 106


def test_piocher():
    etat = creer_partie(
        [{"nom": "A", "est_ia": False}, {"nom": "B", "est_ia": True, "niveau": "Facile"}],
        {"nb_manches": 1, "valeur_joker_penalite": 30, "mise_initiale_min": 30})
    before = len(etat["joueurs"][0]["chevalet"])
    res = piocher(etat, 1)
    assert res["ok"]
    assert len(res["etat"]["joueurs"][0]["chevalet"]) == before + 1


def test_annuler_tour():
    etat = creer_partie(
        [{"nom": "A", "est_ia": False}, {"nom": "B", "est_ia": True, "niveau": "Facile"}],
        {"nb_manches": 1, "valeur_joker_penalite": 30, "mise_initiale_min": 30})
    backup_debut_tour(etat)
    nb_avant = len(etat["joueurs"][0]["chevalet"])
    piocher(etat, 3)
    annuler_tour(etat)
    assert len(etat["joueurs"][0]["chevalet"]) == nb_avant


def test_jouer_tour_refuse_si_des_tuiles_du_plateau_disparaissent():
    """Issue #187 : jouer_tour doit refuser tout coup dont le plateau
    résultant ne contient plus toutes les tuiles présentes en début de
    tour, même si chaque combinaison proposée est individuellement valide
    (ex. une combinaison déjà posée, amputée par erreur du plateau
    résultant)."""
    etat = creer_partie(
        [{"nom": "A", "est_ia": False}, {"nom": "B", "est_ia": True, "niveau": "Facile"}],
        {"nb_manches": 1, "valeur_joker_penalite": 30, "mise_initiale_min": 30})
    combo_a = [t(5, "rouge"), t(6, "rouge"), t(7, "rouge")]
    combo_b = [t(7, "bleu"), t(7, "jaune"), t(7, "noir")]
    etat["plateau"] = [[x.as_dict() for x in combo_a],
                       [x.as_dict() for x in combo_b]]
    etat["index_joueur_actuel"] = 0
    etat["joueurs"][0]["mise_initiale_faite"] = True
    etat["joueurs"][0]["chevalet"] = [t(1, "noir").as_dict(),
                                      t(2, "noir").as_dict(),
                                      t(3, "noir").as_dict()]

    # Plateau proposé : combo_a conservée, mais combo_b a disparu (remplacée
    # par une nouvelle combinaison valide formée depuis la main seule) —
    # exactement le symptôme du bug #187 (coup individuellement valide,
    # mais qui perd des tuiles déjà posées).
    nouveau_plateau = [[x.as_dict() for x in combo_a],
                       [t(1, "noir").as_dict(), t(2, "noir").as_dict(),
                        t(3, "noir").as_dict()]]
    res = jouer_tour(etat, ["noir_1_a", "noir_2_a", "noir_3_a"], nouveau_plateau)

    assert res["ok"] is False
    assert "disparu" in res["erreur"]
    assert set(res["tuiles_disparues"]) == {"bleu_7_a", "jaune_7_a", "noir_7_a"}
    # Le plateau d'origine ne doit pas avoir été modifié par le coup refusé.
    assert etat["plateau"] == [[x.as_dict() for x in combo_a],
                               [x.as_dict() for x in combo_b]]


# --------------------------------------------------------------------------- #
# Manches multiples (issue #203, suite de #192)
# --------------------------------------------------------------------------- #

def _partie(nb_manches, nb_joueurs=2):
    joueurs = [{"nom": "A", "est_ia": False}]
    for i in range(1, nb_joueurs):
        joueurs.append({"nom": f"IA{i}", "est_ia": True, "niveau": "Facile"})
    return creer_partie(
        joueurs,
        {"nb_manches": nb_manches, "valeur_joker_penalite": 30,
         "mise_initiale_min": 30})


def _finir_manche(etat, idx_gagnant, tuiles_perdants):
    """Termine la manche courante : le joueur ``idx_gagnant`` vide son
    chevalet, les autres gardent ``tuiles_perdants`` tuiles. Utilise
    ``passer_tour`` pour déclencher la fin de manche du moteur."""
    etat["index_joueur_actuel"] = idx_gagnant
    for i, joueur in enumerate(etat["joueurs"]):
        joueur["chevalet"] = ([] if i == idx_gagnant
                              else [x.as_dict() for x in tuiles_perdants])
    return passer_tour(etat)


def test_creer_partie_respecte_et_borne_nb_manches():
    """Issue #203 : `creer_partie` lit le nombre de manches demandé (et non
    plus un forçage à 1), en le bornant à [1, 9]. Un config.json ancien ou
    sans la clé retombe sur 1."""
    assert _partie(5)["config"]["nb_manches"] == 5
    assert _partie(1)["config"]["nb_manches"] == 1
    assert _partie(20)["config"]["nb_manches"] == 9   # borné à 9
    assert _partie(0)["config"]["nb_manches"] == 1    # borné à 1
    etat = creer_partie([{"nom": "A", "est_ia": False},
                         {"nom": "B", "est_ia": True, "niveau": "Facile"}],
                        {})  # aucune clé nb_manches
    assert etat["config"]["nb_manches"] == 1
    assert etat["manche_numero"] == 1


def test_une_seule_manche_termine_le_match():
    """Avec une seule manche (défaut), la fin de la manche termine le match."""
    etat = _partie(1)
    _finir_manche(etat, 0, [t(10, "rouge"), t(11, "rouge")])
    assert etat["manche_terminee"] is True
    assert est_fin_partie(etat) is True
    assert etat["terminee"] is True
    # Vainqueur du match = celui qui a vidé son chevalet (score cumulé le plus
    # élevé), joker à la valeur du réglage.
    assert etat["gagnant_match_index"] == 0
    assert etat["joueurs"][0]["score_cumul"] == 21   # 10 + 11
    assert etat["joueurs"][1]["score_cumul"] == -21


def test_manche_intermediaire_ne_termine_pas_le_match():
    """Avec plusieurs manches, la fin d'une manche NON finale ne termine pas
    le match (l'UI proposera « Manche suivante »)."""
    etat = _partie(3)
    _finir_manche(etat, 0, [t(5, "bleu"), t(6, "bleu")])
    assert etat["manche_terminee"] is True
    assert est_fin_partie(etat) is False
    assert etat.get("terminee") is not True
    assert "gagnant_match_index" not in etat


def test_nouvelle_manche_cumule_scores_et_tourne_le_donneur():
    """Issue #203 : nouvelle_manche incrémente le compteur, conserve le score
    cumulé, remet la manche à zéro (mise initiale, score de manche, nouvelle
    donne de 106 tuiles) et fait tourner le joueur qui commence."""
    etat = _partie(3)
    _finir_manche(etat, 0, [t(10, "rouge"), t(11, "rouge")])  # A gagne +21
    cumul_avant = [j["score_cumul"] for j in etat["joueurs"]]
    assert cumul_avant == [21, -21]

    nouvelle_manche(etat)
    assert etat["manche_numero"] == 2
    assert etat["manche_terminee"] is False
    # Rotation : la manche 2 commence par le joueur d'index 1.
    assert etat["index_joueur_actuel"] == 1
    assert etat["tour_numero"] == 1
    # Score cumulé conservé, score de manche et mise initiale remis à zéro.
    assert [j["score_cumul"] for j in etat["joueurs"]] == [21, -21]
    assert all(j["score_manche"] == 0 for j in etat["joueurs"])
    assert all(j["mise_initiale_faite"] is False for j in etat["joueurs"])
    assert all(len(j["chevalet"]) == 14 for j in etat["joueurs"])
    total = sum(len(j["chevalet"]) for j in etat["joueurs"]) + len(etat["pioche"])
    assert total == 106
    assert etat["plateau"] == [] and etat["dernier_coup_ia"] is None


def test_derniere_manche_designe_le_vainqueur_au_cumul():
    """À la dernière manche, le match est terminé et le gagnant est le joueur
    au score cumulé le plus élevé (pas forcément le gagnant de la dernière
    manche)."""
    etat = _partie(2)
    # Manche 1 : A vide son chevalet, B garde 40 pts → A +40, B -40.
    _finir_manche(etat, 0, [t(13, "rouge"), t(13, "bleu"), t(13, "jaune"),
                            t(1, "noir")])
    nouvelle_manche(etat)
    # Manche 2 : B vide son chevalet, A garde 5 pts → B +5, A -5.
    # Cumuls finaux : A = 40 - 5 = 35 ; B = -40 + 5 = -35 → A gagne le match
    # alors que B a gagné la DERNIÈRE manche.
    _finir_manche(etat, 1, [t(5, "noir")])
    assert est_fin_partie(etat) is True
    assert etat["terminee"] is True
    assert etat["joueurs"][0]["score_cumul"] == 35
    assert etat["joueurs"][1]["score_cumul"] == -35
    assert etat["gagnant_manche_index"] == 1       # B a gagné la manche 2
    assert etat["gagnant_match_index"] == 0        # A gagne le match (cumul)
    assert etat["egalite_match"] is False


def test_egalite_au_cumul_signalee():
    """En cas d'égalité des scores cumulés en fin de match, egalite_match est
    vrai (le classement affichera l'égalité)."""
    etat = _partie(2)
    _finir_manche(etat, 0, [t(5, "noir")])   # A +5, B -5
    nouvelle_manche(etat)
    _finir_manche(etat, 1, [t(5, "rouge")])  # B +5, A -5 → cumuls 0 et 0
    assert etat["terminee"] is True
    assert etat["joueurs"][0]["score_cumul"] == 0
    assert etat["joueurs"][1]["score_cumul"] == 0
    assert etat["egalite_match"] is True


def test_rotation_du_donneur_sur_tout_le_match():
    """La manche N commence par le joueur (N-1) % nb_joueurs."""
    etat = _partie(4, nb_joueurs=3)
    assert etat["index_joueur_actuel"] == 0        # manche 1 → joueur 0
    for attendu in (1, 2, 0):                       # manches 2, 3, 4
        _finir_manche(etat, 0, [t(5, "noir")])
        nouvelle_manche(etat)
        assert etat["index_joueur_actuel"] == attendu


def test_reprise_ancienne_sauvegarde_sans_compteur_de_manches():
    """Issue #203 : une partie sauvegardée avec nb_manches > 1 mais SANS
    compteur de manches (état d'avant les manches multiples) est reprise comme
    une partie d'une seule manche."""
    ancien = _partie(1)
    ancien["config"]["nb_manches"] = 5   # valeur enregistrée jadis
    del ancien["manche_numero"]          # état d'avant #203
    normaliser_etat_reprise(ancien)
    assert ancien["config"]["nb_manches"] == 1
    assert ancien["manche_numero"] == 1


def test_reprise_match_recent_au_milieu_conserve_les_manches():
    """Une partie récente reprise au MILIEU d'un match (manche 2 sur 3)
    conserve son nombre de manches et son compteur."""
    etat = _partie(3)
    _finir_manche(etat, 0, [t(5, "noir")])
    nouvelle_manche(etat)                # on est en manche 2
    assert etat["manche_numero"] == 2
    normaliser_etat_reprise(etat)        # reprise à l'identique
    assert etat["config"]["nb_manches"] == 3
    assert etat["manche_numero"] == 2


# --------------------------------------------------------------------------- #
# Blocage de manche : vraie règle du Rummikub (issue #255, remplace
# l'ancienne approximation « pioche vide termine la manche immédiatement »).
# --------------------------------------------------------------------------- #

def _vider_pioche_et_garnir(etat, chevalets):
    """Vide la pioche et donne à chaque joueur ``i`` le chevalet
    ``chevalets[i]`` (liste de Tuile) — prépare un scénario de blocage."""
    etat["pioche"] = []
    for i, tuiles in enumerate(chevalets):
        etat["joueurs"][i]["chevalet"] = [x.as_dict() for x in tuiles]
    etat["index_joueur_actuel"] = 0


def test_passer_tour_seul_ne_termine_pas_la_manche_meme_pioche_vide():
    """Un seul passage (pioche vide) ne suffit pas à bloquer la manche : il
    faut un tour COMPLET de passes (tous les joueurs)."""
    etat = _partie(1, nb_joueurs=2)
    _vider_pioche_et_garnir(etat, [[t(1, "noir")], [t(2, "noir")]])
    passer_tour(etat)
    assert etat["manche_terminee"] is False
    assert etat["passes_consecutives"] == 1
    assert etat["index_joueur_actuel"] == 1


def test_manche_se_termine_par_blocage_apres_un_tour_complet_de_passes():
    """2 joueurs : la manche se termine BLOQUÉE quand les deux ont passé de
    suite, pioche vide. Le gagnant est celui dont les tuiles restantes
    valent le moins de points (#255, point 4) — pas un chevalet vide."""
    etat = _partie(1, nb_joueurs=2)
    _vider_pioche_et_garnir(
        etat, [[t(1, "noir")], [t(13, "rouge"), t(13, "bleu")]])
    passer_tour(etat)   # joueur 0 passe
    assert etat["manche_terminee"] is False
    res = passer_tour(etat)   # joueur 1 passe : tour complet de passes
    assert res["ok"] is True
    assert etat["manche_terminee"] is True
    assert etat["manche_bloquee"] is True
    # Joueur 0 : 1 pt de pénalité ; joueur 1 : 26 pts → joueur 0 gagne.
    assert etat["gagnant_manche_index"] == 0
    assert etat["joueurs"][0]["score_manche"] == 26
    assert etat["joueurs"][1]["score_manche"] == -26
    assert etat["joueurs"][0]["score_cumul"] == 26
    assert etat["joueurs"][1]["score_cumul"] == -26


def test_pose_reinitialise_le_compteur_de_passes():
    """Une pose réussie remet le compteur de passes à 0 : le blocage exige
    un tour COMPLET de passes consécutives, sans aucune pose entre-temps."""
    etat = _partie(1, nb_joueurs=2)
    _vider_pioche_et_garnir(
        etat, [[t(1, "noir")],
              [t(5, "rouge"), t(6, "rouge"), t(7, "rouge"), t(9, "noir")]])
    passer_tour(etat)   # joueur 0 passe (compteur=1)
    assert etat["passes_consecutives"] == 1

    # Joueur 1 pose une suite valide (mise initiale déjà faite, hors mise),
    # SANS vider son chevalet (une tuile, noir_9, reste en main).
    etat["joueurs"][1]["mise_initiale_faite"] = True
    nouveau_plateau = [[t(5, "rouge").as_dict(), t(6, "rouge").as_dict(),
                        t(7, "rouge").as_dict()]]
    res = jouer_tour(etat, ["rouge_5_a", "rouge_6_a", "rouge_7_a"],
                     nouveau_plateau)
    assert res["ok"] is True
    assert etat["passes_consecutives"] == 0   # remis à 0 par la pose
    assert etat["manche_terminee"] is False    # pas encore un tour complet

    # Il faut repartir sur un tour complet de passes pour bloquer.
    passer_tour(etat)   # joueur 0
    assert etat["manche_terminee"] is False
    passer_tour(etat)   # joueur 1
    assert etat["manche_terminee"] is True
    assert etat["manche_bloquee"] is True


def test_piocher_sans_tuile_compte_comme_un_passe_pour_le_blocage():
    """``piocher`` sur une pioche déjà vide ne tire aucune tuile — #255 :
    équivaut à un passage pour le compteur de blocage (sinon la partie ne
    bloquerait jamais par cette voie)."""
    etat = _partie(1, nb_joueurs=2)
    _vider_pioche_et_garnir(etat, [[t(1, "noir")], [t(2, "noir")]])
    res = piocher(etat)
    assert res["tuiles_piochees"] == []
    assert etat["passes_consecutives"] == 1
    assert etat["manche_terminee"] is False
    res2 = piocher(etat)
    assert res2["tuiles_piochees"] == []
    assert etat["manche_terminee"] is True
    assert etat["manche_bloquee"] is True


def test_piocher_une_vraie_tuile_ne_touche_pas_au_compteur_de_passes():
    """Une pioche qui tire réellement une tuile (pile non vide) n'est pas un
    passage : le compteur de blocage n'est pas affecté."""
    etat = _partie(1, nb_joueurs=2)
    etat["joueurs"][0]["chevalet"] = [t(1, "noir").as_dict()]
    etat["joueurs"][1]["chevalet"] = [t(2, "noir").as_dict()]
    etat["index_joueur_actuel"] = 1
    etat["passes_consecutives"] = 1   # joueur 0 avait passé juste avant
    res = piocher(etat, 1)
    assert len(res["tuiles_piochees"]) == 1
    assert etat["passes_consecutives"] == 1   # inchangé (pioche non vide)


def test_manche_bloquee_a_trois_joueurs():
    """La règle de blocage fonctionne aussi à 3 joueurs (pas seulement 2) :
    il faut un tour COMPLET de 3 passes consécutives."""
    etat = _partie(1, nb_joueurs=3)
    _vider_pioche_et_garnir(
        etat, [[t(10, "noir")], [t(1, "noir")],
               [t(13, "rouge"), t(13, "bleu")]])
    passer_tour(etat)   # joueur 0
    assert etat["manche_terminee"] is False
    passer_tour(etat)   # joueur 1
    assert etat["manche_terminee"] is False
    passer_tour(etat)   # joueur 2 : tour complet
    assert etat["manche_terminee"] is True
    assert etat["manche_bloquee"] is True
    # Joueur 1 (1 pt) est le moins pénalisé : il gagne.
    assert etat["gagnant_manche_index"] == 1


def test_manche_bloquee_ne_peut_jamais_durer_indefiniment():
    """Garde-fou de construction (#255, point 5) : même si tous les joueurs
    passent indéfiniment (pioche vide), la manche se termine forcément au
    plus tard après ``nb_joueurs`` passages consécutifs — jamais de partie
    infinie par cette voie."""
    etat = _partie(1, nb_joueurs=4)
    _vider_pioche_et_garnir(
        etat, [[t(1, "noir")], [t(2, "noir")], [t(3, "noir")], [t(4, "noir")]])
    for _ in range(4):
        assert etat["manche_terminee"] is False
        passer_tour(etat)
    assert etat["manche_terminee"] is True
    assert etat["manche_bloquee"] is True


def test_reprise_partie_sauvegardee_avec_pioche_vide_continue_sans_erreur():
    """Issue #255, point 7 : une partie sauvegardée AVANT cette issue (donc
    sans ``passes_consecutives``/``manche_bloquee``), avec une pioche déjà
    vide et la manche non terminée, continue sous la nouvelle règle sans
    erreur — jusqu'au blocage normal."""
    etat = _partie(1, nb_joueurs=2)
    _vider_pioche_et_garnir(etat, [[t(1, "noir")], [t(2, "noir")]])
    del etat["passes_consecutives"]
    del etat["manche_bloquee"]

    normaliser_etat_reprise(etat)
    assert etat["passes_consecutives"] == 0
    assert etat["manche_bloquee"] is False

    passer_tour(etat)
    assert etat["manche_terminee"] is False
    passer_tour(etat)
    assert etat["manche_terminee"] is True
    assert etat["manche_bloquee"] is True


# --------------------------------------------------------------------------- #
# Réglage de TEST « fin de manche à la pioche vide » (issue #256, désactivé
# par défaut — réservé aux scripts de mesure, voir docs/contexte/
# ia_anti_don_joker.md §10). Ne touche jamais le comportement par défaut.
# --------------------------------------------------------------------------- #

def test_fin_manche_pioche_vide_test_desactivee_par_defaut_garde_la_regle_255():
    """Sans le réglage de test (défaut, comme tout appelant existant), la
    pioche vide après un coup ne termine PAS la manche : seul le blocage
    (#255) le fait — comportement strictement inchangé."""
    etat = _partie(1, nb_joueurs=2)
    _vider_pioche_et_garnir(etat, [[t(1, "noir")], [t(2, "noir")]])
    res = piocher(etat)   # pioche déjà vide, aucune tuile tirée
    assert res["tuiles_piochees"] == []
    assert etat["manche_terminee"] is False
    assert "manche_terminee_pioche_vide_test" not in etat


def test_fin_manche_pioche_vide_test_active_termine_des_que_la_pioche_est_vide():
    """Réglage de test activé (``fin_manche_pioche_vide=True``) : la manche
    se termine dès que la pioche est vide après le coup d'un joueur, SANS
    attendre le blocage — comme avant #255. Le gagnant est celui dont les
    tuiles restantes valent le moins de points (même décompte que la manche
    bloquée, #255)."""
    etat = _partie(1, nb_joueurs=2)
    etat["pioche"] = [t(1, "bleu").as_dict()]   # une seule tuile restante
    etat["joueurs"][0]["chevalet"] = [t(1, "noir").as_dict()]
    etat["joueurs"][1]["chevalet"] = [t(13, "rouge").as_dict(),
                                      t(13, "bleu").as_dict()]
    etat["index_joueur_actuel"] = 0

    res = piocher(etat, fin_manche_pioche_vide=True)   # vide la pioche
    assert res["tuiles_piochees"] != []
    assert etat["pioche"] == []
    assert etat["manche_terminee"] is True
    assert etat["manche_bloquee"] is False   # pas un vrai blocage
    assert etat["manche_terminee_pioche_vide_test"] is True
    # Joueur 0 : 1 pt de pénalité ; joueur 1 : 26 pts → joueur 0 gagne.
    assert etat["gagnant_manche_index"] == 0
    assert etat["joueurs"][0]["score_manche"] == 26
    assert etat["joueurs"][1]["score_manche"] == -26


def test_fin_manche_pioche_vide_test_via_passer_tour():
    """Le réglage de test s'applique aussi via ``passer_tour`` (joueur sans
    coup possible, pioche déjà vide) — pas seulement via ``piocher``."""
    etat = _partie(1, nb_joueurs=2)
    _vider_pioche_et_garnir(
        etat, [[t(1, "noir")], [t(13, "rouge"), t(13, "bleu")]])
    res = passer_tour(etat, fin_manche_pioche_vide=True)
    assert res["ok"] is True
    assert etat["manche_terminee"] is True
    assert etat["manche_bloquee"] is False
    assert etat["manche_terminee_pioche_vide_test"] is True
    assert etat["gagnant_manche_index"] == 0


def test_fin_manche_pioche_vide_test_ne_s_applique_pas_a_un_chevalet_vide():
    """Un coup qui vide le chevalet reste une victoire normale (chevalet
    vide), même avec le réglage de test activé et la pioche vide en même
    temps — l'exception du chevalet vide prime toujours."""
    etat = _partie(1, nb_joueurs=2)
    etat["pioche"] = []
    etat["joueurs"][0]["mise_initiale_faite"] = True
    etat["joueurs"][0]["chevalet"] = [t(5, "rouge").as_dict(),
                                      t(6, "rouge").as_dict(),
                                      t(7, "rouge").as_dict()]
    etat["joueurs"][1]["chevalet"] = [t(1, "noir").as_dict()]
    etat["index_joueur_actuel"] = 0
    nouveau_plateau = [[t(5, "rouge").as_dict(), t(6, "rouge").as_dict(),
                        t(7, "rouge").as_dict()]]
    res = jouer_tour(etat, ["rouge_5_a", "rouge_6_a", "rouge_7_a"],
                     nouveau_plateau, fin_manche_pioche_vide=True)
    assert res["ok"] is True
    assert etat["manche_terminee"] is True
    assert etat["manche_bloquee"] is False
    assert "manche_terminee_pioche_vide_test" not in etat
    assert etat["gagnant_manche_index"] == 0


def test_nouvelle_manche_efface_le_drapeau_de_test():
    """Le drapeau ``manche_terminee_pioche_vide_test`` ne doit jamais
    persister d'une manche à l'autre (``nouvelle_manche`` l'efface, comme
    ``manche_bloquee``)."""
    etat = _partie(2, nb_joueurs=2)
    _vider_pioche_et_garnir(
        etat, [[t(1, "noir")], [t(13, "rouge"), t(13, "bleu")]])
    passer_tour(etat, fin_manche_pioche_vide=True)
    assert etat.get("manche_terminee_pioche_vide_test") is True
    etat = nouvelle_manche(etat)
    assert "manche_terminee_pioche_vide_test" not in etat


def test_partie_deja_terminee_non_modifiee_par_la_reprise():
    """Une partie déjà terminée n'est pas modifiée par la normalisation de
    reprise (#255, point 7)."""
    etat = _partie(1, nb_joueurs=2)
    _finir_manche(etat, 0, [t(10, "rouge")])
    assert etat["terminee"] is True
    score_cumul_avant = [j["score_cumul"] for j in etat["joueurs"]]
    normaliser_etat_reprise(etat)
    assert etat["terminee"] is True
    assert [j["score_cumul"] for j in etat["joueurs"]] == score_cumul_avant
