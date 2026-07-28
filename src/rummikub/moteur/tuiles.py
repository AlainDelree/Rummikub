"""Modèle des tuiles Rummikub : dataclass Tuile, création/mélange/distribution."""

from dataclasses import dataclass
from typing import Optional
import random

from rummikub.config import (
    COULEURS,
    NB_SERIES,
    VALEUR_MIN,
    VALEUR_MAX,
    NB_JOKERS,
    NB_TUILES_DEPART,
)


@dataclass
class Tuile:
    id: str                 # ex. "rouge_7_a", "joker_1"
    valeur: Optional[int]   # 1-13, None si joker
    couleur: Optional[str]  # "rouge"|"bleu"|"jaune"|"noir", None si joker
    est_joker: bool = False

    def valeur_penalite(self, valeur_joker: int = 30) -> int:
        return valeur_joker if self.est_joker else (self.valeur or 0)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "valeur": self.valeur,
            "couleur": self.couleur,
            "est_joker": self.est_joker,
        }


def creer_sac() -> list[Tuile]:
    """2 séries × 4 couleurs × 13 valeurs + 2 jokers = 106 tuiles.

    IDs : "rouge_7_a", "rouge_7_b", "joker_1", "joker_2".
    """
    sac: list[Tuile] = []
    for serie in range(NB_SERIES):
        label = chr(ord("a") + serie)  # 'a', 'b', ...
        for couleur in COULEURS:
            for valeur in range(VALEUR_MIN, VALEUR_MAX + 1):
                sac.append(Tuile(f"{couleur}_{valeur}_{label}", valeur, couleur))
    for n in range(1, NB_JOKERS + 1):
        sac.append(Tuile(f"joker_{n}", None, None, est_joker=True))
    return sac


def melanger(sac: list[Tuile]) -> list[Tuile]:
    """Fisher-Yates ; retourne une nouvelle liste (n'altère pas l'entrée)."""
    resultat = list(sac)
    for i in range(len(resultat) - 1, 0, -1):
        j = random.randint(0, i)
        resultat[i], resultat[j] = resultat[j], resultat[i]
    return resultat


def distribuer(sac: list[Tuile], nb_joueurs: int) -> dict:
    """Mélange le sac puis distribue NB_TUILES_DEPART tuiles à chaque joueur.

    Retourne {"chevalets": [[Tuile×14], ...], "pioche": [Tuile...]}.
    """
    melange = melanger(sac)
    chevalets: list[list[Tuile]] = []
    curseur = 0
    for _ in range(nb_joueurs):
        chevalets.append(melange[curseur:curseur + NB_TUILES_DEPART])
        curseur += NB_TUILES_DEPART
    pioche = melange[curseur:]
    return {"chevalets": chevalets, "pioche": pioche}
