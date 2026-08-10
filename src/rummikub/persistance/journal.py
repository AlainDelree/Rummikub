"""Journal de partie optionnel : trace chaque action de jeu dans un fichier
JSON horodaté afin de pouvoir rejouer une partie et identifier à quel coup une
tuile (ex. un joker) a été perdue.

Activé uniquement si ``config.LOG_PARTIES`` est ``True``. Quand il est ``False``
(défaut), :func:`logger_action` retourne immédiatement : aucun fichier n'est
créé, aucun overhead n'est introduit.

Les fichiers sont écrits sous ``RACINE_DATA/logs_parties`` et nommés
``partie_AAAAMMJJ_HHMMSS.json`` (horodatage de la première action de la partie).
Au plus :data:`MAX_FICHIERS` fichiers sont conservés — le plus ancien est
supprimé au-delà.

Remarque : seules les actions qui transitent par le back-end Python sont
tracées (pose, pioche, fin de tour, annulation, tour IA). Le tri du chevalet est
purement côté JS et ne remonte jamais au serveur : il n'est donc pas journalisé.
"""

import copy
import json
from datetime import datetime
from pathlib import Path

from rummikub import config

# Nombre maximum de fichiers de journal conservés dans le dossier de logs.
MAX_FICHIERS = 20

# Cache mémoire : id_partie -> {"chemin": Path, "data": dict}. Évite de relire le
# fichier à chaque action. Perdu au redémarrage de l'application (une partie
# reprise repart alors sur un nouveau fichier), ce qui est acceptable pour un
# simple outil de débogage.
_journaux: dict = {}


def _dossier_logs() -> Path:
    return config.RACINE_DATA / "logs_parties"


def _noms_joueurs(etat: dict) -> list:
    return [j.get("nom") for j in etat.get("joueurs", [])]


def _main_humain(etat: dict) -> list:
    """Chevalet complet du premier joueur humain (``est_ia`` faux)."""
    for j in etat.get("joueurs", []):
        if not j.get("est_ia"):
            return copy.deepcopy(j.get("chevalet", []))
    return []


def _mains_joueurs(etat: dict) -> list:
    """Chevalets de tous les joueurs (humain + IA), dans le même ordre que
    ``etat["joueurs"]``. Chaque entrée porte le nom du joueur et sa liste de
    tuiles, ce qui permet de vérifier la conservation des 106 tuiles à chaque
    coup (mains + pioche + plateau)."""
    return [
        {"nom": j.get("nom"), "tuiles": copy.deepcopy(j.get("chevalet", []))}
        for j in etat.get("joueurs", [])
    ]


def _rotation(dossier: Path) -> None:
    """Conserve au plus ``MAX_FICHIERS - 1`` fichiers avant d'en créer un nouveau
    (le total après création reste donc <= MAX_FICHIERS). Les noms étant
    horodatés, le tri lexicographique équivaut au tri chronologique."""
    fichiers = sorted(dossier.glob("partie_*.json"))
    surplus = len(fichiers) - (MAX_FICHIERS - 1)
    for f in fichiers[:max(0, surplus)]:
        try:
            f.unlink()
        except OSError:
            pass


def _creer_journal(etat: dict) -> dict:
    dossier = _dossier_logs()
    dossier.mkdir(parents=True, exist_ok=True)
    _rotation(dossier)
    debut = datetime.now()
    nom = "partie_" + debut.strftime("%Y%m%d_%H%M%S") + ".json"
    data = {
        "partie_id": etat.get("id"),
        "debut": debut.isoformat(timespec="seconds"),
        "joueurs": _noms_joueurs(etat),
        "actions": [],
    }
    return {"chemin": dossier / nom, "data": data}


def logger_action(etat: dict, action: str) -> None:
    """Enregistre une action de jeu dans le journal de la partie courante.

    ``action`` : type d'action (ex. ``"pose"``, ``"pioche"``, ``"fin_de_tour"``,
    ``"annulation"``, ``"tour_ia"``).

    No-op immédiat si ``config.LOG_PARTIES`` est ``False``. Toute erreur d'écriture
    est silencieusement ignorée : le journal ne doit jamais interrompre le jeu.
    """
    if not getattr(config, "LOG_PARTIES", False):
        return
    if not etat:
        return
    try:
        pid = etat.get("id")
        journal = _journaux.get(pid)
        if journal is None:
            journal = _creer_journal(etat)
            _journaux[pid] = journal
        journal["data"]["actions"].append({
            "horodatage": datetime.now().isoformat(timespec="seconds"),
            "action": action,
            "tour": etat.get("tour_numero"),
            "joueur_actuel": etat.get("index_joueur_actuel"),
            "main_humain": _main_humain(etat),
            "mains_joueurs": _mains_joueurs(etat),
            "plateau": copy.deepcopy(etat.get("plateau", [])),
            "pioche": copy.deepcopy(etat.get("pioche", [])),
            "sac_restant": len(etat.get("pioche", [])),
        })
        with open(journal["chemin"], "w", encoding="utf-8") as f:
            json.dump(journal["data"], f, ensure_ascii=False, indent=2)
    except Exception:
        # Le journal est un outil de débogage : une écriture qui échoue ne doit
        # jamais faire échouer l'action de jeu qui vient d'être traitée.
        pass
