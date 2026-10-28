import json
from pathlib import Path

from rummikub.moteur.tuiles import Tuile
from rummikub.moteur.description_coup import (
    decrire_coup_ia, etapes_coup_ia, mesurer_coup_ia,
    _contracter, _decrire_combo, _label_combo)

_DONNEES = Path(__file__).resolve().parent / "donnees"


def _charger_plateaux(nom):
    d = json.loads((_DONNEES / nom).read_text(encoding="utf-8"))
    return d["plateau_avant"], d["plateau_apres"]


def t(v, c, serie="a"):
    return Tuile(f"{c}_{v}_{serie}", v, c).as_dict()


def j(n=1, c="rouge"):
    return Tuile(f"joker_{n}", None, c, est_joker=True).as_dict()


def _ids_plateau(plateau):
    return [d["id"] for combo in plateau for d in combo]


def _ids_cadre(cadre):
    return [c["tuile"]["id"] for c in cadre]


def _verifier_invariants(avant, apres, etapes):
    """Invariants communs à toute suite d'étapes (issue #191, point 7) :
    - chaque tuile (plateau d'avant + tuiles posées) n'est jamais, à aucune
      étape, à deux endroits à la fois (plateau et cadre confondus) ;
    - la toute première étape est « Départ » et reproduit le plateau d'avant ;
    - la toute dernière étape reproduit exactement le plateau d'après, avec
      un cadre vide ;
    - aucune étape ne laisse le plateau+cadre inchangés par rapport à la
      précédente (pas d'étape sans effet visible)."""
    assert etapes[0]["titre"] == "Départ"
    ids_avant = sorted(sorted(d["id"] for d in c) for c in avant)
    ids_depart = sorted(sorted(d["id"] for d in c) for c in etapes[0]["plateau"])
    assert ids_depart == ids_avant

    precedent = None
    for etape in etapes:
        combines = _ids_plateau(etape["plateau"]) + _ids_cadre(etape["cadre"])
        assert len(combines) == len(set(combines)), \
            f"tuile dupliquée à l'étape {etape['titre'] or '(sans titre)'}"
        empreinte = (tuple(sorted(combines)),
                     tuple(sorted(_ids_plateau(etape["plateau"]))))
        # "Les jokers" est volontairement une vue d'ensemble qui ne change
        # rien au plateau/cadre de "Départ" juste avant : seules les étapes
        # SANS titre (les changements réels) doivent toujours différer de
        # la précédente.
        if precedent is not None and not etape["titre"]:
            assert empreinte != precedent, "étape sans changement visible"
        precedent = empreinte

    assert etapes[-1]["cadre"] == []
    ids_apres = sorted(sorted(d["id"] for d in c) for c in apres)
    ids_derniere = sorted(sorted(d["id"] for d in c) for c in etapes[-1]["plateau"])
    assert ids_derniere == ids_apres


# ------------------------------------------------------------- contractions

def test_contraction_de_le_devient_du_pour_un_groupe():
    assert _contracter("de", "le groupe de 7") == "du groupe de 7"


def test_contraction_a_le_devient_au_pour_un_groupe():
    assert _contracter("à", "le groupe de 7") == "au groupe de 7"


def test_contraction_de_la_suite_ne_se_contracte_pas():
    assert _contracter("de", "la suite rouge (5 à 9)") == "de la suite rouge (5 à 9)"
    assert _contracter("à", "la suite rouge (5 à 9)") == "à la suite rouge (5 à 9)"


def test_contraction_de_les_devient_des():
    assert _contracter("de", "les groupes de 7 et 8") == "des groupes de 7 et 8"


def test_contraction_a_les_devient_aux():
    assert _contracter("à", "les suites rouge et bleue") == "aux suites rouge et bleue"


