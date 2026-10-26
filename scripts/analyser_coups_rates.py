#!/usr/bin/env python3
"""Analyse des « coups ratés » de l'IA à partir des journaux de parties
(issue #188, suite de #185).

Pour chaque décision d'une IA de piocher ou de passer, reconstitue l'état
exact (chevalets, plateau) qu'elle affrontait — enregistré dans le journal
juste avant cette décision — et interroge le solveur d'Expert
(``moteur/solveur.py``) sur cet état avec un budget de temps généreux. Si le
solveur trouve un coup qui pose au moins une tuile, la décision est un
« coup raté ».

Logique de détection et de résumé : voir ``persistance/coups_rates.py`` (pur,
testé indépendamment). Ce script est en ligne de commande, moteur Python
seul (aucun import pywebview — voir CONTEXTE.md §7).

ATTENTION — à lire avant d'interpréter le résultat : le solveur gèle
certaines combinaisons déjà posées sur le plateau pour limiter la
combinatoire (voir la docstring de ``moteur/solveur.py``). Un coup non
trouvé ne prouve donc PAS qu'aucun coup n'existe : les coups ratés détectés
ci-dessous sont une BORNE BASSE, jamais une liste exhaustive. Ne JAMAIS
conclure d'un chiffre bas que le niveau joue parfaitement.

Usage :

    python scripts/analyser_coups_rates.py
    python scripts/analyser_coups_rates.py chemin/vers/partie_xxx.json
    python scripts/analyser_coups_rates.py --tous
    python scripts/analyser_coups_rates.py --tous --dossier chemin/vers/logs_parties
    python scripts/analyser_coups_rates.py --budget 20 --budget-production 1.5

Cette analyse ne modifie jamais l'IA ni le moteur : elle se limite à relire
des journaux déjà écrits et à interroger le solveur en lecture pure.
"""

import argparse
import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parent.parent
_SRC = _RACINE / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from rummikub.persistance.bilan import charger_journal, lister_journaux  # noqa: E402
from rummikub.persistance.coups_rates import (  # noqa: E402
    analyser_journal, calculer_resume, top_coups_rates,
)

LIBELLE_MOMENT = {"avant_mise": "avant la mise initiale",
                   "apres_mise": "après la mise initiale"}

AVERTISSEMENT = (
    "ATTENTION : le solveur Expert gèle certaines combinaisons déjà posées sur\n"
    "le plateau pour limiter la combinatoire (voir moteur/solveur.py) — un coup\n"
    "non trouvé ne prouve pas qu'aucun coup n'existe. Les coups ratés détectés\n"
    "ci-dessus sont une BORNE BASSE, pas une liste exhaustive."
)


def _dossier_defaut() -> Path:
    try:
        from rummikub import config
        return config.RACINE_DATA / "logs_parties"
    except Exception:
        return _RACINE / "data" / "logs_parties"


def _ordre_niveaux() -> list:
    try:
        from rummikub import config
        return list(config.NIVEAUX)
    except Exception:
        return []


def _fmt_pct(valeur) -> str:
    return "—" if valeur is None else f"{valeur * 100:.0f} %"


def afficher_resume(resume: dict, flux=sys.stdout) -> None:
    if not resume:
        print("Aucune décision de piocher/passer d'une IA trouvée pour ce filtre.",
              file=flux)
        return

    ordre = _ordre_niveaux()
    niveaux = sorted(resume, key=lambda n: (ordre.index(n) if n in ordre
                                            else len(ordre), n))
    for niveau in niveaux:
        print(f"=== {niveau} ===", file=flux)
        for moment in ("avant_mise", "apres_mise"):
            s = resume[niveau].get(moment)
            if not s:
                continue
            print(f"  {LIBELLE_MOMENT[moment]} :", file=flux)
            print(f"    Décisions pioche/passe analysées : {s['decisions']}", file=flux)
            print(f"    Coups ratés détectés             : {s['coups_rates']} "
                  f"({_fmt_pct(s['pct_rates'])})", file=flux)
            if niveau == "Expert" and s["coups_rates"]:
                print(f"    ... dont limités par le budget de production (1,5 s) : "
                      f"{s['budget_limite']}", file=flux)
            if s["inconclusifs"]:
                print(f"    Décisions inconclusives (budget généreux épuisé)  : "
                      f"{s['inconclusifs']}", file=flux)
        print(file=flux)


def afficher_top(resultats: list, n: int = 5, flux=sys.stdout) -> None:
    top = top_coups_rates(resultats, n=n)
    if not top:
        return
    print(f"=== {len(top)} coup(s) raté(s) le(s) plus important(s) (à examiner à la main) ===",
          file=flux)
    for r in top:
        detail = (f"tour {r['tour']} — {r['nom']} ({r['niveau']}, {r['action']}) : "
                  f"{r['nb_tuiles']} tuile(s) ratée(s)")
        if r["moment"] == "avant_mise" and r["points_ouverture"] is not None:
            detail += f", ouverture à {r['points_ouverture']} points"
        print(f"  - {detail}", file=flux)
    print(file=flux)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyse des coups ratés (pioche/passe) d'une IA à partir "
                     "des journaux de parties (issue #188).")
    parser.add_argument("fichier", nargs="?", default=None,
                        help="Journal à analyser (défaut : le plus récent du dossier).")
    parser.add_argument("--tous", action="store_true",
                        help="Analyser tous les journaux du dossier plutôt que le "
                             "seul plus récent.")
    parser.add_argument("--dossier", default=None,
                        help="Dossier des journaux (défaut : RACINE_DATA/logs_parties).")
    parser.add_argument("--budget", type=float, default=10.0,
                        help="Budget de temps généreux du solveur, en secondes "
                             "(défaut 10).")
    parser.add_argument("--budget-production", type=float, default=None,
                        help="Budget de production à comparer pour Expert "
                             "(défaut : celui utilisé en jeu, voir moteur/ia.py).")
    parser.add_argument("--top", type=int, default=5,
                        help="Nombre de coups ratés détaillés à afficher (défaut 5).")
    args = parser.parse_args(argv)

    dossier = Path(args.dossier) if args.dossier else _dossier_defaut()

    if args.fichier:
        chemins = [Path(args.fichier)]
    elif args.tous:
        chemins = lister_journaux(dossier)
    else:
        tous = lister_journaux(dossier)
        chemins = [tous[-1]] if tous else []

    if not chemins:
        print("Aucun journal trouvé.", file=sys.stderr)
        return 0

    kwargs = {"budget_genereux": args.budget}
    if args.budget_production is not None:
        kwargs["budget_production"] = args.budget_production

    tous_resultats = []
    for chemin in chemins:
        data = charger_journal(chemin)
        if data is None:
            print(f"Journal illisible ou invalide, ignoré : {chemin}", file=sys.stderr)
            continue
        print(f"Analyse de {chemin.name}...", file=sys.stderr)

        def _progres(resultat, _chemin=chemin):
            marque = " <- coup raté" if resultat["coup_rate"] else ""
            print(f"  tour {resultat['tour']} ({resultat['nom']}, {resultat['niveau']}, "
                  f"{resultat['action']}){marque}", file=sys.stderr)

        resultats = analyser_journal(data, on_resultat=_progres, **kwargs)
        tous_resultats.extend(resultats)

    resume = calculer_resume(tous_resultats)
    afficher_resume(resume)
    afficher_top(tous_resultats, n=args.top)
    print(AVERTISSEMENT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
