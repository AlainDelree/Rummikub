"""Vérification du front-end du rejeu pas-à-pas (issue #191) avec Playwright,
chargé directement sur `jeu.html` (jamais la vraie application pywebview,
inaccessible en test) : on injecte un état fictif dans la variable globale
`etat` de jeu.js et on pilote l'interface comme le ferait un joueur.

Nécessite `pip install playwright` puis `playwright install chromium` (pas
une dépendance de production : absente de requirements.txt, le test est
sauté proprement si le module ou le navigateur ne sont pas disponibles).
"""

import json
from pathlib import Path

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")

from rummikub.moteur.tuiles import Tuile
from rummikub.moteur.description_coup import (
    decrire_coup_ia, etapes_coup_ia, mesurer_coup_ia)

WEB_DIR = Path(__file__).resolve().parents[1] / "src" / "rummikub" / "ui" / "web"
_DONNEES = Path(__file__).resolve().parent / "donnees"


def _coup_depuis_plateaux(avant, apres, nom):
    """Construit un dict ``dernier_coup_ia`` comme le ferait ``api.py`` après
    une pose (résumé, étapes condensées/détaillées, mesure)."""
    return {
        "type": "pose", "nom": nom, "joueur_index": 0,
        "plateau_avant": avant, "plateau_apres": apres,
        "resume": decrire_coup_ia(avant, apres, nom=nom)["texte"],
        "etapes": etapes_coup_ia(avant, apres, mode="modification"),
        "etapes_detaillees": etapes_coup_ia(avant, apres, mode="detaille"),
        "mesure": mesurer_coup_ia(avant, apres),
    }


def _coup_clara():
    """Vrai coup de Clara au tour 45 (grande ampleur, issue #207)."""
    d = json.loads((_DONNEES / "pas_a_pas_clara_tour45.json").read_text("utf-8"))
    return _coup_depuis_plateaux(d["plateau_avant"], d["plateau_apres"], "Clara")


def _t(v, c, serie="a"):
    return Tuile(f"{c}_{v}_{serie}", v, c).as_dict()


def _j(n=1, c="rouge"):
    return Tuile(f"joker_{n}", None, c, est_joker=True).as_dict()


def _coup_bruno():
    """Coup décrit dans le contexte de l'issue #191 : 3 bleu remplace le
    joker du groupe de 3, le joker libéré forme un nouveau groupe de 11 avec
    les deux 11 de la main."""
    avant = [[_t(3, "rouge"), _t(3, "noir"), _j(1)]]
    apres = [
        [_t(3, "rouge"), _t(3, "noir"), _t(3, "bleu")],
        [_t(11, "bleu"), _t(11, "noir"), _j(1)],
    ]
    return _coup_depuis_plateaux(avant, apres, "Bruno")


@pytest.fixture(scope="module")
def browser():
    with playwright_sync.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # navigateur non installé sur la machine
            pytest.skip(f"chromium indisponible pour Playwright : {exc}")
        yield b
        b.close()


@pytest.fixture
def page(browser):
    pg = browser.new_page()
    pg.goto(WEB_DIR.joinpath("jeu.html").as_uri())
    # Branche les écouteurs de boutons (dont ceux du pas-à-pas) sans passer
    # par le reste de init(), qui dépend de window.pywebview (absent ici).
    pg.evaluate("brancherEvenements()")
    yield pg
    pg.close()


def _injecter_coup(page, coup):
    page.evaluate(
        """(coup) => {
            etat = { dernier_coup_ia: coup, config: {}, joueurs: [] };
            rafraichirBoutonRejouerIA();
        }""",
        coup,
    )


def test_bouton_pas_a_pas_visible_pour_un_coup_a_plusieurs_changements(page):
    _injecter_coup(page, _coup_bruno())
    btn = page.locator("#btn-pas-a-pas-coup-ia")
    assert not btn.is_hidden()
    assert btn.is_enabled()