def test_decrire_combo_groupe_et_suite_avec_contraction_en_contexte():
    groupe = [t(7, "rouge"), t(7, "bleu"), t(7, "jaune")]
    suite = [t(5, "noir"), t(6, "noir"), t(7, "noir")]
    assert _contracter("de", _decrire_combo(groupe)) == "du groupe de 7"
    assert _contracter("à", _decrire_combo(groupe)) == "au groupe de 7"
    assert _contracter("de", _decrire_combo(suite)) == "de la suite noire (5 à 7)"
    assert _contracter("à", _decrire_combo(suite)) == "à la suite noire (5 à 7)"


# -------------------------------------------- accords en français (issue #198)

def test_accord_suite_avec_les_quatre_couleurs():
    """« suite » est féminin : la couleur s'accorde (« noire », « bleue ») ou
    reste invariable (« rouge », « jaune » sont déjà identiques au féminin) —
    point 3 de l'issue #198."""
    attendu = {"rouge": "suite rouge", "bleu": "suite bleue",
               "jaune": "suite jaune", "noir": "suite noire"}
    for couleur, suffixe in attendu.items():
        suite = [t(5, couleur), t(6, couleur), t(7, couleur)]
        assert _decrire_combo(suite) == f"la {suffixe} (5 à 7)"
        assert _decrire_combo(suite, indef=True) == f"une {suffixe} (5 à 7)"
        assert _label_combo(suite) == suffixe


def test_accord_groupe_reste_invariable_avec_les_quatre_couleurs():
    """« groupe » est masculin et ne s'accorde jamais avec une couleur, qui
    reste toujours sous sa forme de base (« noir », jamais « noire »)."""
    for couleur in ("rouge", "bleu", "jaune", "noir"):
        groupe = [t(7, "rouge" if couleur != "rouge" else "bleu"),
                  t(7, couleur), t(7, "jaune" if couleur != "jaune" else "noir")]
        assert _decrire_combo(groupe) == "le groupe de 7"
        assert couleur in _decrire_combo(groupe, indef=True, couleurs=True)
        assert f"{couleur}e" not in _decrire_combo(groupe, indef=True, couleurs=True)


# --------------------------------------------------------------- coups simples

def test_coup_simple_extension_d_une_suite():
    avant = [[t(7, "rouge"), t(8, "rouge"), t(9, "rouge")]]
    apres = [[t(7, "rouge"), t(8, "rouge"), t(9, "rouge"), t(10, "rouge")]]

    r = decrire_coup_ia(avant, apres)

    assert r["nb_combinaisons_defaites"] == 0
    assert r["nb_combinaisons_creees"] == 0
    assert r["nb_combinaisons_modifiees"] == 1
    assert r["jokers_deplaces"] == []
    assert [d["id"] for d in r["tuiles_posees"]] == ["rouge_10_a"]
    assert "10 rouge" in r["texte"]
    assert "complét" in r["texte"]
    # Un coup simple ne touchant qu'une seule combinaison reste une phrase.
    assert r["texte"].count(".") == 1

    etapes = etapes_coup_ia(avant, apres)
    _verifier_invariants(avant, apres, etapes)
    # Départ + 1 seul changement visible : pas de bouton "Pas à pas" (le
    # front-end ne l'affiche qu'à partir de 2 changements, cf. jeu.js).
    changements = [e for e in etapes if not e["titre"]]
    assert len(changements) == 1


def test_coup_simple_nouveau_groupe():
    avant = []
    apres = [[t(7, "rouge"), t(7, "bleu"), t(7, "jaune")]]

    r = decrire_coup_ia(avant, apres)

    assert r["nb_combinaisons_defaites"] == 0
    assert r["nb_combinaisons_creees"] == 1
    assert r["nb_combinaisons_modifiees"] == 0
    assert len(r["tuiles_posees"]) == 3
    assert "groupe de 7" in r["texte"]
    assert "7 rouge" in r["texte"] and "7 bleu" in r["texte"] and "7 jaune" in r["texte"]


def test_coup_sans_changement():
    r = decrire_coup_ia([], [])
    assert r["texte"] == "N'a rien changé sur le plateau."
    assert r["nb_combinaisons_defaites"] == 0
    assert r["nb_combinaisons_creees"] == 0
    assert r["nb_combinaisons_modifiees"] == 0
    assert etapes_coup_ia([], []) == []


