#!/usr/bin/env python3
"""Tournoi « en échelle » des cinq niveaux d'IA Rummikub, par DUELS entre
niveaux voisins (issue #213, critère resserré par #220).

Vérifie que l'échelle des niveaux (``config.NIVEAUX`` : Débutant → Facile →
Intermédiaire → Avancé → Expert, voir ``moteur/niveaux.py``) est bien
CROISSANTE : chaque niveau doit battre nettement le niveau juste en dessous.
Joue des matchs à 2 joueurs EN MIROIR (donne rejouée places échangées,
reproductible sous ``graine_ia`` — comme ``scripts/comparer_niveaux_ia.py``)
entre des paires de niveaux, puis affiche, pour chaque paire, le taux de
victoire du niveau le PLUS FORT avec son intervalle de confiance à 95 %.

Paires jouées :
  - toutes les paires ADJACENTES de l'échelle (Débutant–Facile, Facile–
    Intermédiaire, Intermédiaire–Avancé, Avancé–Expert) ;
  - quelques paires NON ADJACENTES de contrôle (Débutant–Intermédiaire,
    Facile–Avancé, Intermédiaire–Expert), qui doivent montrer un écart encore
    plus net.

AVERTISSEMENT IMPORTANT (issue #213 §2) : Avancé et Expert sont STRICTEMENT
IDENTIQUES en force (même solveur exact complet, sans aucune étape
supplémentaire). Expert avait porté une vérification de finition en fin de
partie (#221, retirée par #236, jamais un coup changé), puis un sixième
niveau, « Champion du Monde », d'autres stratégies multi-tours (retiré par
#235, aucun effet mesurable sur le taux de victoire face à Expert). La paire
Avancé–Expert est donc ATTENDUE à ~50 % / égalité statistique : ce n'est PAS
un échec de l'échelle. Le script le signale explicitement pour cette paire.

**#220 retire le relevé des tuiles restantes en défaite** (miroir d'un niveau
contre lui-même, option ``--donnes-profil``) : voir CONTEXTE.md §16 pour les
raisons (mesure non comparable à un humain, parties qui ne finissent plus dès
que ``perturbation_max >= 1``, tout le temps imparti consommé sans que les
duels ne soient jamais joués — #216/#217). Le seul critère de force retenu est
désormais le duel entre niveaux voisins ci-dessus.

Ce script RÉUTILISE ``comparer`` de ``scripts/comparer_niveaux_ia.py`` (logique
de match miroir déjà reproductible et éprouvée) plutôt que de la réimplémenter.

Limite de temps FERME (``--limite-temps``) : en plus de l'arrêt propre interne
(aucune nouvelle paire/donne lancée au-delà), un garde-fou EXTERNE
(sous-processus surveillé, voir ``scripts/_limite_temps_ferme.py``) termine le
tournoi — et tout sous-processus qu'il aurait créé — si la limite est dépassée
d'une marge bornée. Code de sortie : ``0`` terminé normalement, ``3`` arrêté
sur la limite de temps, ``1`` erreur.

Résultats PARTIELS, avec ``--sortie``, écrits en continu (après chaque donne) :
chaque paire affiche victoires/parties jouées, taux ± marge, et donnes
terminées/prévues — marquée « partiel » tant qu'elle n'est pas finie.

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
                        tournoi : on ne LANCE plus de nouvelle paire une fois
                        la limite dépassée, et un garde-fou externe termine le
                        processus (et tout sous-processus) si elle est quand
                        même dépassée.
    --sortie FICHIER    Fichier où écrire les résultats PARTIELS en continu
                        (après chaque donne).
    --budget-solveur S  Budget du solveur exact par tour, en secondes (défaut
                        production = 1.5 s). À signaler si réduit (la force
                        d'Avancé en dépend).
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
from rummikub.moteur import ia as _ia  # noqa: E402

# Réutilisation directe de la logique de match miroir, reproductible, de #213.
from comparer_niveaux_ia import comparer, intervalle_confiance_95  # noqa: E402
from _limite_temps_ferme import (  # noqa: E402
    CODE_LIMITE_TEMPS, CODE_TERMINE, lancer_avec_limite_ferme,
)
from _rapport_duels import (  # noqa: E402
    SEUIL_NET_BAS, SEUIL_NET_HAUT, entete_machine, verdict_ecart,
)
from _verif_solveur_exact import exiger_solveur_exact_ou_quitter  # noqa: E402

logger = logging.getLogger("echelle_niveaux")


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
    solveur un-tour complet sans bridage (Avancé/Expert, issue #213 §2)."""
    ba = _niveaux.bridage_pour(niveau_a)
    bb = _niveaux.bridage_pour(niveau_b)
    return ba.complet and bb.complet


