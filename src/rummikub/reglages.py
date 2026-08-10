import json
from rummikub import config
from rummikub.config import FICHIER_CFG, RACINE_DATA

DEFAUTS = {
    "prenom": "Joueur",
    "avatar_index": 0,
    "mise_initiale_min": 30,
    "nb_manches": 1,
    "valeur_joker_penalite": 30,
    "vitesse_ia": "Lente",
    "mode_reorg": "clic",   # "clic" (appui long + clic) ou "drag" (glisser-déposer)
    "log_parties": False,   # journal de partie (débogage) : voir config.LOG_PARTIES
}

def charger():
    try:
        cfg = {**DEFAUTS, **json.loads(FICHIER_CFG.read_text("utf-8"))}
    except Exception:
        cfg = dict(DEFAUTS)
    # La préférence log_parties pilote la constante globale config.LOG_PARTIES,
    # lue dynamiquement par persistance/journal.py (via getattr). On la synchronise
    # à chaque chargement de la config utilisateur.
    config.LOG_PARTIES = bool(cfg.get("log_parties", False))
    return cfg

def sauvegarder(data: dict):
    merged = {**charger(), **data}
    RACINE_DATA.mkdir(parents=True, exist_ok=True)
    FICHIER_CFG.write_text(json.dumps(merged, ensure_ascii=False, indent=2), "utf-8")
    return merged
