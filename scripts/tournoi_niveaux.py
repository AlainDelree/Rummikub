#!/usr/bin/env python3
r"""Tournoi à 2, 3 ou 4 IA de niveaux différents à UNE MÊME TABLE, avec
rotation des sièges, statistiques par niveau et reprise après interruption
(issue #276, suite de l'étude #275 — le moteur et ``scripts/simulation_ia.py``
savent déjà faire jouer 2 à 4 niveaux différents, sans aucune anomalie).

**Complément des duels, pas un outil de calibrage.** ``scripts/
comparer_niveaux_ia.py``/``calibrer_echelle.py`` restent la méthode de
calibrage de l'échelle (duels à deux, cible 60-70 %, voir docs/contexte/
niveaux_ia_calibrage.md). Ce script sert à VÉRIFIER l'ordre de force à
quatre joueurs à une même table (Alain : Expert, Avancé, Intermédiaire,
Facile) — il ne recalibre rien et ne modifie ni le moteur, ni l'IA, ni
``moteur/niveaux.py``.

Déroulement : pour chaque donne (distribution de tuiles), tous les niveaux
demandés jouent ENSEMBLE, à tour de rôle, sur ``len(niveaux)`` ROTATIONS des
sièges (rotation cyclique : chaque niveau occupe une fois chaque siège). La
graine est fixée AVANT la création de la partie, et seule l'affectation
niveau → siège change entre les rotations d'une même donne : la distribution
des tuiles est donc identique, et l'avantage du premier joueur s'annule,
comme le miroir à deux joueurs de ``comparer_niveaux_ia.py``.

Réutilise directement (même boucle de tour, même traitement des coups
invalides/tuiles disparues que ``scripts/simulation_ia.py``) :
  * ``moteur.ia.jouer_niveau_bride`` — le même chemin de production que le
    jeu (``jouer_ia``), avec un budget de temps du solveur explicite ;
  * ``_limite_temps_ferme`` — limite de temps FERME (sous-processus
    surveillé, Linux et Windows) ;
  * ``_verif_solveur_exact`` — refus de démarrer sans ``highspy``/``numpy`` ;
  * ``_rapport_duels.entete_machine`` — en-tête machine/dépendances.

Usage :

    # petit lot d'essai (10 donnes = 40 manches à 4 niveaux)
    python scripts/tournoi_niveaux.py --dossier /tmp/tournoi_276 --donnes 10

    # campagne complète (100 donnes = 400 manches), reprenable après coupure
    python scripts/tournoi_niveaux.py --dossier /tmp/tournoi_276 --donnes 100

    # trois niveaux seulement, noms sans accent acceptés (lanceur Windows)
    python scripts/tournoi_niveaux.py --dossier /tmp/t --niveaux Expert,Avance,Facile

    # lecture seule du rapport, sans rien jouer ni perturber un calcul en cours
    python scripts/tournoi_niveaux.py --dossier /tmp/tournoi_276 --statut

    # PC fixe Windows (venv dédié de calibration, même convention que
    # calibrer_echelle.py — voir docs/contexte/niveaux_ia_calibrage.md) :
    C:\Tournois\venv\Scripts\python.exe scripts\tournoi_niveaux.py --dossier C:\Tournois\tournoi_276 --donnes 10

Options :
    --niveaux LISTE     2 à 4 niveaux séparés par des virgules (défaut
                        « Expert,Avancé,Intermédiaire,Facile »). Les noms
                        sans accent sont acceptés (ex. « Avance »,
                        « Intermediaire ») — un nom inconnu est refusé avec
                        la liste des noms valides.
    --donnes N          Nombre de donnes distinctes (défaut 50 ; chacune
                        jouée en ``len(niveaux)`` rotations de sièges).
                        Augmenter sur un dossier existant PROLONGE la
                        campagne sans la recommencer.
    --seed N            Graine de base (défaut 0) : la donne i utilise la
                        graine ``seed + i``.
    --max-tours N       Garde-fou anti-blocage par manche (défaut 300).
    --budget-solveur S  Budget de temps du solveur par coup, en secondes,
                        appliqué à tous les niveaux (défaut : valeur du
                        jeu, 1,5 s).
    --dossier CHEMIN    Dossier où écrire les résultats et le rapport en
                        continu (hors du dépôt) — requis.
    --processus N       Nombre de processus en parallèle (1 ou 2, défaut 1).
    --limite-temps S    Limite de temps FERME pour toute la campagne
                        (garde-fou externe par sous-processus, voir
                        ``_limite_temps_ferme.py``).
    --statut            Affiche le rapport et quitte, sans rien jouer ni
                        rien écrire (lecture seule, n'interfère jamais avec
                        un calcul en cours).
    -v, --verbose       Journalise le détail de la campagne.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import statistics
import subprocess
import sys
import time
import unicodedata
from concurrent.futures import ProcessPoolExecutor, wait
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "src"
SCRIPTS = RACINE / "scripts"
for _p in (SRC, SCRIPTS):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rummikub.config import NIVEAUX
from rummikub.moteur import niveaux as _niveaux
from rummikub.moteur.ia import jouer_niveau_bride
from rummikub.moteur.partie import (
    annuler_tour,
    backup_debut_tour,
    creer_partie,
    jouer_tour,
    passer_tour,
    piocher,
)
from comparer_niveaux_ia import moyenne
from _limite_temps_ferme import (
    CODE_LIMITE_TEMPS, CODE_TERMINE, lancer_avec_limite_ferme,
)
from _rapport_duels import entete_machine
from _verif_solveur_exact import exiger_solveur_exact_ou_quitter

logger = logging.getLogger("tournoi_niveaux")

NIVEAUX_DEFAUT = ["Expert", "Avancé", "Intermédiaire", "Facile"]
DONNES_DEFAUT = 50
MAX_TOURS_DEFAUT = 300


# --------------------------------------------------------------------------- #
# Noms de niveaux : accent-insensibles (lanceur Windows du PC fixe, issue
# #276) — refuse un nom inconnu en listant les noms valides.
# --------------------------------------------------------------------------- #

def _normaliser_nom(texte: str) -> str:
    """Sans accent, sans espace de bord, en minuscules — pour une comparaison
    tolérante aux caractères accentués passés de façon fragile par le
    lanceur Windows du PC fixe (encodage de la console, voir l'issue)."""
    sans_accent = unicodedata.normalize("NFKD", texte)
    sans_accent = "".join(c for c in sans_accent if not unicodedata.combining(c))
    return sans_accent.strip().lower()


_NIVEAUX_PAR_CLE = {_normaliser_nom(n): n for n in NIVEAUX}


def resoudre_niveau(texte: str) -> str:
    """Nom canonique d'un niveau (``rummikub.config.NIVEAUX``), accent-
    insensible. Lève ``ValueError`` (message en français, liste des noms
    valides) si ``texte`` ne correspond à aucun niveau connu."""
    canonique = _NIVEAUX_PAR_CLE.get(_normaliser_nom(texte))
    if canonique is None:
        raise ValueError(
            f"niveau inconnu : {texte!r} (valides : {', '.join(NIVEAUX)})")
    return canonique


def parser_niveaux(texte: str) -> list[str]:
    """``"N1,N2,..."`` → liste de 2 à 4 noms canoniques, SANS doublon (un
    niveau répété casserait l'attribution des statistiques par niveau, voir
    :func:`stats_par_niveau`)."""
    noms = [n.strip() for n in texte.split(",") if n.strip()]
    if not 2 <= len(noms) <= 4:
        raise ValueError(
            "--niveaux doit contenir entre 2 et 4 niveaux séparés par des "
            f"virgules (reçu {len(noms)})")
    resolus = [resoudre_niveau(n) for n in noms]
    if len(set(resolus)) != len(resolus):
        raise ValueError(
            f"--niveaux ne doit pas contenir de niveau répété : {resolus}")
    return resolus


# --------------------------------------------------------------------------- #
# Rotation des sièges : à n niveaux, n rotations — chaque niveau occupe une
# fois chaque siège (issue #276, point 3).
# --------------------------------------------------------------------------- #

def rotation(niveaux: list[str], r: int) -> list[str]:
    """Niveaux affectés à chaque siège (index 0..n-1) pour la rotation
    ``r`` (0..n-1) : décalage cyclique de ``niveaux``. Pour un siège ``i``
    fixé, ``(i + r) % n`` parcourt exactement une fois chaque valeur de
    0 à n-1 quand ``r`` varie — chaque niveau occupe donc une fois chaque
    siège sur les n rotations."""
    n = len(niveaux)
    return [niveaux[(i + r) % n] for i in range(n)]


def construire_joueurs(niveaux_par_siege: list[str]) -> list[dict]:
    return [
        {"nom": f"Siège {i + 1} ({niveau})", "est_ia": True, "niveau": niveau}
        for i, niveau in enumerate(niveaux_par_siege)
    ]


# --------------------------------------------------------------------------- #
# Un tour d'IA (même logique que ``scripts/simulation_ia.py`` : coup invalide
# ou tuiles disparues → pioche de secours, exception → pioche de secours,
# anomalie journalisée) — ``jouer_niveau_bride`` au lieu de ``jouer_ia`` pour
# transmettre un budget de temps du solveur explicite, chronométré PAR
# NIVEAU (issue #276, point 4 : temps par tour moyen/maximum).
# --------------------------------------------------------------------------- #

def jouer_un_tour(etat: dict, idx: int, niveaux_par_siege: list[str],
                  temps_par_niveau: dict[str, list[float]],
                  anomalies: list[str],
                  budget_temps: float | None) -> dict:
    niveau = niveaux_par_siege[idx]
    backup_debut_tour(etat)
    debut = time.monotonic()
    try:
        res_ia = jouer_niveau_bride(etat, idx, niveau, budget_temps=budget_temps)
    except Exception:
        temps_par_niveau.setdefault(niveau, []).append(time.monotonic() - debut)
        logger.exception("Exception de l'IA %s (siège %d) au tour %d",
                         niveau, idx + 1, etat["tour_numero"])
        anomalies.append(
            f"tour {etat['tour_numero']} : exception IA ({niveau}, "
            f"siège {idx + 1})")
        annuler_tour(etat)
        return piocher(etat)["etat"]
    temps_par_niveau.setdefault(niveau, []).append(time.monotonic() - debut)

    action = res_ia.get("action")
    if action == "jouer":
        res = jouer_tour(etat, res_ia["ids_tuiles"], res_ia["nouveau_plateau"])
        if res["ok"]:
            return res["etat"]
        tuiles_disparues = bool(res.get("tuiles_disparues"))
        if tuiles_disparues:
            logger.error(
                "ANOMALIE : coup refusé (%s, siège %d) au tour %d car des "
                "tuiles du plateau auraient disparu : %s",
                niveau, idx + 1, etat["tour_numero"], res["erreur"])
        else:
            logger.warning(
                "Coup invalide proposé par %s (siège %d) au tour %d : %s",
                niveau, idx + 1, etat["tour_numero"], res["erreur"])
        anomalies.append(
            f"tour {etat['tour_numero']} : coup invalide ({niveau}, "
            f"siège {idx + 1}) — {res['erreur']}"
            + (" [TUILES DISPARUES]" if tuiles_disparues else ""))
        annuler_tour(etat)
        return piocher(etat)["etat"]
    if action == "piocher":
        return piocher(etat)["etat"]
    if action == "passer":
        return passer_tour(etat)["etat"]

    logger.warning("Action IA inconnue %r (%s, siège %d) au tour %d",
                   action, niveau, idx + 1, etat["tour_numero"])
    anomalies.append(
        f"tour {etat['tour_numero']} : action inconnue ({action!r}) de "
        f"{niveau} (siège {idx + 1})")
    annuler_tour(etat)
    return piocher(etat)["etat"]


def jouer_une_manche(niveaux_par_siege: list[str], max_tours: int,
                     budget_temps: float | None, graine: int) -> dict:
    """Joue UNE manche complète (une rotation d'une donne). La graine est
    fixée AVANT ``creer_partie`` (distribution des tuiles ET, via
    ``graine_ia``, reproductibilité de l'affaiblissement des niveaux bridés
    — voir ``moteur/niveaux.py``) : seule l'affectation niveau → siège change
    d'une rotation à l'autre de la même donne (issue #276, point 3)."""
    random.seed(graine)  # aléa de jeu (distribution des tuiles), pas de sécurité
    etat = creer_partie(construire_joueurs(niveaux_par_siege),
                        {"nb_manches": 1, "graine_ia": graine})
    backup_debut_tour(etat)

    temps_par_niveau: dict[str, list[float]] = {}
    anomalies: list[str] = []
    tours = 0
    arretee_garde_fou = False

    while not etat["manche_terminee"]:
        tours += 1
        if tours > max_tours:
            arretee_garde_fou = True
            break
        idx = etat["index_joueur_actuel"]
        etat = jouer_un_tour(etat, idx, niveaux_par_siege, temps_par_niveau,
                             anomalies, budget_temps)
        backup_debut_tour(etat)

    if arretee_garde_fou:
        fin = "limite_tours"
    elif etat.get("manche_bloquee"):
        fin = "manche_bloquee"
    else:
        fin = "chevalet_vide"

    return {
        "niveaux_par_siege": niveaux_par_siege,
        "scores_par_siege": [j["score_manche"] for j in etat["joueurs"]],
        "tours": tours,
        "fin": fin,
        "decidee": fin != "limite_tours",
        "anomalies": anomalies,
        "temps_par_niveau": temps_par_niveau,
    }


# --------------------------------------------------------------------------- #
# Écriture atomique / lecture tolérante à une coupure brutale (même mécanique
# que ``scripts/calibrer_echelle.py``).
# --------------------------------------------------------------------------- #

def _ecrire_atomique(chemin: Path, texte: str) -> None:
    tmp = chemin.with_name(chemin.name + ".tmp")
    tmp.write_text(texte, encoding="utf-8")
    tmp.replace(chemin)


def _ecrire_json_atomique(chemin: Path, data: dict) -> None:
    _ecrire_atomique(chemin, json.dumps(data, ensure_ascii=False, indent=2))


def _ecrire_jsonl_atomique(chemin: Path, enregistrements: list[dict]) -> None:
    texte = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in enregistrements)
    _ecrire_atomique(chemin, texte)