# ----------------------------------------------- joker récupéré puis rejoué

def test_joker_recupere_puis_rejoue_ailleurs():
    # Suite rouge 5-6-(7 en joker) : l'IA échange le joker contre le 7 rouge
    # réel de sa main, puis rejoue le joker libéré dans un nouveau groupe.
    avant = [[t(5, "rouge"), t(6, "rouge"), j(1)]]
    apres = [
        [t(5, "rouge"), t(6, "rouge"), t(7, "rouge")],
        [t(8, "noir"), t(8, "jaune"), j(1)],
    ]

    r = decrire_coup_ia(avant, apres)

    assert r["nb_combinaisons_defaites"] == 0  # la suite garde sa majorité
    assert r["nb_combinaisons_creees"] == 1
    assert r["nb_combinaisons_modifiees"] == 1
    assert len(r["jokers_deplaces"]) == 1
    depl = r["jokers_deplaces"][0]
    assert "suite rouge" in depl["depuis"]
    assert "groupe de 8" in depl["vers"]
    assert "joker" in r["texte"].lower()
    assert "groupe de 8" in r["texte"]
    # Contractions correctes dans la phrase du joker.
    assert "de la suite rouge" in r["texte"]
    assert "au groupe de 8" in r["texte"]

    etapes = etapes_coup_ia(avant, apres)
    _verifier_invariants(avant, apres, etapes)
    changements = [e for e in etapes if not e["titre"]]
    assert len(changements) >= 2  # touche plus d'une combinaison

    # L'écran "Les jokers" doit exister et préciser que le remplaçant (7
    # rouge) vient de la main, pas du plateau.
    jokers_ecran = next(e for e in etapes if e["titre"] == "Les jokers")
    assert "de sa main" in jokers_ecran["texte"]

    # Le joker doit être libéré (visible dans le cadre) avant d'être
    # réutilisé : trouver l'étape où il entre dans le cadre, puis celle où
    # il en sort, et vérifier l'ordre.
    idx_libere = next(i for i, e in enumerate(etapes)
                        if "joker_1" in _ids_cadre(e["cadre"]))
    idx_repris = next(i for i, e in enumerate(etapes)
                        if i > idx_libere and "joker_1" not in _ids_cadre(e["cadre"]))
    assert idx_libere < idx_repris


# --------------------------------------------------- démantèlement d'un groupe

def test_coup_touchant_plusieurs_combinaisons_demantele_un_groupe():
    # Un groupe de 12 est complètement démantelé : chacune de ses 3 tuiles
    # rejoint une combinaison DIFFÉRENTE, recomposée avec des tuiles de main.
    avant = [[t(12, "rouge"), t(12, "bleu"), t(12, "jaune")]]
    apres = [
        [t(10, "rouge"), t(11, "rouge"), t(12, "rouge")],
        [t(11, "bleu"), t(12, "bleu"), t(13, "bleu")],
        [t(12, "jaune"), t(12, "noir"), j(1)],
    ]

    r = decrire_coup_ia(avant, apres)

    assert r["nb_combinaisons_defaites"] == 1
    assert r["nb_combinaisons_creees"] == 3
    assert r["nb_combinaisons_modifiees"] == 0
    assert "groupe de 12" in r["texte"]
    assert "défait" in r["texte"]
    # Deux combinaisons différentes partagent le nom "groupe de 12" (celle
    # qui est défaite et celle qui est créée) : les couleurs désambiguïsent.
    assert "groupe de 12 rouge, bleu et jaune" in r["texte"]
    assert "groupe de 12 jaune, noir et joker" in r["texte"]
    ids_posees = {d["id"] for d in r["tuiles_posees"]}
    assert ids_posees == {"rouge_10_a", "rouge_11_a", "bleu_11_a",
                           "bleu_13_a", "noir_12_a", "joker_1"}

    # Découpage DÉTAILLÉ (condense=False, bouton « Détailler » du front-end,
    # issue #207) : une étape par mouvement de tuile.
    etapes = etapes_coup_ia(avant, apres, condense=False)
    _verifier_invariants(avant, apres, etapes)
    changements = [e for e in etapes if not e["titre"]]
    # 3 retraits (un par tuile, chacune vers une destination différente) + 3
    # créations.
    assert len(changements) == 6

    # Le groupe de 12 d'origine reste affiché, rétréci et "provisoire",
    # entre le moment où il perd sa première tuile et celui où il disparaît
    # (sa dernière tuile libérée).
    provisoires_vus = any(e["provisoires"] for e in etapes)
    assert provisoires_vus


