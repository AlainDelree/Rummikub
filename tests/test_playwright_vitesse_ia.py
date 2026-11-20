"""Vérifie que la vitesse « Rapide » de l'IA est bien la plus courte des
trois réglages exposés aux joueurs (Lente/Normale-« Moyenne »/Rapide), pour
l'animation du coup en direct ET pour son rejeu à la demande (issue #251).

Chargé directement sur `jeu.html` (jamais la vraie application pywebview,
voir CONTEXTE.md §7) : les constantes du script (`VITESSES_IA`,
`MULTIPLICATEURS_REJEU_IA`, `PAUSES_REJEU_IA`) sont lues directement via
`page.evaluate`, sans passer par `init()`.

Nécessite `pip install playwright` puis `playwright install chromium` (pas
une dépendance de production : absente de requirements.txt, le test est
sauté proprement si le module ou le navigateur ne sont pas disponibles).
"""

from pathlib import Path

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")

WEB_DIR = Path(__file__).resolve().parents[1] / "src" / "rummikub" / "ui" / "web"


@pytest.fixture(scope="module")
def browser():
    with playwright_sync.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # navigateur non installé sur la machine
            pytest.skip(f"chromium indisponible pour Playwright : {exc}")
        yield b
        b.close()


@pytest.fixture(scope="module")
def page(browser):
    pg = browser.new_page()
    pg.goto(WEB_DIR.joinpath("jeu.html").as_uri())
    yield pg
    pg.close()


def test_vitesses_ia_rapide_plus_courte_que_normale_plus_courte_que_lente(page):
    vitesses = page.evaluate("VITESSES_IA")
    rapide, normale, lente = vitesses["Rapide"], vitesses["Normale"], vitesses["Lente"]
    # reflexion/tuile dépendent strictement des 3 vitesses depuis toujours.
    for cle in ("reflexion", "tuile"):
        assert rapide[cle] < normale[cle] < lente[cle], (
            f"{cle} : Rapide={rapide[cle]} Normale={normale[cle]} Lente={lente[cle]}")
    # premiereTuile/finPose (issue #251) : seule "Rapide" a été raccourcie,
    # "Normale" et "Lente" gardent volontairement la même valeur qu'avant.
    for cle in ("premiereTuile", "finPose"):
        assert rapide[cle] < normale[cle] <= lente[cle], (
            f"{cle} : Rapide={rapide[cle]} Normale={normale[cle]} Lente={lente[cle]}")


def test_rejeu_rapide_plus_court_que_moyenne_plus_court_que_lente(page):
    multiplicateurs = page.evaluate("MULTIPLICATEURS_REJEU_IA")
    assert multiplicateurs["Rapide"] < multiplicateurs["Moyenne"] < multiplicateurs["Lente"]

    pauses = page.evaluate("PAUSES_REJEU_IA")
    for cle in ("premiere", "fin"):
        assert pauses["Rapide"][cle] <= pauses["Moyenne"][cle] <= pauses["Lente"][cle]
    assert pauses["Rapide"]["fin"] < pauses["Moyenne"]["fin"]


def test_rapide_nettement_plus_rapide_sur_un_coup_a_une_tuile(page):
    # Le scénario qui motive l'issue #251 : un coup d'UNE seule tuile, le cas
    # le plus fréquent, où le délai entre tuiles ne joue aucun rôle (boucle
    # d'une seule itération) — seules premiereTuile + finPose comptent.
    vitesses = page.evaluate("VITESSES_IA")
    total_rapide = vitesses["Rapide"]["premiereTuile"] + vitesses["Rapide"]["finPose"]
    total_normale = vitesses["Normale"]["premiereTuile"] + vitesses["Normale"]["finPose"]
    assert total_rapide * 2 <= total_normale, (
        f"Rapide ({total_rapide} ms) n'est pas nettement plus court que "
        f"Normale ({total_normale} ms) sur un coup à une seule tuile")