def _lire_enregistrements(chemin: Path) -> list[dict]:
    """Lecture PURE (jamais de ré-écriture) — tolère une dernière ligne mal
    terminée par une coupure brutale (ignorée, comme le reste du fichier)."""
    if not chemin.is_file():
        return []
    enregistrements = []
    with chemin.open(encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                enregistrements.append(json.loads(ligne))
            except json.JSONDecodeError:
                break  # ligne tronquée en fin de fichier : on arrête là
    return enregistrements


# --------------------------------------------------------------------------- #
# Reprise par donne : une donne est complète quand ses n rotations (0..n-1)
# sont TOUTES présentes, où qu'elles soient dans le fichier — une donne
# incomplète (coupure brutale en plein milieu) est purgée et rejouée en
# entier, jamais dupliquée (issue #276, point 1).
# --------------------------------------------------------------------------- #

def _regrouper_par_donne(enregistrements: list[dict]) -> dict[int, list[dict]]:
    par_donne: dict[int, list[dict]] = {}
    for r in enregistrements:
        par_donne.setdefault(r["donne"], []).append(r)
    return par_donne


def _donnes_completes(enregistrements: list[dict], n_rotations: int) -> set[int]:
    par_donne = _regrouper_par_donne(enregistrements)
    return {
        d for d, recs in par_donne.items()
        if sorted(x["rotation"] for x in recs) == list(range(n_rotations))
    }


def fichier_resultats(dossier: Path, worker: int) -> Path:
    return dossier / f"resultats_{worker}.jsonl"


def donnes_pour_worker(donnes_visees: int, nb_processus: int, worker: int) -> list[int]:
    return [d for d in range(1, donnes_visees + 1)
           if (d - 1) % nb_processus == worker]


def _purger_donnes_incompletes(chemin: Path, n_rotations: int) -> set[int]:
    """Purge du fichier toute donne INCOMPLÈTE (coupure brutale en plein
    milieu d'une donne, où qu'elle soit dans le fichier — pas seulement en
    fin) et renvoie l'ensemble des numéros de donne restés complets. Lecture
    pure si rien à purger (aucune écriture)."""
    enregistrements = _lire_enregistrements(chemin)
    completes = _donnes_completes(enregistrements, n_rotations)
    valides = [r for r in enregistrements if r["donne"] in completes]
    if len(valides) != len(enregistrements):
        _ecrire_jsonl_atomique(chemin, valides)
    return completes


def jouer_pour_worker(worker: int, dossier: Path, niveaux: list[str],
                      donnes_visees: int, nb_processus: int, seed: int,
                      max_tours: int, budget_temps: float | None,
                      deadline: float | None) -> bool:
    """Joue les donnes manquantes assignées à ``worker`` (reprise : les
    donnes déjà complètes dans son fichier ne sont jamais rejouées). Renvoie
    ``True`` si interrompu par ``deadline`` avant d'avoir fini."""
    n_rotations = len(niveaux)
    chemin = fichier_resultats(dossier, worker)
    completes = _purger_donnes_incompletes(chemin, n_rotations)

    assignees = donnes_pour_worker(donnes_visees, nb_processus, worker)
    restantes = [d for d in assignees if d not in completes]
    for d in restantes:
        if deadline is not None and time.monotonic() >= deadline:
            return True
        graine_donne = seed + (d - 1)
        lignes = []
        for r in range(n_rotations):
            manche = jouer_une_manche(rotation(niveaux, r), max_tours,
                                      budget_temps, graine_donne)
            manche["donne"] = d
            manche["rotation"] = r
            lignes.append(manche)
        with chemin.open("a", encoding="utf-8") as f:
            for ligne in lignes:
                f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
                f.flush()
    return False


def tous_les_enregistrements(dossier: Path, nb_processus: int) -> list[dict]:
    tous: list[dict] = []
    for worker in range(nb_processus):
        tous.extend(_lire_enregistrements(fichier_resultats(dossier, worker)))
    return tous


def jouer_campagne(dossier: Path, niveaux: list[str], donnes_visees: int,
                   nb_processus: int, seed: int, max_tours: int,
                   budget_temps: float | None, deadline: float | None) -> bool:
    """Joue toute la campagne (reprise comprise), en 1 processus (séquentiel,
    rapport régénéré après chaque donne) ou plusieurs (une partition de
    donnes par processus, rapport régénéré toutes les ~2s depuis le disque).
    Renvoie ``True`` si interrompu par ``deadline``."""
    debut = time.monotonic()

    def _rapport_partiel() -> None:
        _ecrire_rapport_disque(dossier, niveaux, donnes_visees, seed, max_tours,
                               budget_temps, nb_processus,
                               time.monotonic() - debut, None)

    if nb_processus <= 1:
        interrompu = jouer_pour_worker(0, dossier, niveaux, donnes_visees, 1,
                                       seed, max_tours, budget_temps, deadline)
        _rapport_partiel()
    else:
        with ProcessPoolExecutor(max_workers=nb_processus) as executor:
            futures = [executor.submit(
                            jouer_pour_worker, k, dossier, niveaux, donnes_visees,
                            nb_processus, seed, max_tours, budget_temps, deadline)
                      for k in range(nb_processus)]
            restantes = set(futures)
            while restantes:
                _fini, restantes = wait(restantes, timeout=2.0)
                _rapport_partiel()
            interrompu = any(f.result() for f in futures)

    duree = time.monotonic() - debut
    _ecrire_rapport_disque(dossier, niveaux, donnes_visees, seed, max_tours,
                           budget_temps, nb_processus, duree, interrompu)
    return interrompu


# --------------------------------------------------------------------------- #
# Statistiques (issue #276, point 4)
# --------------------------------------------------------------------------- #

def intervalle_wilson(victoires: int, total: int, z: float = 1.96
                      ) -> tuple[float, float, float]:
    """Intervalle de confiance de WILSON (score) pour une proportion, à
    95 % par défaut (contrairement à l'approximation normale de Wald
    utilisée par ``comparer_niveaux_ia.intervalle_confiance_95``, toujours
    comprise dans [0, 1], plus fiable sur un petit échantillon ou un taux
    proche de 0/100 %). Renvoie ``(taux_observe, borne_basse, borne_haute)``."""
    if total == 0:
        return 0.0, 0.0, 0.0
    p = victoires / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    marge = (z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5)) / denom
    return p, max(0.0, centre - marge), min(1.0, centre + marge)


