#!/usr/bin/env python3
"""Analyse des « coups ratés » de l'IA — et, en option, d'un joueur humain —
à partir des journaux de parties (issue #193, suite de #188).

Pour chaque décision (pose, pioche ou passe) d'un joueur, reconstitue
l'état exact (chevalets, plateau) qu'il affrontait — enregistré dans le
journal juste avant cette décision — et interroge le solveur d'Expert
(``moteur/solveur.py``) sur cet état avec un budget de temps GÉNÉREUX
(10 s par défaut). Trois catégories de décision sous-optimale :

  - pioche/passe alors qu'un coup existait (« coup raté », comme #188) ;
  - pose d'un nombre de tuiles inférieur au maximum trouvé par le solveur
    (« pose sous-optimale », nouveau) ;
  - (joueur humain uniquement) pose d'un nombre de tuiles SUPÉRIEUR à ce que
    le solveur trouve même avec le budget généreux (« le solveur est battu »
    — les cas les plus précieux pour l'améliorer).

Logique de détection et de résumé : voir ``persistance/coups_rates.py`` (pur,
testé indépendamment). Ce script est en ligne de commande, moteur Python
seul (aucun import pywebview — voir CONTEXTE.md §7).

ATTENTION — à lire avant d'interpréter le résultat :
  1. Le solveur gèle certaines combinaisons déjà posées sur le plateau pour
     limiter la combinatoire (voir la docstring de ``moteur/solveur.py``).
     Un coup non trouvé ne prouve donc PAS qu'aucun coup n'existe : les
     coups ratés détectés ci-dessous sont une BORNE BASSE, jamais une liste
     exhaustive.
  2. Un budget de temps TROP COURT fait manquer des coups ratés qui
     demandent plus de réflexion : ils sont alors comptés comme
     « inconclusifs », PAS comme « aucun coup raté » — ne jamais lire un
     chiffre bas comme une preuve que le niveau joue bien avec un budget
     court (voir ``--budget`` ci-dessous).
  3. Ne JAMAIS conclure d'un petit échantillon de parties à une vérité
     stratégique générale sur le style d'un joueur (option ``--joueur``).

Usage :

    python scripts/analyser_coups_rates.py
    python scripts/analyser_coups_rates.py chemin/vers/partie_xxx.json
    python scripts/analyser_coups_rates.py --tous
    python scripts/analyser_coups_rates.py --tous --dossier chemin/vers/logs_parties
    python scripts/analyser_coups_rates.py --budget 20 --budget-production 1.5
    python scripts/analyser_coups_rates.py --tous --budget-mesure
    python scripts/analyser_coups_rates.py --tous --retenter-inconclusifs
    python scripts/analyser_coups_rates.py --tous --enregistrer-cas-reference
    python scripts/analyser_coups_rates.py --tous --joueur "Alain"
    python scripts/analyser_coups_rates.py --tous --depuis 20261001

    # Régénérer les cas de référence humains (tests/donnees/cas_expert_humain_*.json)
    # avec le bon attendu_min_tuiles, après la correction du comptage de #201 :
    python scripts/analyser_coups_rates.py --tous --joueur "Alain" \
        --enregistrer-cas-reference --ecraser

Cette analyse ne modifie jamais l'IA ni le moteur : elle se limite à relire
des journaux déjà écrits et à interroger le solveur en lecture pure.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

_RACINE = Path(__file__).resolve().parent.parent
_SRC = _RACINE / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from rummikub.moteur.ia import BUDGET_TEMPS_EXPERT  # noqa: E402
from rummikub.persistance.bilan import charger_journal, lister_journaux  # noqa: E402
from rummikub.persistance.coups_rates import (  # noqa: E402
    BUDGETS_SERIE_DEFAUT,
    analyser_decision_complete, budget_necessaire, calculer_resume_complet,
    detecter_reserves_joueur, extraire_decisions_ia_toutes,
    extraire_decisions_joueur, filtrer_journaux_depuis,
    repartition_budget_necessaire, resume_joueur_humain,
    top_coups_rates_complet, repartition_solveurs, LIBELLES_SOLVEUR,
)

LIBELLE_MOMENT = {"avant_mise": "avant la mise initiale",
                   "apres_mise": "après la mise initiale"}

BUDGET_INCONCLUSIFS_DEFAUT = 30.0
LIMITE_TEMPS_INCONCLUSIFS_DEFAUT = 300.0  # 5 min, ferme, pour toute la passe.

AVERTISSEMENT = (
    "ATTENTION :\n"
    "1. Le solveur Expert gèle certaines combinaisons déjà posées sur le\n"
    "   plateau pour limiter la combinatoire (voir moteur/solveur.py) — un coup\n"
    "   non trouvé ne prouve pas qu'aucun coup n'existe. Les coups ratés/poses\n"
    "   sous-optimales détectés ci-dessus sont une BORNE BASSE, pas une liste\n"
    "   exhaustive.\n"
    "2. Les décisions « inconclusives » (budget généreux épuisé sans rien\n"
    "   trouver) ne sont PAS des coups non ratés : le nombre réel de coups\n"
    "   ratés est incertain dans la fourchette [coups_rates ; coups_rates +\n"
    "   inconclusifs]. Ne jamais lire une baisse du compteur de coups ratés\n"
    "   obtenue avec un budget plus court comme un signe d'amélioration.\n"
    "3. (--joueur) Ne tirer aucune conclusion stratégique d'un échantillon de\n"
    "   quelques parties : ces chiffres restent descriptifs."
)


def _juge_maison_exact(etat, idx, budget_temps=None):
    """Juge par défaut (#213) : modèle exact de la MAISON
    (``moteur/solveur_exact.py``). Même signature de callable que le juge
    externe de #204 ``(etat, idx, budget_temps=...) -> coup|None``. Renvoie
    ``None`` (plutôt que lever) si le modèle échoue à conclure, pour que
    l'analyse se poursuive sans erreur."""
    from rummikub.moteur import solveur_exact as _mex
    try:
        return _mex.resoudre_coup_exact(
            etat, idx, budget_temps=budget_temps if budget_temps else 10.0)
    except (_mex.BudgetExactDepasse, _mex.SolveurExactIndisponible):
        return None


def _dossier_defaut() -> Path:
    try:
        from rummikub import config
        return config.RACINE_DATA / "logs_parties"
    except Exception:
        return _RACINE / "data" / "logs_parties"


def _dossier_donnees_test() -> Path:
    return _RACINE / "tests" / "donnees"


def _ordre_niveaux() -> list:
    try:
        from rummikub import config
        return list(config.NIVEAUX)
    except Exception:
        return []


def _fmt_pct(valeur) -> str:
    return "—" if valeur is None else f"{valeur * 100:.0f} %"


def _fmt(valeur, suffixe="") -> str:
    return "—" if valeur is None else f"{valeur:.2f}{suffixe}"


# --------------------------------------------------------------------------- #
# Description en français + complexité du coup proposé (issue #196).
# --------------------------------------------------------------------------- #

def afficher_description_coup(description, titre: str, flux=sys.stdout, indent="      ") -> None:
    """Affiche le texte français, les étapes et la complexité d'une
    description produite par ``persistance/coups_rates.decrire_coup``
    (``None`` si le solveur n'a proposé aucun plateau — affiché tel quel,
    jamais confondu avec « aucun coup raté », voir avertissement)."""
    if description is None:
        print(f"{indent}{titre} : aucun coup proposé par le solveur.", file=flux)
        return
    print(f"{indent}{titre} :", file=flux)
    print(f"{indent}  {description['texte']}", file=flux)
    c = description["complexite"]
    joker = "avec échange de joker" if c["a_joker"] else "sans joker"
    print(f"{indent}  Complexité : {c['nb_combinaisons_touchees']} combinaison(s) "
          f"touchée(s), {joker}, {c['nb_etapes']} étape(s) -> taille {c['taille']} "
          f"(petit 1-2, moyen 3-5, grand 6+) ; {c['categorie']}  [mesure #196, conservée]",
          file=flux)
    if description["etapes"]:
        print(f"{indent}  Étapes :", file=flux)
        for n, etape in enumerate(description["etapes"], start=1):
            prefixe = f"[{etape['titre']}] " if etape["titre"] else ""
            print(f"{indent}    {n}. {prefixe}{etape['texte']}", file=flux)


# --------------------------------------------------------------------------- #
# Mode IA (défaut) : poses + pioches/passes, par niveau et par phase.
# --------------------------------------------------------------------------- #

def _charger_parties(chemins):
    """Charge les journaux de ``chemins`` et regroupe les fichiers d'une même
    partie reprise en une seule suite d'actions (issue #202, voir
    ``persistance/parties_liees.py``). Retourne la liste des parties fusionnées
    (dicts de ``fusionner_groupe`` : ``data``, ``debut_present``, ``fichiers``,
    ``partie_id``) ; les journaux illisibles sont signalés et ignorés."""
    from rummikub.persistance.parties_liees import fusionner_journaux
    journaux = []
    for chemin in chemins:
        data = charger_journal(chemin)
        if data is None:
            print(f"Journal illisible ou invalide, ignoré : {chemin}", file=sys.stderr)
            continue
        journaux.append({"nom": chemin.name, "data": data})
    return fusionner_journaux(journaux)


def _etiquette_partie(partie) -> str:
    """Nom représentatif d'une partie fusionnée pour l'affichage/les cas de
    référence : le fichier le plus récent (où vivent les décisions de fin de
    partie)."""
    fichiers = partie["fichiers"]
    return fichiers[-1] if fichiers else "?"


def _decisions_ia_par_cle(chemins):
    """``{(etiquette_partie, tour, nom): decision}`` pour toutes les IA, sur
    les parties fusionnées — même clé que ``resultat["fichier"]`` produit par
    :func:`_analyser_tous_journaux_ia` (nécessaire à --retenter-inconclusifs,
    --budget-mesure et --enregistrer-cas-reference après le regroupement des
    fichiers d'une partie reprise, issue #202)."""
    par_cle = {}
    for partie in _charger_parties(chemins):
        etiq = _etiquette_partie(partie)
        for d in extraire_decisions_ia_toutes(partie["data"], partie["debut_present"]):
            par_cle[(etiq, d["tour"], d["nom"])] = d
    return par_cle


def _analyser_tous_journaux_ia(chemins, budget_genereux=10.0,
                               budget_production=BUDGET_TEMPS_EXPERT, solveur=None):
    """Retourne la liste des résultats (avec ``fichier`` ajouté sur chaque
    entrée) sur toutes les parties, IA uniquement — les fichiers d'une même
    partie reprise sont reliés et analysés d'un seul tenant (issue #202).
    ``solveur`` (issue #204, ``--juge-exact``) : voir
    ``persistance/coups_rates.analyser_decision_complete``."""
    tous = []
    for partie in _charger_parties(chemins):
        fichiers = partie["fichiers"]
        etiq = _etiquette_partie(partie)
        if len(fichiers) > 1:
            print(f"Analyse de la partie {etiq} (reprise répartie sur "
                  f"{len(fichiers)} fichiers : {', '.join(fichiers)})...", file=sys.stderr)
        else:
            print(f"Analyse de {etiq}...", file=sys.stderr)
        if not partie["debut_present"]:
            print("  (début de partie manquant : les décisions dont la mise "
                  "initiale est indéterminable sont exclues et comptées à part)",
                  file=sys.stderr)
        decisions = extraire_decisions_ia_toutes(partie["data"], partie["debut_present"])
        for decision in decisions:
            resultat = analyser_decision_complete(
                decision, budget_genereux=budget_genereux,
                budget_production=budget_production, solveur=solveur)
            resultat["fichier"] = etiq
            marque = ""
            if resultat.get("mise_initiale_inconnue"):
                marque = " <- mise initiale inconnue (exclu)"
            elif resultat["coup_rate"]:
                marque = " <- coup raté"
            elif resultat["pose_sous_optimale"]:
                marque = f" <- pose sous-optimale ({resultat['nb_tuiles_manquantes']} manquante(s))"
            elif resultat["inconclusif"]:
                marque = " <- inconclusif"
            print(f"  tour {resultat['tour']} ({resultat['nom']}, {resultat['niveau']}, "
                  f"{resultat['action']}){marque}", file=sys.stderr)
            tous.append(resultat)
    return tous


def afficher_repartition_solveurs(chemins, flux=sys.stdout) -> None:
    """Répartition du mécanisme décideur des coups d'Expert (#211, 5bis) :
    modèle exact / recherche de repli / Avancé en repli / non noté. Permet de
    savoir, en lisant un journal, si Expert a joué avec le modèle exact ou s'est
    replié silencieusement (``highspy``/``numpy`` absents)."""
    repart = repartition_solveurs(_charger_parties(chemins))
    total = sum(repart.values())
    if not total:
        return
    print("=== Mécanisme décideur des coups d'Expert (#211) ===", file=flux)
    for code in ("exact", "recherche", "avance", None):
        n = repart.get(code, 0)
        if not n:
            continue
        pct = 100.0 * n / total
        print(f"  {LIBELLES_SOLVEUR[code]:20s} : {n} coup(s) ({pct:.1f} %)",
              file=flux)
    if repart.get("recherche") or repart.get("avance"):
        print("  (des coups en repli sont présents : à exclure/signaler dans "
              "une analyse qui suppose le modèle exact.)", file=flux)
    print(file=flux)


def afficher_resume_complet(resume: dict, flux=sys.stdout) -> None:
    if not resume:
        print("Aucune décision d'une IA trouvée pour ce filtre.", file=flux)
        return
    ordre = _ordre_niveaux()
    niveaux = sorted(resume, key=lambda n: (ordre.index(n) if n in ordre
                                            else len(ordre), n or ""))
    for niveau in niveaux:
        print(f"=== {niveau} ===", file=flux)
        for moment in ("avant_mise", "apres_mise"):
            s = resume[niveau].get(moment)
            if not s:
                continue
            print(f"  {LIBELLE_MOMENT[moment]} :", file=flux)
            print(f"    Décisions analysées (pose/pioche/passe) : {s['decisions']}", file=flux)
            print(f"    Pioche/passe alors qu'un coup existait  : {s['pioche_passe_ratees']}",
                  file=flux)
            print(f"    Poses sous-optimales                    : {s['poses_sous_optimales']} "
                  f"({s['tuiles_manquantes_poses']} tuile(s) manquante(s) au total)", file=flux)
            if niveau == "Expert" and s["budget_limite"]:
                print(f"    ... dont limitées par le budget de production (1,5 s) : "
                      f"{s['budget_limite']}", file=flux)
            if s["inconclusifs"]:
                print(f"    Décisions inconclusives (budget généreux épuisé)  : "
                      f"{s['inconclusifs']}", file=flux)
            nb_classes = s["coups_simples"] + s["coups_complexes"]
            if nb_classes:
                print(f"    ... dont coups simples (<= 2 combinaisons, sans joker) : "
                      f"{s['coups_simples']}, complexes (3+ combinaisons ou joker) : "
                      f"{s['coups_complexes']}  [mesure #196, conservée]", file=flux)
                print(f"    ... dont par taille (#198) : petits (1-2) {s['coups_petits']}, "
                      f"moyens (3-5) {s['coups_moyens']}, grands (6+) {s['coups_grands']} ; "
                      f"avec joker {s['coups_avec_joker']}, sans joker {s['coups_sans_joker']}",
                      file=flux)
        inc = resume[niveau].get("inconnu")
        if inc:
            print(f"  Décisions dont l'état de mise initiale est inconnu (historique "
                  f"de début manquant, exclues du calcul) : {inc['decisions']}", file=flux)
        print(file=flux)


def afficher_tableau_tailles(resume: dict, flux=sys.stdout) -> None:
    """Tableau récapitulatif, toutes phases (avant/après mise) confondues :
    répartition par taille et par présence de joker, pour chaque niveau
    d'IA (point 1 de l'issue #198) — pour juger d'un coup d'œil si les
    coups ratés/poses sous-optimales sont à la portée d'un humain."""
    ordre = _ordre_niveaux()
    niveaux = sorted(resume, key=lambda n: (ordre.index(n) if n in ordre
                                            else len(ordre), n or ""))
    lignes = []
    for niveau in niveaux:
        total = {"coups_petits": 0, "coups_moyens": 0, "coups_grands": 0,
                 "coups_avec_joker": 0, "coups_sans_joker": 0}
        for moment in ("avant_mise", "apres_mise"):
            s = resume[niveau].get(moment)
            if not s:
                continue
            for cle in total:
                total[cle] += s[cle]
        if sum(total.values()):
            lignes.append((niveau, total))
    if not lignes:
        return
    print("=== Répartition des coups ratés/poses sous-optimales par taille (point 1, "
          "issue #198) ===", file=flux)
    print(f"{'Niveau':<14} {'Petit':>6} {'Moyen':>6} {'Grand':>6} {'Joker':>6} "
          f"{'Sans joker':>11}", file=flux)
    for niveau, t in lignes:
        print(f"{(niveau or '?'):<14} {t['coups_petits']:>6} {t['coups_moyens']:>6} "
              f"{t['coups_grands']:>6} {t['coups_avec_joker']:>6} "
              f"{t['coups_sans_joker']:>11}", file=flux)
    print(file=flux)


def afficher_top_complet(resultats: list, n: int, flux=sys.stdout) -> None:
    top = top_coups_rates_complet(resultats, n=n)
    if not top:
        return
    print(f"=== {len(top)} coup(s) raté(s)/pose(s) sous-optimale(s) le(s) plus "
          f"important(s) ===", file=flux)
    for r in top:
        categorie = "coup raté" if r["coup_rate"] else "pose sous-optimale"
        detail = (f"{r.get('fichier', '?')}, tour {r['tour']} — {r['nom']} ({r['niveau']}, "
                  f"{r['action']}) : {categorie}, {r['nb_tuiles_manquantes']} tuile(s) ratée(s)")
        if r["moment"] == "avant_mise" and r["points_ouverture"] is not None:
            detail += f", ouverture à {r['points_ouverture']} points"
        print(f"  - {detail}", file=flux)
        afficher_description_coup(r.get("description_solveur"),
                                  "Coup proposé par le solveur", flux=flux)
    print(file=flux)


# --------------------------------------------------------------------------- #
# Cas inconclusifs : seconde passe à budget plus grand (point 6 bis).
# --------------------------------------------------------------------------- #

def _retenter_inconclusifs(resultats, decisions_par_cle, budget_inconclusifs,
                           limite_temps_totale):
    """Pour chaque décision restée inconclusive, retente le solveur avec un
    budget plus grand (``--budget-inconclusifs``), sous une limite de durée
    TOTALE ferme pour toute la passe (``--limite-temps-inconclusifs``) — on
    arrête dès qu'elle est dépassée, même si des décisions restent à
    retenter (signalé). Met à jour les résultats EN PLACE."""
    limite = time.monotonic() + limite_temps_totale
    a_retenter = [r for r in resultats if r["inconclusif"]]
    if not a_retenter:
        return 0, 0
    print(f"\nNouvelle tentative sur {len(a_retenter)} décision(s) inconclusive(s) "
          f"(budget {budget_inconclusifs} s, limite totale {limite_temps_totale} s)...",
          file=sys.stderr)
    tranchees = arretees_par_limite = 0
    for r in a_retenter:
        if time.monotonic() > limite:
            arretees_par_limite += 1
            continue
        decision = decisions_par_cle.get((r["fichier"], r["tour"], r["nom"]))
        if decision is None:
            continue
        nouveau = analyser_decision_complete(decision, budget_genereux=budget_inconclusifs,
                                             budget_production=r.get("budget_production", 1.5))
        nouveau["fichier"] = r["fichier"]
        r.clear()
        r.update(nouveau)
        if not nouveau["inconclusif"]:
            tranchees += 1
    if arretees_par_limite:
        print(f"ATTENTION : limite de durée totale atteinte, "
              f"{arretees_par_limite} décision(s) non retentée(s).", file=sys.stderr)
    return tranchees, arretees_par_limite


# --------------------------------------------------------------------------- #
# Option de consultation d'un tour précis (point 2 de l'issue #196).
# --------------------------------------------------------------------------- #

def _detailer_tour(chemins, tour: int, budget_genereux: float, budget_production: float,
                   nom_joueur=None, solveur=None):
    """Cherche, dans ``chemins``, les décisions (IA, ou du joueur
    ``nom_joueur`` si fourni) au tour ``tour`` et les analyse une par une,
    indépendamment du reste du script — ``--fichier F --tour N`` (point 2 de
    l'issue #196). Retourne une liste de ``(nom_fichier, decision, resultat)``
    (généralement 0 ou 1 décision par fichier, un tour donné appartenant à un
    seul joueur)."""
    trouvees = []
    for partie in _charger_parties(chemins):
        etiq = _etiquette_partie(partie)
        if nom_joueur:
            decisions = extraire_decisions_joueur(partie["data"], nom_joueur,
                                                  partie["debut_present"])
        else:
            decisions = extraire_decisions_ia_toutes(partie["data"],
                                                     partie["debut_present"])
        for d in decisions:
            if d["tour"] != tour:
                continue
            resultat = analyser_decision_complete(
                d, budget_genereux=budget_genereux, budget_production=budget_production,
                solveur=solveur)
            trouvees.append((etiq, d, resultat))
    return trouvees


def afficher_detail_tour(trouvees: list, tour: int, flux=sys.stdout) -> None:
    print(f"=== Détail du tour {tour} ===", file=flux)
    if not trouvees:
        print("  Aucune décision trouvée à ce tour.", file=flux)
        print(file=flux)
        return
    for fichier, d, r in trouvees:
        print(f"  {fichier} — {r['nom']}" + (f" ({r['niveau']})" if r["niveau"] else "") +
              f", action : {r['action']}", file=flux)
        print(f"    Tuiles posées en réalité : {r['nb_tuiles_reel']}  —  "
              f"tuiles proposées par le solveur : {r['nb_tuiles_solveur']}", file=flux)
        if r["inconclusif"]:
            print("    Inconclusif : le budget généreux s'est épuisé sans qu'aucune "
                  "branche n'ait abouti (voir --budget).", file=flux)
        else:
            print(f"    coup_rate={r['coup_rate']}  pose_sous_optimale="
                  f"{r['pose_sous_optimale']}  joueur_bat_solveur={r['joueur_bat_solveur']}",
                  file=flux)
        afficher_description_coup(r.get("description_solveur"),
                                  "Coup proposé par le solveur", flux=flux)
        if r.get("description_reel"):
            afficher_description_coup(r.get("description_reel"),
                                      "Coup réellement joué", flux=flux)
        print(file=flux)


# --------------------------------------------------------------------------- #
# Enregistrement de nouveaux cas de référence (point 6 bis / 6 ter).
# --------------------------------------------------------------------------- #

def _nom_fichier_cas(prefixe: str, fichier: str, tour) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "", Path(fichier).stem)[-12:]
    return f"cas_expert_{prefixe}_{base}_tour{tour}.json"


