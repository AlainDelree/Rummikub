#!/usr/bin/env python3
"""Tournoi « en échelle » des six niveaux d'IA Rummikub (issue #213).

Vérifie que l'échelle des niveaux (``config.NIVEAUX`` : Débutant → Facile →
Intermédiaire → Avancé → Expert → Champion du Monde, voir ``moteur/niveaux.py``)
est bien CROISSANTE : chaque niveau doit battre nettement le niveau juste en
dessous. Joue des matchs à 2 joueurs EN MIROIR (donne rejouée places échangées,
reproductible sous ``graine_ia`` — comme ``scripts/comparer_niveaux_ia.py``)
entre des paires de niveaux, puis affiche, pour chaque paire, le taux de
victoire du niveau le PLUS FORT avec son intervalle de confiance à 95 %.

Paires jouées :
  - toutes les paires ADJACENTES de l'échelle (Débutant–Facile, Facile–
    Intermédiaire, Intermédiaire–Avancé, Avancé–Expert, Expert–Champion du
    Monde) ;
  - quelques paires NON ADJACENTES de contrôle (Débutant–Intermédiaire,
    Facile–Avancé, Intermédiaire–Expert), qui doivent montrer un écart encore
    plus net.

AVERTISSEMENT IMPORTANT (issue #213 §2) : Avancé, Expert et Champion du Monde
sont PROVISOIREMENT IDENTIQUES — ils jouent tous le même solveur exact d'un
tour, COMPLET et sans bridage ; les stratégies multi-tours (réserve, non-don de
joker, rétention défensive — CONTEXTE.md §13) qui doivent distinguer Expert et
Champion du Monde ne sont pas encore implémentées. Les paires formées
uniquement de niveaux de ce trio (Avancé–Expert, Expert–Champion du Monde) sont
donc ATTENDUES à ~50 % / égalité statistique : ce n'est PAS un échec de
l'échelle, c'est le comportement documenté tant que ces stratégies n'existent
pas. Le script le signale explicitement pour chaque paire concernée.

Ce script RÉUTILISE ``comparer`` de ``scripts/comparer_niveaux_ia.py`` (logique
de match miroir déjà reproductible et éprouvée) plutôt que de la réimplémenter.

Usage :

    python scripts/echelle_niveaux.py
    python scripts/echelle_niveaux.py --donnes 60 --seed 7
    python scripts/echelle_niveaux.py --donnes 3 --limite-temps 60   # smoke

Options :
    --donnes N          Nombre de donnes distinctes par paire (défaut 40 ;
                        chacune jouée 2 fois en miroir → 2N matchs/paire).
                        L'issue demande au moins 40 par paire pour conclure ;
                        une valeur basse (p. ex. 3) permet un essai rapide.
    --seed N            Graine aléatoire, campagne reproductible (défaut 0).
    --max-tours N       Garde-fou anti-blocage par manche (défaut 300).
    --limite-temps S    Limite de temps FERME, en secondes, pour tout le
                        tournoi (comme ``scripts/match_solveurs.py``) : on ne
                        LANCE plus de nouvelle paire une fois la limite
                        dépassée, et on affiche les résultats PARTIELS déjà
                        obtenus. Sans elle, toutes les paires sont jouées.
    -v, --verbose       Journalise le détail de chaque paire.
"""

import argparse
import logging
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "src"
SCRIPTS = RACINE / "scripts"
for _p in (SRC, SCRIPTS):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rummikub.config import NIVEAUX  # noqa: E402
from rummikub.moteur import niveaux as _niveaux  # noqa: E402

# Réutilisation directe de la logique de match miroir, reproductible, de #213.
from comparer_niveaux_ia import (  # noqa: E402
    comparer, intervalle_confiance_95,
)

logger = logging.getLogger("echelle_niveaux")

# Seuils d'un écart « net » attendu entre deux niveaux adjacents distincts
# (issue #213 §2 : un niveau plus fort gagne « nettement », visé 60–80 %).
SEUIL_NET_BAS = 0.60
SEUIL_NET_HAUT = 0.80


def _paires_tournoi() -> list[tuple[str, str]]:
    """Paires (niveau_faible, niveau_fort) à jouer : toutes les paires
    ADJACENTES de l'échelle, plus quelques paires NON ADJACENTES de contrôle.
    L'ordre garantit que le second élément est toujours le niveau supposé le
    plus fort (indice supérieur dans ``config.NIVEAUX``)."""
    idx = {n: i for i, n in enumerate(NIVEAUX)}
    adjacentes = [(NIVEAUX[i], NIVEAUX[i + 1]) for i in range(len(NIVEAUX) - 1)]
    # Contrôles non adjacents (écart de 2 crans), bornés aux niveaux existants.
    non_adjacentes = []
    for bas, haut in (("Débutant", "Intermédiaire"),
                      ("Facile", "Avancé"),
                      ("Intermédiaire", "Expert")):
        if bas in idx and haut in idx:
            non_adjacentes.append((bas, haut))
    return adjacentes, non_adjacentes