def intervalle_confiance_moyenne(valeurs: list[float], z: float = 1.96
                                 ) -> tuple[float, float]:
    """Moyenne et marge d'erreur (IC 95 % par défaut, approximation normale
    sur l'écart-type de l'échantillon) — pour une grandeur CONTINUE (score),
    à distinguer de :func:`intervalle_wilson` (proportion de victoires)."""
    if not valeurs:
        return 0.0, 0.0
    m = moyenne(valeurs)
    if len(valeurs) < 2:
        return m, 0.0
    marge = z * statistics.stdev(valeurs) / (len(valeurs) ** 0.5)
    return m, marge


def places_depuis_scores(scores: list[int]) -> list[float]:
    """Place de chaque siège (1 = meilleur score), en PARTAGEANT la place
    moyenne en cas d'égalité (« fractional ranking » standard) — issue #276,
    point 4 : deux scores égaux pour la 2e place partagent tous deux 2.5."""
    n = len(scores)
    ordre = sorted(range(n), key=lambda i: -scores[i])
    places = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and scores[ordre[j + 1]] == scores[ordre[i]]:
            j += 1
        rang_moyen = (i + 1 + j + 1) / 2
        for k in range(i, j + 1):
            places[ordre[k]] = rang_moyen
        i = j + 1
    return places


