"""Vérification du front-end de l'écran d'accueil pour le réglage « Nombre de
manches » réintroduit (issue #203, suite de #192), avec Playwright, chargé
directement sur `accueil.html` (jamais la vraie application pywebview,
inaccessible en test, voir CONTEXTE.md §7) : on mocke `window.pywebview.api`
et on pilote l'interface comme le ferait un joueur.

Nécessite `pip install playwright` puis `playwright install chromium` (pas
une dépendance de production : absente de requirements.txt, le test est
sauté proprement si le module ou le navigateur ne sont pas disponibles).
"""

import json
from pathlib import Path

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")

WEB_DIR = Path(__file__).resolve().parents[1] / "src" / "rummikub" / "ui" / "web"

# Réglages sauvegardés avec un nombre de manches valide (3) : la valeur que
# l'app doit réafficher et transmettre à la création de la partie.
_REGLAGES = {
    "prenom": "Alain",
    "avatar_index": 0,
    "mise_initiale_min": 30,
    "nb_manches": 3,
    "valeur_joker_penalite": 30,
    "vitesse_ia": "Normale",
    "ia_auto": False,
    "mode_reorg": "clic",
    "dezoom_auto": True,
}

_MOCK_API_JS = """
window._reglagesSauvegardes = null;
window._partieLancee = null;
window.pywebview = {
    api: {
        charger_accueil: () => Promise.resolve({
            reglages: %s,
            parties: [],
        }),
        sauvegarder_reglages: (data) => {
            window._reglagesSauvegardes = data;
            const merged = Object.assign({}, %s, data);
            return Promise.resolve(merged);
        },
        nom_ia_aleatoire: () => Promise.resolve({nom: "Robot"}),
        supprimer_partie: () => Promise.resolve({ok: true}),
        lancer_nouvelle_partie: (config) => {
            window._partieLancee = config;
            return Promise.resolve({ok: true});
        },
        reprendre_partie: () => Promise.resolve({ok: true}),
    },
};
""" % (json.dumps(_REGLAGES), json.dumps(_REGLAGES))


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
    erreurs = []
    pg.on("console", lambda msg: erreurs.append(msg.text) if msg.type == "error" else None)
    pg.on("pageerror", lambda exc: erreurs.append(str(exc)))
    pg.add_init_script(_MOCK_API_JS)
    pg.goto(WEB_DIR.joinpath("accueil.html").as_uri())
    pg.evaluate("window.dispatchEvent(new Event('pywebviewready'))")
    pg.wait_for_function("etat.reglages !== null")
    pg._erreurs_console = erreurs
    yield pg
    pg.close()


def test_champ_nombre_de_manches_present(page):
    # Le champ réintroduit par #203 existe dans le panneau « Règles du jeu ».
    page.click("#btn-reglages")
    page.click("button[data-onglet='regles']")
    assert page.query_selector("#rgl-manches") is not None
    assert "Nombre de manches" in page.inner_text("#overlay-reglages")


def test_valeur_rechargee_depuis_les_reglages(page):
    # remplirChampsReglages() reflète la valeur enregistrée (3 ici).
    page.click("#btn-reglages")
    page.click("button[data-onglet='regles']")
    assert page.input_value("#rgl-manches") == "3"


def test_reglages_enregistrent_le_nombre_de_manches(page):
    page.click("#btn-reglages")
    page.click("button[data-onglet='regles']")
    page.select_option("#rgl-manches", "5")
    page.click("#btn-fermer-rgl")
    page.wait_for_function("window._reglagesSauvegardes !== null")
    donnees = page.evaluate("window._reglagesSauvegardes")
    assert donnees["nb_manches"] == 5
    assert page._erreurs_console == []


def test_lancer_partie_transmet_le_nombre_de_manches(page):
    # Ajoute un adversaire puis règle 4 manches et lance : lancer_nouvelle_partie
    # doit recevoir nb_manches dans les règles.
    page.click("button.btn-ajout-niveau[data-niveau='Facile']")
    page.click("#btn-reglages")
    page.click("button[data-onglet='regles']")
    page.select_option("#rgl-manches", "4")
    page.click("#btn-fermer-rgl")
    page.click("#btn-lancer")
    page.wait_for_function("window._partieLancee !== null")
    config = page.evaluate("window._partieLancee")
    assert config["regles"]["nb_manches"] == 4
    assert page._erreurs_console == []


def test_valeur_hors_bornes_retombe_sur_1(page):
    # Une valeur enregistrée hors de [1, 9] (ou absente) est réaffichée comme 1.
    page.evaluate("etat.reglages.nb_manches = 99; remplirChampsReglages();")
    assert page.input_value("#rgl-manches") == "1"
    page.evaluate("delete etat.reglages.nb_manches; remplirChampsReglages();")
    assert page.input_value("#rgl-manches") == "1"
    assert page._erreurs_console == []
