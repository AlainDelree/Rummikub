"""Vérification du front-end de la case « Tri automatique » du chevalet quand
une tuile posée (zone de pose ou tapis) ou annulée est REPRISE avant de jouer
le tour (issue #251) : elle doit retrouver sa place triée dans le chevalet,
exactement comme une tuile piochée (`insererTrie`, issue #126/#130), tant que
la case est cochée. Avec la case décochée, le comportement d'avant (retour en
fin de chevalet) ne doit pas changer.

Chargé directement sur `jeu.html` (jamais la vraie application pywebview,
inaccessible en test, voir docs/contexte/tests_frontend.md §7) : les fonctions du script sont
appelées directement via `page.evaluate`, comme dans
`test_playwright_pas_a_pas.py`, sans passer par `init()` (qui dépend de
`window.pywebview`, absent ici).

Nécessite `pip install playwright` puis `playwright install chromium` (pas
une dépendance de production : absente de requirements.txt, le test est
sauté proprement si le module ou le navigateur ne sont pas disponibles).
"""

from pathlib import Path

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")

WEB_DIR = Path(__file__).resolve().parents[1] / "src" / "rummikub" / "ui" / "web"

# Trois tuiles du chevalet, délibérément PAS dans l'ordre trié (couleur puis
# valeur croissante, cf. comparerTuiles) : rouge_2 < rouge_8 < bleu_2.
_TUILE_A = {"id": "rouge_8", "valeur": 8, "couleur": "rouge", "est_joker": False}
_TUILE_B = {"id": "bleu_2", "valeur": 2, "couleur": "bleu", "est_joker": False}
_TUILE_C = {"id": "rouge_2", "valeur": 2, "couleur": "rouge", "est_joker": False}

_ORDRE_TRIE = ["rouge_2", "rouge_8", "bleu_2"]


def _etat(chevalet_serveur):
    return {
        "joueurs": [
            {"est_ia": False, "chevalet": chevalet_serveur, "mise_initiale_faite": True},
        ],
        "index_joueur_actuel": 0,
        "manche_terminee": False,
        "pioche": [],
        "config": {},
        "dernier_coup_ia": None,
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
    erreurs = []
    pg.on("console", lambda msg: erreurs.append(msg.text) if msg.type == "error" else None)
    pg.on("pageerror", lambda exc: erreurs.append(str(exc)))
    pg.goto(WEB_DIR.joinpath("jeu.html").as_uri())
    pg._erreurs_console = erreurs
    yield pg
    pg.close()


def _preparer_chevalet(page, tri_auto, chevalet_serveur=None):
    """Place chevaletLocal = [A, B, C] (non trié), triAutoActif selon le
    paramètre, et un état minimal pour que placerTuileDansRangee()/
    reprendreTuileRangee()/onAnnuler() fonctionnent sans window.pywebview."""
    page.evaluate(
        """([a, b, c, triAuto, etatDict]) => {
            etat = etatDict;
            chevaletLocal = [a, b, c];
            travail = [[], []];
            rangeeActive = 0;
            tuileSelectionnee = null;
            tuilesCeTour = [];
            tuilesOrigineTapis = [];
            plateauLocal = [];
            triAutoActif = triAuto;
        }""",
        [_TUILE_A, _TUILE_B, _TUILE_C, tri_auto,
         _etat(chevalet_serveur if chevalet_serveur is not None else [_TUILE_A, _TUILE_B, _TUILE_C])],
    )


def _chevalet_ids(page):
    return [t["id"] for t in page.evaluate("chevaletLocal")]


def test_tuile_reprise_zone_de_pose_retrouve_sa_place_triee(page):
    # Tri automatique coché : pose rouge_8 dans la zone de pose, puis la
    # reprend AVANT de jouer. Elle doit retomber à sa place triée du chevalet
    # (entre rouge_2 et bleu_2), pas n'importe où.
    _preparer_chevalet(page, tri_auto=True)
    page.evaluate(
        "(id) => { tuileSelectionnee = id; placerTuileDansRangee(); }",
        _TUILE_A["id"],
    )
    assert _chevalet_ids(page) == ["bleu_2", "rouge_2"]

    page.evaluate("(id) => reprendreTuileRangee(id, 0)", _TUILE_A["id"])
    assert _chevalet_ids(page) == _ORDRE_TRIE
    assert page._erreurs_console == []


def test_tuile_reprise_zone_de_pose_sans_tri_auto_va_en_fin(page):
    # Case décochée : comportement d'avant inchangé, la tuile reprise repart
    # simplement en fin de chevalet.
    _preparer_chevalet(page, tri_auto=False)
    page.evaluate(
        "(id) => { tuileSelectionnee = id; placerTuileDansRangee(); }",
        _TUILE_A["id"],
    )
    page.evaluate("(id) => reprendreTuileRangee(id, 0)", _TUILE_A["id"])
    assert _chevalet_ids(page) == ["bleu_2", "rouge_2", "rouge_8"]
    assert page._erreurs_console == []


def test_tuile_reprise_sur_le_tapis_retrouve_sa_place_triee(page):
    # Même défaut pour une tuile de la main déjà posée sur le tapis ce tour
    # (etendreTapis), puis reprise via reprendreTuile().
    _preparer_chevalet(page, tri_auto=True)
    page.evaluate(
        """(id) => {
            tuileSelectionnee = id;
            plateauLocal = [[{id: "noir_5", valeur: 5, couleur: "noir", est_joker: false}]];
            etendreTapis(0, "fin");
        }""",
        _TUILE_A["id"],
    )
    assert _chevalet_ids(page) == ["bleu_2", "rouge_2"]

    page.evaluate("(id) => reprendreTuile(id)", _TUILE_A["id"])
    assert _chevalet_ids(page) == _ORDRE_TRIE
    assert page._erreurs_console == []


def test_vider_rangee_retrouve_la_place_triee(page):
    # Troisième chemin de retour au chevalet : vider une rangée de pose
    # entière (bouton "✕") plutôt que reprendre une seule tuile.
    _preparer_chevalet(page, tri_auto=True)
    page.evaluate(
        "(id) => { tuileSelectionnee = id; placerTuileDansRangee(); }",
        _TUILE_A["id"],
    )
    page.evaluate("() => viderRangee(0)")
    assert _chevalet_ids(page) == _ORDRE_TRIE
    assert page._erreurs_console == []


def test_annulation_du_tour_retrie_le_chevalet(page):
    # onAnnuler() repart de l'ordre SERVEUR (reinitChevaletLocal), jamais
    # trié : avec la case cochée, il doit être retrié tout de suite après,
    # comme pour une reprise individuelle (issue #251, qui généralise le
    # correctif déjà appliqué au rejeu de l'IA par l'issue #158).
    chevalet_serveur = [_TUILE_B, _TUILE_C, _TUILE_A]  # ordre serveur non trié
    _preparer_chevalet(page, tri_auto=True, chevalet_serveur=chevalet_serveur)
    page.evaluate("async () => { await onAnnuler(); }")
    assert _chevalet_ids(page) == _ORDRE_TRIE


def test_annulation_du_tour_sans_tri_auto_garde_ordre_serveur(page):
    chevalet_serveur = [_TUILE_B, _TUILE_C, _TUILE_A]
    _preparer_chevalet(page, tri_auto=False, chevalet_serveur=chevalet_serveur)
    page.evaluate("async () => { await onAnnuler(); }")
    assert _chevalet_ids(page) == ["bleu_2", "rouge_2", "rouge_8"]
