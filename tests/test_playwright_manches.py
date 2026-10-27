"""Vérification du front-end des manches multiples (issue #203) avec
Playwright, chargé directement sur `jeu.html` (jamais la vraie application
pywebview, inaccessible en test, voir CONTEXTE.md §7) : on injecte un état
fictif dans la variable globale `etat` de jeu.js et on appelle directement les
fonctions d'affichage concernées.

Nécessite `pip install playwright` puis `playwright install chromium` (sauté
proprement si le module ou le navigateur sont absents).
"""

from pathlib import Path

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")

WEB_DIR = Path(__file__).resolve().parents[1] / "src" / "rummikub" / "ui" / "web"


def _joueur(nom, score_manche, score_cumul, est_ia=False):
    return {"nom": nom, "est_ia": est_ia, "niveau": "Expert" if est_ia else None,
            "avatar_index": 0, "chevalet": [], "mise_initiale_faite": True,
            "score_manche": score_manche, "score_cumul": score_cumul}


def _etat(nb_manches, manche_numero, joueurs, *, manche_terminee=False,
          terminee=False, gagnant_manche_index=None):
    return {
        "id": "test", "phase": "jeu", "tour_numero": 1,
        "manche_numero": manche_numero, "index_joueur_actuel": 0,
        "joueurs": joueurs, "pioche": [], "plateau": [],
        "manche_terminee": manche_terminee, "terminee": terminee,
        "gagnant_manche_index": gagnant_manche_index,
        "config": {"nb_manches": nb_manches},
    }


@pytest.fixture(scope="module")
def browser():
    with playwright_sync.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"chromium indisponible pour Playwright : {exc}")
        yield b
        b.close()


@pytest.fixture
def page(browser):
    pg = browser.new_page()
    pg.goto(WEB_DIR.joinpath("jeu.html").as_uri())
    yield pg
    pg.close()


def _injecter(page, etat):
    page.evaluate("(e) => { etat = e; }", etat)


def test_indicateur_manche_affiche_quand_plusieurs_manches(page):
    _injecter(page, _etat(3, 2, [_joueur("Alain", 0, 10),
                                 _joueur("Bot", 0, -10, est_ia=True)]))
    page.evaluate("rafraichirIndicateurManche()")
    ind = page.locator("#indicateur-manche")
    assert not ind.is_hidden()
    assert ind.inner_text() == "Manche 2 / 3"


def test_indicateur_manche_masque_pour_une_seule_manche(page):
    _injecter(page, _etat(1, 1, [_joueur("Alain", 0, 0),
                                 _joueur("Bot", 0, 0, est_ia=True)]))
    page.evaluate("rafraichirIndicateurManche()")
    assert page.locator("#indicateur-manche").is_hidden()


def test_ecran_fin_de_manche_intermediaire(page):
    # Manche 1 sur 3 terminée (pas la dernière) : overlay-fin avec bouton
    # « Manche suivante » et les scores manche + cumul, PAS le classement final.
    etat = _etat(3, 1,
                 [_joueur("Alain", 30, 30), _joueur("Bot", -30, -30, est_ia=True)],
                 manche_terminee=True, terminee=False, gagnant_manche_index=0)
    _injecter(page, etat)
    page.evaluate("afficherFinDeManche()")
    assert "overlay-visible" in page.get_attribute("#overlay-fin", "class")
    assert "overlay-cache" in page.get_attribute("#overlay-classement", "class")
    assert not page.locator("#btn-nouvelle-manche").is_hidden()
    txt = page.inner_text("#tableau-scores")
    assert "Alain" in txt and "Bot" in txt
    assert "Total" in page.inner_text("#tableau-scores")   # colonne cumul
    assert "remporte la manche" in page.inner_text("#titre-fin")


def test_ecran_classement_final_derniere_manche(page):
    # Dernière manche (terminee) : classement final par score cumulé.
    etat = _etat(2, 2,
                 [_joueur("Alain", -5, 25), _joueur("Bot", 5, -25, est_ia=True)],
                 manche_terminee=True, terminee=True, gagnant_manche_index=1)
    _injecter(page, etat)
    page.evaluate("afficherFinDeManche()")
    assert "overlay-visible" in page.get_attribute("#overlay-classement", "class")
    # Vainqueur du match = plus haut score cumulé (Alain, 25) même si Bot a
    # gagné la dernière manche.
    assert "Alain remporte la partie" in page.inner_text("#titre-classement")


def test_classement_final_affiche_egalite(page):
    etat = _etat(2, 2,
                 [_joueur("Alain", 0, 0), _joueur("Bot", 0, 0, est_ia=True)],
                 manche_terminee=True, terminee=True, gagnant_manche_index=0)
    _injecter(page, etat)
    page.evaluate("afficherFinDeManche()")
    assert "overlay-visible" in page.get_attribute("#overlay-classement", "class")
    titre = page.inner_text("#titre-classement")
    assert "Égalité" in titre
    assert "Alain" in titre and "Bot" in titre
