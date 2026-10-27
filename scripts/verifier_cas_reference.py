#!/usr/bin/env python3
"""Vérifie le drapeau ``mise_initiale_faite`` des cas de référence
``tests/donnees/cas_expert_*.json`` créés par l'analyse (issue #202, point 5).

Ces fichiers figent, pour un tour précis d'une partie journalisée, l'état
exact (``etat``) soumis au solveur — dont la clé ``mise_initiale_faite`` de
chaque joueur. Quand le cas provient d'un FICHIER DE PARTIE REPRISE analysé
AVANT ce correctif, ce drapeau a pu être figé à tort à ``False`` (l'ancienne
analyse ne voyait pas les poses faites avant la fermeture du jeu — voir
``persistance/coups_rates.py``), ce qui bride le solveur et fausse le résultat
attendu.

Deux usages :

  1. Sans ``--dossier`` : se contente de LISTER les cas et leur drapeau
     ``mise_initiale_faite`` (rapport, aucune modification). Un drapeau
     ``False`` sur un tour élevé est à examiner (candidat « partie reprise »).

  2. Avec ``--dossier CHEMIN`` (dossier des journaux ``logs_parties``) :
     retrouve la partie d'origine de chaque cas (par l'identifiant encodé dans
     le nom de fichier), REGROUPE ses fichiers reprise
     (``persistance/parties_liees.py``), recalcule le drapeau correct pour le
     tour et le joueur du cas, et le COMPARE à celui figé. Avec ``--ecraser``,
     réécrit le drapeau des cas erronés (régénération ciblée).

Ce script ne modifie jamais l'IA ni le moteur : lecture/correction de fichiers
de test uniquement.

Usage :

    python scripts/verifier_cas_reference.py
    python scripts/verifier_cas_reference.py --dossier data/logs_parties
    python scripts/verifier_cas_reference.py --dossier data/logs_parties --ecraser
"""

import argparse
import json
import re
import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parent.parent
_SRC = _RACINE / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from rummikub.persistance.bilan import charger_journal, lister_journaux  # noqa: E402
from rummikub.persistance.coups_rates import extraire_toutes_decisions  # noqa: E402
from rummikub.persistance.parties_liees import fusionner_journaux  # noqa: E402

# Nom d'un cas de référence : cas_expert_<prefixe>_<base>_tour<N>.json, où
# <base> = 12 derniers caractères alphanumériques du nom du journal d'origine
# (voir scripts/analyser_coups_rates.py::_nom_fichier_cas).
_RE_CAS = re.compile(r"^cas_expert_.*?_([a-zA-Z0-9]+)_tour(\d+)\.json$")


def _dossier_cas() -> Path:
    return _RACINE / "tests" / "donnees"


def _base_alnum(nom_journal: str) -> str:
    """12 derniers caractères alphanumériques du *stem* d'un nom de journal —
    même calcul que ``_nom_fichier_cas`` pour relier un cas à sa partie."""
    return re.sub(r"[^a-zA-Z0-9]+", "", Path(nom_journal).stem)[-12:]


def _parties_par_base(dossier: Path) -> dict:
    """``{base_alnum: partie_fusionnee}`` : regroupe les journaux du dossier
    par partie reprise et indexe chaque partie par la base alphanumérique de
    CHACUN de ses fichiers (un cas peut citer n'importe lequel)."""
    journaux = []
    for chemin in lister_journaux(dossier):
        data = charger_journal(chemin)
        if data is not None:
            journaux.append({"nom": chemin.name, "data": data})
    index = {}
    for partie in fusionner_journaux(journaux):
        for nom in partie["fichiers"]:
            index[_base_alnum(nom)] = partie
    return index


def _drapeau_correct(partie, tour: int, idx: int):
    """Drapeau ``mise_initiale_faite`` recalculé pour le joueur ``idx`` au tour
    ``tour`` de ``partie`` (fusionnée). Retourne ``True``/``False``,
    ``"inconnu"`` (historique manquant) ou ``None`` (tour/joueur introuvable)."""
    decisions = extraire_toutes_decisions(
        partie["data"], lambda joueur, i: i == idx, partie["debut_present"])
    for d in decisions:
        if d["tour"] == tour and d["idx"] == idx:
            if d["mise_initiale_inconnue"]:
                return "inconnu"
            return d["etat"]["joueurs"][idx]["mise_initiale_faite"]
    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Vérifie le drapeau mise_initiale_faite des cas de "
                    "référence cas_expert_*.json (issue #202).")
    parser.add_argument("--dossier", default=None,
                        help="Dossier des journaux (logs_parties) pour recalculer "
                             "le drapeau correct ; sans lui, simple rapport.")
    parser.add_argument("--ecraser", action="store_true",
                        help="Réécrit le drapeau des cas erronés (nécessite --dossier).")
    parser.add_argument("--cas", default=None,
                        help="Dossier des cas (défaut : tests/donnees).")
    args = parser.parse_args(argv)

    dossier_cas = Path(args.cas) if args.cas else _dossier_cas()
    index = _parties_par_base(Path(args.dossier)) if args.dossier else None

    cas = sorted(dossier_cas.glob("cas_expert_*.json"))
    if not cas:
        print(f"Aucun cas_expert_*.json dans {dossier_cas}.", file=sys.stderr)
        return 0

    nb_corriges = nb_suspects = 0
    for chemin in cas:
        data = json.loads(chemin.read_text(encoding="utf-8"))
        idx = data.get("idx")
        joueurs = data.get("etat", {}).get("joueurs", [])
        fige = (joueurs[idx].get("mise_initiale_faite")
                if isinstance(idx, int) and 0 <= idx < len(joueurs) else None)
        m = _RE_CAS.match(chemin.name)
        base, tour = (m.group(1), int(m.group(2))) if m else (None, None)

        ligne = f"{chemin.name} : idx={idx}, mise_initiale_faite={fige}"
        if fige is False:
            nb_suspects += 1
            ligne += "  <- False : à examiner (candidat partie reprise)"

        if index is not None and base is not None and base in index:
            correct = _drapeau_correct(index[base], tour, idx)
            if correct is None:
                ligne += "  [tour/joueur introuvable dans la partie recalculée]"
            elif correct == "inconnu":
                ligne += "  [recalcul : mise initiale INCONNUE, historique manquant]"
            elif correct != fige:
                ligne += f"  [recalcul : devrait être {correct}]"
                if args.ecraser:
                    joueurs[idx]["mise_initiale_faite"] = correct
                    chemin.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
                    ligne += "  -> CORRIGÉ"
                    nb_corriges += 1
            else:
                ligne += "  [recalcul : OK]"
        elif index is not None:
            ligne += "  [partie d'origine introuvable dans --dossier]"

        print(ligne)

    print(f"\n{len(cas)} cas examiné(s), {nb_suspects} à drapeau False, "
          f"{nb_corriges} corrigé(s).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