def jouer_paire(niveau_faible: str, niveau_fort: str, nb_donnes: int,
                seed: int, max_tours: int, deadline: float | None,
                on_donne=None) -> dict:
    """Joue une paire (niveau_faible en camp A, niveau_fort en camp B), DONNE
    PAR DONNE, en vérifiant ``deadline`` (instant monotone) avant CHAQUE donne —
    une donne du solveur complet pouvant durer des dizaines de secondes, c'est
    la granularité la plus fine que permet la réutilisation de ``comparer``
    (comme ``match_solveurs`` s'arrête entre deux parties). Agrège les résumés
    des donnes effectivement jouées et renvoie un résumé centré sur le niveau
    FORT : victoires, matchs décidés, taux et IC 95 %.

    ``on_donne``, si fourni, est appelé après CHAQUE donne avec le résumé
    PARTIEL accumulé jusque-là (mêmes clés que le résultat final) — permet
    d'écrire les résultats partiels en continu (issue #220).

    Chaque donne ``i`` utilise ``seed + i`` : toutes les paires jouent ainsi la
    MÊME suite de donnes (comparables entre elles) et la campagne reste
    reproductible."""
    victoires_fort = matchs_decides = nuls = 0
    donnes_jouees = 0
    fins = {"chevalet_vide": 0, "pioche_vide": 0, "garde_fou": 0}
    identiques = _niveaux_identiques(niveau_faible, niveau_fort)
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
        if on_donne is not None:
            taux, marge = intervalle_confiance_95(victoires_fort, matchs_decides)
            on_donne({
                "niveau_faible": niveau_faible, "niveau_fort": niveau_fort,
                "identiques": identiques, "donnes_demandees": nb_donnes,
                "donnes_jouees": donnes_jouees, "matchs_decides": matchs_decides,
                "victoires_fort": victoires_fort, "nuls": nuls,
                "taux_fort": taux, "marge": marge, "fins": dict(fins),
            })

    taux, marge = intervalle_confiance_95(victoires_fort, matchs_decides)
    return {
        "niveau_faible": niveau_faible,
        "niveau_fort": niveau_fort,
        "identiques": identiques,
        "donnes_demandees": nb_donnes,
        "donnes_jouees": donnes_jouees,
        "matchs_decides": matchs_decides,
        "victoires_fort": victoires_fort,
        "nuls": nuls,
        "taux_fort": taux,
        "marge": marge,
        "fins": fins,
    }


# --------------------------------------------------------------------------- #
# Résultats partiels écrits en continu (issue #220)
# --------------------------------------------------------------------------- #

def _ecrire(sortie, lignes: list[str]) -> None:
    """Réécrit INTÉGRALEMENT le fichier de sortie (résultats partiels), comme
    ``scripts/valider_bas_echelle.py``."""
    if sortie is None:
        return
    Path(sortie).write_text("\n".join(lignes) + "\n", encoding="utf-8")


def _entete_rapport(nb_donnes: int, seed: int, max_tours: int,
                    limite_temps: float | None,
                    budget_solveur: float | None) -> list[str]:
    lignes = ["=" * 78,
              "TOURNOI EN ÉCHELLE PAR DUELS ENTRE NIVEAUX VOISINS (issue #213, "
              "critère #220)"]
    lignes.extend(entete_machine())
    budget_txt = (f"{budget_solveur:.2f} s/tour" if budget_solveur is not None
                  else "production (1.50 s)")
    lignes.append(f"donnes={nb_donnes} seed={seed} max_tours={max_tours} "
                  f"budget_solveur={budget_txt}"
                  + (f" limite_temps={limite_temps:.0f}s"
                     if limite_temps is not None else ""))
    lignes.append("=" * 78)
    return lignes


