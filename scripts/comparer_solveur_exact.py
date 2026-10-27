#!/usr/bin/env python3
"""Comparaison du solveur d'Expert (``moteur/solveur.py``) avec le solveur
EXACT indépendant de la bibliothèque ``rummikub-solver`` (licence MIT — issue
#204, suite de #201).

Pour chaque cas de référence ``tests/donnees/cas_expert_*.json`` ET
``tests/donnees/reference_*.json``, affiche :
  - le nombre de tuiles que NOTRE solveur pose au budget de PRODUCTION (1,5 s)
    et à un budget GÉNÉREUX (10 s) ;
  - le nombre de tuiles du solveur EXACT et sa durée de calcul ;
  - l'écart (exact − notre solveur à 1,5 s).
En fin de sortie : combien de cas notre solveur rate à 1,5 s, l'écart moyen et
maximal, le temps total du solveur exact, et le résultat des deux contrôles
indépendants de l'adaptateur (``valider_combinaison`` + conservation du
plateau, voir ``scripts/solveur_exact.py``).

Le cas ``reference_victoire_manquee_ines_tour85.json`` sert de test de
non-régression de la suite : une IA Expert avec 2 tuiles en main n'en a posé
qu'une ; notre solveur n'en trouve qu'une, même à 10 s, alors que le solveur
exact en trouve 2 (victoire immédiate manquée).

Option ``--journaux`` (``--tous``/``--dossier``) : compare AUSSI sur toutes les
décisions d'IA de vrais journaux de parties. L'utilisateur la lance lui-même —
le dossier de travail de l'agent ne contient aucun journal.

Ce script NE MODIFIE NI le solveur d'Expert, NI le jeu, NI les niveaux d'IA :
il interroge les deux solveurs en lecture pure. La bibliothèque étant une
dépendance de développement seulement, le script se sépare proprement si elle
est absente (voir ``scripts/solveur_exact.py`` et CONTEXTE.md §14).

Usage :

    python scripts/comparer_solveur_exact.py
    python scripts/comparer_solveur_exact.py --budget-production 1.5 --budget 10
    python scripts/comparer_solveur_exact.py --journaux --tous
    python scripts/comparer_solveur_exact.py --journaux --tous --dossier data/logs_parties
"""

import argparse
import json
import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parent.parent
_SRC = _RACINE / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import solveur_exact  # noqa: E402
from rummikub.moteur.solveur import resoudre_coup, BudgetDepasse  # noqa: E402


def _dossier_donnees_test() -> Path:
    return _RACINE / "tests" / "donnees"


def _notre_nb(etat: dict, idx: int, budget: float):
    """Nombre de tuiles posées par NOTRE solveur à ce budget, ou ``None`` si
    inconclusif (budget épuisé sans qu'aucune branche n'aboutisse)."""
    try:
        coup = resoudre_coup(etat, idx, budget_temps=budget)
    except BudgetDepasse:
        return None
    return len(coup["ids_tuiles"]) if coup else 0


def _fmt_nb(n) -> str:
    return "inconcl." if n is None else str(n)


# --------------------------------------------------------------------------- #
# Mode « cas de référence » (défaut).
# --------------------------------------------------------------------------- #

def _lister_cas() -> list:
    dossier = _dossier_donnees_test()
    cas = sorted(dossier.glob("cas_expert_*.json")) + sorted(dossier.glob("reference_*.json"))
    return cas