def _enregistrer_cas_reference(decision: dict, attendu_min_tuiles: int, prefixe: str,
                               dossier: Path, ecraser: bool = False) -> Path:
    """Enregistre ``decision`` au même format que ``tests/donnees/
    cas_expert_*.json`` (clé ``attendu_min_tuiles``), SANS écraser un fichier
    existant PAR DÉFAUT (point 6 bis de l'issue #193) — ``ecraser=True``
    (``--ecraser`` du script, issue #201) lève ce garde-fou, nécessaire pour
    RÉGÉNÉRER un cas ``cas_expert_humain_*.json`` existant avec le bon
    ``attendu_min_tuiles`` après la correction du comptage de #201 (ces
    fichiers, enregistrés avant #201, portent l'ancien nombre gonflé — voir
    la docstring de ``persistance/coups_rates.py``, section #201). Retourne
    le chemin écrit, ou ``None`` si un fichier de ce nom existait déjà et
    ``ecraser`` est resté à ``False``."""
    nom = _nom_fichier_cas(prefixe, decision["fichier"], decision["tour"])
    chemin = dossier / nom
    if chemin.exists() and not ecraser:
        return None
    data = {"idx": decision["idx"], "etat": decision["etat"],
            "attendu_min_tuiles": attendu_min_tuiles}
    chemin.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return chemin