# --------------------------------------------- coup en chaîne (Bruno, Expert)

def _plateau_bruno_simple():
    avant = [[t(3, "rouge"), t(3, "noir"), j(1)]]
    apres = [
        [t(3, "rouge"), t(3, "noir"), t(3, "bleu")],
        [t(11, "bleu"), t(11, "noir"), j(1)],
    ]
    return avant, apres


def test_bruno_cas_simple_texte_et_etapes():
    """Cas décrit dans le contexte de l'issue #191 : Bruno pose 3 bleu, 11
    bleu et 11 noir ; le 3 bleu remplace le joker du groupe de 3, et le
    joker libéré forme un nouveau groupe de 11 avec les deux 11 de la main."""
    avant, apres = _plateau_bruno_simple()

    r = decrire_coup_ia(avant, apres, nom="Bruno")
    assert r["texte"] == (
        "Bruno a posé 3 tuiles de sa main : 3 bleu, 11 bleu et 11 noir. "
        "Création d'un groupe de 11. "
        "Le 3 bleu remplace le joker dans le groupe de 3. "
        "Le joker est passé du groupe de 3 au groupe de 11.")

    etapes = etapes_coup_ia(avant, apres)
    _verifier_invariants(avant, apres, etapes)

    # Départ : plateau d'avant, cadre rempli des 3 tuiles de la main.
    depart = etapes[0]
    assert depart["titre"] == "Départ"
    assert {c["tuile"]["id"] for c in depart["cadre"]} == \
        {"bleu_3_a", "bleu_11_a", "noir_11_a"}
    assert all(c["origine"] == "main" for c in depart["cadre"])

    # "Les jokers" juste après "Départ" : c'est le cœur du coup (point 3bis).
    assert etapes[1]["titre"] == "Les jokers"

    # Exactement 2 changements visibles : le remplacement dans le groupe de
    # 3 (le joker rejoint le cadre), puis la formation du nouveau groupe de
    # 11 (le cadre se vide).
    changements = [e for e in etapes if not e["titre"]]
    assert len(changements) == 2
    assert "joker_1" in _ids_cadre(changements[0]["cadre"])
    assert changements[1]["cadre"] == []


def _plateau_bruno_expert_chaine():
    """Coup en chaîne observé en jeu (Bruno, Expert, issue #191 point 7)."""
    groupe11 = [t(11, "bleu"), t(11, "noir"), j(1)]
    groupe12 = [t(12, "rouge"), t(12, "bleu"), t(12, "noir")]
    suite_jaune = [t(11, "jaune"), t(12, "jaune"), t(13, "jaune")]
    suite_noire = [t(6, "noir"), t(7, "noir"), t(8, "noir"), t(9, "noir"),
                    t(10, "noir"), t(11, "noir", "b")]
    groupe7 = [t(7, "noir", "b"), t(7, "jaune"), t(7, "rouge")]
    avant = [groupe11, groupe12, suite_jaune, suite_noire, groupe7]

    apres = [
        [t(13, "bleu"), t(13, "jaune"), j(1)],
        [t(7, "rouge"), t(7, "bleu"), t(7, "jaune"), t(7, "noir", "b")],
        [t(12, "rouge"), t(12, "bleu"), t(12, "jaune")],
        [t(11, "bleu"), t(11, "jaune"), t(11, "noir")],
        [t(6, "noir"), t(7, "noir"), t(8, "noir")],
        [t(9, "noir"), t(10, "noir"), t(11, "noir", "b"), t(12, "noir")],
    ]
    return avant, apres