def stats_par_niveau(enregistrements: list[dict], niveaux: list[str]) -> dict[str, dict]:
    decidees = [r for r in enregistrements if r["decidee"]]
    resultat: dict[str, dict] = {}
    for niveau in niveaux:
        places: list[float] = []
        scores: list[int] = []
        victoires = 0
        for r in decidees:
            idx = r["niveaux_par_siege"].index(niveau)
            scores_m = r["scores_par_siege"]
            places.append(places_depuis_scores(scores_m)[idx])
            scores.append(scores_m[idx])
            if scores_m[idx] == max(scores_m):
                victoires += 1
        n = len(decidees)
        taux, ic_basse, ic_haute = intervalle_wilson(victoires, n)
        score_moy, score_marge = intervalle_confiance_moyenne(
            [float(s) for s in scores])
        resultat[niveau] = {
            "manches_jouees": n,
            "victoires": victoires,
            "taux_victoire": taux, "ic_basse": ic_basse, "ic_haute": ic_haute,
            "place_moyenne": moyenne(places) if places else 0.0,
            "score_moyen": score_moy, "score_marge": score_marge,
        }
    return resultat


def matrice_qui_bat_qui(enregistrements: list[dict], niveaux: list[str]
                        ) -> dict[tuple[str, str], tuple[float, int]]:
    """``(A, B) -> (part_de_manches_ou_A_a_un_meilleur_score, n_manches)`` —
    les manches à égalité comptent 0.5 pour chaque camp (la somme ``(A,B)`` +
    ``(B,A)`` vaut alors toujours 1), pour juger aussi les niveaux non
    voisins (issue #276, point 4)."""
    decidees = [r for r in enregistrements if r["decidee"]]
    matrice: dict[tuple[str, str], tuple[float, int]] = {}
    for a in niveaux:
        for b in niveaux:
            if a == b:
                continue
            gain = 0.0
            total = 0
            for r in decidees:
                ia = r["niveaux_par_siege"].index(a)
                ib = r["niveaux_par_siege"].index(b)
                sa, sb = r["scores_par_siege"][ia], r["scores_par_siege"][ib]
                total += 1
                if sa > sb:
                    gain += 1.0
                elif sa == sb:
                    gain += 0.5
            matrice[(a, b)] = (gain / total if total else 0.0, total)
    return matrice


