#!/usr/bin/env python3
"""Outil de calibration DESCENDANTE de l'échelle des cinq niveaux d'IA, par
DUELS entre niveaux voisins, avec des réglages (perturbation/oubli) donnés en
LIGNE DE COMMANDE — sans jamais toucher à `moteur/niveaux.BRIDAGES` (issue
#240).

Depuis le retrait de « Champion du Monde » (#235/#236), Avancé et Expert
jouent EXACTEMENT pareil (égalité statistique) et Facile n'est pas plus fort
que Débutant avec les réglages actuels : cet outil sert à chercher, PAR LA
MESURE, des réglages où chaque niveau bat nettement le niveau juste en
dessous (cible : 60 à 70 % de victoires, réglable).

Méthode décidée par Alain (DESCENDANTE, à documenter dans CONTEXTE.md) :
Expert reste à fond, on règle Avancé contre Expert (fixe), puis Intermédiaire
contre Avancé (figé), puis Facile contre Intermédiaire, puis Débutant contre
Facile — chaque réglage ne dépend QUE du niveau juste au-dessus, déjà figé.

Trois modes d'utilisation :

1. **Mesure brute** des quatre paires adjacentes (ou de paires choisies) avec
   des réglages candidats :

       python scripts/calibrer_echelle.py --dossier /tmp/calib_240 \\
           --reglage "Avancé=inf/0.05" --donnes 40

   `--paire` permet de restreindre/étendre aux paires voulues, y compris non
   adjacentes (mesure de l'étendue totale de l'échelle) :

       python scripts/calibrer_echelle.py --dossier /tmp/calib_240 \\
           --paire Débutant:Expert --donnes 20

2. **Balayage** de plusieurs réglages candidats pour UN niveau, tous joués
   contre un niveau FIXE :

       python scripts/calibrer_echelle.py --dossier /tmp/calib_240 \\
           --candidats "Avancé=inf/0.03,inf/0.06,inf/0.10" --contre Expert \\
           --donnes 40 --processus 2

3. **Statut** (lecture seule, n'interfère jamais avec un calcul en cours) :

       python scripts/calibrer_echelle.py --dossier /tmp/calib_240 --statut

Reprise après interruption : relancer EXACTEMENT la même commande sur le même
``--dossier`` reprend à la dernière DONNE COMPLÈTE de chaque paire/candidat
(aucune partie déjà écrite n'est rejouée). Augmenter ``--donnes`` sur un
dossier existant PROLONGE la série (mesure grossière d'abord, puis affinée) ;
tout autre changement de réglage est REFUSÉ (le dossier ne mélange jamais
deux séries différentes — voir ``reglages.json``).

Réutilise directement (aucune logique dupliquée) :
  * ``comparer_niveaux_ia.comparer`` — garde-fou solveur exact, export par
    partie (``--export-resultats``/``mode_fichier="a"``, #228 point 5, déjà
    pensé pour la reprise), budget de temps du solveur ;
  * ``_rapport_duels`` — en-tête machine/dépendances ;
  * ``_limite_temps_ferme`` — limite de temps FERME (sous-processus
    surveillé, Linux et Windows) ;
  * ``_verif_solveur_exact`` — refus de démarrer sans ``highspy``/``numpy``.

Rapport écrit en continu dans ``<dossier>/rapport.txt`` (relisible à tout
moment, y compris pendant un calcul, via ``--statut``) : pour chaque paire, le
nombre de victoires du niveau le plus fort, le taux ± IC 95 %, le verdict
(« dans la cible » / « trop faible » / « trop fort »), l'écart en Elo, et (en
mode paires) la distance Elo cumulée de chaque niveau à Expert.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
import unicodedata
from concurrent.futures import ProcessPoolExecutor, wait
from dataclasses import asdict, dataclass
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "src"
SCRIPTS = RACINE / "scripts"
for _p in (SRC, SCRIPTS):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rummikub.config import NIVEAUX  # noqa: E402
from rummikub.moteur import ia as _ia  # noqa: E402
from rummikub.moteur import niveaux as _niveaux  # noqa: E402

from comparer_niveaux_ia import comparer, intervalle_confiance_95  # noqa: E402
from _limite_temps_ferme import (  # noqa: E402
    CODE_LIMITE_TEMPS, CODE_TERMINE, lancer_avec_limite_ferme,
)
from _rapport_duels import entete_machine  # noqa: E402
from _verif_solveur_exact import exiger_solveur_exact_ou_quitter  # noqa: E402

logger = logging.getLogger("calibrer_echelle")

DONNES_DEFAUT = 40
MAX_TOURS_DEFAUT = 300
CIBLE_BASSE_DEFAUT = 0.60
CIBLE_HAUTE_DEFAUT = 0.70


# --------------------------------------------------------------------------- #
# Réglages en ligne de commande (perturbation/oubli) — jamais niveaux.py
# --------------------------------------------------------------------------- #

def _parser_perturbation(texte: str) -> int | None:
    texte = texte.strip().lower()
    if texte in ("inf", "none", "illimite", "illimité", "∞"):
        return None
    try:
        valeur = int(texte)
    except ValueError:
        raise ValueError(f"perturbation invalide (entier ou « inf ») : {texte!r}")
    if valeur < 0:
        raise ValueError(f"perturbation négative interdite : {valeur}")
    return valeur


def _parser_oubli(texte: str) -> float:
    try:
        valeur = float(texte.strip())
    except ValueError:
        raise ValueError(f"taux d'oubli invalide (nombre entre 0 et 1) : {texte!r}")
    if not 0.0 <= valeur <= 1.0:
        raise ValueError(f"taux d'oubli hors de [0, 1] : {valeur}")
    return valeur


def _parser_niveau(texte: str) -> str:
    niveau = texte.strip()
    if niveau not in NIVEAUX:
        raise ValueError(f"niveau inconnu : {niveau!r} (attendu l'un de {NIVEAUX})")
    return niveau


def parser_reglage(texte: str) -> tuple[str, "_niveaux.Bridage"]:
    """``"Niveau=perturbation/oubli"`` → ``(niveau, Bridage)``. Perturbation :
    entier >= 0, ou ``inf``/``none``/``illimite`` pour le solveur complet.
    Oubli : nombre dans [0, 1]. Lève ``ValueError`` (message en français) sur
    tout format invalide."""
    if "=" not in texte:
        raise ValueError(
            f"réglage invalide (attendu « Niveau=perturbation/oubli ») : {texte!r}")
    niveau_txt, reste = texte.split("=", 1)
    niveau = _parser_niveau(niveau_txt)
    if "/" not in reste:
        raise ValueError(
            f"réglage invalide pour {niveau} "
            f"(attendu « perturbation/oubli ») : {reste!r}")
    pert_txt, oubli_txt = reste.split("/", 1)
    return niveau, _niveaux.Bridage(perturbation_max=_parser_perturbation(pert_txt),
                                    taux_oubli=_parser_oubli(oubli_txt))


def parser_candidats(texte: str) -> tuple[str, list["_niveaux.Bridage"]]:
    """``"Niveau=P1/O1,P2/O2,..."`` → ``(niveau, [Bridage, ...])``."""
    if "=" not in texte:
        raise ValueError(
            f"candidats invalides (attendu « Niveau=p1/o1,p2/o2,... ») : {texte!r}")
    niveau_txt, reste = texte.split("=", 1)
    niveau = _parser_niveau(niveau_txt)
    candidats: list[_niveaux.Bridage] = []
    for brut in reste.split(","):
        brut = brut.strip()
        if not brut:
            continue
        if "/" not in brut:
            raise ValueError(
                f"candidat invalide pour {niveau} "
                f"(attendu « perturbation/oubli ») : {brut!r}")
        pert_txt, oubli_txt = brut.split("/", 1)
        candidats.append(_niveaux.Bridage(perturbation_max=_parser_perturbation(pert_txt),
                                          taux_oubli=_parser_oubli(oubli_txt)))
    if not candidats:
        raise ValueError(f"aucun candidat fourni pour {niveau}")
    return niveau, candidats


def parser_paire(texte: str) -> tuple[str, str]:
    """``"Faible:Fort"`` → ``(faible, fort)`` — le rapport mesure le taux de
    victoire du second nom, quels que soient leurs rangs dans l'échelle (sert
    aussi à mesurer l'étendue totale, p. ex. ``Débutant:Expert``)."""
    if ":" not in texte:
        raise ValueError(f"paire invalide (attendu « Faible:Fort ») : {texte!r}")
    faible_txt, fort_txt = texte.split(":", 1)
    return _parser_niveau(faible_txt), _parser_niveau(fort_txt)