def test_chaine_bruno_expert_enchainement_tuile_par_tuile():
    avant, apres = _plateau_bruno_expert_chaine()

    # Ce test vérifie l'ordre causal TUILE PAR TUILE : découpage détaillé
    # (condense=False, issue #207).
    etapes = etapes_coup_ia(avant, apres, condense=False)
    _verifier_invariants(avant, apres, etapes)

    # Le 11 jaune doit être présenté comme venant du plateau (suite jaune),
    # jamais de la main : vérifié via l'étape où il entre dans le cadre.
    etape_retrait_11jaune = next(
        e for e in etapes if "jaune_11_a" in _ids_cadre(e["cadre"]))
    carte_11jaune = next(c for c in etape_retrait_11jaune["cadre"]
                           if c["tuile"]["id"] == "jaune_11_a")
    assert carte_11jaune["origine"] == "plateau"

    # L'écran "Les jokers" mentionne explicitement que le remplaçant du
    # joker (le 11 jaune) vient du plateau, pas de la main.
    jokers_ecran = next(e for e in etapes if e["titre"] == "Les jokers")
    assert "11 jaune" in jokers_ecran["texte"]
    assert "venant de la suite jaune" in jokers_ecran["texte"]
    assert "de sa main" not in jokers_ecran["texte"]

    # Ordre causal : le 11 jaune sort de la suite jaune AVANT de remplacer
    # le joker du groupe de 11 ; le 12 jaune sort de la suite jaune AVANT de
    # remplacer le 12 noir du groupe de 12 ; le 12 noir libéré prolonge la
    # suite noire APRÈS avoir été libéré.
    def premiere_etape_ou(pred):
        return next(i for i, e in enumerate(etapes) if pred(e))

    idx_sortie_11jaune = premiere_etape_ou(
        lambda e: "jaune_11_a" in _ids_cadre(e["cadre"]))
    idx_swap_groupe11 = premiere_etape_ou(
        lambda e: any({"bleu_11_a", "jaune_11_a", "noir_11_a"} ==
                       {d["id"] for d in c} for c in e["plateau"]))
    assert idx_sortie_11jaune < idx_swap_groupe11

    idx_sortie_12jaune = premiere_etape_ou(
        lambda e: "jaune_12_a" in _ids_cadre(e["cadre"]))
    idx_swap_groupe12 = premiere_etape_ou(
        lambda e: any({"rouge_12_a", "bleu_12_a", "jaune_12_a"} ==
                       {d["id"] for d in c} for c in e["plateau"]))
    assert idx_sortie_12jaune < idx_swap_groupe12

    idx_liberation_12noir = premiere_etape_ou(
        lambda e: "noir_12_a" in _ids_cadre(e["cadre"]))
    idx_suite_finale_12noir = premiere_etape_ou(
        lambda e: any({"noir_9_a", "noir_10_a", "noir_11_b", "noir_12_a"} ==
                       {d["id"] for d in c} for c in e["plateau"]))
    assert idx_liberation_12noir < idx_suite_finale_12noir

    # Dernière étape = plateau d'après exactement, cadre vide (déjà vérifié
    # par _verifier_invariants, répété ici pour la lisibilité du test).
    assert etapes[-1]["cadre"] == []


# ------------------------------------------------- tuiles identiques (#197)