def test_cadre_se_vide_progressivement_et_plateau_final_correct(page):
    _injecter_coup(page, _coup_bruno())
    page.click("#btn-pas-a-pas-coup-ia")

    overlay = page.locator("#overlay-pas-a-pas")
    assert "overlay-visible" in overlay.get_attribute("class")

    def ids_cadre():
        return page.locator("#cadre-tuiles-pas-a-pas .tuile-jeu").evaluate_all(
            "els => els.map(e => e.dataset.id)")

    def ids_plateau():
        return page.locator("#zone-plateau-pas-a-pas .tuile-jeu").evaluate_all(
            "els => els.map(e => e.dataset.id)")

    # Étape 0 ("Départ") : les 3 tuiles de la main sont dans le cadre, toutes
    # avec le pourtour vert "ce-tour" de la légende (tuile venue de la main).
    assert page.evaluate('document.getElementById("soustitre-etape-pas-a-pas").textContent') == "Départ"
    assert sorted(ids_cadre()) == ["bleu_11_a", "bleu_3_a", "noir_11_a"]
    assert page.locator("#cadre-tuiles-pas-a-pas .tuile-jeu.ce-tour").count() == 3
    assert page.locator("#cadre-tuiles-pas-a-pas .tuile-jeu.deplacee-tapis").count() == 0

    # Aucune tuile du cadre n'apparaît en même temps sur le plateau.
    assert set(ids_cadre()).isdisjoint(ids_plateau())

    # Étape 1 ("Les jokers") : vue d'ensemble, rien ne change encore.
    page.click("#btn-pas-a-pas-suivant")
    assert page.evaluate('document.getElementById("soustitre-etape-pas-a-pas").textContent') == "Les jokers"
    assert sorted(ids_cadre()) == ["bleu_11_a", "bleu_3_a", "noir_11_a"]

    # Étape 2 : le 3 bleu a rejoint le plateau (groupe de 3), le joker,
    # libéré, apparaît dans le cadre avec le pourtour orange "deplacee-tapis"
    # (tuile venue du plateau, pas de la main).
    page.click("#btn-pas-a-pas-suivant")
    assert "bleu_3_a" in ids_plateau()
    assert sorted(ids_cadre()) == ["bleu_11_a", "joker_1", "noir_11_a"]
    assert page.locator("#cadre-tuiles-pas-a-pas .tuile-jeu.deplacee-tapis").count() == 1
    assert set(ids_cadre()).isdisjoint(ids_plateau())

    # Étape 3 (dernière) : cadre vide, affiché comme tel ("vide"), plateau
    # final identique au plateau_apres fourni.
    page.click("#btn-pas-a-pas-suivant")
    assert ids_cadre() == []
    assert page.locator("#cadre-tuiles-pas-a-pas .cadre-vide").inner_text() == "vide"
    assert sorted(ids_plateau()) == sorted(
        ["rouge_3_a", "noir_3_a", "bleu_3_a", "bleu_11_a", "noir_11_a", "joker_1"])
    assert page.locator("#btn-pas-a-pas-suivant").is_disabled()


def _ids_surbrillance_forte(page):
    """Ids des tuiles portant la classe de surbrillance FORTE de l'étape
    courante (issue #209), que ce soit dans l'aperçu du plateau ou dans le
    cadre « tuiles à placer »."""
    return set(page.locator(
        "#zone-plateau-pas-a-pas .tuile-jeu.tuile-pas-active,"
        " #cadre-tuiles-pas-a-pas .tuile-jeu.tuile-pas-active"
    ).evaluate_all("els => els.map(e => e.dataset.id)"))


def test_surbrillance_forte_suit_exactement_les_tuiles_de_chaque_etape(page):
    """Issue #209 : à CHAQUE étape, les tuiles portant la classe de
    surbrillance forte sont exactement celles que la phrase nomme
    (etape.surbrillance), ni plus ni moins, plateau et cadre confondus — et il
    y en a au moins une dès que l'étape décrit un geste sur une tuile."""
    coup = _coup_clara()
    _injecter_coup(page, coup)
    page.click("#btn-pas-a-pas-coup-ia")

    etapes = coup["etapes"]
    assert len(etapes) >= 2  # coup à plusieurs étapes (point 5 de l'issue)
    for i, etape in enumerate(etapes):
        if i:
            page.click("#btn-pas-a-pas-suivant")
        attendus = set(etape["surbrillance"])
        assert _ids_surbrillance_forte(page) == attendus, f"étape {i}"
        # Chaque étape du coup de Clara décrit un geste → au moins une tuile.
        assert attendus, f"étape {i} sans tuile mise en avant"


def test_surbrillance_forte_joker_et_remplacant_plateau_et_cadre(page):
    """Issue #209, point 2 : à l'écran « Les jokers » d'un coup où un joker est
    remplacé (cas Bruno), le joker (sur le plateau) ET sa tuile de remplacement
    (dans le cadre) sont tous deux mis en avant."""
    _injecter_coup(page, _coup_bruno())
    page.click("#btn-pas-a-pas-coup-ia")
    page.click("#btn-pas-a-pas-suivant")  # étape 1 : « Les jokers »
    assert page.evaluate(
        'document.getElementById("soustitre-etape-pas-a-pas").textContent'
    ) == "Les jokers"
    # joker_1 est encore dans son groupe d'origine (plateau), bleu_3_a attend
    # dans le cadre : la surbrillance forte couvre les deux provenances.
    assert _ids_surbrillance_forte(page) == {"joker_1", "bleu_3_a"}
    assert page.locator(
        "#cadre-tuiles-pas-a-pas .tuile-jeu.tuile-pas-active"
    ).count() == 1
    assert page.locator(
        "#zone-plateau-pas-a-pas .tuile-jeu.tuile-pas-active"
    ).count() == 1


