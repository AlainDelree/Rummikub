#!/usr/bin/env python3
"""Compare deux campagnes APPARIÉES de ``comparer_niveaux_ia.py --export-
resultats`` (issue #225, point 5bis) — typiquement une campagne Champion du
Monde AVEC « garder un joker en main » et une campagne identique (même
``--seed``, même ``--donnes``, mêmes niveaux) SANS (``--sans-garde-joker``).

Avec la même graine, les deux campagnes jouent EXACTEMENT les mêmes donnes
dans le même ordre : un match ne peut donc différer entre les deux fichiers
QUE si un coup a réellement changé en cours de route (la stratégie testée, ou
tout autre facteur non contrôlé — voir l'avertissement ci-dessous). C'est ce
qui rend la comparaison appariée BEAUCOUP plus sensible qu'un simple taux de
victoire global sur deux campagnes indépendantes (la plupart des 200+ parties
d'une campagne ne sont de toute façon jamais concernées par la stratégie,
voir CONTEXTE.md §13 — comparer les quelques parties qui ONT divergé est
beaucoup plus informatif que de comparer deux taux de victoire noyés dans le
bruit).

**Avertissement important** : deux campagnes à la même graine peuvent AUSSI
diverger pour une raison SANS AUCUN LIEN avec la stratégie testée — une
simple variation du budget de temps réellement consommé par le solveur exact
(charge de la machine au moment de l'exécution) peut faire basculer un coup
d'un tour entre deux exécutions, même identiques par ailleurs (voir
``moteur/solveur_exact.BudgetExactDepasse``). Une partie divergente n'est
donc pas la PREUVE que la stratégie a changé quelque chose : c'est un
candidat à inspecter (regarder son statut ``garde_joker``/``verif_finition``
dans le journal de la partie, si disponible) avant toute conclusion.

Usage :

    python scripts/comparer_niveaux_ia.py --niveau-a Expert \\
        --niveau-b "Champion du Monde" --donnes 300 --seed 7 \\
        --export-resultats /tmp/avec.jsonl
    python scripts/comparer_niveaux_ia.py --niveau-a Expert \\
        --niveau-b "Champion du Monde" --donnes 300 --seed 7 \\
        --sans-garde-joker --export-resultats /tmp/sans.jsonl
    python scripts/comparer_campagnes_appariees.py /tmp/avec.jsonl /tmp/sans.jsonl

Format d'un fichier (une ligne JSON par match, écrite par ``comparer_niveaux_
ia.comparer`` quand ``--export-resultats`` est fourni) :
    ``donne`` (numéro, 1-indexé), ``ordre`` (``["A", "B"]`` ou ``["B", "A"]``),
    ``niveau_a``/``niveau_b``, ``vainqueur_camp`` (``"A"``/``"B"``/``None`` si
    nul), ``arretee_garde_fou`` (bool), ``score_a``/``score_b``.
"""

import argparse
import json
import sys
from math import comb
from pathlib import Path