def bridages_resolus(reglages: list[tuple[str, "_niveaux.Bridage"]]
                     ) -> dict[str, "_niveaux.Bridage"]:
    """Réglage effectif de chaque niveau pour cette campagne : les valeurs du
    jeu (``niveaux.BRIDAGES``, jamais modifiées), sauf ceux explicitement
    donnés par ``--reglage``."""
    resolus = dict(_niveaux.BRIDAGES)
    for niveau, bridage in reglages:
        resolus[niveau] = bridage
    return resolus


def paires_adjacentes_defaut() -> list[tuple[str, str]]:
    return [(NIVEAUX[i], NIVEAUX[i + 1]) for i in range(len(NIVEAUX) - 1)]


# --------------------------------------------------------------------------- #
# Tâches (une paire, ou un candidat de balayage contre un niveau fixe)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Tache:
    label: str
    niveau_a: str
    bridage_a: "_niveaux.Bridage"
    niveau_b: str                      # camp dont on mesure le taux de victoire
    bridage_b: "_niveaux.Bridage"


def _slug(nom: str) -> str:
    """Nom de fichier ASCII sûr sous Windows/Linux (« Débutant » → « Debutant »)."""
    norme = unicodedata.normalize("NFKD", nom)
    return "".join(c for c in norme if not unicodedata.combining(c))


