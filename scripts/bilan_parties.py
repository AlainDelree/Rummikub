#!/usr/bin/env python3
"""Bilan des parties jouées, par niveau d'IA rencontré par un joueur humain
(issue #185).

Lit les journaux de parties (``RACINE_DATA/logs_parties/partie_*.json``, voir
``src/rummikub/persistance/journal.py``) et affiche, pour chaque niveau d'IA
affronté par un humain dans une partie TERMINÉE (les parties abandonnées en
cours sont exclues, voir ``persistance/bilan.py``) :

- le nombre de parties, les victoires/défaites de l'humain et son taux de
  victoire ;
- la marge moyenne (tuiles restantes de l'IA quand l'humain gagne, de
  l'humain quand l'IA gagne) ;
- le nombre moyen de tours par partie ;
- la part des tours où l'IA a pioché ou passé plutôt que posé, et la
  répartition de ces tours entre début/milieu/fin de partie.

Script en ligne de commande, indépendant de toute interface (aucun import
pywebview — voir CONTEXTE.md §7).

Usage :

    python scripts/bilan_parties.py
    python scripts/bilan_parties.py --joueur Alain
    python scripts/bilan_parties.py --depuis 2026-10-01 --jusqu 2026-10-31
    python scripts/bilan_parties.py --dossier chemin/vers/logs_parties
"""

import argparse
import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parent.parent
_SRC = _RACINE / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from rummikub.persistance.bilan import calculer_bilan, charger_toutes_parties  # noqa: E402


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


def _fmt_moyenne(valeur, decimales=1) -> str:
    return "—" if valeur is None else f"{valeur:.{decimales}f}"


def _fmt_moment(repartition) -> str:
    if not repartition:
        return "—"
    return " / ".join(f"{k}={v * 100:.0f}%" for k, v in repartition.items())


def afficher_bilan(bilan: dict, flux=sys.stdout) -> None:
    if not bilan:
        print("Aucune partie terminée trouvée pour ce filtre.", file=flux)
        return

    ordre = _ordre_niveaux()
    niveaux = sorted(bilan, key=lambda n: (ordre.index(n) if n in ordre
                                           else len(ordre), n))

    for niveau in niveaux:
        s = bilan[niveau]
        print(f"=== {niveau} ===", file=flux)
        print(f"  Parties              : {s['parties']}", file=flux)
        print(f"  Victoires humain      : {s['victoires_humain']}", file=flux)
        print(f"  Défaites humain       : {s['defaites_humain']}", file=flux)
        print(f"  Taux de victoire      : {_fmt_pct(s['taux_victoire_humain'])}",
              file=flux)
        print(f"  Marge moy. (victoire) : {_fmt_moyenne(s['marge_moyenne_victoire'])} "
              "tuile(s) restante(s) côté IA", file=flux)
        print(f"  Marge moy. (défaite)  : {_fmt_moyenne(s['marge_moyenne_defaite'])} "
              "tuile(s) restante(s) côté humain", file=flux)
        print(f"  Tours moyens/partie   : {_fmt_moyenne(s['tours_moyens'])}", file=flux)
        print(f"  Tours IA pioche/passe : {_fmt_pct(s['part_pioche_ou_passe'])}"
              f"  (répartition : {_fmt_moment(s['repartition_moment_pioche_ou_passe'])})",
              file=flux)
        print(file=flux)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Bilan des parties jouées, par niveau d'IA (issue #185).")
    parser.add_argument("--joueur", default=None,
                        help="Ne garder que les parties jouées par ce joueur humain.")
    parser.add_argument("--depuis", default=None,
                        help="Date minimale (ISO, ex. 2026-10-01).")
    parser.add_argument("--jusqu", default=None,
                        help="Date maximale (ISO, ex. 2026-10-31).")
    parser.add_argument("--dossier", default=None,
                        help="Dossier des journaux (défaut : RACINE_DATA/logs_parties).")
    args = parser.parse_args(argv)

    dossier = Path(args.dossier) if args.dossier else _dossier_defaut()
    parties = charger_toutes_parties(dossier)
    bilan = calculer_bilan(parties, nom_joueur=args.joueur,
                           depuis=args.depuis, jusqu=args.jusqu)
    afficher_bilan(bilan)
    return 0


if __name__ == "__main__":
    sys.exit(main())
