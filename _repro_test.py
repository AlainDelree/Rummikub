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
            {"id": "noir_7_a", "valeur": 7, "couleur": "noir", "est_joker": False},
            {"id": "noir_8_a", "valeur": 8, "couleur": "noir", "est_joker": False},
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

    # Select the chevalet tile (the 6)
    page.click('#chevalet .tuile-jeu')
    page.wait_for_timeout(100)

    # Find the zone-ext-interne between 5 and 7 (index 4 in combo, 0-based: 2,3,4,5,[ins],7,8)
    # zones-ext-interne are created for idxTuile>0 ; order in combo: 2(0),3(1),4(2),5(3),7(4),8(5)
    # So the interne zone before '7' (idxTuile=4) is the 4th (0-indexed) zone-ext-interne -> nth-child
    zones = page.query_selector_all('.zone-ext-interne')
    print("nb zones-ext-interne:", len(zones))
    # click the one right before value 7 : that's the 4th interne zone (index 3, since idxTuile starts at 1)
    # idxTuile values with >0: 1,2,3,4,5 -> zones correspond to idxTuile=1..5, we want idxTuile=4 (before '7')
    zones[3].click()
    page.wait_for_timeout(200)

    html = page.inner_html("#zone-plateau")
    print("---- PLATEAU HTML ----")
    print(html)

    print("---- CONSOLE/ERRORS ----")
    for m in msgs:
        print(m)

    browser.close()