def comparer_cas(budget_production: float, budget_genereux: float,
                 flux=sys.stdout) -> int:
    cas = _lister_cas()
    if not cas:
        print("Aucun cas de référence trouvé.", file=sys.stderr)
        return 0

    print(f"=== Comparaison sur {len(cas)} cas de référence "
          f"(notre solveur {budget_production} s / {budget_genereux} s "
          f"vs exact) ===", file=flux)
    entete = (f"{'cas':46s} {'min':>4} {'exact':>6} {'1.5s':>6} "
              f"{'10s':>5} {'écart':>6} {'durée_exact':>12}")
    print(entete, file=flux)
    print("-" * len(entete), file=flux)

    nb_rates_prod = 0
    ecarts = []
    total_duree_exact = 0.0
    tous_valides = True
    toutes_conservations = True
    lignes_invalides = []

    for chemin in cas:
        data = json.loads(chemin.read_text(encoding="utf-8"))
        etat, idx = data["etat"], data["idx"]
        attendu_min = data.get("attendu_min_tuiles")

        res = solveur_exact.resoudre_exact(etat, idx)
        total_duree_exact += res.duree
        if not res.toutes_valides:
            tous_valides = False
            lignes_invalides.append((chemin.name, res.combos_invalides))
        if not res.conservation_ok:
            toutes_conservations = False

        n_prod = _notre_nb(etat, idx, budget_production)
        n_gen = _notre_nb(etat, idx, budget_genereux)

        # Écart mesuré au budget de production (celui du jeu livré).
        ref_prod = n_prod if n_prod is not None else 0
        ecart = res.nb_tuiles - ref_prod
        ecarts.append(ecart)
        if ecart > 0:
            nb_rates_prod += 1

        marque = ""
        if ecart > 0:
            marque = f"  <- rate {ecart} à {budget_production}s"
        caveat = "" if res.mise_faite else "  [mode INITIAL, cf. caveat]"
        print(f"{chemin.name:46s} {str(attendu_min if attendu_min is not None else '—'):>4} "
              f"{res.nb_tuiles:>6} {_fmt_nb(n_prod):>6} {_fmt_nb(n_gen):>5} "
              f"{ecart:>+6} {res.duree * 1000:>9.1f} ms{marque}{caveat}", file=flux)

    print("-" * len(entete), file=flux)
    print(f"\n=== Synthèse ===", file=flux)
    print(f"  Cas où notre solveur rate des tuiles à {budget_production} s : "
          f"{nb_rates_prod} / {len(cas)}", file=flux)
    if ecarts:
        print(f"  Écart (exact − notre solveur à {budget_production} s) : "
              f"moyen {sum(ecarts) / len(ecarts):.2f}, maximal {max(ecarts)}", file=flux)
    print(f"  Temps total du solveur exact : {total_duree_exact * 1000:.1f} ms "
          f"({total_duree_exact / len(cas) * 1000:.1f} ms/cas en moyenne)", file=flux)
    print(f"  Backend exact : {solveur_exact._backend_defaut()}", file=flux)
    print(f"  Toutes les combinaisons proposées sont valides "
          f"(valider_combinaison) : {tous_valides}", file=flux)
    print(f"  Conservation des tuiles du plateau sur tous les cas : "
          f"{toutes_conservations}", file=flux)
    if lignes_invalides:
        print("  ATTENTION — combinaisons invalides détectées :", file=flux)
        for nom, invalides in lignes_invalides:
            print(f"    {nom} : {invalides}", file=flux)
    print(file=flux)
    return 0


# --------------------------------------------------------------------------- #
# Mode « journaux » (option, l'utilisateur fournit les journaux).
# --------------------------------------------------------------------------- #

