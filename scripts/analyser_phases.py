#!/usr/bin/env python3
"""Analyse une trace brute par tour (``comparer_niveaux_ia.py
--export-trace``, issue #226) en découpant chaque manche, JOUEUR PAR JOUEUR,
en trois phases :

  1. **Prologue** : tous les tours d'un joueur avant sa propre ouverture
     (y compris le tour de l'ouverture elle-même, qui clôt le prologue —
     avant ce tour, le joueur ne peut ni toucher au tapis ni s'en servir).
  2. **Développement** : après l'ouverture, tant que le chevalet compte
     PLUS de ``--seuil`` tuiles AU DÉBUT du tour (défaut 5).
  3. **Fin** : chevalet de ``--seuil`` tuiles ou moins au début du tour.

Les phases sont définies JOUEUR PAR JOUEUR (l'ouverture d'un joueur ne
dépend pas de celle de l'autre) — un même tour global peut donc être
« prologue » pour le joueur qui vient de jouer et « développement » pour
l'autre, qui a déjà ouvert.

Ne modifie ni ne rejoue AUCUNE partie : pure lecture/analyse d'un fichier de
trace déjà produit. ``--seuil`` est répétable pour comparer plusieurs
découpages en un seul passage sur le fichier (ex. ``--seuil 5 --seuil 6``).

Question centrale (voir CONTEXTE.md §13) : à quelle phase se creuse l'écart
entre le futur gagnant et le futur perdant d'une manche ? Trois « moments »
sont comparés :
  (a) à la FIN du prologue (quand le SECOND joueur à ouvrir vient d'ouvrir) ;
  (b) à l'ENTRÉE en phase Fin de CHAQUE joueur (deux événements possibles par
      manche, regroupés) ;
pour chacun, on calcule l'écart de tuiles restantes en main entre les deux
joueurs à cet instant, et le taux de victoire du joueur alors en avance
(moins de tuiles en main).

Usage :

    python scripts/analyser_phases.py /tmp/trace.jsonl
    python scripts/analyser_phases.py /tmp/trace.jsonl --seuil 5 --seuil 6
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rummikub.config import NB_TUILES_DEPART  # noqa: E402

PHASES = ("prologue", "developpement", "fin")
LIBELLES_PHASES = {
    "prologue": "Prologue (avant l'ouverture)",
    "developpement": "Développement (ouvert, chevalet > seuil)",
    "fin": "Fin (ouvert, chevalet <= seuil)",
}


# --------------------------------------------------------------------------- #
# Lecture + regroupement par manche
# --------------------------------------------------------------------------- #

def charger_trace(chemin) -> list[dict]:
    lignes = []
    with open(chemin, encoding="utf-8") as f:
        for num, brute in enumerate(f, start=1):
            brute = brute.strip()
            if not brute:
                continue
            try:
                lignes.append(json.loads(brute))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{chemin} ligne {num} : JSON invalide ({exc})") from exc
    return lignes


def regrouper_par_manche(lignes: list[dict]) -> dict:
    """Regroupe les lignes par manche (clé : donne, ordre, manche — une
    manche est indépendante des autres, même d'un même match : redistribution
    complète à chaque ``nouvelle_manche``)."""
    manches: dict = defaultdict(lambda: {"tours": [], "resultat": None})
    for ligne in lignes:
        cle = (ligne["donne"], tuple(ligne["ordre"]), ligne["manche"])
        if ligne["type"] == "tour":
            manches[cle]["tours"].append(ligne)
        elif ligne["type"] == "resultat":
            manches[cle]["resultat"] = ligne
    return manches


# --------------------------------------------------------------------------- #
# Classification d'un tour en phase (#226)
# --------------------------------------------------------------------------- #

def phase_du_tour(ligne: dict, seuil: int) -> str:
    if not ligne["ouvert_avant"]:
        return "prologue"
    return "fin" if ligne["chevalet_avant"] <= seuil else "developpement"


# --------------------------------------------------------------------------- #
# Analyse d'une manche
# --------------------------------------------------------------------------- #

def _stats_vides() -> dict:
    return {ph: {"n_tours": 0, "tuiles_posees": 0, "pioches": 0} for ph in PHASES}


def analyser_manche(tours: list[dict], resultat: dict, seuil: int) -> dict:
    tours_tries = sorted(tours, key=lambda l: l["tour"])
    ordre = resultat["ordre"]
    vainqueur_idx = ordre.index(resultat["vainqueur_camp"])
    perdant_idx = 1 - vainqueur_idx

    par_idx = {0: [l for l in tours_tries if l["index_joueur"] == 0],
               1: [l for l in tours_tries if l["index_joueur"] == 1]}

    joueurs = {}
    for idx in (0, 1):
        stats = _stats_vides()
        ouverture_tour = None
        chevalet_a_ouverture = None
        nb_pioches_avant_ouverture = 0
        for ligne in par_idx[idx]:
            phase = phase_du_tour(ligne, seuil)
            s = stats[phase]
            s["n_tours"] += 1
            s["tuiles_posees"] += ligne["nb_tuiles_posees"]
            if ligne["action"] == "pioche":
                s["pioches"] += 1
            if phase == "prologue":
                if ligne["ouvert_apres"]:
                    ouverture_tour = ligne["tour"]
                    chevalet_a_ouverture = ligne["chevalet_avant"]
                elif ligne["action"] == "pioche":
                    nb_pioches_avant_ouverture += 1
        joueurs[idx] = {
            "niveau": par_idx[idx][0]["niveau"] if par_idx[idx] else None,
            "stats": stats,
            "ouverture_tour": ouverture_tour,
            "chevalet_a_ouverture": chevalet_a_ouverture,
            "nb_pioches_avant_ouverture": nb_pioches_avant_ouverture,
        }

    # Replay chronologique pour les deux points de bascule (#226, point 2) :
    # état courant du chevalet de chacun, mis à jour après chaque tour.
    chevalet_actuel = {0: NB_TUILES_DEPART, 1: NB_TUILES_DEPART}
    ouverture_vue = {0: False, 1: False}
    fin_prologue = None
    entree_fin = {0: None, 1: None}
    for ligne in tours_tries:
        idx = ligne["index_joueur"]
        autre = 1 - idx
        if (ligne["ouvert_avant"] and entree_fin[idx] is None
                and ligne["chevalet_avant"] <= seuil):
            entree_fin[idx] = {
                "tour": ligne["tour"],
                "chevalet_lui": ligne["chevalet_avant"],
                "chevalet_autre": chevalet_actuel[autre],
            }
        chevalet_actuel[idx] = ligne["chevalet_apres"]
        if (not ligne["ouvert_avant"]) and ligne["ouvert_apres"]:
            ouverture_vue[idx] = True
            if ouverture_vue[autre] and fin_prologue is None:
                fin_prologue = {
                    "tour": ligne["tour"],
                    "idx_second_ouvreur": idx,
                    "chevalet_second_ouvreur": chevalet_actuel[idx],
                    "chevalet_premier_ouvreur": chevalet_actuel[autre],
                }

    return {
        "vainqueur_idx": vainqueur_idx, "perdant_idx": perdant_idx,
        "joueurs": joueurs,
        "fin_prologue": fin_prologue,
        "entree_fin": entree_fin,
        "fin_manche": resultat["fin"],
        "tours_totaux": resultat["tours"],
    }


# --------------------------------------------------------------------------- #
# Agrégation sur toutes les manches
# --------------------------------------------------------------------------- #

def moyenne(valeurs: list[float]) -> float:
    return sum(valeurs) / len(valeurs) if valeurs else 0.0


def _resume_distribution(valeurs: list[float]) -> dict:
    if not valeurs:
        return {"n": 0, "moyenne": 0.0, "mediane": 0.0, "min": 0.0, "max": 0.0}
    return {
        "n": len(valeurs), "moyenne": moyenne(valeurs),
        "mediane": median(valeurs), "min": min(valeurs), "max": max(valeurs),
    }


def _ajouter_checkpoint(compteur: dict, idx_leader, idx_vainqueur, ecart: int) -> None:
    """``idx_leader`` est ``None`` en cas d'égalité stricte (pas de joueur en
    avance) — compté à part, jamais mêlé au taux de victoire."""
    compteur["ecarts"].append(ecart)
    if idx_leader is None:
        compteur["egalites"] += 1
        return
    compteur["n"] += 1
    if idx_leader == idx_vainqueur:
        compteur["leader_gagne"] += 1


def _nouveau_checkpoint() -> dict:
    return {"n": 0, "leader_gagne": 0, "egalites": 0, "ecarts": []}


def analyser(lignes: list[dict], seuil: int) -> dict:
    manches_brutes = regrouper_par_manche(lignes)
    manches_ignorees = 0
    manches = []
    for groupe in manches_brutes.values():
        if groupe["resultat"] is None:
            manches_ignorees += 1
            continue
        manches.append(analyser_manche(groupe["tours"], groupe["resultat"], seuil))

    duree_phase = {role: {ph: [] for ph in PHASES} for role in ("gagnant", "perdant")}
    tuiles_posees_phase = {role: {ph: [] for ph in PHASES} for role in ("gagnant", "perdant")}
    pioches_phase = {role: {ph: [0, 0] for ph in PHASES} for role in ("gagnant", "perdant")}
    tour_ouverture = {"gagnant": [], "perdant": []}
    pioches_avant_ouverture = {"gagnant": [], "perdant": []}
    chevalet_a_ouverture = {"gagnant": [], "perdant": []}

    fins_manche = defaultdict(int)
    manches_sans_double_ouverture = 0

    cp_fin_prologue = _nouveau_checkpoint()
    cp_entree_fin = _nouveau_checkpoint()

    for m in manches:
        fins_manche[m["fin_manche"]] += 1
        for idx, role in ((m["vainqueur_idx"], "gagnant"), (m["perdant_idx"], "perdant")):
            info = m["joueurs"][idx]
            tour_ouverture[role].append(info["ouverture_tour"])
            pioches_avant_ouverture[role].append(info["nb_pioches_avant_ouverture"])
            if info["chevalet_a_ouverture"] is not None:
                chevalet_a_ouverture[role].append(info["chevalet_a_ouverture"])
            for ph in PHASES:
                s = info["stats"][ph]
                duree_phase[role][ph].append(s["n_tours"])
                tuiles_posees_phase[role][ph].append(s["tuiles_posees"])
                pioches_phase[role][ph][0] += s["pioches"]
                pioches_phase[role][ph][1] += s["n_tours"]

        fp = m["fin_prologue"]
        if fp is None:
            manches_sans_double_ouverture += 1
        else:
            if fp["chevalet_second_ouvreur"] == fp["chevalet_premier_ouvreur"]:
                leader = None
            else:
                leader = (fp["idx_second_ouvreur"]
                         if fp["chevalet_second_ouvreur"] < fp["chevalet_premier_ouvreur"]
                         else 1 - fp["idx_second_ouvreur"])
            ecart = abs(fp["chevalet_second_ouvreur"] - fp["chevalet_premier_ouvreur"])
            _ajouter_checkpoint(cp_fin_prologue, leader, m["vainqueur_idx"], ecart)

        for idx in (0, 1):
            ef = m["entree_fin"][idx]
            if ef is None:
                continue
            autre = 1 - idx
            if ef["chevalet_lui"] == ef["chevalet_autre"]:
                leader = None
            else:
                leader = idx if ef["chevalet_lui"] < ef["chevalet_autre"] else autre
            ecart = abs(ef["chevalet_lui"] - ef["chevalet_autre"])
            _ajouter_checkpoint(cp_entree_fin, leader, m["vainqueur_idx"], ecart)

    return {
        "seuil": seuil,
        "nb_manches": len(manches),
        "manches_ignorees": manches_ignorees,
        "manches_sans_double_ouverture": manches_sans_double_ouverture,
        "fins_manche": dict(fins_manche),
        "duree_phase": duree_phase,
        "tuiles_posees_phase": tuiles_posees_phase,
        "pioches_phase": pioches_phase,
        "tour_ouverture": {role: _resume_distribution(
            [v for v in vals if v is not None])
            for role, vals in tour_ouverture.items()},
        "pioches_avant_ouverture": {role: _resume_distribution(vals)
                                   for role, vals in pioches_avant_ouverture.items()},
        "chevalet_a_ouverture": {role: _resume_distribution(vals)
                                for role, vals in chevalet_a_ouverture.items()},
        "cp_fin_prologue": cp_fin_prologue,
        "cp_entree_fin": cp_entree_fin,
    }


# --------------------------------------------------------------------------- #
# Rapport
# --------------------------------------------------------------------------- #

def _taux(compteur: dict) -> tuple:
    if compteur["n"] == 0:
        return 0.0, 0
    return compteur["leader_gagne"] / compteur["n"], compteur["n"]


def afficher_rapport(resume: dict) -> None:
    seuil = resume["seuil"]
    print("=" * 70)
    print(f"ANALYSE PAR PHASES — seuil N = {seuil} tuile(s)")
    print(f"Manches analysées : {resume['nb_manches']} "
         f"(ignorées, arrêtées par le garde-fou avant résultat : "
         f"{resume['manches_ignorees']})")
    print(f"Fins de manche : " + ", ".join(
        f"{v} {k}" for k, v in resume["fins_manche"].items()))
    print("-" * 70)

    print("  DURÉE MOYENNE DE CHAQUE PHASE (en tours du joueur) :")
    for ph in PHASES:
        g = moyenne(resume["duree_phase"]["gagnant"][ph])
        p = moyenne(resume["duree_phase"]["perdant"][ph])
        print(f"    {LIBELLES_PHASES[ph]:<45} gagnant {g:5.1f}  perdant {p:5.1f}")
    print("-" * 70)

    print("  OUVERTURE :")
    for role in ("gagnant", "perdant"):
        d = resume["tour_ouverture"][role]
        print(f"    Tour d'ouverture ({role:<8}) : moyenne {d['moyenne']:.1f}, "
             f"médiane {d['mediane']:.1f}, min {d['min']:.0f}, max {d['max']:.0f} "
             f"(n={d['n']})")
    for role in ("gagnant", "perdant"):
        d = resume["pioches_avant_ouverture"][role]
        print(f"    Pioches avant ouverture ({role:<8}) : moyenne {d['moyenne']:.1f} "
             f"(n={d['n']})")
    for role in ("gagnant", "perdant"):
        d = resume["chevalet_a_ouverture"][role]
        print(f"    Chevalet à l'ouverture ({role:<8}) : moyenne {d['moyenne']:.1f} "
             f"(n={d['n']})")
    print("-" * 70)

    print("  TUILES POSÉES / TOUR ET FRÉQUENCE DE PIOCHE, PAR PHASE :")
    for role in ("gagnant", "perdant"):
        for ph in PHASES:
            n_tours = sum(resume["duree_phase"][role][ph])
            tuiles = sum(resume["tuiles_posees_phase"][role][ph])
            pioches, total = resume["pioches_phase"][role][ph]
            moy_tuiles = tuiles / n_tours if n_tours else 0.0
            freq_pioche = pioches / total if total else 0.0
            print(f"    {role:<8} / {LIBELLES_PHASES[ph]:<40} : "
                 f"{moy_tuiles:4.2f} tuile(s)/tour, "
                 f"pioche {freq_pioche * 100:4.1f} % ({total} tour(s))")
    print("-" * 70)

    print("  QUESTION CENTRALE — où l'écart se creuse-t-il ?")
    print(f"    Manches sans double ouverture observée (fin du prologue non "
         f"calculable) : {resume['manches_sans_double_ouverture']}")

    fp = resume["cp_fin_prologue"]
    taux_fp, n_fp = _taux(fp)
    print(f"    (a) FIN DU PROLOGUE (quand le second joueur ouvre) : "
         f"écart moyen {moyenne(fp['ecarts']):.1f} tuile(s) "
         f"({len(fp['ecarts'])} manche(s), {fp['egalites']} égalité(s)) — "
         f"le joueur en avance gagne {taux_fp * 100:.1f} % des manches (n={n_fp}).")

    ef = resume["cp_entree_fin"]
    taux_ef, n_ef = _taux(ef)
    print(f"    (b) ENTRÉE EN PHASE FIN (chaque joueur, événements regroupés) : "
         f"écart moyen {moyenne(ef['ecarts']):.1f} tuile(s) "
         f"({len(ef['ecarts'])} événement(s), {ef['egalites']} égalité(s)) — "
         f"le joueur en avance gagne {taux_ef * 100:.1f} % des manches (n={n_ef}).")
    print("=" * 70)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Analyse une trace brute par tour (--export-trace de "
                    "comparer_niveaux_ia.py) en phases prologue/"
                    "développement/fin (issue #226).")
    parser.add_argument("trace", help="Fichier de trace JSON Lines.")
    parser.add_argument("--seuil", type=int, action="append", default=None,
                        help="Seuil N de tuiles définissant la phase de fin "
                             "(répétable ; défaut : 5).")
    args = parser.parse_args(argv[1:])

    try:
        lignes = charger_trace(args.trace)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    if not lignes:
        parser.error(f"{args.trace} est vide ou ne contient aucune ligne lisible.")

    for seuil in (args.seuil or [5]):
        afficher_rapport(analyser(lignes, seuil))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