def test_quitter_pas_a_pas_ne_modifie_jamais_la_partie(page):
    coup = _coup_bruno()
    _injecter_coup(page, coup)
    page.click("#btn-pas-a-pas-coup-ia")
    page.click("#btn-pas-a-pas-suivant")
    page.click("#btn-pas-a-pas-quitter")
    overlay = page.locator("#overlay-pas-a-pas")
    assert "overlay-cache" in overlay.get_attribute("class")
    # L'état de la partie (ici, le coup mémorisé) n'a pas été touché.
    etat_apres = page.evaluate("etat.dernier_coup_ia")
    assert etat_apres["resume"] == coup["resume"]


# ===================================================== issue #207 : condensé, etc.

def test_bouton_pas_a_pas_present_pour_le_coup_de_clara(page):
    """Défaut 2 de l'issue #207 : le coup de Clara (14 tuiles du plateau
    déplacées) doit faire apparaître le bouton « Pas à pas »."""
    _injecter_coup(page, _coup_clara())
    btn = page.locator("#btn-pas-a-pas-coup-ia")
    assert not btn.is_hidden()
    assert btn.is_enabled()


def test_coup_pure_creation_sans_bouton(page):
    """Un coup qui ne fait que créer une combinaison depuis la main reste sans
    bouton « Pas à pas » (issue #207, défaut 2)."""
    avant = []
    apres = [[_t(7, "rouge"), _t(7, "bleu"), _t(7, "noir")]]
    _injecter_coup(page, _coup_depuis_plateaux(avant, apres, "David"))
    assert page.locator("#btn-pas-a-pas-coup-ia").is_hidden()


def test_ligne_de_taille_affichee_en_tete(page):
    """La ligne d'ampleur du coup (issue #207, point 3) est affichée à
    l'ouverture du pas-à-pas."""
    _injecter_coup(page, _coup_clara())
    page.click("#btn-pas-a-pas-coup-ia")
    ligne = page.locator("#ligne-taille-pas-a-pas").inner_text()
    assert "grande taille" in ligne
    assert "14 tuiles du plateau déplacées" in ligne
    assert "6 combinaisons modifiées" in ligne
    assert "4 tuiles" in ligne


def test_bouton_detailler_bascule_condense_detaille(page):
    """Le bouton « Détailler » (issue #207, point 2) bascule vers le découpage
    tuile par tuile et revient au condensé ; le condensé est le mode par défaut
    à l'ouverture."""
    coup = _coup_clara()
    nb_condense = len(coup["etapes"])
    nb_detaille = len(coup["etapes_detaillees"])
    assert nb_detaille > nb_condense
    _injecter_coup(page, coup)
    page.click("#btn-pas-a-pas-coup-ia")

    def total_etapes():
        txt = page.locator("#compteur-etape-pas-a-pas").inner_text()
        return int(txt.split("/")[-1].strip())

    assert total_etapes() == nb_condense                  # condensé par défaut
    page.click("#btn-pas-a-pas-detailler")
    assert total_etapes() == nb_detaille                  # détaillé
    page.click("#btn-pas-a-pas-detailler")
    assert total_etapes() == nb_condense                  # retour au condensé

    # Réouvrir rouvre toujours en condensé.
    page.click("#btn-pas-a-pas-detailler")
    page.click("#btn-pas-a-pas-quitter")
    page.click("#btn-pas-a-pas-coup-ia")
    assert total_etapes() == nb_condense


def test_bascule_avant_apres(page):
    """La bascule « Avant / Après » (issue #207, point 4) montre les deux
    plateaux avec une légende, en lecture seule, sans modifier la partie."""
    coup = _coup_clara()
    _injecter_coup(page, coup)
    page.click("#btn-pas-a-pas-coup-ia")

    # Au départ : vue étapes visible, comparaison cachée.
    assert not page.locator("#vue-etapes-pas-a-pas").is_hidden()
    assert page.locator("#vue-comparaison-pas-a-pas").is_hidden()

    page.click("#btn-pas-a-pas-comparaison")
    assert page.locator("#vue-etapes-pas-a-pas").is_hidden()
    assert not page.locator("#vue-comparaison-pas-a-pas").is_hidden()

    # Les deux plateaux portent des tuiles ; la légende est présente.
    nb_avant = page.locator("#comparaison-avant .tuile-jeu").count()
    nb_apres = page.locator("#comparaison-apres .tuile-jeu").count()
    assert nb_avant > 0 and nb_apres > 0
    assert page.locator("#legende-pas-a-pas").count() == 1
    # Au moins une combinaison mise en évidence (modifiée/créée) côté après.
    assert page.locator("#comparaison-apres .combi-modifiee").count() >= 1
    # Tuiles distinguées selon leur origine (main / déplacée).
    assert page.locator("#comparaison-apres .tuile-jeu.ce-tour").count() >= 1
    assert page.locator("#comparaison-apres .tuile-jeu.deplacee-tapis").count() >= 1

    # Retour aux étapes.
    page.click("#btn-pas-a-pas-comparaison")
    assert not page.locator("#vue-etapes-pas-a-pas").is_hidden()
    assert page.locator("#vue-comparaison-pas-a-pas").is_hidden()

    # La partie n'a pas été modifiée.
    assert page.evaluate("etat.dernier_coup_ia.resume") == coup["resume"]


