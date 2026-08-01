import json
from rummikub.config import FICHIER_CFG, RACINE_DATA

DEFAUTS = {
    "prenom": "Joueur",
    "avatar_index": 0,
    "mise_initiale_min": 30,
    "nb_manches": 1,
    "valeur_joker_penalite": 30,
    "vitesse_ia": "Lente",
    "mode_reorg": "clic",   # "clic" (appui long + clic) ou "drag" (glisser-déposer)
}

def charger():
    try:
        return {**DEFAUTS, **json.loads(FICHIER_CFG.read_text("utf-8"))}
    except Exception:
        return dict(DEFAUTS)

def sauvegarder(data: dict):
    merged = {**charger(), **data}
    RACINE_DATA.mkdir(parents=True, exist_ok=True)
    FICHIER_CFG.write_text(json.dumps(merged, ensure_ascii=False, indent=2), "utf-8")
    return merged