# --------------------------------------------------------------------------- #
# Mode joueur humain (point 6 ter).
# --------------------------------------------------------------------------- #

def _analyser_joueur(chemins, nom_joueur, budget_genereux, budget_production,
                     verifier_reserve_pioche, solveur=None):
    """Analyse ``nom_joueur`` partie par partie (les fichiers d'une partie
    reprise sont reliés d'abord, issue #202 : la détection de réserve compare
    deux tours CONSÉCUTIFS du même joueur dans la MÊME partie — y compris à
    travers la reprise — jamais à travers deux parties différentes)."""
    agrege = {"nb_tours_analyses": 0, "coups_peut_etre_rates": [],
              "solveur_bat": [], "reserves_reussies": [], "reserves_perdues": [],
              "poses": 0, "poses_max": 0, "total_reel": 0, "total_solveur": 0,
              "pioches": 0, "pioches_coup_possible": 0,
              "jokers_joues": 0, "jokers_attente_total": 0,
              "complexite_simples": 0, "complexite_complexes": 0,
              "complexite_petits": 0, "complexite_moyens": 0, "complexite_grands": 0,
              "complexite_avec_joker": 0, "complexite_sans_joker": 0}

    for partie in _charger_parties(chemins):
        etiq = _etiquette_partie(partie)
        decisions = extraire_decisions_joueur(partie["data"], nom_joueur,
                                              partie["debut_present"])
        if not decisions:
            continue
        print(f"Analyse de {etiq} ({len(decisions)} décision(s) de "
              f"{nom_joueur})...", file=sys.stderr)
        resultats = [analyser_decision_complete(d, budget_genereux=budget_genereux,
                                                budget_production=budget_production,
                                                solveur=solveur)
                    for d in decisions]
        reserves = detecter_reserves_joueur(
            decisions, resultats, verifier_a_evite_pioche=verifier_reserve_pioche)
        resume = resume_joueur_humain(decisions, resultats, reserves)

        for liste_cle in ("coups_peut_etre_rates", "solveur_bat",
                          "reserves_reussies", "reserves_perdues"):
            for entree in resume[liste_cle]:
                agrege[liste_cle].append(dict(entree, fichier=etiq))
        agrege["nb_tours_analyses"] += resume["nb_tours_analyses"]
        agrege["complexite_simples"] += resume["complexite"]["simples"]
        agrege["complexite_complexes"] += resume["complexite"]["complexes"]
        agrege["complexite_petits"] += resume["complexite"]["petits"]
        agrege["complexite_moyens"] += resume["complexite"]["moyens"]
        agrege["complexite_grands"] += resume["complexite"]["grands"]
        agrege["complexite_avec_joker"] += resume["complexite"]["avec_joker"]
        agrege["complexite_sans_joker"] += resume["complexite"]["sans_joker"]
        style = resume["style"]
        if style["nb_poses"]:
            agrege["poses"] += style["nb_poses"]
            agrege["poses_max"] += round(style["part_poses_au_max"] * style["nb_poses"])
            agrege["total_reel"] += style["moyenne_tuiles_posees"] * style["nb_poses"]
            agrege["total_solveur"] += style["moyenne_tuiles_max_solveur"] * style["nb_poses"]
        if style["nb_pioches"]:
            agrege["pioches"] += style["nb_pioches"]
            agrege["pioches_coup_possible"] += round(
                style["part_pioches_coup_possible"] * style["nb_pioches"])
        if style["nb_jokers_joues"]:
            agrege["jokers_joues"] += style["nb_jokers_joues"]
            agrege["jokers_attente_total"] += (
                style["jokers_tours_attente_moyenne"] * style["nb_jokers_joues"])

        # Pour --enregistrer-cas-reference : il faut pouvoir retrouver la
        # décision d'origine (état complet) d'une entrée de solveur_bat.
        for i, d in enumerate(decisions):
            if i in reserves["indices_a_exclure"]:
                continue
            r = resultats[i]
            if r["joueur_bat_solveur"]:
                d["fichier"] = etiq
                agrege.setdefault("_decisions_solveur_bat", []).append((d, r))

    return agrege