def jouer_tournoi(nb_donnes: int, seed: int, max_tours: int,
                  limite_temps: float | None = None, sortie=None,
                  budget_solveur: float | None = None) -> dict:
    """Joue toutes les paires (adjacentes puis contrôles non adjacents) sous la
    limite de temps FERME ``limite_temps`` (secondes). La limite est vérifiée
    avant chaque DONNE (voir :func:`jouer_paire`) : on arrête de lancer du
    travail dès qu'elle est dépassée et on exploite les résultats partiels. Une
    paire peut donc n'être jouée que sur une partie de ses donnes (ou pas du
    tout). Si ``sortie`` est fourni, les résultats partiels y sont écrits en
    continu, après chaque donne (issue #220)."""
    debut = time.monotonic()
    deadline = (debut + limite_temps) if limite_temps is not None else None
    adjacentes, non_adjacentes = _paires_tournoi()
    resultats = {"adjacentes": [], "non_adjacentes": []}
    interrompu = False
    paires_incompletes: list[tuple[str, str, int, int]] = []

    lignes = _entete_rapport(nb_donnes, seed, max_tours, limite_temps,
                             budget_solveur)
    _ecrire(sortie, lignes)

    groupes = (("adjacentes", "PAIRES ADJACENTES", adjacentes),
              ("non_adjacentes", "PAIRES DE CONTRÔLE (non adjacentes)",
               non_adjacentes))
    for categorie, libelle, paires in groupes:
        if not paires:
            continue
        lignes.append("")
        lignes.append(f"{libelle} :")
        _ecrire(sortie, lignes)
        for faible, fort in paires:
            if deadline is not None and time.monotonic() >= deadline:
                interrompu = True
                paires_incompletes.append((faible, fort, 0, nb_donnes))
                lignes.append(f"    {faible} vs {fort}: non jouée "
                              "(limite de temps) [partiel]")
                _ecrire(sortie, lignes)
                break
            logger.info("Paire %s vs %s...", faible, fort)
            lignes.append("")
            idx_ligne = len(lignes) - 1

            def _maj(res_partiel, idx_ligne=idx_ligne):
                lignes[idx_ligne] = _ligne_paire(res_partiel)
                _ecrire(sortie, lignes)

            res = jouer_paire(faible, fort, nb_donnes, seed, max_tours,
                              deadline, on_donne=_maj)
            resultats[categorie].append(res)
            if res["donnes_jouees"] < nb_donnes:
                interrompu = True
                paires_incompletes.append(
                    (faible, fort, res["donnes_jouees"], nb_donnes))
                break
        if interrompu:
            break

    duree = time.monotonic() - debut
    lignes.append("")
    lignes.append(f"Temps total : {duree:.1f} s.")
    if interrompu:
        lignes.append("(!) ARRÊTÉ SUR LA LIMITE DE TEMPS : tournoi INCOMPLET.")
        for faible, fort, jouees, demandees in paires_incompletes:
            lignes.append(f"    Paire incomplète : {faible} vs {fort} "
                          f"({jouees}/{demandees} donnes).")
    else:
        lignes.append("TERMINÉ NORMALEMENT (toutes les paires/donnes jouées).")
    lignes.append("=" * 78)
    _ecrire(sortie, lignes)

    return {
        "resultats": resultats,
        "interrompu": interrompu,
        "paires_incompletes": paires_incompletes,
        "duree_s": duree,
        "nb_donnes": nb_donnes,
        "seed": seed,
        "max_tours": max_tours,
    }


# --------------------------------------------------------------------------- #
# Affichage (stdout, rapport détaillé avec verdicts)
# --------------------------------------------------------------------------- #

def _ligne_paire(res: dict) -> str:
    paire = f"{res['niveau_faible']} vs {res['niveau_fort']}"
    if res["donnes_jouees"] == 0:
        return f"  {paire:<40s} non jouée (limite de temps) [partiel]"
    partiel = " [partiel]" if res["donnes_jouees"] < res["donnes_demandees"] else ""
    if res["matchs_decides"] == 0:
        return (f"  {paire:<40s} aucun match décidé "
                f"({res['donnes_jouees']}/{res['donnes_demandees']} donne(s))"
                f"{partiel}")
    taux = res["taux_fort"] * 100
    marge = res["marge"] * 100
    cote = (f"{res['victoires_fort']}/{res['matchs_decides']}")
    verdict = verdict_ecart(res["taux_fort"], res["marge"], res["identiques"])
    donnes = f"[{res['donnes_jouees']}/{res['donnes_demandees']}d]"
    return (f"  {paire:<40s} {res['niveau_fort']:<18s} "
            f"{cote:>9s}  {taux:5.1f} % ± {marge:4.1f} pt  "
            f"{donnes:<8s}{partiel} {verdict}")