def test_echange_tuiles_identiques_main_contre_plateau_dans_une_combinaison():
    """Point 2 de l'issue #197 (recoupe le point 1 : l'échange reste dans
    une seule combinaison) : le 3 jaune déjà posé quitte la suite jaune
    (1 à 3) pour former un nouveau groupe de 3, et le 3 jaune de la main
    prend exactement sa place dans la suite — les deux tuiles sont
    indiscernables à l'écran, donc la suite n'est jamais mentionnée."""
    avant = [[t(1, "jaune"), t(2, "jaune"), t(3, "jaune")]]
    apres = [
        [t(1, "jaune"), t(2, "jaune"), t(3, "jaune", "b")],
        [t(3, "jaune"), t(3, "noir"), t(3, "bleu")],
    ]

    r = decrire_coup_ia(avant, apres)
    assert r["nb_combinaisons_modifiees"] == 0
    assert r["nb_combinaisons_creees"] == 1
    assert "suite" not in r["texte"]
    assert sorted(d["id"] for d in r["tuiles_posees"]) == \
        ["bleu_3_a", "jaune_3_b", "noir_3_a"]

    etapes = etapes_coup_ia(avant, apres)
    _verifier_invariants(avant, apres, etapes)
    changements = [e for e in etapes if not e["titre"]]
    assert len(changements) == 1  # une seule étape visible : le nouveau groupe


def test_echange_tuiles_identiques_entre_deux_combinaisons_sans_la_main():
    """Point 1 de l'issue #197 : deux combinaisons du plateau s'échangent
    leurs tuiles de même aspect (chacune attend une tuile libérée par
    l'autre, un cycle de dépendances strict — c'est le cas réel qui faisait
    planter ``etapes_coup_ia`` avec un ``KeyError``, issue #197 point 0).
    Un coup sans aucun autre changement est donc entièrement sans effet."""
    avant = [
        [t(1, "jaune"), t(2, "jaune"), t(3, "jaune", "a")],
        [t(3, "jaune", "b"), t(3, "noir"), t(3, "bleu")],
    ]
    apres = [
        [t(1, "jaune"), t(2, "jaune"), t(3, "jaune", "b")],
        [t(3, "jaune", "a"), t(3, "noir"), t(3, "bleu")],
    ]

    r = decrire_coup_ia(avant, apres)
    assert r["texte"] == "N'a rien changé sur le plateau."
    assert r["nb_combinaisons_modifiees"] == 0

    etapes = etapes_coup_ia(avant, apres)
    changements = [e for e in etapes if not e["titre"]]
    assert changements == []


def test_regression_echange_cyclique_entre_deux_combinaisons_avec_coup_reel():
    """Reproduction du plantage réel (issue #197 point 0, cas fourni par
    Alain après l'incident : ``tests/donnees/erreur_description_*.json``) :
    un coup de l'IA qui, en même temps qu'il pose un nouveau groupe de 12,
    échange deux paires de tuiles indiscernables entre combinaisons
    existantes (3 jaune et 4 rouge). Avant la correction, le suivi par
    identifiant plantait avec ``KeyError: 'jaune_3_a'`` (``del cadre[...]``
    sur une tuile jamais déposée dans le cadre)."""
    import json
    from pathlib import Path

    chemin = Path(__file__).resolve().parent / "donnees" / \
        "erreur_description_20261027_115033.json"
    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    avant, apres = donnees["plateau_avant"], donnees["plateau_apres"]

    r = decrire_coup_ia(avant, apres, nom="Bruno")
    assert "12 jaune" in r["texte"]
    assert "remplace" not in r["texte"]
    assert "suite" not in r["texte"]
    assert r["nb_combinaisons_modifiees"] == 0  # les deux échanges s'annulent
    assert r["nb_combinaisons_creees"] == 1

    etapes = etapes_coup_ia(avant, apres)
    _verifier_invariants(avant, apres, etapes)
    changements = [e for e in etapes if not e["titre"]]
    assert len(changements) == 1  # seule la formation du groupe de 12 est visible


