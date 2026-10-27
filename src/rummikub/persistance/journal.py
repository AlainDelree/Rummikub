"""Journal de partie optionnel : trace chaque action de jeu dans un fichier
JSON horodaté afin de pouvoir rejouer une partie, identifier à quel coup une
tuile (ex. un joker) a été perdue, et établir un bilan par niveau d'IA (issue
#185, voir ``persistance/bilan.py`` et ``scripts/bilan_parties.py``).

Activé uniquement si ``config.LOG_PARTIES`` est ``True``. Quand il est ``False``
(défaut), :func:`logger_action` retourne immédiatement : aucun fichier n'est
créé, aucun overhead n'est introduit.

Les fichiers sont écrits sous ``RACINE_DATA/logs_parties`` et nommés
``partie_AAAAMMJJ_HHMMSS.json`` (horodatage de la première action de la partie).
Au plus :data:`MAX_FICHIERS` fichiers sont conservés — le plus ancien est
supprimé au-delà.

Remarque : seules les actions qui transitent par le back-end Python sont
tracées (pose, pioche, passe, annulation, tour IA). Le tri du chevalet est
purement côté JS et ne remonte jamais au serveur : il n'est donc pas journalisé.

Format d'un fichier (clés au niveau racine) :
    ``partie_id``, ``debut`` (ISO), ``joueurs`` (liste de
    ``{"nom", "est_ia", "niveau"}``), ``actions`` (liste d'entrées, voir
    :func:`logger_action`).

Chaque entrée de ``actions`` porte, en plus des champs de débogage déjà
existants (mains, plateau, pioche...) :
    ``auteur_index`` : index du joueur qui a pris la décision de ce tour.
    ``action`` : ``"pose"``, ``"pioche"``, ``"passe"`` ou ``"annulation"``.
    ``nb_tuiles_posees`` : nombre de tuiles RÉELLEMENT sorties de la main du
    joueur par cette décision (0 sauf pour ``"pose"`` — voir issue #201 :
    avant ce correctif, ce champ comptait aussi les tuiles du plateau
    déplacées ce tour pour un coup HUMAIN, ce qui le rendait supérieur au
    nombre réel de tuiles posées depuis la main ; un coup d'IA n'a jamais
    été affecté, ``ids_tuiles`` ne contenant pour elle que des tuiles de la
    main — voir ``moteur/solveur.py``/``moteur/ia.py``).
    ``nb_tuiles_deplacees`` : nombre de tuiles du plateau déplacées ce tour
    sans venir de la main (0 sauf pour ``"pose"`` d'un joueur humain — champ
    ajouté par #201, absent des journaux antérieurs : à lire comme 0 dans ce
    cas, voir ``persistance/coups_rates.py`` qui ne s'appuie d'ailleurs
    jamais sur ce champ, seulement sur la variation réelle de la main).
    ``termine`` : ``True`` si la partie est terminée après cette action.
    ``gagnant_index`` : index du gagnant de la manche si ``termine``, sinon
    ``None``.

Une partie dont la DERNIÈRE action enregistrée n'a pas ``termine: True`` a été
abandonnée en cours (ou est toujours en cours) : ``persistance/bilan.py``
l'exclut du bilan sur ce seul critère. Les fichiers écrits par une version
antérieure du journal (sans ces champs) restent lisibles : les champs absents
sont traités comme ``None``/``False``, ce qui les range naturellement parmi
les parties non exploitables pour le bilan plutôt que de faire planter sa
lecture.
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


def _joueurs_info(etat: dict) -> list:
    """Identité des joueurs pour l'en-tête du journal (issue #185) : nom,
    statut IA et niveau — nécessaires au bilan par niveau d'IA sans avoir à
    rouvrir la base SQLite (qui ne garde que les 5 dernières parties)."""
    return [{"nom": j.get("nom"), "est_ia": bool(j.get("est_ia")),
             "niveau": j.get("niveau")} for j in etat.get("joueurs", [])]


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
        "joueurs": _joueurs_info(etat),
        "actions": [],
    }
    return {"chemin": dossier / nom, "data": data}


def logger_action(etat: dict, action: str, *,
                   auteur_index: int = None, nb_tuiles_posees: int = 0,
                   nb_tuiles_deplacees: int = 0) -> None:
    """Enregistre une action de jeu dans le journal de la partie courante.

    ``action`` : type de décision prise (``"pose"``, ``"pioche"``, ``"passe"``
    ou ``"annulation"``).
    ``auteur_index`` : index (dans ``etat["joueurs"]``) du joueur qui a pris
    cette décision — à distinguer de ``etat["index_joueur_actuel"]``, déjà
    avancé au joueur suivant au moment de l'appel.
    ``nb_tuiles_posees`` : nombre de tuiles RÉELLEMENT sorties de la main du
    joueur par cette décision (0 pour ``"pioche"``/``"passe"``/``"annulation"``,
    et pour une IA, dont ``ids_tuiles`` ne contient jamais que des tuiles de
    la main — voir issue #201).
    ``nb_tuiles_deplacees`` : nombre de tuiles du plateau déplacées (pas
    posées) par cette même décision (0 sauf, potentiellement, pour une pose
    humaine — voir ``ui/api.py:jeu_jouer_coup``).

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
            "auteur_index": auteur_index,
            "nb_tuiles_posees": nb_tuiles_posees,
            "nb_tuiles_deplacees": nb_tuiles_deplacees,
            "termine": bool(etat.get("terminee")),
            "gagnant_index": etat.get("gagnant_manche_index"),
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
