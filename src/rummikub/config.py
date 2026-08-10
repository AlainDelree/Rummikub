from pathlib import Path
import os
import sys

if getattr(sys, "frozen", False):
    RACINE_PROJET = Path(sys._MEIPASS)
    # Application gelée (PyInstaller) : installée dans un dossier en lecture
    # seule (ex. C:\Program Files\Rummikub), donc les données utilisateur
    # (SQLite, config.json) doivent aller dans un dossier accessible en
    # écriture — %APPDATA%\Rummikub, sinon PermissionError [WinError 5].
    RACINE_DATA = Path(os.environ.get("APPDATA", Path.home())) / "Rummikub"
    FICHIER_CFG = RACINE_DATA / "config.json"
else:
    RACINE_PROJET = Path(__file__).resolve().parent.parent.parent
    RACINE_DATA  = RACINE_PROJET / "data"
    FICHIER_CFG  = RACINE_PROJET / "config.json"

RACINE_WEB   = Path(__file__).parent / "ui" / "web"
FICHIER_DB   = RACINE_DATA / "parties.db"

COULEURS           = ["rouge", "bleu", "jaune", "noir"]
# Couleurs des 2 jokers (standard Rummikub : un rouge, un noir). L'ordre suit
# les IDs joker_1, joker_2. Purement visuel : la logique de jeu identifie un
# joker par son drapeau est_joker, jamais par sa couleur.
COULEURS_JOKERS    = ["rouge", "noir"]
NB_SERIES          = 2
VALEUR_MIN         = 1
VALEUR_MAX         = 13
NB_JOKERS          = 2
NB_TUILES_DEPART   = 14
MISE_INITIALE_MIN  = 30
NIVEAUX            = ["Débutant", "Facile", "Intermédiaire", "Avancé", "Expert"]
AVATARS            = [f"avatar-{i:02d}" for i in range(1, 16)]

# Journal de partie (débogage) : si True, chaque action de jeu est tracée dans
# un fichier JSON horodaté sous RACINE_DATA/logs_parties (voir persistance/
# journal.py). Désactivé par défaut → aucun overhead, aucun fichier créé.
# Valeur pilotable depuis la config utilisateur JSON (clé "log_parties") :
# elle est écrasée au chargement de la config (voir reglages.charger()).
LOG_PARTIES        = False