def afficher_resume_joueur(nom_joueur: str, agrege: dict, flux=sys.stdout) -> None:
    print(f"=== Joueur humain : {nom_joueur} ===", file=flux)
    print(f"  Tours analysés (hors inconclusifs) : {agrege['nb_tours_analyses']}", file=flux)
    print(file=flux)

    print(f"  (a) Coups peut-être ratés (pose partielle ou pioche/passe alors "
          f"qu'un coup existait, hors réserves) : {len(agrege['coups_peut_etre_rates'])}",
          file=flux)
    for e in agrege["coups_peut_etre_rates"][:10]:
        print(f"    - {e['fichier']}, tour {e['tour']} ({e['action']}) : "
              f"{e['nb_tuiles_manquantes']} tuile(s) manquante(s) (posé "
              f"{e['nb_tuiles_reel']}, solveur {e['nb_tuiles_solveur']}) — à vérifier à la main",
              file=flux)
        afficher_description_coup(e.get("description_solveur"),
                                  "Coup proposé par le solveur", flux=flux)
    print(file=flux)

    print(f"  (b) Le solveur est BATTU (le joueur pose plus que le solveur, "
          f"même au budget généreux) : {len(agrege['solveur_bat'])} — les cas les "
          f"plus précieux pour améliorer le solveur", file=flux)
    for e in agrege["solveur_bat"][:10]:
        print(f"    - {e['fichier']}, tour {e['tour']} : +{e['nb_tuiles_excedentaires']} "
              f"tuile(s) de plus que le solveur (posé {e['nb_tuiles_reel']}, "
              f"solveur {e['nb_tuiles_solveur']})", file=flux)
        afficher_description_coup(e.get("description_solveur"),
                                  "Coup proposé par le solveur", flux=flux)
        afficher_description_coup(e.get("description_reel"),
                                  "Coup réellement joué", flux=flux)
    print(file=flux)

    simples, complexes = agrege["complexite_simples"], agrege["complexite_complexes"]
    if simples + complexes:
        print(f"  Complexité des coups (a) ci-dessus : {simples} simple(s) "
              f"(<= 2 combinaisons, sans joker), {complexes} complexe(s) "
              f"(3+ combinaisons ou joker)  [mesure #196, conservée]", file=flux)
        print(f"  Répartition par taille (point 1, issue #198) — dit si ces coups "
              f"sont à la portée d'un humain :", file=flux)
        print(f"    {'Petit':>6} {'Moyen':>6} {'Grand':>6} {'Joker':>6} {'Sans joker':>11}",
              file=flux)
        print(f"    {agrege['complexite_petits']:>6} {agrege['complexite_moyens']:>6} "
              f"{agrege['complexite_grands']:>6} {agrege['complexite_avec_joker']:>6} "
              f"{agrege['complexite_sans_joker']:>11}", file=flux)
        print(file=flux)

    print(f"  Technique de la « réserve » (jamais comptée ci-dessus) :", file=flux)
    print(f"    Réussies : {len(agrege['reserves_reussies'])}  —  "
          f"Perdues : {len(agrege['reserves_perdues'])}", file=flux)
    print(file=flux)

    poses, pioches = agrege["poses"], agrege["pioches"]
    jokers = agrege["jokers_joues"]
    print("  Statistiques de style (descriptives uniquement, voir avertissement) :", file=flux)
    print(f"    Poses au maximum du solveur : "
          f"{_fmt_pct(agrege['poses_max'] / poses if poses else None)} ({poses} pose(s))",
          file=flux)
    print(f"    Tuiles posées / tour (vs max solveur) : "
          f"{_fmt(agrege['total_reel'] / poses if poses else None)} / "
          f"{_fmt(agrege['total_solveur'] / poses if poses else None)}", file=flux)
    print(f"    Pioches alors qu'un coup existait : "
          f"{_fmt_pct(agrege['pioches_coup_possible'] / pioches if pioches else None)} "
          f"({pioches} pioche(s))", file=flux)
    print(f"    Jokers joués : {jokers}, tours d'attente moyens avant d'être joués : "
          f"{_fmt(agrege['jokers_attente_total'] / jokers if jokers else None)}", file=flux)
    print(file=flux)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyse des coups ratés, poses sous-optimales et budget "
                     "nécessaire d'une IA (ou d'un joueur humain) à partir des "
                     "journaux de parties (issue #193, suite de #188).")
    parser.add_argument("fichier", nargs="?", default=None,
                        help="Journal à analyser (défaut : le plus récent du dossier).")
    parser.add_argument("--tous", action="store_true",
                        help="Analyser tous les journaux du dossier plutôt que le "
                             "seul plus récent.")
    parser.add_argument("--dossier", default=None,
                        help="Dossier des journaux (défaut : RACINE_DATA/logs_parties).")
    parser.add_argument("--depuis", default=None,
                        help="Ne garder que les journaux dont le nom "
                             "(partie_AAAAMMJJ_HHMMSS.json) indique une date égale ou "
                             "postérieure à AAAAMMJJ (ex. --depuis 20261001) — utile pour "
                             "isoler les parties jouées avec la dernière version de l'IA "
                             "(issue #198). Affiche le nombre de journaux retenus.")
    parser.add_argument("--budget", type=float, default=10.0,
                        help="Budget de temps GÉNÉREUX du solveur, en secondes "
                             "(défaut 10 — recommandé, voir avertissement). Un budget "
                             "plus court sous-compte les coups ratés qui demandent "
                             "plus de réflexion.")
    parser.add_argument("--budget-production", type=float, default=None,
                        help="Budget de production à comparer pour Expert "
                             "(défaut : celui utilisé en jeu, voir moteur/ia.py).")
    parser.add_argument("--top", type=int, default=5,
                        help="Nombre de coups ratés/poses sous-optimales détaillés à "
                             "afficher (défaut 5).")
    parser.add_argument("--tour", type=int, default=None,
                        help="Détaille un tour précis (ex. --fichier F --tour N, issue "
                             "#196) : nom du joueur, tuiles posées en réalité vs "
                             "proposées par le solveur, texte français et étapes du coup "
                             "proposé (et du coup réel si --joueur). Vient EN PLUS de "
                             "l'affichage habituel, jamais à la place.")
    parser.add_argument("--budget-mesure", action="store_true",
                        help="Pour chaque coup raté/pose sous-optimale, mesure le plus "
                             "petit budget (série 1,5/3/6/10/20/30 s) qui le retrouve, "
                             "et affiche la répartition. Coûteux (relance le solveur "
                             "plusieurs fois par cas) — désactivé par défaut.")
    parser.add_argument("--retenter-inconclusifs", action="store_true",
                        help="Retente les décisions inconclusives avec un budget plus "
                             "grand (--budget-inconclusifs), sous une limite de durée "
                             "totale ferme (--limite-temps-inconclusifs).")
    parser.add_argument("--budget-inconclusifs", type=float,
                        default=BUDGET_INCONCLUSIFS_DEFAUT,
                        help=f"Budget pour la seconde passe sur les inconclusifs "
                             f"(défaut {BUDGET_INCONCLUSIFS_DEFAUT} s).")
    parser.add_argument("--limite-temps-inconclusifs", type=float,
                        default=LIMITE_TEMPS_INCONCLUSIFS_DEFAUT,
                        help="Limite de durée TOTALE, en secondes, de la passe sur les "
                             f"inconclusifs (défaut {LIMITE_TEMPS_INCONCLUSIFS_DEFAUT} s).")
    parser.add_argument("--enregistrer-cas-reference", action="store_true",
                        help="Enregistre les coups ratés/poses sous-optimales (ou, avec "
                             "--joueur, les cas où le joueur bat le solveur) les plus "
                             "importants comme nouveaux fichiers tests/donnees/"
                             "cas_expert_*.json (n'écrase jamais un fichier existant, "
                             "sauf --ecraser).")
    parser.add_argument("--ecraser", action="store_true",
                        help="(--enregistrer-cas-reference) Écrase un fichier "
                             "cas_expert_*.json existant au lieu de le laisser intact "
                             "(défaut : jamais). Sert à RÉGÉNÉRER les fichiers "
                             "cas_expert_humain_*.json avec le bon attendu_min_tuiles "
                             "après la correction du comptage de tuiles posées (issue "
                             "#201) : lancer `--joueur <nom> --enregistrer-cas-reference "
                             "--ecraser` avec --tous sur les mêmes journaux qui ont "
                             "servi à produire les anciens fichiers.")
    parser.add_argument("--joueur", default=None,
                        help="Nom d'un joueur HUMAIN : applique la même analyse à ses "
                             "décisions plutôt qu'à celles d'une IA (point 6 ter).")
    parser.add_argument("--verifier-reserve-evite-pioche", action="store_true",
                        help="(--joueur) Pour chaque réserve réussie, vérifie si elle a "
                             "évité une pioche au tour suivant (appel solveur "
                             "supplémentaire — coûteux).")
    parser.add_argument("--juge-exact", action="store_true",
                        help="Utilise le solveur EXACT de la bibliothèque "
                             "rummikub-solver (licence MIT, dépendance de DÉVELOPPEMENT) "
                             "comme JUGE à la place du solveur maison : il n'y a alors "
                             "plus ni décision « inconclusive » ni coup manqué à cause du "
                             "gel de combinaisons. Désactivé par défaut ; si la "
                             "bibliothèque est absente, le signale clairement et s'arrête "
                             "(voir scripts/solveur_exact.py et CONTEXTE.md §14).")
    args = parser.parse_args(argv)

    # Juge de l'analyse (issue #213, suite de #204) :
    #   * PAR DÉFAUT = modèle exact de la MAISON (``moteur/solveur_exact.py``,
    #     celui qui joue Expert/Avancé/Champion) — optimum exact du tour, plus
    #     aucune décision « inconclusive » ni coup manqué par gel de
    #     combinaisons (contrairement à l'ancien défaut, la recherche
    #     arborescente ``moteur/solveur.py``, désormais simple repli si
    #     highspy/numpy manquent).
    #   * ``--juge-exact`` = bibliothèque externe ``rummikub-solver`` (#204),
    #     devenue un CONTRÔLE CROISÉ facultatif et indépendant.
    solveur_juge = None  # None => repli ultime sur la recherche arborescente maison
    if args.juge_exact:
        _racine = Path(__file__).resolve().parent
        if str(_racine) not in sys.path:
            sys.path.insert(0, str(_racine))
        try:
            import solveur_exact
        except Exception as exc:  # pragma: no cover
            print(f"--juge-exact : impossible d'importer l'adaptateur du solveur "
                  f"exact ({exc}).", file=sys.stderr)
            return 1
        if not solveur_exact.DISPONIBLE:
            print(solveur_exact.MESSAGE_INSTALLATION, file=sys.stderr)
            return 1
        solveur_juge = solveur_exact.resoudre_coup_exact
        print(f"JUGE (contrôle croisé) : bibliothèque rummikub-solver (backend "
              f"{solveur_exact._backend_defaut()}) — optimum exact indépendant "
              f"du modèle maison.\n", file=sys.stderr)
    else:
        from rummikub.moteur import solveur_exact as _maison_exact
        if _maison_exact.DISPONIBLE:
            solveur_juge = _juge_maison_exact
            print("JUGE par défaut : modèle exact de la MAISON "
                  "(moteur/solveur_exact.py) — optimum exact du tour, aucune "
                  "décision « inconclusive » (#213). Contrôle croisé facultatif "
                  "avec --juge-exact (bibliothèque rummikub-solver).\n",
                  file=sys.stderr)
        else:
            print("highspy/numpy absents : le juge se replie sur la recherche "
                  "arborescente (moteur/solveur.py) — borne basse, voir "
                  "CONTEXTE.md §14.\n", file=sys.stderr)

    if args.budget < 10.0:
        print(f"AVERTISSEMENT : --budget {args.budget} s est inférieur au budget "
              f"généreux recommandé (10 s) — les coups qui demandent plus de temps de "
              f"réflexion seront comptés à tort comme inconclusifs ou non ratés, "
              f"jamais comme coups ratés confirmés.\n", file=sys.stderr)

    dossier = Path(args.dossier) if args.dossier else _dossier_defaut()

    if args.fichier:
        chemins = [Path(args.fichier)]
    else:
        tous = filtrer_journaux_depuis(lister_journaux(dossier), args.depuis)
        if args.depuis:
            print(f"{len(tous)} journal(aux) retenu(s) après filtre --depuis {args.depuis}.",
                  file=sys.stderr)
        chemins = tous if args.tous else ([tous[-1]] if tous else [])

    if not chemins:
        print(f"Aucun journal trouvé dans {dossier}.", file=sys.stderr)
        return 0

    budget_production = args.budget_production  # None -> défaut de analyser_decision_complete

    if args.joueur:
        agrege = _analyser_joueur(chemins, args.joueur, args.budget,
                                  budget_production or 1.5, args.verifier_reserve_evite_pioche,
                                  solveur=solveur_juge)
        afficher_resume_joueur(args.joueur, agrege)
        if args.tour is not None:
            trouvees = _detailer_tour(chemins, args.tour, args.budget,
                                      budget_production or 1.5, nom_joueur=args.joueur,
                                      solveur=solveur_juge)
            afficher_detail_tour(trouvees, args.tour)
        if args.enregistrer_cas_reference:
            candidats = sorted(agrege.get("_decisions_solveur_bat", []),
                               key=lambda dr: dr[1]["nb_tuiles_excedentaires"], reverse=True)
            for d, r in candidats[:3]:
                chemin = _enregistrer_cas_reference(
                    d, r["nb_tuiles_reel"], "humain", _dossier_donnees_test(),
                    ecraser=args.ecraser)
                if chemin:
                    print(f"Cas de référence enregistré : {chemin}", file=sys.stderr)
        print(AVERTISSEMENT)
        return 0

    kwargs = {"budget_genereux": args.budget, "solveur": solveur_juge}
    if budget_production is not None:
        kwargs["budget_production"] = budget_production

    resultats = _analyser_tous_journaux_ia(chemins, **kwargs)

    if args.retenter_inconclusifs:
        decisions_par_cle = _decisions_ia_par_cle(chemins)
        tranchees, arretees = _retenter_inconclusifs(
            resultats, decisions_par_cle, args.budget_inconclusifs,
            args.limite_temps_inconclusifs)
        print(f"{tranchees} décision(s) tranchée(s) par la seconde passe, "
              f"{arretees} non retentée(s) (limite de temps).\n", file=sys.stderr)

    resume = calculer_resume_complet(resultats)
    afficher_resume_complet(resume)
    afficher_repartition_solveurs(chemins)
    afficher_tableau_tailles(resume)
    afficher_top_complet(resultats, n=args.top)

    if args.tour is not None:
        trouvees = _detailer_tour(chemins, args.tour, args.budget,
                                  budget_production or BUDGET_TEMPS_EXPERT,
                                  solveur=solveur_juge)
        afficher_detail_tour(trouvees, args.tour)

    if args.budget_mesure and solveur_juge is not None:
        print("--budget-mesure est sans objet avec un juge EXACT (modèle maison "
              "par défaut, ou bibliothèque avec --juge-exact : aucun budget de "
              "temps pertinent) : mesure ignorée.\n", file=sys.stderr)
    elif args.budget_mesure:
        a_mesurer = [r for r in resultats if r["coup_rate"] or r["pose_sous_optimale"]]
        print(f"=== Budget nécessaire (mesuré sur {len(a_mesurer)} coup(s) "
              f"raté(s)/sous-optimal(aux)) ===")
        decisions_par_cle = _decisions_ia_par_cle(chemins)
        valeurs = []
        for r in a_mesurer:
            decision = decisions_par_cle.get((r["fichier"], r["tour"], r["nom"]))
            if decision is None:
                continue
            cible = r["nb_tuiles_solveur"]
            valeurs.append(budget_necessaire(decision, cible))
        repartition = repartition_budget_necessaire(valeurs)
        for b in sorted(BUDGETS_SERIE_DEFAUT):
            print(f"  à portée de {b} s : {repartition[b]}")
        print(f"  indéterminé (> {max(BUDGETS_SERIE_DEFAUT)} s nécessaires) : "
              f"{repartition['indetermine']}")
        print()

    if args.enregistrer_cas_reference:
        candidats = top_coups_rates_complet(resultats, n=3)
        decisions_par_cle = _decisions_ia_par_cle(chemins)
        for r in candidats:
            d = decisions_par_cle.get((r["fichier"], r["tour"], r["nom"]))
            if d is None:
                continue
            decision = dict(d, fichier=r["fichier"])
            chemin_ecrit = _enregistrer_cas_reference(
                decision, r["nb_tuiles_solveur"], "ia", _dossier_donnees_test(),
                ecraser=args.ecraser)
            if chemin_ecrit:
                print(f"Cas de référence enregistré : {chemin_ecrit}", file=sys.stderr)

    print(AVERTISSEMENT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