def _niveaux_identiques(niveau_a: str, niveau_b: str) -> bool:
    """Vrai si les deux niveaux jouent EXACTEMENT le même moteur : tous deux le
    solveur un-tour complet sans bridage (Avancé/Expert/Champion du Monde tant
    que les stratégies multi-tours ne sont pas implémentées, issue #213 §2)."""
    ba = _niveaux.bridage_pour(niveau_a)
    bb = _niveaux.bridage_pour(niveau_b)
    return ba.complet and bb.complet


def jouer_paire(niveau_faible: str, niveau_fort: str, nb_donnes: int,
                seed: int, max_tours: int, deadline: float | None) -> dict:
    """Joue une paire (niveau_faible en camp A, niveau_fort en camp B), DONNE
    PAR DONNE, en vérifiant ``deadline`` (instant monotone) avant CHAQUE donne —
    une donne du solveur complet pouvant durer des dizaines de secondes, c'est
    la granularité la plus fine que permet la réutilisation de ``comparer``
    (comme ``match_solveurs`` s'arrête entre deux parties). Agrège les résumés
    des donnes effectivement jouées et renvoie un résumé centré sur le niveau
    FORT : victoires, matchs décidés, taux et IC 95 %.

    Chaque donne ``i`` utilise ``seed + i`` : toutes les paires jouent ainsi la
    MÊME suite de donnes (comparables entre elles) et la campagne reste
    reproductible."""
    victoires_fort = matchs_decides = nuls = 0
    donnes_jouees = 0
    fins = {"chevalet_vide": 0, "pioche_vide": 0, "garde_fou": 0}
    for i in range(nb_donnes):
        if deadline is not None and time.monotonic() >= deadline:
            break
        resume = comparer(niveau_faible, niveau_fort, 1, seed + i, max_tours,
                          nb_manches=1, preferer_simple=True)
        victoires_fort += resume["victoires"]["B"]
        matchs_decides += resume["matchs_decides"]
        nuls += resume["matchs_nuls"]
        for cle in fins:
            fins[cle] += resume["fins"][cle]
        donnes_jouees += 1

    taux, marge = intervalle_confiance_95(victoires_fort, matchs_decides)
    return {
        "niveau_faible": niveau_faible,
        "niveau_fort": niveau_fort,
        "identiques": _niveaux_identiques(niveau_faible, niveau_fort),
        "donnes_demandees": nb_donnes,
        "donnes_jouees": donnes_jouees,
        "matchs_decides": matchs_decides,
        "victoires_fort": victoires_fort,
        "nuls": nuls,
        "taux_fort": taux,
        "marge": marge,
        "fins": fins,
    }


def jouer_tournoi(nb_donnes: int, seed: int, max_tours: int,
                  limite_temps: float | None) -> dict:
    """Joue toutes les paires (adjacentes puis contrôles non adjacents) sous la
    limite de temps FERME ``limite_temps`` (secondes). La limite est vérifiée
    avant chaque DONNE (voir :func:`jouer_paire`) : on arrête de lancer du
    travail dès qu'elle est dépassée et on exploite les résultats partiels. Une
    paire peut donc n'être jouée que sur une partie de ses donnes (ou pas du
    tout)."""
    debut = time.monotonic()
    deadline = (debut + limite_temps) if limite_temps is not None else None
    adjacentes, non_adjacentes = _paires_tournoi()
    resultats = {"adjacentes": [], "non_adjacentes": []}
    interrompu = False

    for categorie, paires in (("adjacentes", adjacentes),
                              ("non_adjacentes", non_adjacentes)):
        for faible, fort in paires:
            if deadline is not None and time.monotonic() >= deadline:
                interrompu = True
                break
            logger.info("Paire %s vs %s...", faible, fort)
            res = jouer_paire(faible, fort, nb_donnes, seed, max_tours, deadline)
            resultats[categorie].append(res)
            if res["donnes_jouees"] < nb_donnes:
                interrompu = True
                break
        if interrompu:
            break

    return {
        "resultats": resultats,
        "interrompu": interrompu,
        "duree_s": time.monotonic() - debut,
        "nb_donnes": nb_donnes,
        "seed": seed,
        "max_tours": max_tours,
    }


# --------------------------------------------------------------------------- #
# Affichage
# --------------------------------------------------------------------------- #

def _ligne_paire(res: dict) -> str:
    paire = f"{res['niveau_faible']} vs {res['niveau_fort']}"
    if res["donnes_jouees"] == 0:
        return f"  {paire:<40s} non jouée (limite de temps)"
    if res["matchs_decides"] == 0:
        return (f"  {paire:<40s} aucun match décidé "
                f"({res['donnes_jouees']}/{res['donnes_demandees']} donne(s))")
    taux = res["taux_fort"] * 100
    marge = res["marge"] * 100
    cote = (f"{res['victoires_fort']}/{res['matchs_decides']}")
    ecart_signif = abs(res["taux_fort"] - 0.5) > res["marge"]
    if res["identiques"]:
        verdict = "ÉGALITÉ ATTENDUE (solveur identique, #213 §2)"
    elif not ecart_signif:
        verdict = "non significatif"
    elif SEUIL_NET_BAS <= res["taux_fort"] <= SEUIL_NET_HAUT:
        verdict = "net (60–80 %)"
    elif res["taux_fort"] > SEUIL_NET_HAUT:
        verdict = "très net (>80 %)"
    else:
        verdict = "significatif mais faible (<60 %)"
    donnes = f"[{res['donnes_jouees']}/{res['donnes_demandees']}d]"
    return (f"  {paire:<40s} {res['niveau_fort']:<18s} "
            f"{cote:>9s}  {taux:5.1f} % ± {marge:4.1f} pt  {donnes:<8s} {verdict}")