def construire_taches(mode: str, *, paires: list[tuple[str, str]] | None = None,
                      niveau_candidat: str | None = None,
                      candidats: list["_niveaux.Bridage"] | None = None,
                      contre: str | None = None,
                      resolus: dict[str, "_niveaux.Bridage"] | None = None,
                      ) -> list[Tache]:
    if mode == "balayage":
        return [
            Tache(label=f"{_slug(niveau_candidat)}_cand{i + 1}_vs_{_slug(contre)}",
                 niveau_a=niveau_candidat, bridage_a=cand,
                 niveau_b=contre, bridage_b=resolus[contre])
            for i, cand in enumerate(candidats)
        ]
    paires_a_jouer = paires if paires else paires_adjacentes_defaut()
    return [
        Tache(label=f"{_slug(f)}_vs_{_slug(g)}", niveau_a=f, bridage_a=resolus[f],
             niveau_b=g, bridage_b=resolus[g])
        for f, g in paires_a_jouer
    ]


def taches_depuis_empreinte(empreinte: dict) -> list[Tache]:
    return [
        Tache(label=t["label"], niveau_a=t["niveau_a"],
             bridage_a=_niveaux.Bridage(**t["bridage_a"]),
             niveau_b=t["niveau_b"], bridage_b=_niveaux.Bridage(**t["bridage_b"]))
        for t in empreinte["taches"]
    ]


# --------------------------------------------------------------------------- #
# Empreinte des réglages (refus de mélanger deux séries dans un même dossier)
# --------------------------------------------------------------------------- #

class ReglagesIncompatibles(Exception):
    pass


def construire_empreinte(mode: str, taches: list[Tache], donnes: int, seed: int,
                         max_tours: int, budget_solveur: float | None,
                         cible_basse: float, cible_haute: float) -> dict:
    return {
        "mode": mode,
        "taches": [
            {"label": t.label, "niveau_a": t.niveau_a, "bridage_a": asdict(t.bridage_a),
             "niveau_b": t.niveau_b, "bridage_b": asdict(t.bridage_b)}
            for t in taches
        ],
        "donnes": donnes,
        "seed": seed,
        "max_tours": max_tours,
        "budget_solveur": budget_solveur,
        "cible_basse": cible_basse,
        "cible_haute": cible_haute,
    }


def _sans_donnes(empreinte: dict) -> dict:
    return {k: v for k, v in empreinte.items() if k != "donnes"}


def verifier_ou_ecrire_empreinte(dossier: Path, empreinte: dict) -> dict:
    """Écrit ``reglages.json`` au premier lancement. Sur un dossier déjà
    initialisé : si les réglages (hors ``donnes``, qui peut AUGMENTER pour
    prolonger la série sans la recommencer) sont IDENTIQUES, renvoie
    l'empreinte existante (``donnes`` porté au plus grand des deux) ; sinon
    lève :class:`ReglagesIncompatibles` SANS rien écrire ni jouer."""
    chemin = dossier / "reglages.json"
    if not chemin.is_file():
        _ecrire_json_atomique(chemin, empreinte)
        return empreinte
    existant = json.loads(chemin.read_text(encoding="utf-8"))
    if _sans_donnes(existant) != _sans_donnes(empreinte):
        raise ReglagesIncompatibles(
            f"le dossier {dossier} contient déjà une série de calibration "
            "avec des réglages DIFFÉRENTS (niveaux/réglages, paires ou "
            "balayage, graine, max_tours, budget solveur, ou cible). "
            "Relancez dans un dossier vide, ou reprenez avec EXACTEMENT les "
            "mêmes réglages (seul --donnes peut augmenter pour prolonger "
            "la série).")
    if empreinte["donnes"] > existant["donnes"]:
        existant = dict(existant, donnes=empreinte["donnes"])
        _ecrire_json_atomique(chemin, existant)
    return existant