def charger_resultats(chemin) -> dict:
    """Lit un fichier JSON Lines écrit par ``--export-resultats`` et l'indexe
    par ``(donne, tuple(ordre))`` — la clé qui identifie un même match joué
    dans les deux campagnes (même graine, même ordre des places)."""
    records = {}
    with open(chemin, encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            rec = json.loads(ligne)
            cle = (rec["donne"], tuple(rec["ordre"]))
            records[cle] = rec
    return records


def test_des_signes(k: int, n: int) -> float | None:
    """P-value bilatérale du test des signes (hypothèse nulle : chaque sens
    est équiprobable, p=0.5) — sans dépendance externe (``scipy`` absent des
    dépendances du projet) : somme exacte des deux queues de la loi
    binomiale(n, 0.5). ``None`` si ``n == 0`` (rien à tester)."""
    if n == 0:
        return None
    k = min(k, n - k)
    p_une_queue = sum(comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * p_une_queue)


def comparer_fichiers(chemin_1, chemin_2) -> dict:
    """Compare deux fichiers de résultats appariés (issue #225, point 5bis).

    Pour chaque match présent dans LES DEUX fichiers (même ``donne``, même
    ``ordre``) et non arrêté par le garde-fou anti-blocage dans l'un ou
    l'autre : identique si le même camp (« A » ou « B », ou nul) gagne dans
    les deux fichiers ; sinon divergent, classé par SENS (le camp A gagne
    dans le fichier 1 mais pas dans le fichier 2, ou l'inverse) quand la
    divergence implique effectivement un gain/perte NETTE du camp A ; les
    divergences où le camp A ne gagne ni dans l'un ni dans l'autre (ex. camp
    B gagnant d'un côté, match nul de l'autre) sont comptées dans
    ``divergentes`` mais PAS dans le test des signes (direction ambiguë pour
    le camp A).

    Suppose que les deux fichiers viennent de la MÊME commande ``comparer_
    niveaux_ia.py`` (mêmes ``--niveau-a``/``--niveau-b``, donc le camp « A »
    désigne le même niveau dans les deux fichiers) — à l'exception du
    réglage testé (p. ex. ``--sans-garde-joker``). Ce n'est PAS vérifié ici :
    c'est à l'appelant de lancer les deux campagnes avec les mêmes arguments.

    Retourne un dict : ``n_commun``, ``absentes`` (clés présentes dans un
    seul des deux fichiers), ``non_comparables`` (garde-fou), ``identiques``,
    ``divergentes``, ``camp_a_gagne_fichier1_pas_fichier2``,
    ``camp_a_gagne_fichier2_pas_fichier1``, ``n_signe``, ``p_value_signe``."""
    r1 = charger_resultats(chemin_1)
    r2 = charger_resultats(chemin_2)
    cles_communes = sorted(set(r1) & set(r2))
    absentes = (set(r1) | set(r2)) - (set(r1) & set(r2))

    identiques = 0
    divergentes = 0
    non_comparables = 0
    a_gagne_1_pas_2 = 0
    a_gagne_2_pas_1 = 0

    for cle in cles_communes:
        rec1, rec2 = r1[cle], r2[cle]
        if rec1.get("arretee_garde_fou") or rec2.get("arretee_garde_fou"):
            non_comparables += 1
            continue
        v1, v2 = rec1.get("vainqueur_camp"), rec2.get("vainqueur_camp")
        if v1 == v2:
            identiques += 1
            continue
        divergentes += 1
        a_gagne_1 = (v1 == "A")
        a_gagne_2 = (v2 == "A")
        if a_gagne_1 and not a_gagne_2:
            a_gagne_1_pas_2 += 1
        elif a_gagne_2 and not a_gagne_1:
            a_gagne_2_pas_1 += 1

    n_signe = a_gagne_1_pas_2 + a_gagne_2_pas_1
    p_value = test_des_signes(a_gagne_1_pas_2, n_signe)

    return {
        "n_commun": len(cles_communes),
        "absentes": len(absentes),
        "non_comparables": non_comparables,
        "identiques": identiques,
        "divergentes": divergentes,
        "camp_a_gagne_fichier1_pas_fichier2": a_gagne_1_pas_2,
        "camp_a_gagne_fichier2_pas_fichier1": a_gagne_2_pas_1,
        "n_signe": n_signe,
        "p_value_signe": p_value,
    }


def _niveau_camp_a(chemin) -> str | None:
    """Premier ``niveau_a`` trouvé dans le fichier, pour affichage (quel
    niveau le camp « A » désigne) — ``None`` si le fichier est vide."""
    with open(chemin, encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if ligne:
                return json.loads(ligne).get("niveau_a")
    return None


def afficher_rapport(resume: dict, chemin_1, chemin_2) -> None:
    print("=" * 70)
    print(f"COMPARAISON APPARIÉE : {chemin_1} (fichier 1) vs {chemin_2} "
         f"(fichier 2)")
    niveau_a = _niveau_camp_a(chemin_1)
    if niveau_a:
        print(f"Camp « A » = {niveau_a} (dans les deux fichiers, en "
             f"principe — vérifier que les deux campagnes partagent bien "
             f"--niveau-a/--niveau-b).")
    print("-" * 70)
    print(f"Matchs communs aux deux fichiers : {resume['n_commun']}")
    if resume["absentes"]:
        print(f"  *** {resume['absentes']} match(s) présent(s) dans UN SEUL "
             f"des deux fichiers (--donnes ou --seed différents ?) : ignoré(s). ***")
    if resume["non_comparables"]:
        print(f"Non comparables (arrêtés par le garde-fou anti-blocage dans "
             f"l'un des deux fichiers) : {resume['non_comparables']}")
    print(f"Parties IDENTIQUES (même vainqueur dans les deux fichiers) : "
         f"{resume['identiques']}")
    print(f"Parties DIVERGENTES (vainqueur différent) : {resume['divergentes']}")
    print(f"  — dont camp A gagne dans le fichier 1 mais pas dans le fichier "
         f"2 : {resume['camp_a_gagne_fichier1_pas_fichier2']}")
    print(f"  — dont camp A gagne dans le fichier 2 mais pas dans le fichier "
         f"1 : {resume['camp_a_gagne_fichier2_pas_fichier1']}")
    if resume["n_signe"]:
        p = resume["p_value_signe"]
        print(f"Test des signes sur ces {resume['n_signe']} partie(s) "
             f"divergente(s) à direction nette (H0 : chaque sens "
             f"équiprobable) : p = {p:.4f} "
             f"({'significatif' if p < 0.05 else 'NON significatif'} au "
             f"seuil 5 %).")
    else:
        print("Aucune partie divergente à direction nette pour le camp A : "
             "test des signes non applicable.")
    print("-" * 70)
    print("ATTENTION : une partie divergente n'est pas la PREUVE que la "
         "stratégie testée a changé quelque chose — une simple variation du "
         "budget de temps réellement consommé par le solveur exact (charge "
         "de la machine) peut aussi faire basculer un coup entre deux "
         "exécutions par ailleurs identiques. Inspecter le journal de la "
         "partie avant toute conclusion.")
    print("=" * 70)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Compare deux campagnes appariées (même graine) de "
                    "comparer_niveaux_ia.py --export-resultats (issue #225, "
                    "point 5bis).")
    parser.add_argument("fichier_1", help="Résultats de la première campagne "
                        "(p. ex. AVEC la stratégie).")
    parser.add_argument("fichier_2", help="Résultats de la seconde campagne, "
                        "même graine (p. ex. SANS la stratégie).")
    args = parser.parse_args(argv[1:])

    for chemin in (args.fichier_1, args.fichier_2):
        if not Path(chemin).is_file():
            parser.error(f"fichier introuvable : {chemin}")

    resume = comparer_fichiers(args.fichier_1, args.fichier_2)
    afficher_rapport(resume, args.fichier_1, args.fichier_2)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