def comparer_journaux(chemins: list, budget_production: float,
                      budget_genereux: float, flux=sys.stdout) -> int:
    from rummikub.persistance.bilan import charger_journal
    from rummikub.persistance.parties_liees import fusionner_journaux
    from rummikub.persistance.coups_rates import extraire_decisions_ia_toutes

    journaux = []
    for chemin in chemins:
        data = charger_journal(chemin)
        if data is None:
            print(f"Journal illisible, ignoré : {chemin}", file=sys.stderr)
            continue
        journaux.append({"nom": chemin.name, "data": data})
    parties = fusionner_journaux(journaux)

    print(f"=== Comparaison sur les décisions d'IA de {len(parties)} partie(s) "
          f"(notre solveur {budget_production} s / {budget_genereux} s vs exact) ===",
          file=flux)

    nb_decisions = 0
    nb_exact_superieur_prod = 0
    nb_exact_superieur_gen = 0
    ecarts_prod = []
    total_duree_exact = 0.0
    tous_valides = True
    toutes_conservations = True
    pires = []  # (ecart, étiquette, exact, notre_gen)

    for partie in parties:
        fichiers = partie["fichiers"]
        etiq = fichiers[-1] if fichiers else "?"
        decisions = extraire_decisions_ia_toutes(partie["data"], partie["debut_present"])
        for d in decisions:
            if d.get("moment") == "inconnu":
                continue
            nb_decisions += 1
            res = solveur_exact.resoudre_exact(d["etat"], d["idx"])
            total_duree_exact += res.duree
            if not res.toutes_valides:
                tous_valides = False
            if not res.conservation_ok:
                toutes_conservations = False

            n_prod = _notre_nb(d["etat"], d["idx"], budget_production)
            n_gen = _notre_nb(d["etat"], d["idx"], budget_genereux)
            ref_prod = n_prod if n_prod is not None else 0
            ref_gen = n_gen if n_gen is not None else 0
            ecart_prod = res.nb_tuiles - ref_prod
            ecarts_prod.append(ecart_prod)
            if ecart_prod > 0:
                nb_exact_superieur_prod += 1
            if res.nb_tuiles - ref_gen > 0:
                nb_exact_superieur_gen += 1
                pires.append((res.nb_tuiles - ref_gen, f"{etiq} tour {d['tour']} ({d['nom']})",
                              res.nb_tuiles, ref_gen))

    print(f"  Décisions d'IA comparées : {nb_decisions}", file=flux)
    print(f"  Exact > notre solveur à {budget_production} s : {nb_exact_superieur_prod}",
          file=flux)
    print(f"  Exact > notre solveur à {budget_genereux} s (le solveur maison "
          f"dépassé même généreusement) : {nb_exact_superieur_gen}", file=flux)
    if ecarts_prod:
        print(f"  Écart (exact − notre solveur à {budget_production} s) : "
              f"moyen {sum(ecarts_prod) / len(ecarts_prod):.2f}, "
              f"maximal {max(ecarts_prod)}", file=flux)
    print(f"  Temps total du solveur exact : {total_duree_exact * 1000:.1f} ms", file=flux)
    print(f"  Combinaisons toutes valides : {tous_valides} — conservation : "
          f"{toutes_conservations}", file=flux)
    if pires:
        pires.sort(reverse=True)
        print("\n  Cas où le solveur exact dépasse notre solveur même à budget "
              "généreux (les plus précieux) :", file=flux)
        for ecart, etiq, exact, gen in pires[:15]:
            print(f"    +{ecart} : {etiq} — exact {exact}, notre solveur {gen}", file=flux)
    print(file=flux)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare le solveur d'Expert au solveur exact de la "
                    "bibliothèque rummikub-solver (issue #204).")
    parser.add_argument("--budget-production", type=float, default=1.5,
                        help="Budget de production de notre solveur (défaut 1,5 s).")
    parser.add_argument("--budget", type=float, default=10.0,
                        help="Budget généreux de notre solveur (défaut 10 s).")
    parser.add_argument("--journaux", action="store_true",
                        help="Compare aussi sur les décisions d'IA de vrais journaux "
                             "de parties (l'utilisateur fournit les journaux).")
    parser.add_argument("--tous", action="store_true",
                        help="(--journaux) Tous les journaux du dossier, pas seulement "
                             "le plus récent.")
    parser.add_argument("--dossier", default=None,
                        help="(--journaux) Dossier des journaux "
                             "(défaut : RACINE_DATA/logs_parties).")
    args = parser.parse_args(argv)

    if not solveur_exact.DISPONIBLE:
        print(solveur_exact.MESSAGE_INSTALLATION, file=sys.stderr)
        return 1

    if args.journaux:
        from rummikub.persistance.bilan import lister_journaux
        if args.dossier:
            dossier = Path(args.dossier)
        else:
            try:
                from rummikub import config
                dossier = config.RACINE_DATA / "logs_parties"
            except Exception:
                dossier = _RACINE / "data" / "logs_parties"
        tous = lister_journaux(dossier)
        if not tous:
            print(f"Aucun journal trouvé dans {dossier}.", file=sys.stderr)
            return 0
        chemins = tous if args.tous else [tous[-1]]
        return comparer_journaux(chemins, args.budget_production, args.budget)

    return comparer_cas(args.budget_production, args.budget)


if __name__ == "__main__":
    sys.exit(main())