# --------------------------------------------------------------------------- #
# Écriture atomique (tolérante à une coupure brutale, issue #240 point 3)
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


# --------------------------------------------------------------------------- #
# Résultats par partie (réutilise comparer(..., export_resultats=...))
# --------------------------------------------------------------------------- #

def fichier_tache(dossier: Path, label: str) -> Path:
    return dossier / f"resultats_{label}.jsonl"


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


def _stats_depuis_enregistrements(enregistrements: list[dict]) -> dict:
    """Nombre de DONNES complètes (2 lignes chacune, miroir) à partir de 1
    (toute ligne au-delà d'un trou, ou toute donne incomplète en fin de
    fichier, est ignorée) et statistiques agrégées sur ces donnes complètes
    uniquement."""
    par_donne: dict[int, list[dict]] = {}
    for rec in enregistrements:
        par_donne.setdefault(rec["donne"], []).append(rec)
    n_complet = 0
    while (n_complet + 1) in par_donne and len(par_donne[n_complet + 1]) == 2:
        n_complet += 1
    valides = [rec for rec in enregistrements if rec["donne"] <= n_complet]
    decides = sum(1 for r in valides if not r["arretee_garde_fou"])
    victoires_b = sum(1 for r in valides if r.get("vainqueur_camp") == "B")
    garde_fou = sum(1 for r in valides if r["arretee_garde_fou"])
    return {"donnes_completes": n_complet, "decides": decides,
            "victoires_b": victoires_b, "garde_fou": garde_fou}


def _tronquer_si_necessaire(chemin: Path) -> int:
    """À appeler UNE SEULE FOIS, par le process qui va écrire dans ``chemin``,
    AVANT de rejouer quoi que ce soit (jamais pendant qu'un autre processus y
    écrit — voir :func:`jouer_tache`). Réécrit le fichier s'il contenait une
    donne incomplète en fin de fichier (coupure brutale) ; renvoie le nombre
    de donnes complètes déjà présentes (reprise à partir de là)."""
    enregistrements = _lire_enregistrements(chemin)
    stats = _stats_depuis_enregistrements(enregistrements)
    valides = [r for r in enregistrements if r["donne"] <= stats["donnes_completes"]]
    if len(valides) != len(enregistrements):
        _ecrire_jsonl_atomique(chemin, valides)
    return stats["donnes_completes"]


# --------------------------------------------------------------------------- #
# Jeu d'une tâche (réutilise directement comparer(), aucune logique dupliquée)
# --------------------------------------------------------------------------- #

def jouer_tache(tache: Tache, dossier: Path, donnes_visees: int, seed: int,
                max_tours: int, budget_solveur: float | None,
                deadline: float | None, on_donne=None) -> bool:
    """Joue, DONNE PAR DONNE, les donnes manquantes de ``tache`` jusqu'à
    ``donnes_visees`` (reprise à la dernière donne complète). Chaque donne est
    un appel à ``comparer()`` (``donnes_debut``/``donnes_fin``, #228 point 5,
    ``mode_fichier="a"``) qui écrit ses deux parties miroir dans le fichier
    JSON Lines de la tâche. ``on_donne``, si fourni, est appelé après CHAQUE
    donne (mode séquentiel uniquement : pas picklable pour un sous-processus).
    Renvoie ``True`` si interrompu par ``deadline`` avant ``donnes_visees``."""
    _niveaux.BRIDAGES[tache.niveau_a] = tache.bridage_a
    _niveaux.BRIDAGES[tache.niveau_b] = tache.bridage_b
    chemin = fichier_tache(dossier, tache.label)
    nb_complet = _tronquer_si_necessaire(chemin)
    for i in range(nb_complet, donnes_visees):
        if deadline is not None and time.monotonic() >= deadline:
            return True
        comparer(tache.niveau_a, tache.niveau_b, donnes_visees, seed, max_tours,
                nb_manches=1, preferer_simple=True, export_resultats=str(chemin),
                budget_temps=budget_solveur, donnes_debut=i, donnes_fin=i + 1,
                mode_fichier="a")
        if on_donne is not None:
            on_donne()
    return False