def test_deux_jokers_echange_dans_une_combinaison_vs_vrai_deplacement():
    """Point 3 de l'issue #197, les deux clauses en un seul coup : le
    joker du groupe de 5 est remplacé par l'AUTRE joker (pas un
    déplacement, aucune étape ni mention) ; le premier joker, libéré,
    forme un nouveau groupe de 9 ; le second joker, lui, part RÉELLEMENT
    du groupe de 11 (remplacé par le 11 jaune de la main) pour rejoindre
    le groupe de 5 — un vrai déplacement, qui doit rester décrit même si
    deux jokers existent dans ce coup."""
    avant = [
        [t(5, "rouge"), t(5, "noir"), j(1)],
        [t(11, "bleu"), t(11, "noir"), j(2)],
    ]
    apres = [
        [t(5, "rouge"), t(5, "noir"), j(2)],
        [t(11, "bleu"), t(11, "noir"), t(11, "jaune")],
        [t(9, "bleu"), t(9, "noir"), j(1)],
    ]

    r = decrire_coup_ia(avant, apres)
    assert len(r["jokers_deplaces"]) == 1
    depl = r["jokers_deplaces"][0]
    assert "groupe de 11" in depl["depuis"]
    assert "groupe de 5" in depl["vers"]
    # Le groupe de 5 (destination du SEUL joker réellement déplacé) n'est
    # jamais décrit comme "modifié" : son propre échange (joker1 <-> joker2)
    # est invisible.
    assert r["nb_combinaisons_modifiees"] == 1  # seul le groupe de 11
    assert r["nb_combinaisons_creees"] == 1  # le nouveau groupe de 9

    etapes = etapes_coup_ia(avant, apres)
    _verifier_invariants(avant, apres, etapes)
    jokers_ecran = next(e for e in etapes if e["titre"] == "Les jokers")
    assert "groupe de 11" in jokers_ecran["texte"]
    assert "groupe de 5" in jokers_ecran["texte"]
    # Exactement 2 changements visibles : le remplacement dans le groupe de
    # 11, puis la formation du groupe de 9 — jamais une étape pour le
    # groupe de 5 (l'échange des deux jokers y est indiscernable).
    changements = [e for e in etapes if not e["titre"]]
    assert len(changements) == 2


# ============================================================ pas-à-pas condensé
# (issue #207) : regroupement des gestes par combinaison, mesure d'ampleur,
# neutralisation des échanges de tuiles identiques dans le RÉSUMÉ.

def _verifier_invariants_condense(avant, apres, etapes):
    """Invariants du découpage CONDENSÉ (issue #207). Comme
    ``_verifier_invariants`` pour « aucune tuile à deux endroits » et « plateau
    final == plateau d'après, cadre vide », mais la détection d'étape sans
    effet se fait au niveau du GROUPEMENT des combinaisons (en condensé, des
    tuiles regroupées plateau→plateau gardent le même ENSEMBLE d'ids d'une
    étape à l'autre, tout en formant une combinaison visiblement différente)."""
    assert etapes[0]["titre"] == "Départ"
    precedent = None
    for etape in etapes:
        combines = _ids_plateau(etape["plateau"]) + _ids_cadre(etape["cadre"])
        assert len(combines) == len(set(combines)), \
            f"tuile dupliquée à l'étape {etape['titre'] or '(sans titre)'}"
        # Empreinte sensible au groupement (combinaisons + cadre).
        empreinte = (tuple(sorted(tuple(sorted(d["id"] for d in c))
                                  for c in etape["plateau"])),
                     tuple(sorted(_ids_cadre(etape["cadre"]))))
        if precedent is not None and not etape["titre"]:
            assert empreinte != precedent, "étape condensée sans effet visible"
        precedent = empreinte
    assert etapes[-1]["cadre"] == []
    ids_apres = sorted(sorted(d["id"] for d in c) for c in apres)
    ids_derniere = sorted(sorted(d["id"] for d in c) for c in etapes[-1]["plateau"])
    assert ids_derniere == ids_apres


def test_condense_clara_tour45_moins_de_douze_etapes():
    """Le vrai coup de Clara au tour 45 (30 étapes en détaillé) se parcourt en
    moins de 12 étapes une fois condensé, borné par « combinaisons modifiées
    + 4 » (issue #207, point 1), avec les mêmes invariants qu'avant."""
    avant, apres = _charger_plateaux("pas_a_pas_clara_tour45.json")
    condense = etapes_coup_ia(avant, apres)              # condense=True par défaut
    detaille = etapes_coup_ia(avant, apres, condense=False)

    _verifier_invariants_condense(avant, apres, condense)
    assert len(condense) < 12
    assert len(condense) < len(detaille)      # vraiment plus court

    mesure = mesurer_coup_ia(avant, apres)
    assert len(condense) <= mesure["nb_combinaisons_modifiees"] + 4