# ======================================================== issue #214 : front-end

def test_reperes_origine_relient_depart_et_arrivee(page):
    """Point 3 de l'issue #214 : quand une tuile change de place à une étape, un
    repère d'origine est présent — un bandeau « Départ » dans la zone quittée et
    une pastille « arrivée » sur la tuile à sa nouvelle place. L'écran « Départ »
    (pas d'étape précédente) n'en porte aucun."""
    coup = _coup_clara()
    _injecter_coup(page, coup)
    page.click("#btn-pas-a-pas-coup-ia")

    # Étape 0 « Départ » : aucun repère (rien n'a encore bougé).
    assert page.locator(".bandeau-departs").count() == 0
    assert page.locator(".pastille-arrivee").count() == 0

    vu_bandeau = vu_pastille = False
    for _ in range(len(coup["etapes"]) - 1):
        page.click("#btn-pas-a-pas-suivant")
        if page.locator(".bandeau-departs").count() > 0:
            vu_bandeau = True
        if page.locator(".pastille-arrivee").count() > 0:
            vu_pastille = True
    assert vu_bandeau, "aucun bandeau « Départ » rencontré"
    assert vu_pastille, "aucune pastille « arrivée » rencontrée"


def test_comparaison_combinaison_inchangee_non_surlignee(page):
    """Défaut 5a de l'issue #214 : une combinaison identique avant et après (même
    contenu, identifiants internes ré-étiquetés) ne doit PLUS être entourée de
    bleu. Ici le groupe de 13 est inchangé (relabellisé a→b), seule la suite
    rouge est étendue : une seule combinaison mise en évidence côté après."""
    avant = [
        [_t(13, "rouge", "a"), _t(13, "noir", "a"), _t(13, "bleu", "a")],
        [_t(1, "rouge"), _t(2, "rouge"), _t(3, "rouge")],
    ]
    apres = [
        [_t(13, "rouge", "b"), _t(13, "noir", "b"), _t(13, "bleu", "b")],
        [_t(1, "rouge"), _t(2, "rouge"), _t(3, "rouge"), _t(4, "rouge")],
    ]
    coup = _coup_depuis_plateaux(avant, apres, "Léo")
    # Ouverture directe de la vue comparaison (ce coup ne « mérite » pas le
    # bouton, mais la comparaison se rend de la même façon).
    page.evaluate(
        """(coup) => {
            etat = { dernier_coup_ia: coup, config: {}, joueurs: [] };
            coupPasAPasActuel = coup;
            modeComparaisonPasAPas = true;
            document.getElementById('overlay-pas-a-pas').className = 'overlay-visible';
            appliquerVuePasAPas();
        }""",
        coup,
    )
    # Deux combinaisons après, une SEULE mise en évidence (la suite étendue).
    assert page.locator("#comparaison-apres .groupe-combinaison").count() == 2
    assert page.locator("#comparaison-apres .combi-modifiee").count() == 1
    assert page.locator("#comparaison-avant .combi-modifiee").count() == 1


def test_legende_comparaison_illustree_par_des_tuiles(page):
    """Point 5c de l'issue #214 : chaque repère de la légende contient un vrai
    exemple — UNE tuile dans le repère vert, UNE dans l'orange, TROIS côte à côte
    dans le repère bleu (une combinaison), pour que la forme se comprenne sans
    lire le texte."""
    _injecter_coup(page, _coup_clara())
    page.click("#btn-pas-a-pas-coup-ia")
    page.click("#btn-pas-a-pas-comparaison")

    leg = page.locator("#legende-pas-a-pas")
    assert leg.locator(".legende-tuile-mini.ce-tour").count() == 1
    assert leg.locator(".legende-tuile-mini.deplacee-tapis").count() == 1
    # Repère bleu = une combinaison miniature de trois tuiles.
    assert leg.locator(".legende-combi-illustree").count() == 1
    assert leg.locator(".legende-combi-illustree .legende-tuile-mini").count() == 3