def jouer_campagne(dossier: Path, taches: list[Tache], donnes_visees: int, seed: int,
                   max_tours: int, budget_solveur: float | None, nb_processus: int,
                   deadline: float | None, cible_basse: float, cible_haute: float,
                   mode: str) -> bool:
    """Joue toutes les ``taches``, en 1 processus (séquentiel, rapport
    régénéré après CHAQUE donne) ou 2 (une tâche par processus, rapport
    régénéré toutes les ~2s depuis le disque pendant que les travailleurs
    écrivent). Renvoie ``True`` si interrompu par ``deadline``."""
    debut = time.monotonic()

    def _rapport_partiel() -> None:
        _ecrire_rapport_disque(dossier, taches, donnes_visees, seed, cible_basse,
                               cible_haute, mode, time.monotonic() - debut, None)

    if nb_processus <= 1:
        interrompu = False
        for tache in taches:
            if deadline is not None and time.monotonic() >= deadline:
                interrompu = True
                break
            if jouer_tache(tache, dossier, donnes_visees, seed, max_tours,
                           budget_solveur, deadline, on_donne=_rapport_partiel):
                interrompu = True
                break
    else:
        with ProcessPoolExecutor(max_workers=nb_processus) as executor:
            futures = [executor.submit(jouer_tache, t, dossier, donnes_visees, seed,
                                       max_tours, budget_solveur, deadline)
                      for t in taches]
            restantes = set(futures)
            while restantes:
                _fini, restantes = wait(restantes, timeout=2.0)
                _rapport_partiel()
            interrompu = any(f.result() for f in futures)

    duree = time.monotonic() - debut
    _ecrire_rapport_disque(dossier, taches, donnes_visees, seed, cible_basse,
                           cible_haute, mode, duree, interrompu)
    return interrompu


# --------------------------------------------------------------------------- #
# Statistiques : verdict et Elo (formule habituelle)
# --------------------------------------------------------------------------- #

def verdict_cible(taux: float, cible_basse: float, cible_haute: float) -> str:
    """Les trois verdicts demandés par l'issue #240, point 2 : « dans la
    cible », « trop faible » (le niveau du haut n'est pas assez plus fort) ou
    « trop fort » (l'écart est trop grand)."""
    if cible_basse <= taux <= cible_haute:
        return "dans la cible"
    if taux < cible_basse:
        return "trop faible (le niveau du haut n'est pas assez plus fort)"
    return "trop fort (l'écart est trop grand)"


def elo_depuis_taux(victoires: int, decides: int) -> float | None:
    """Écart Elo (formule habituelle, ``400·log10(p/(1-p))``) correspondant à
    un taux de victoire. ``None`` si aucune partie décidée. Correction de
    continuité (``+0.5``/``+1``) pour éviter un écart infini à 0 %/100 % sur
    un petit échantillon — approximation, pas une mesure exacte."""
    if decides == 0:
        return None
    p = (victoires + 0.5) / (decides + 1)
    return 400 * math.log10(p / (1 - p))


def _distances_elo_a_expert(aretes: dict[tuple[str, str], float]) -> dict[str, float]:
    """Distance Elo cumulée de chaque niveau à Expert (0 pour Expert),
    préférant une arête DIRECTE vers Expert si mesurée, sinon la chaîne des
    paires adjacentes mesurées. Un niveau dont la chaîne est rompue (paire
    manquante) est absent du résultat."""
    distances = {"Expert": 0.0}
    for i in range(len(NIVEAUX) - 2, -1, -1):
        bas, haut = NIVEAUX[i], NIVEAUX[i + 1]
        direct = aretes.get((bas, "Expert"))
        if direct is not None:
            distances[bas] = -direct
            continue
        if haut not in distances:
            continue  # chaîne rompue plus haut : les niveaux encore plus bas
                      # peuvent quand même avoir une arête DIRECTE vers Expert
        via_chaine = aretes.get((bas, haut))
        if via_chaine is not None:
            distances[bas] = distances[haut] - via_chaine
    return distances


# --------------------------------------------------------------------------- #
# Rapport lisible (continu, et via --statut)
# --------------------------------------------------------------------------- #

def _texte_bridage(bridage: "_niveaux.Bridage") -> str:
    p = "inf" if bridage.perturbation_max is None else str(bridage.perturbation_max)
    return f"{p}/{bridage.taux_oubli:.2f}"