def victoires_par_siege(enregistrements: list[dict], n_sieges: int
                        ) -> tuple[list[int], int]:
    decidees = [r for r in enregistrements if r["decidee"]]
    comptes = [0] * n_sieges
    for r in decidees:
        meilleur = max(r["scores_par_siege"])
        for i, s in enumerate(r["scores_par_siege"]):
            if s == meilleur:
                comptes[i] += 1
    return comptes, len(decidees)


def repartition_fins(enregistrements: list[dict]) -> dict[str, int]:
    fins = {"chevalet_vide": 0, "manche_bloquee": 0, "limite_tours": 0}
    for r in enregistrements:
        fins[r["fin"]] = fins.get(r["fin"], 0) + 1
    return fins


def temps_par_niveau_agrege(enregistrements: list[dict]) -> dict[str, list[float]]:
    agg: dict[str, list[float]] = {}
    for r in enregistrements:
        for niveau, temps in r.get("temps_par_niveau", {}).items():
            agg.setdefault(niveau, []).extend(temps)
    return agg


def commit_git() -> str | None:
    try:
        # commande fixe, aucune saisie utilisateur — identifie seulement le commit courant
        res = subprocess.run(["git", "rev-parse", "--short", "HEAD"],  # noqa: S607  # nosec B603,B607
                             cwd=RACINE, capture_output=True, text=True,
                             timeout=5, check=False)
    except OSError:
        return None
    if res.returncode != 0:
        return None
    return res.stdout.strip() or None


