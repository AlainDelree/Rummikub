import json, pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).parent
WEB = ROOT / "src" / "rummikub" / "ui" / "web"
URL = f"file://{WEB}/jeu.html"

ETAT = {
    "index_joueur_actuel": 0,
    "manche_terminee": False,
    "pioche": ["x"] * 10,
    "historique": [],
    "config": {"ia_auto": False, "mode_reorg": "clic", "vitesse_ia": "Normale"},
    "joueurs": [
        {
            "nom": "Alain", "est_ia": False, "mise_initiale_faite": True,
            "score_manche": 0, "avatar_index": None,
            "chevalet": [
                {"id": "noir_6_a", "valeur": 6, "couleur": "noir", "est_joker": False},
            ],
        },
        {
            "nom": "Ordi", "est_ia": True, "niveau": "facile", "mise_initiale_faite": True,
            "score_manche": 0, "avatar_index": None,
            "chevalet": [{"id": "x1", "valeur": 1, "couleur": "rouge", "est_joker": False}],
        },
    ],
    "plateau": [
        [
            {"id": "noir_2_a", "valeur": 2, "couleur": "noir", "est_joker": False},
            {"id": "noir_3_a", "valeur": 3, "couleur": "noir", "est_joker": False},
            {"id": "noir_4_a", "valeur": 4, "couleur": "noir", "est_joker": False},
            {"id": "noir_5_a", "valeur": 5, "couleur": "noir", "est_joker": False},
        ]
    ],
}

INIT_SCRIPT = f"""
window.pywebview = {{
  api: {{
    jeu_get_etat: async () => ({json.dumps(ETAT)}),
    jeu_jouer_coup: async () => ({{ok: true}}),
  }}
}};
"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.add_init_script(INIT_SCRIPT)
    msgs = []
    page.on("console", lambda m: msgs.append(m.text))
    page.on("pageerror", lambda e: msgs.append("PAGEERROR: " + str(e)))
    page.goto(URL)
    page.wait_for_timeout(300)

    print("---- AVANT double-clic ----")
    print("nb tuiles plateau:", len(page.query_selector_all('#zone-plateau .tuile-jeu')))
    print("nb tuiles travail (rangee 0):", len(page.query_selector_all('.rangee-tuiles[data-rangee="0"] .tuile-jeu')))

    # Double-clic réel sur la 1re tuile du tapis (noir_2_a)
    tuile = page.query_selector('#zone-plateau .tuile-jeu')
    tuile.dblclick()
    page.wait_for_timeout(200)

    print("---- APRES double-clic (via page.dblclick) ----")
    print("nb tuiles plateau:", len(page.query_selector_all('#zone-plateau .tuile-jeu')))
    print("nb tuiles travail (rangee 0):", len(page.query_selector_all('.rangee-tuiles[data-rangee="0"] .tuile-jeu')))
    sel = page.evaluate("tuileSelectionnee")
    print("tuileSelectionnee:", sel)
    combo_active = page.evaluate("comboActive")
    print("comboActive:", combo_active)
    fantome = page.query_selector('#tuile-fantome')
    print("fantome present:", fantome is not None)

    print("---- CONSOLE/ERRORS ----")
    for m in msgs:
        print(m)

    browser.close()