def _ligne_resultat(t: Tache, stats: dict, taux: float, marge: float,
                    elo: float | None, verdict: str, donnes_visees: int,
                    prefixe: str, mode: str) -> str:
    nom = (f"{t.niveau_a} ({_texte_bridage(t.bridage_a)}) vs {t.niveau_b}"
          if mode == "balayage" else f"{t.niveau_a} vs {t.niveau_b}")
    partiel = " [partiel]" if stats["donnes_completes"] < donnes_visees else ""
    if stats["decides"] == 0:
        corps = "aucune partie décidée"
    else:
        elo_txt = f"{elo:+.0f} Elo" if elo is not None else "Elo n/a"
        corps = (f"{t.niveau_b} {stats['victoires_b']}/{stats['decides']} = "
                f"{taux * 100:5.1f} % ± {marge * 100:4.1f} pt  {elo_txt}  {verdict}")
    gf = f" (garde-fou×{stats['garde_fou']})" if stats["garde_fou"] else ""
    return (f"{prefixe}{nom:<28s} "
           f"[{stats['donnes_completes']}/{donnes_visees}d]{partiel} {corps}{gf}")


def generer_rapport(dossier: Path, taches: list[Tache], donnes_visees: int, seed: int,
                    cible_basse: float, cible_haute: float, mode: str,
                    duree_s: float | None, interrompu: bool | None) -> str:
    lignes = ["=" * 78,
              "CALIBRATION DE L'ÉCHELLE DES NIVEAUX PAR DUELS (issue #240)"]
    lignes.extend(entete_machine())
    lignes.append(f"Dossier : {dossier}")
    lignes.append(f"donnes_visees={donnes_visees} seed={seed} "
                  f"mode={'balayage' if mode == 'balayage' else 'paires'} "
                  f"cible={cible_basse * 100:.0f}-{cible_haute * 100:.0f} %")
    lignes.append("=" * 78)
    lignes.append("")
    lignes.append("Réglages joués dans ce dossier :")
    vus: dict[tuple[str, "_niveaux.Bridage"], None] = {}
    for t in taches:
        vus.setdefault((t.niveau_a, t.bridage_a), None)
        vus.setdefault((t.niveau_b, t.bridage_b), None)
    for niveau, bridage in vus:
        p = "∞" if bridage.perturbation_max is None else str(bridage.perturbation_max)
        lignes.append(f"    {niveau:<16s} perturbation={p:<4s} "
                      f"oubli={bridage.taux_oubli:.2f}")
    lignes.append("")
    lignes.append(("RÉSULTATS DU BALAYAGE (classés par proximité de la cible) :"
                   if mode == "balayage" else "RÉSULTATS PAR PAIRE :"))

    resultats = []
    for t in taches:
        enregistrements = _lire_enregistrements(fichier_tache(dossier, t.label))
        stats = _stats_depuis_enregistrements(enregistrements)
        taux, marge = intervalle_confiance_95(stats["victoires_b"], stats["decides"])
        elo = elo_depuis_taux(stats["victoires_b"], stats["decides"])
        verdict = (verdict_cible(taux, cible_basse, cible_haute)
                  if stats["decides"] else "indéterminé (aucune partie décidée)")
        resultats.append((t, stats, taux, marge, elo, verdict))

    if mode == "balayage":
        milieu = (cible_basse + cible_haute) / 2
        resultats.sort(key=lambda r: abs(r[2] - milieu) if r[1]["decides"] else 1e9)
        for rang, (t, stats, taux, marge, elo, verdict) in enumerate(resultats, 1):
            lignes.append(_ligne_resultat(t, stats, taux, marge, elo, verdict,
                                          donnes_visees, prefixe=f"  {rang:>2d}. ",
                                          mode=mode))
    else:
        for t, stats, taux, marge, elo, verdict in resultats:
            lignes.append(_ligne_resultat(t, stats, taux, marge, elo, verdict,
                                          donnes_visees, prefixe="  ", mode=mode))

    if mode == "paires":
        aretes = {(t.niveau_a, t.niveau_b): elo
                 for t, _s, _tx, _m, elo, _v in resultats if elo is not None}
        distances = _distances_elo_a_expert(aretes)
        lignes.append("")
        lignes.append("DISTANCE ELO CUMULÉE À EXPERT (approximative, voir ci-dessus) :")
        for niveau in NIVEAUX:
            if niveau in distances:
                lignes.append(f"  {niveau:<16s} {distances[niveau]:+.0f}")
            else:
                lignes.append(f"  {niveau:<16s} non calculable (paire manquante)")

    lignes.append("")
    if duree_s is not None:
        lignes.append(f"Temps total : {duree_s:.1f} s.")
    if interrompu is True:
        lignes.append("(!) ARRÊTÉ SUR LA LIMITE DE TEMPS : campagne INCOMPLÈTE "
                      "— relancer la même commande pour reprendre.")
    elif interrompu is False:
        lignes.append("TERMINÉ NORMALEMENT (toutes les donnes demandées jouées).")
    else:
        lignes.append("(statut : campagne possiblement EN COURS ailleurs — relancer "
                      "la même commande pour reprendre/continuer.)")
    lignes.append("=" * 78)
    return "\n".join(lignes) + "\n"