# --------------------------------------------------------------------------- #
# Rapport lisible (continu, et via --statut) — UTF-8, sans caractère fragile
# à l'affichage d'une console Windows (issue #276, point 4).
# --------------------------------------------------------------------------- #

def _texte_bridage(niveau: str) -> str:
    b = _niveaux.BRIDAGES.get(niveau)
    if b is None:
        return "réglage introuvable"
    p = "illimite" if b.perturbation_max is None else str(b.perturbation_max)
    return (f"perturbation={p} oubli={b.taux_oubli:.2f} "
           f"eviter_don_joker={b.eviter_don_joker}")


def generer_rapport(dossier: Path, niveaux: list[str], donnes_visees: int,
                    seed: int, max_tours: int, budget_solveur: float | None,
                    nb_processus: int, duree_s: float | None,
                    interrompu: bool | None) -> str:
    enregistrements = tous_les_enregistrements(dossier, nb_processus)
    n_rotations = len(niveaux)
    n_donnes_completes = len(_donnes_completes(enregistrements, n_rotations))
    n_manches = len(enregistrements)

    lignes = ["=" * 78,
              "TOURNOI A PLUSIEURS NIVEAUX D'IA, ROTATION DES SIEGES (issue #276)"]
    lignes.extend(entete_machine())
    commit = commit_git()
    lignes.append(f"Commit : {commit if commit else 'inconnu'}")
    lignes.append(f"Dossier : {dossier}")
    lignes.append(f"Niveaux (ordre d'entree) : {', '.join(niveaux)}")
    lignes.append(f"donnes_visees={donnes_visees} seed={seed} "
                  f"max_tours={max_tours} "
                  f"budget_solveur={'defaut (1.5s)' if budget_solveur is None else budget_solveur} "
                  f"processus={nb_processus}")
    lignes.append(f"Rotations par donne : {n_rotations} "
                  f"(chaque niveau occupe une fois chaque siege)")
    lignes.append("")
    lignes.append("Reglages REELS lus dans moteur/niveaux.py (jamais modifies "
                  "par ce script) :")
    for niveau in niveaux:
        lignes.append(f"    {niveau:<16s} {_texte_bridage(niveau)}")
    lignes.append("=" * 78)
    lignes.append("")

    stats = stats_par_niveau(enregistrements, niveaux)
    lignes.append("RESULTATS PAR NIVEAU :")
    for niveau in niveaux:
        s = stats[niveau]
        lignes.append(
            f"  {niveau:<16s} {s['manches_jouees']:>4d} manche(s) decidee(s)  "
            f"victoires {s['victoires']}/{s['manches_jouees']} = "
            f"{s['taux_victoire'] * 100:5.1f} % "
            f"[IC95 Wilson {s['ic_basse'] * 100:5.1f}-{s['ic_haute'] * 100:5.1f} %]  "
            f"place moy. {s['place_moyenne']:.2f}  "
            f"score moy. {s['score_moyen']:+.1f} +/- {s['score_marge']:.1f}")
    lignes.append("")

    lignes.append("MATRICE « QUI BAT QUI » (part des manches ou la ligne a un "
                  "meilleur score que la colonne, egalite = 0.5) :")
    matrice = matrice_qui_bat_qui(enregistrements, niveaux)
    entete = "               " + "".join(f"{n[:10]:>12s}" for n in niveaux)
    lignes.append(entete)
    for a in niveaux:
        cellules = []
        for b in niveaux:
            if a == b:
                cellules.append(f"{'--':>12s}")
            else:
                taux, _n = matrice[(a, b)]
                cellules.append(f"{taux * 100:11.1f}%")
        lignes.append(f"  {a:<13s}" + "".join(cellules))
    lignes.append("")

    comptes_sieges, n_decidees = victoires_par_siege(enregistrements, n_rotations)
    lignes.append("VICTOIRES PAR SIEGE (controle de l'absence de biais de "
                  "position) :")
    for i, c in enumerate(comptes_sieges):
        part = (100 * c / n_decidees) if n_decidees else 0.0
        lignes.append(f"    Siege {i + 1} : {c}/{n_decidees} = {part:.1f} %")
    lignes.append("")

    fins = repartition_fins(enregistrements)
    total_fins = sum(fins.values()) or 1
    lignes.append("REPARTITION DES FINS DE MANCHE :")
    lignes.append(
        f"    chevalet vide : {fins['chevalet_vide']} "
        f"({100 * fins['chevalet_vide'] / total_fins:.1f} %)  —  "
        f"manche bloquee : {fins['manche_bloquee']} "
        f"({100 * fins['manche_bloquee'] / total_fins:.1f} %)  —  "
        f"limite de tours : {fins['limite_tours']} "
        f"({100 * fins['limite_tours'] / total_fins:.1f} %)")
    if enregistrements:
        lignes.append(
            f"Nombre moyen de tours par manche : "
            f"{moyenne([r['tours'] for r in enregistrements]):.1f}")
    lignes.append("")

    temps_agg = temps_par_niveau_agrege(enregistrements)
    if temps_agg:
        lignes.append("TEMPS DE CALCUL PAR TOUR, PAR NIVEAU :")
        for niveau in niveaux:
            temps = temps_agg.get(niveau, [])
            if not temps:
                continue
            lignes.append(
                f"    {niveau:<16s} moyen {moyenne(temps) * 1000:.0f} ms  "
                f"maximum {max(temps) * 1000:.0f} ms  (n={len(temps)})")
        lignes.append("")

    total_anomalies = sum(len(r.get("anomalies", [])) for r in enregistrements)
    lignes.append(f"Nombre d'anomalies (coup invalide, tuiles disparues, "
                  f"exception IA) : {total_anomalies}")
    if total_anomalies:
        lignes.append("    (detail dans les journaux -v, ou champ "
                      "\"anomalies\" des fichiers resultats_*.jsonl)")
    lignes.append("")

    lignes.append(f"Manches jouees : {n_manches} "
                  f"({n_donnes_completes}/{donnes_visees} donne(s) complete(s), "
                  f"{n_rotations} rotation(s) chacune).")
    if duree_s is not None:
        lignes.append(f"Temps total : {duree_s:.1f} s.")
    if interrompu is True:
        lignes.append("(!) ARRETE SUR LA LIMITE DE TEMPS : campagne "
                      "PARTIELLE — relancer la meme commande pour reprendre.")
    elif interrompu is False:
        if n_donnes_completes >= donnes_visees:
            lignes.append("TERMINEE NORMALEMENT (toutes les donnes "
                          "demandees jouees).")
        else:
            lignes.append("PARTIELLE (interrompue avant la fin, sans "
                          "limite de temps explicite) — relancer la meme "
                          "commande pour reprendre.")
    else:
        lignes.append("(statut : campagne possiblement EN COURS ailleurs — "
                      "relancer la meme commande pour reprendre/continuer.)")
    lignes.append("=" * 78)
    return "\n".join(lignes) + "\n"


