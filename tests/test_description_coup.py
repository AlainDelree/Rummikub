from rummikub.moteur.tuiles import Tuile
from rummikub.moteur.description_coup import decrire_coup_ia, etapes_coup_ia


def t(v, c):
    return Tuile(f"{c}_{v}_a", v, c).as_dict()


def j(n=1, c="rouge"):
    return Tuile(f"joker_{n}", None, c, est_joker=True).as_dict()


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
    assert len(etapes) == 1  # pas de bouton "Pas à pas" pour un coup simple


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


def test_joker_recupere_puis_rejoue_ailleurs():
    # Suite rouge 5-6-(7 en joker) : l'IA échange le joker contre le 7 rouge
    # réel de sa main, puis rejoue le joker libéré dans un nouveau groupe.
    avant = [[t(5, "rouge"), t(6, "rouge"), j(1)]]
    apres = [
        [t(5, "rouge"), t(6, "rouge"), t(7, "rouge")],
        [t(8, "noir"), t(8, "jaune"), j(1)],
    ]

    r = decrire_coup_ia(avant, apres)

    assert r["nb_combinaisons_defaites"] == 0  # la suite garde sa majorité (2/3)
    assert r["nb_combinaisons_creees"] == 1
    assert r["nb_combinaisons_modifiees"] == 1
    assert len(r["jokers_deplaces"]) == 1
    depl = r["jokers_deplaces"][0]
    assert "suite rouge" in depl["depuis"]
    assert "groupe de 8" in depl["vers"]
    assert "joker" in r["texte"].lower()
    assert "groupe de 8" in r["texte"]

    etapes = etapes_coup_ia(avant, apres)
    assert len(etapes) >= 2  # touche plus d'une combinaison → pas-à-pas possible


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
    assert "défaite" in r["texte"]
    ids_posees = {d["id"] for d in r["tuiles_posees"]}
    assert ids_posees == {"rouge_10_a", "rouge_11_a", "bleu_11_a",
                           "bleu_13_a", "noir_12_a", "joker_1"}

    etapes = etapes_coup_ia(avant, apres)
    assert len(etapes) == 4  # 1 combinaison défaite + 3 nouvelles combinaisons
    assert etapes[0]["texte"] == "Le groupe de 12 est défait."
    # La toute dernière étape doit correspondre exactement au plateau d'après.
    ids_derniere_etape = sorted(
        sorted(d["id"] for d in combo) for combo in etapes[-1]["plateau"])
    ids_attendus = sorted(sorted(d["id"] for d in combo) for combo in apres)
    assert ids_derniere_etape == ids_attendus