def _ecrire_rapport_disque(dossier: Path, taches: list[Tache], donnes_visees: int,
                           seed: int, cible_basse: float, cible_haute: float,
                           mode: str, duree_s: float | None,
                           interrompu: bool | None) -> None:
    texte = generer_rapport(dossier, taches, donnes_visees, seed, cible_basse,
                            cible_haute, mode, duree_s, interrompu)
    _ecrire_atomique(dossier / "rapport.txt", texte)


def commande_statut(dossier: Path) -> int:
    """Affiche l'avancement d'une série existante SANS rien jouer ni rien
    écrire (issue #240, point 3 : « sans perturber le calcul »)."""
    chemin = dossier / "reglages.json"
    if not chemin.is_file():
        print(f"ERREUR : aucune série de calibration dans {dossier} "
             f"({chemin} absent).", file=sys.stderr)
        return 1
    empreinte = json.loads(chemin.read_text(encoding="utf-8"))
    taches = taches_depuis_empreinte(empreinte)
    print(generer_rapport(dossier, taches, empreinte["donnes"], empreinte["seed"],
                          empreinte["cible_basse"], empreinte["cible_haute"],
                          empreinte["mode"], duree_s=None, interrompu=None), end="")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _construire_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calibration DESCENDANTE de l'échelle des cinq niveaux "
                    "d'IA par duels, réglages en ligne de commande "
                    "(issue #240).")
    parser.add_argument("--dossier", required=True,
                        help="Dossier où écrire les résultats par partie et "
                             "le rapport (en continu) — hors du dépôt.")
    parser.add_argument("--statut", action="store_true",
                        help="Affiche l'avancement du dossier et quitte, "
                             "sans rien jouer ni rien écrire.")
    parser.add_argument("--reglage", action="append", default=[],
                        metavar="Niveau=perturbation/oubli",
                        help="Réglage candidat d'un niveau (répétable), p. "
                             "ex. « Facile=2/0.30 ». Perturbation : entier "
                             ">= 0 ou « inf ». Oubli : [0, 1]. Les niveaux "
                             "non précisés gardent les valeurs du jeu "
                             "(niveaux.BRIDAGES, jamais modifié).")
    parser.add_argument("--paire", action="append", default=[],
                        metavar="Faible:Fort",
                        help="Paire à jouer (répétable), p. ex. "
                             "« Avancé:Expert » ou « Débutant:Expert » "
                             "(étendue totale). Défaut : les quatre paires "
                             "adjacentes de l'échelle.")
    parser.add_argument("--candidats", default=None,
                        metavar="Niveau=p1/o1,p2/o2,...",
                        help="Mode BALAYAGE : plusieurs réglages candidats "
                             "pour UN niveau, tous joués contre --contre.")
    parser.add_argument("--contre", default=None, choices=NIVEAUX,
                        help="Niveau FIXE contre lequel jouer --candidats.")
    parser.add_argument("--donnes", type=int, default=DONNES_DEFAUT,
                        help=f"Donnes distinctes par paire/candidat (défaut "
                             f"{DONNES_DEFAUT} ; chacune jouée 2 fois en "
                             "miroir). Augmenter sur un dossier existant "
                             "PROLONGE la série sans la recommencer.")
    parser.add_argument("--seed", type=int, default=0,
                        help="Graine aléatoire commune à toutes les "
                             "paires/candidats (défaut 0, reproductible).")
    parser.add_argument("--max-tours", type=int, default=MAX_TOURS_DEFAUT,
                        help=f"Garde-fou anti-blocage par manche (défaut "
                             f"{MAX_TOURS_DEFAUT}).")
    parser.add_argument("--budget-solveur", type=float, default=None,
                        help="Budget de temps du solveur par coup, en "
                             "secondes, appliqué à TOUTES les parties "
                             "(défaut : valeur du jeu, 1,5 s). À relever sur "
                             "une machine lente.")
    parser.add_argument("--processus", type=int, default=1, choices=(1, 2),
                        help="Nombre de processus en parallèle (1 ou 2).")
    parser.add_argument("--cible-basse", type=float, default=CIBLE_BASSE_DEFAUT,
                        help=f"Borne basse de la cible de taux de victoire "
                             f"(défaut {CIBLE_BASSE_DEFAUT}).")
    parser.add_argument("--cible-haute", type=float, default=CIBLE_HAUTE_DEFAUT,
                        help=f"Borne haute de la cible (défaut "
                             f"{CIBLE_HAUTE_DEFAUT}).")
    parser.add_argument("--limite-temps", type=float, default=None,
                        help="Limite de temps FERME, en secondes, pour toute "
                             "la campagne (garde-fou externe par "
                             "sous-processus, voir _limite_temps_ferme.py).")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Journalise le détail de la campagne.")
    parser.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    return parser