def _ecrire_rapport_disque(dossier: Path, niveaux: list[str], donnes_visees: int,
                           seed: int, max_tours: int, budget_solveur: float | None,
                           nb_processus: int, duree_s: float | None,
                           interrompu: bool | None) -> None:
    texte = generer_rapport(dossier, niveaux, donnes_visees, seed, max_tours,
                            budget_solveur, nb_processus, duree_s, interrompu)
    _ecrire_atomique(dossier / "rapport.txt", texte)


# --------------------------------------------------------------------------- #
# Empreinte des réglages (refus de mélanger deux campagnes dans un dossier)
# --------------------------------------------------------------------------- #

class ReglagesIncompatibles(Exception):
    pass


def construire_empreinte(niveaux: list[str], donnes: int, seed: int,
                         max_tours: int, budget_solveur: float | None,
                         nb_processus: int) -> dict:
    return {"niveaux": niveaux, "donnes": donnes, "seed": seed,
            "max_tours": max_tours, "budget_solveur": budget_solveur,
            "nb_processus": nb_processus}


def _sans_donnes(empreinte: dict) -> dict:
    return {k: v for k, v in empreinte.items() if k != "donnes"}


def verifier_ou_ecrire_empreinte(dossier: Path, empreinte: dict) -> dict:
    """Écrit ``reglages.json`` au premier lancement. Sur un dossier déjà
    initialisé : si les réglages (hors ``donnes``, qui peut AUGMENTER pour
    prolonger la campagne sans la recommencer) sont IDENTIQUES, renvoie
    l'empreinte existante (``donnes`` porté au plus grand des deux) ; sinon
    lève :class:`ReglagesIncompatibles` SANS rien écrire ni rien jouer —
    ``--processus`` fait partie des réglages verrouillés : changer le
    nombre de processus entre deux lancements changerait l'affectation des
    donnes aux fichiers ``resultats_*.jsonl`` et casserait la reprise."""
    chemin = dossier / "reglages.json"
    if not chemin.is_file():
        _ecrire_json_atomique(chemin, empreinte)
        return empreinte
    existant = json.loads(chemin.read_text(encoding="utf-8"))
    if _sans_donnes(existant) != _sans_donnes(empreinte):
        raise ReglagesIncompatibles(
            f"le dossier {dossier} contient déjà une campagne avec des "
            "réglages DIFFÉRENTS (niveaux, graine, max_tours, budget "
            "solveur, ou nombre de processus). Relancez dans un dossier "
            "vide, ou reprenez avec EXACTEMENT les mêmes réglages (seul "
            "--donnes peut augmenter pour prolonger la campagne).")
    if empreinte["donnes"] > existant["donnes"]:
        existant = dict(existant, donnes=empreinte["donnes"])
        _ecrire_json_atomique(chemin, existant)
    return existant