def afficher_rapport(rapport: dict) -> None:
    res = rapport["resultats"]
    print("=" * 78)
    print("TOURNOI EN ÉCHELLE DES CINQ NIVEAUX D'IA, PAR DUELS (issue #213, "
          "critère #220)")
    print(f"{rapport['nb_donnes']} donne(s) x 2 (miroir) par paire — "
         f"graine {rapport['seed']}, max_tours {rapport['max_tours']}")
    budget = rapport.get("budget_solveur")
    if budget is not None:
        print(f"  Budget solveur exact : {budget:.2f} s/tour "
              f"(production 1.50 — réduit pour tenir le temps imparti).")
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
    adjacent est-il « net » (60–75 %) ? — en excluant explicitement la paire
    identique Avancé/Expert (égalité ATTENDUE)."""
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

    # (b) Écart « net » (60–75 %) pour chaque paire adjacente distincte.
    nets = [SEUIL_NET_BAS <= r["taux_fort"] <= SEUIL_NET_HAUT for r in distinctes]
    if distinctes:
        print(f"  (b) Écart adjacent « net » "
              f"({int(SEUIL_NET_BAS * 100)}–{int(SEUIL_NET_HAUT * 100)} %) : "
              f"{sum(nets)}/{len(distinctes)} paire(s) distincte(s) dans la "
              f"cible visée par l'issue.")

    # Rappel sur la paire identique.
    if identiques:
        libelles = ", ".join(f"{r['niveau_faible']}–{r['niveau_fort']}"
                             for r in identiques)
        print(f"  (!) Paires ATTENDUES à ~50 % car solveur IDENTIQUE "
              f"(Avancé/Expert, #213 §2) : {libelles}.")
        print("      → Une égalité statistique sur ces paires est NORMALE, "
              "pas un échec de l'échelle.")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _construire_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tournoi en échelle des cinq niveaux d'IA Rummikub, par "
                    "duels entre niveaux voisins (issue #213, critère #220).")
    parser.add_argument("--donnes", type=int, default=40,
                        help="Donnes distinctes par paire (défaut 40 ; "
                             "chacune jouée 2 fois en miroir).")
    parser.add_argument("--seed", type=int, default=0,
                        help="Graine aléatoire (défaut 0, reproductible).")
    parser.add_argument("--max-tours", type=int, default=300,
                        help="Garde-fou anti-blocage par manche (défaut 300).")
    parser.add_argument("--limite-temps", type=float, default=None,
                        help="Limite de temps FERME, en secondes, pour tout le "
                             "tournoi : aucune nouvelle paire/donne lancée "
                             "au-delà, et un garde-fou externe termine le "
                             "processus (et tout sous-processus) si elle est "
                             "quand même dépassée.")
    parser.add_argument("--sortie", default=None,
                        help="Fichier où écrire les résultats PARTIELS en "
                             "continu (après chaque donne).")
    parser.add_argument("--budget-solveur", type=float, default=None,
                        help="Budget du solveur exact par tour, en secondes "
                             "(défaut : production = 1.5). Le réduire accélère "
                             "une campagne longue ; à signaler dans le rapport.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Journalise le détail de chaque paire.")
    parser.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    return parser


def _executer(args) -> int:
    """Logique réelle du tournoi — appelée en sous-processus (``--_worker``)
    quand ``--limite-temps`` est fourni, ou en direct sinon (voir ``main``)."""
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )
    if args.verbose:
        logger.setLevel(logging.INFO)

    if args.budget_solveur is not None:
        # Budget du solveur exact pour TOUTE la campagne (accélère un tournoi
        # long ; à signaler dans le rapport car la force d'Avancé en dépend).
        _ia.BUDGET_TEMPS_EXPERT = args.budget_solveur

    rapport = jouer_tournoi(args.donnes, args.seed, args.max_tours,
                            args.limite_temps, sortie=args.sortie,
                            budget_solveur=args.budget_solveur)
    rapport["budget_solveur"] = args.budget_solveur
    afficher_rapport(rapport)
    return CODE_LIMITE_TEMPS if rapport["interrompu"] else CODE_TERMINE


def main(argv: list[str]) -> int:
    parser = _construire_parser()
    args = parser.parse_args(argv[1:])

    if args.donnes < 1:
        parser.error("--donnes doit être au moins 1")
    if args.budget_solveur is not None and args.budget_solveur <= 0:
        parser.error("--budget-solveur doit être > 0")

    # Échec franc sans solveur exact (issue #223, point 1) : ce tournoi fait
    # jouer Avancé/Expert ET Facile/Intermédiaire (qui consultent aussi le
    # modèle exact, voir ia._coup_selon_perturbation) —
    # pas de ``--sans-exact`` ici, donc toujours requis. AVANT la relance
    # surveillée ci-dessous, pour échouer vite sans sous-processus inutile.
    exiger_solveur_exact_ou_quitter()

    if args._worker or args.limite_temps is None:
        return _executer(args)

    # Relance surveillée (garde-fou externe, #220) : plus de limite de temps
    # qui ne soit pas ferme — voir scripts/_limite_temps_ferme.py.
    return lancer_avec_limite_ferme(Path(__file__), list(argv[1:]),
                                    args.limite_temps)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