def _valider_et_construire(args, parser: argparse.ArgumentParser
                           ) -> tuple[str, list[Tache]]:
    if args.donnes < 1:
        parser.error("--donnes doit être au moins 1")
    if args.max_tours < 1:
        parser.error("--max-tours doit être au moins 1")
    if args.budget_solveur is not None and args.budget_solveur <= 0:
        parser.error("--budget-solveur doit être > 0")
    if not 0.0 < args.cible_basse < args.cible_haute < 1.0:
        parser.error("--cible-basse doit être < --cible-haute, les deux dans ]0, 1[")
    if args.candidats is not None and args.paire:
        parser.error("--paire et --candidats/--contre sont incompatibles "
                     "(paires fixes vs balayage d'un niveau)")
    if args.candidats is not None and args.contre is None:
        parser.error("--candidats exige --contre")
    if args.candidats is None and args.contre is not None:
        parser.error("--contre exige --candidats")

    try:
        reglages = [parser_reglage(r) for r in args.reglage]
        paires = [parser_paire(p) for p in args.paire]
        niveau_candidat = candidats = None
        if args.candidats is not None:
            niveau_candidat, candidats = parser_candidats(args.candidats)
            if niveau_candidat == args.contre:
                raise ValueError("--contre doit différer du niveau balayé "
                                 "par --candidats")
    except ValueError as exc:
        parser.error(str(exc))

    resolus = bridages_resolus(reglages)
    if candidats is not None:
        mode = "balayage"
        taches = construire_taches(mode, niveau_candidat=niveau_candidat,
                                   candidats=candidats, contre=args.contre,
                                   resolus=resolus)
    else:
        mode = "paires"
        taches = construire_taches(mode, paires=paires, resolus=resolus)
    return mode, taches


def _executer(args, dossier: Path, mode: str, taches: list[Tache]) -> int:
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)-8s %(message)s",
                        datefmt="%H:%M:%S")
    if args.verbose:
        logger.setLevel(logging.INFO)

    dossier.mkdir(parents=True, exist_ok=True)
    empreinte = construire_empreinte(mode, taches, args.donnes, args.seed,
                                     args.max_tours, args.budget_solveur,
                                     args.cible_basse, args.cible_haute)
    try:
        empreinte = verifier_ou_ecrire_empreinte(dossier, empreinte)
    except ReglagesIncompatibles as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1

    donnes_visees = empreinte["donnes"]
    deadline = ((time.monotonic() + args.limite_temps)
               if args.limite_temps is not None else None)
    interrompu = jouer_campagne(dossier, taches, donnes_visees, args.seed,
                                args.max_tours, args.budget_solveur,
                                args.processus, deadline, args.cible_basse,
                                args.cible_haute, mode)
    print((dossier / "rapport.txt").read_text(encoding="utf-8"), end="")
    return CODE_LIMITE_TEMPS if interrompu else CODE_TERMINE


def main(argv: list[str]) -> int:
    parser = _construire_parser()
    args = parser.parse_args(argv[1:])
    dossier = Path(args.dossier)

    if args.statut:
        return commande_statut(dossier)

    mode, taches = _valider_et_construire(args, parser)

    # Échec franc sans solveur exact (issue #223/#224) : ce script fait jouer
    # tous les niveaux par le chemin de production (jouer_niveau_bride).
    exiger_solveur_exact_ou_quitter()

    if args._worker or args.limite_temps is None:
        return _executer(args, dossier, mode, taches)

    # Relance surveillée (garde-fou externe, comme echelle_niveaux.py).
    return lancer_avec_limite_ferme(Path(__file__), list(argv[1:]), args.limite_temps)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