def test_condense_mesure_clara_tour45():
    """Mesure d'ampleur annoncée en tête du pas-à-pas (issue #207, point 3)."""
    avant, apres = _charger_plateaux("pas_a_pas_clara_tour45.json")
    mesure = mesurer_coup_ia(avant, apres)
    assert mesure["taille"] == "grand"
    assert mesure["nb_tuiles_posees"] == 4
    assert mesure["nb_tuiles_plateau_deplacees"] == 14
    assert mesure["nb_combinaisons_modifiees"] == 6


def test_condense_position_fabriquee_proprietes():
    """Position fabriquée : un groupe de 12 défait alimente trois nouvelles
    combinaisons. Propriétés du condensé (issue #207, point 5) : même plateau
    final, cadre vide à la fin, aucune tuile à deux endroits, nombre d'étapes
    borné par « combinaisons modifiées + 4 », et strictement plus court que le
    détaillé."""
    avant = [[t(12, "rouge"), t(12, "bleu"), t(12, "jaune")]]
    apres = [
        [t(10, "rouge"), t(11, "rouge"), t(12, "rouge")],
        [t(11, "bleu"), t(12, "bleu"), t(13, "bleu")],
        [t(12, "jaune"), t(12, "noir"), j(1)],
    ]
    condense = etapes_coup_ia(avant, apres)
    detaille = etapes_coup_ia(avant, apres, condense=False)
    _verifier_invariants_condense(avant, apres, condense)
    assert len(condense) < len(detaille)
    mesure = mesurer_coup_ia(avant, apres)
    assert len(condense) <= mesure["nb_combinaisons_modifiees"] + 4
    # 1 combinaison défaite + 3 créées -> 3 étapes de création + Départ.
    changements = [e for e in condense if not e["titre"]]
    assert len(changements) == 3


def test_condense_coup_court_inchange():
    """Un coup court (pose de 3 tuiles formant un groupe) donne le même
    découpage en condensé et en détaillé (issue #207 : « les coups courts
    restent inchangés »)."""
    avant = [[t(7, "rouge"), t(7, "bleu"), t(7, "noir")]]
    apres = [
        [t(7, "rouge"), t(7, "bleu"), t(7, "noir")],
        [t(5, "rouge"), t(5, "bleu"), t(5, "noir")],
    ]
    assert etapes_coup_ia(avant, apres) == etapes_coup_ia(avant, apres, condense=False)


def test_resume_ignore_echange_tuiles_identiques_entre_combinaisons():
    """Défaut 1 de l'issue #207 : deux groupes de 13 dont les tuiles sont
    seulement ré-étiquetées (mêmes deux groupes avant et après, ids permutés)
    ne doivent produire AUCUNE phrase « X remplace Y » dans le résumé — une
    combinaison identique avant et après n'est ni modifiée ni défaite."""
    avant = [
        [t(13, "rouge", "a"), t(13, "noir", "a"), t(13, "bleu", "a")],
        [t(13, "rouge", "b"), t(13, "noir", "b"), t(13, "jaune", "a")],
    ]
    apres = [
        [t(13, "rouge", "b"), t(13, "noir", "b"), t(13, "bleu", "a")],
        [t(13, "rouge", "a"), t(13, "noir", "a"), t(13, "jaune", "a")],
    ]
    r = decrire_coup_ia(avant, apres, nom="Zoe")
    assert "remplace" not in r["texte"]
    assert r["nb_combinaisons_modifiees"] == 0
    assert r["nb_combinaisons_defaites"] == 0
    assert r["texte"] == "N'a rien changé sur le plateau."