def commande_statut(dossier: Path) -> int:
    """Affiche l'avancement d'une campagne existante SANS rien jouer ni rien
    écrire (lecture seule, n'interfère jamais avec un calcul en cours)."""
    chemin = dossier / "reglages.json"
    if not chemin.is_file():
        print(f"ERREUR : aucune campagne de tournoi dans {dossier} "
             f"({chemin} absent).", file=sys.stderr)
        return 1
    empreinte = json.loads(chemin.read_text(encoding="utf-8"))
    print(generer_rapport(dossier, empreinte["niveaux"], empreinte["donnes"],
                          empreinte["seed"], empreinte["max_tours"],
                          empreinte["budget_solveur"], empreinte["nb_processus"],
                          duree_s=None, interrompu=None), end="")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _construire_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tournoi à 2-4 niveaux d'IA à une même table, rotation "
                    "des sièges, statistiques par niveau (issue #276).")
    parser.add_argument("--dossier", required=True,
                        help="Dossier où écrire les résultats par manche et "
                             "le rapport (en continu) — hors du dépôt.")
    parser.add_argument("--statut", action="store_true",
                        help="Affiche l'avancement du dossier et quitte, "
                             "sans rien jouer ni rien écrire.")
    parser.add_argument("--niveaux", type=str,
                        default=",".join(NIVEAUX_DEFAUT),
                        help="2 à 4 niveaux séparés par des virgules "
                             f"(défaut « {','.join(NIVEAUX_DEFAUT)} »). Les "
                             "noms sans accent sont acceptés.")
    parser.add_argument("--donnes", type=int, default=DONNES_DEFAUT,
                        help=f"Donnes distinctes (défaut {DONNES_DEFAUT} ; "
                             "chacune jouée en autant de rotations que de "
                             "niveaux). Augmenter sur un dossier existant "
                             "PROLONGE la campagne sans la recommencer.")
    parser.add_argument("--seed", type=int, default=0,
                        help="Graine de base (défaut 0) : la donne i "
                             "utilise la graine seed + i.")
    parser.add_argument("--max-tours", type=int, default=MAX_TOURS_DEFAUT,
                        help=f"Garde-fou anti-blocage par manche (défaut "
                             f"{MAX_TOURS_DEFAUT}).")
    parser.add_argument("--budget-solveur", type=float, default=None,
                        help="Budget de temps du solveur par coup, en "
                             "secondes, appliqué à tous les niveaux "
                             "(défaut : valeur du jeu, 1,5 s).")
    parser.add_argument("--processus", type=int, default=1, choices=(1, 2),
                        help="Nombre de processus en parallèle (1 ou 2).")
    parser.add_argument("--limite-temps", type=float, default=None,
                        help="Limite de temps FERME, en secondes, pour toute "
                             "la campagne (garde-fou externe par "
                             "sous-processus, voir _limite_temps_ferme.py).")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Journalise le détail de la campagne.")
    parser.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    return parser


def _executer(args, dossier: Path, niveaux: list[str]) -> int:
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)-8s %(message)s",
                        datefmt="%H:%M:%S")
    if args.verbose:
        logger.setLevel(logging.INFO)

    dossier.mkdir(parents=True, exist_ok=True)
    empreinte = construire_empreinte(niveaux, args.donnes, args.seed,
                                     args.max_tours, args.budget_solveur,
                                     args.processus)
    try:
        empreinte = verifier_ou_ecrire_empreinte(dossier, empreinte)
    except ReglagesIncompatibles as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1

    donnes_visees = empreinte["donnes"]
    deadline = ((time.monotonic() + args.limite_temps)
               if args.limite_temps is not None else None)
    interrompu = jouer_campagne(dossier, empreinte["niveaux"], donnes_visees,
                               empreinte["nb_processus"], empreinte["seed"],
                               empreinte["max_tours"], empreinte["budget_solveur"],
                               deadline)
    print((dossier / "rapport.txt").read_text(encoding="utf-8"), end="")
    return CODE_LIMITE_TEMPS if interrompu else CODE_TERMINE


def main(argv: list[str]) -> int:
    parser = _construire_parser()
    args = parser.parse_args(argv[1:])
    dossier = Path(args.dossier)

    if args.statut:
        return commande_statut(dossier)

    try:
        niveaux = parser_niveaux(args.niveaux)
    except ValueError as exc:
        parser.error(str(exc))
        return 2
    if args.donnes < 1:
        parser.error("--donnes doit être au moins 1")
    if args.max_tours < 1:
        parser.error("--max-tours doit être au moins 1")
    if args.budget_solveur is not None and args.budget_solveur <= 0:
        parser.error("--budget-solveur doit être > 0")
    if args.limite_temps is not None and args.limite_temps <= 0:
        parser.error("--limite-temps doit être > 0")

    # Échec franc sans solveur exact (issue #223/#224) : ce script fait
    # jouer tous les niveaux d'IA (y compris Avancé/Expert) par le chemin de
    # production (jouer_niveau_bride).
    exiger_solveur_exact_ou_quitter()

    if args._worker or args.limite_temps is None:
        return _executer(args, dossier, niveaux)

    # Relance surveillée (garde-fou externe, comme calibrer_echelle.py).
    return lancer_avec_limite_ferme(Path(__file__), list(argv[1:]), args.limite_temps)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
