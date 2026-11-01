#!/usr/bin/env python3
"""Corpus de positions réelles de tour d'IA, pour la mesure de limites de
volume de calcul du solveur (issue #222). Partagé par
``scripts/generer_corpus_positions_222.py`` (constitution du corpus) et
``scripts/mesurer_volume_solveur_222.py`` (mesure elle-même).

Chaque position est encodée de façon COMPACTE : seules les tuiles vraiment
nécessaires pour rejouer la résolution du coup (plateau + chevalet du joueur
au trait + mise initiale faite/non faite + réglages de mise) sont conservées,
et chaque tuile est réduite à son identifiant (``"rouge_7_a"``, ``"joker_2"``)
plutôt qu'au dict complet ``{"id", "valeur", "couleur", "est_joker"}`` —
``valeur``/``couleur``/``est_joker`` se déduisent intégralement de l'identifiant
(voir ``rummikub.moteur.tuiles.creer_sac``), ce qui réduit la taille du fichier
d'un facteur ~5 sans perdre d'information. Ceci est un format de MESURE
séparé : aucune autre partie du projet n'en dépend.
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rummikub.config import COULEURS_JOKERS  # noqa: E402


# --------------------------------------------------------------------------- #
# Identifiant de tuile <-> dict complet (déduction pure, pas de dépendance à
# une partie en cours — voir ``tuiles.creer_sac``, format stable du projet).
# --------------------------------------------------------------------------- #

def tuile_dict_depuis_id(id_tuile: str) -> dict:
    """Reconstitue le dict complet d'une tuile à partir de son seul
    identifiant (inverse de ``tuiles.creer_sac``)."""
    if id_tuile.startswith("joker_"):
        n = int(id_tuile.split("_", 1)[1])
        couleur = COULEURS_JOKERS[(n - 1) % len(COULEURS_JOKERS)]
        return {"id": id_tuile, "valeur": None, "couleur": couleur,
                "est_joker": True}
    couleur, valeur, _exemplaire = id_tuile.rsplit("_", 2)
    return {"id": id_tuile, "valeur": int(valeur), "couleur": couleur,
            "est_joker": False}


def _combo_ids(combo: list[dict]) -> list[str]:
    return [t["id"] for t in combo]


def _plateau_ids(plateau: list[list[dict]]) -> list[list[str]]:
    return [_combo_ids(combo) for combo in plateau]


def _plateau_depuis_ids(plateau_ids: list[list[str]]) -> list[list[dict]]:
    return [[tuile_dict_depuis_id(i) for i in combo] for combo in plateau_ids]


# --------------------------------------------------------------------------- #
# Position compacte <-> état minimal exploitable par les solveurs
# --------------------------------------------------------------------------- #

def position_depuis_etat(etat: dict, idx: int, meta: dict) -> dict:
    """Construit une position compacte à partir d'un ``etat`` de partie en
    cours et de l'index du joueur au trait. ``meta`` (phase, graine, niveau,
    nb_joueurs, tour...) est stockée telle quelle à titre documentaire."""
    joueur = etat["joueurs"][idx]
    config_regles = etat.get("config", {})
    return {
        "meta": meta,
        "plateau": _plateau_ids(etat.get("plateau", [])),
        "chevalet": _combo_ids(joueur["chevalet"]),
        "mise_initiale_faite": bool(joueur.get("mise_initiale_faite", True)),
        "mise_initiale_min": config_regles.get("mise_initiale_min"),
        "nb_manches": config_regles.get("nb_manches", 1),
    }


def etat_depuis_position(position: dict) -> tuple[dict, int]:
    """Reconstruit un ``(etat, idx)`` minimal, directement exploitable par
    ``solveur_exact.resoudre_exact`` et ``solveur.resoudre_coup`` (les deux ne
    lisent, pour l'idx fourni, que ``plateau``, ``joueurs[idx].chevalet``,
    ``joueurs[idx].mise_initiale_faite`` et ``config``). ``idx`` vaut toujours
    0 dans l'état reconstruit : un seul joueur (celui au trait) y figure."""
    plateau = _plateau_depuis_ids(position["plateau"])
    chevalet = [tuile_dict_depuis_id(i) for i in position["chevalet"]]
    config_regles = {"nb_manches": position.get("nb_manches", 1)}
    if position.get("mise_initiale_min") is not None:
        config_regles["mise_initiale_min"] = position["mise_initiale_min"]
    etat = {
        "plateau": plateau,
        "joueurs": [{
            "chevalet": chevalet,
            "mise_initiale_faite": position.get("mise_initiale_faite", True),
        }],
        "config": config_regles,
    }
    return etat, 0


def nb_tuiles_plateau(position: dict) -> int:
    return sum(len(combo) for combo in position["plateau"])


def nb_tuiles_main(position: dict) -> int:
    return len(position["chevalet"])
