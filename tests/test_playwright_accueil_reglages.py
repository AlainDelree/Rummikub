"""Vérification du front-end de l'écran d'accueil (issue #192) avec
Playwright, chargé directement sur `accueil.html` (jamais la vraie
application pywebview, inaccessible en test, voir CONTEXTE.md §7) : on
mocke `window.pywebview.api` et on pilote l'interface comme le ferait un
joueur.

Nécessite `pip install playwright` puis `playwright install chromium` (pas
une dépendance de production : absente de requirements.txt, le test est
sauté proprement si le module ou le navigateur ne sont pas disponibles).
"""

import json
from pathlib import Path

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")

WEB_DIR = Path(__file__).resolve().parents[1] / "src" / "rummikub" / "ui" / "web"

# Simule des réglages sauvegardés par une version antérieure à #192, avec
# un nombre de manches > 1 — la valeur que l'app ne doit plus jamais
# relire ni réafficher.
_REGLAGES_ANCIENS = {
    "prenom": "Alain",
    "avatar_index": 0,
    "mise_initiale_min": 30,
    "nb_manches": 5,
    "valeur_joker_penalite": 30,
    "vitesse_ia": "Normale",
    "ia_auto": False,
    "mode_reorg": "clic",
    "dezoom_auto": True,
}

_MOCK_API_JS = """
window._reglagesSauvegardes = null;
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
        lancer_nouvelle_partie: () => Promise.resolve({ok: true}),
        reprendre_partie: () => Promise.resolve({ok: true}),
    },
};
""" % (json.dumps(_REGLAGES_ANCIENS), json.dumps(_REGLAGES_ANCIENS))


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
    # Mock injecté avant tout script de la page, pour que init() (déclenché
    # par "pywebviewready" ou DOMContentLoaded si pywebview déjà présent)
    # trouve l'API dès le chargement.
    pg.add_init_script(_MOCK_API_JS)
    pg.goto(WEB_DIR.joinpath("accueil.html").as_uri())
    # window.pywebview est déjà présent au moment du DOMContentLoaded (fixé
    # par le script d'init ci-dessus avant tout script de la page) : la
    # branche de secours d'accueil.js appelle alors initUneFois() seule,
    # mais au cas où l'ordre d'exécution diffère selon le moteur, on
    # redéclenche explicitement l'événement attendu.
    pg.evaluate("window.dispatchEvent(new Event('pywebviewready'))")
    pg.wait_for_function("etat.reglages !== null")
    pg._erreurs_console = erreurs
    yield pg
    pg.close()


def test_champ_nombre_de_manches_absent_du_dom(page):
    assert page.query_selector("#rgl-manches") is None
    assert "Nombre de manches" not in page.inner_text("#overlay-reglages")


def test_pas_de_trou_dans_le_panneau_regles(page):
    # Le panneau "Règles du jeu" doit garder exactement ses deux réglages
    # restants (mise initiale, valeur du joker), sans label vide à la place
    # de celui retiré.
    page.click("#btn-reglages")
    page.click("button[data-onglet='regles']")
    labels = page.locator("#panneau-regles > label, #panneau-regles > div").all_inner_texts()
    assert len(labels) == 2
    assert any("Mise initiale" in t for t in labels)
    assert any("joker" in t.lower() for t in labels)


def test_reglages_s_enregistrent_et_se_rechargent_sans_erreur(page):
    # Ouvre puis ferme les réglages (fermerReglages -> sauvegarderReglages),
    # avec un ancien nb_manches=5 en mémoire côté mock API.
    page.click("#btn-reglages")
    assert page.get_attribute("#overlay-reglages", "class") == "overlay-visible"
    page.click("#btn-fermer-rgl")
    page.wait_for_function("window._reglagesSauvegardes !== null")

    donnees_envoyees = page.evaluate("window._reglagesSauvegardes")
    assert "nb_manches" not in donnees_envoyees

    # Rouvre : remplirChampsReglages() relit etat.reglages (désormais le
    # retour fusionné du mock, qui contient toujours l'ancien nb_manches=5
    # côté stockage) sans jamais tenter d'accéder à #rgl-manches.
    page.click("#btn-reglages")
    assert page.get_attribute("#overlay-reglages", "class") == "overlay-visible"
    assert page.query_selector("#rgl-manches") is None

    assert page.evaluate("etat.reglages.nb_manches") == 5  # ancienne valeur, inerte
    assert page._erreurs_console == []
