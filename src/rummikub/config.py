from pathlib import Path
import sys

if getattr(sys, "frozen", False):
    RACINE_PROJET = Path(sys._MEIPASS)
else:
    RACINE_PROJET = Path(__file__).resolve().parent.parent.parent

RACINE_WEB   = Path(__file__).parent / "ui" / "web"
RACINE_DATA  = RACINE_PROJET / "data"
FICHIER_DB   = RACINE_DATA / "parties.db"
FICHIER_CFG  = RACINE_PROJET / "config.json"

COULEURS           = ["rouge", "bleu", "jaune", "noir"]
NB_SERIES          = 2
VALEUR_MIN         = 1
VALEUR_MAX         = 13
NB_JOKERS          = 2
NB_TUILES_DEPART   = 14
MISE_INITIALE_MIN  = 30
NIVEAUX            = ["Débutant", "Facile", "Intermédiaire", "Avancé", "Expert"]
AVATARS            = [f"avatar-{i:02d}" for i in range(1, 16)]