def afficher_rapport(rapport: dict) -> None:
    res = rapport["resultats"]
    print("=" * 78)
    print("TOURNOI EN ÉCHELLE DES SIX NIVEAUX D'IA (issue #213)")
    print(f"{rapport['nb_donnes']} donne(s) x 2 (miroir) par paire — "
          f"graine {rapport['seed']}, max_tours {rapport['max_tours']}")
    if rapport["interrompu"]:
        print("  (!) Limite de temps atteinte : résultats PARTIELS "
              "(paires restantes non jouées).")
    print("=" * 78)
    print(f"  {'Paire':<40s} {'Plus fort':<18s} {'V/N':>9s}  "
          f"{'Taux (IC 95 %)':>16s}  Verdict")
    print("-" * 78)

    print("  PAIRES ADJACENTES :")
    for r in res["adjacentes"]:
        print(_ligne_paire(r))
    if res["non_adjacentes"]:
        print("  PAIRES DE CONTRÔLE (non adjacentes) :")
        for r in res["non_adjacentes"]:
            print(_ligne_paire(r))

    print("-" * 78)
    _afficher_verdicts(res)
    print("=" * 78)
    print(f"Temps total du tournoi : {rapport['duree_s']:.1f}s.")


def _afficher_verdicts(res: dict) -> None:
    """Deux vérifications demandées par l'issue : (a) l'échelle est-elle
    strictement croissante sur les paires adjacentes ? (b) chaque écart
    adjacent est-il « net » (60–80 %) ? — en excluant explicitement les paires
    du trio identique Avancé/Expert/Champion du Monde (égalité ATTENDUE)."""
    adjacentes = res["adjacentes"]
    distinctes = [r for r in adjacentes
                  if not r["identiques"] and r["matchs_decides"] > 0]
    identiques = [r for r in adjacentes if r["identiques"]]

    print("  VERDICTS :")
    if not adjacentes:
        print("    Aucune paire adjacente jouée (limite de temps).")
        return

    # (a) Échelle strictement croissante : chaque paire adjacente DISTINCTE a le
    # niveau fort > 50 % de façon significative.
    croissante = all(r["taux_fort"] > 0.5
                     and abs(r["taux_fort"] - 0.5) > r["marge"]
                     for r in distinctes)
    if distinctes:
        print(f"  (a) Échelle strictement croissante sur les paires adjacentes "
              f"DISTINCTES : {'OUI' if croissante else 'NON'} "
              f"({len(distinctes)} paire(s) distincte(s) mesurée(s)).")
    else:
        print("  (a) Aucune paire adjacente distincte jouée pour conclure.")

    # (b) Écart « net » (60–80 %) pour chaque paire adjacente distincte.
    nets = [SEUIL_NET_BAS <= r["taux_fort"] <= SEUIL_NET_HAUT for r in distinctes]
    if distinctes:
        print(f"  (b) Écart adjacent « net » (60–80 %) : "
              f"{sum(nets)}/{len(distinctes)} paire(s) distincte(s) dans la "
              f"cible visée par l'issue.")

    # Rappel sur le trio identique.
    if identiques:
        libelles = ", ".join(f"{r['niveau_faible']}–{r['niveau_fort']}"
                             for r in identiques)
        print(f"  (!) Paires ATTENDUES à ~50 % car solveur IDENTIQUE "
              f"(Avancé/Expert/Champion du Monde, stratégies multi-tours non "
              f"implémentées, #213 §2) : {libelles}.")
        print("      → Une égalité statistique sur ces paires est NORMALE, "
              "pas un échec de l'échelle.")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Tournoi en échelle des six niveaux d'IA Rummikub "
                    "(issue #213).")
    parser.add_argument("--donnes", type=int, default=40,
                        help="Donnes distinctes par paire (défaut 40 ; "
                             "chacune jouée 2 fois en miroir).")
    parser.add_argument("--seed", type=int, default=0,
                        help="Graine aléatoire (défaut 0, reproductible).")
    parser.add_argument("--max-tours", type=int, default=300,
                        help="Garde-fou anti-blocage par manche (défaut 300).")
    parser.add_argument("--limite-temps", type=float, default=None,
                        help="Limite de temps FERME, en secondes, pour tout le "
                             "tournoi (résultats partiels exploités).")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Journalise le détail de chaque paire.")
    args = parser.parse_args(argv[1:])

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.donnes < 1:
        parser.error("--donnes doit être au moins 1")

    rapport = jouer_tournoi(args.donnes, args.seed, args.max_tours,
                            args.limite_temps)
    afficher_rapport(rapport)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
