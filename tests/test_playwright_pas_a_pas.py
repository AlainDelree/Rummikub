"""Vérification du front-end du rejeu pas-à-pas (issue #191) avec Playwright,
chargé directement sur `jeu.html` (jamais la vraie application pywebview,
inaccessible en test) : on injecte un état fictif dans la variable globale
`etat` de jeu.js et on pilote l'interface comme le ferait un joueur.

Nécessite `pip install playwright` puis `playwright install chromium` (pas
une dépendance de production : absente de requirements.txt, le test est
sauté proprement si le module ou le navigateur ne sont pas disponibles).
"""

from pathlib import Path

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")

from rummikub.moteur.tuiles import Tuile
from rummikub.moteur.description_coup import decrire_coup_ia, etapes_coup_ia

WEB_DIR = Path(__file__).resolve().parents[1] / "src" / "rummikub" / "ui" / "web"


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
    resume = decrire_coup_ia(avant, apres, nom="Bruno")
    etapes = etapes_coup_ia(avant, apres)
    return {
        "type": "pose",
        "nom": "Bruno",
        "joueur_index": 1,
        "plateau_avant": avant,
        "plateau_apres": apres,
        "resume": resume["texte"],
        "etapes": etapes,
    }


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
