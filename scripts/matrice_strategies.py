#!/usr/bin/env python3
"""Outil de matrice de comparaisons de stratégies de Champion du Monde,
REPRENABLE, pour tourner plusieurs jours sans surveillance (issue #228).

Décision d'Alain (nov. 2026) : coder d'abord toutes les stratégies
multi-tours de Champion du Monde, PUIS faire tourner les tournois — ce
script enchaîne, tout seul, une SÉRIE de comparaisons de niveaux (par
défaut Expert — témoin, INCHANGÉ — contre Champion du Monde, dont on fait
varier les stratégies actives), sur un PC qui peut rester allumé plusieurs
jours (Pentium, deux cœurs). Il ne crée AUCUNE stratégie : il orchestre les
campagnes de ``scripts/comparer_niveaux_ia.py`` (option ``--strategies-
champion``/``--sans-strategie``, registre de ``moteur/niveaux.py``).

**Méthode d'ablation prévue par Alain** (plan ``ablation``, le défaut) :
témoin (Champion SANS aucune stratégie), puis Champion avec CHAQUE
stratégie SEULE, puis Champion COMPLET privé de CHAQUE stratégie, puis
Champion COMPLET — pour juger chaque stratégie d'abord à son mécanisme
(compteurs génériques « déclenchée »/« a changé le coup », voir
``comparer_niveaux_ia.compteurs_strategies``) et au résultat des SEULES
parties qui divergent (voir ``scripts/comparer_campagnes_appariees.py``,
réutilisé pour le résumé final), jamais au seul taux de victoire global.

**Reprenable** : chaque configuration écrit son export par partie
(``resultats.jsonl``) et sa trace éventuelle LIGNE PAR LIGNE, avec un
``flush()`` immédiat (voir ``comparer_niveaux_ia.comparer``), et un
``checkpoint.json`` écrit de façon ATOMIQUE (fichier temporaire puis
renommage) après CHAQUE donne jouée. Relancer la MÊME commande sur le MÊME
``--dossier`` reprend exactement à la dernière donne complète déjà écrite,
sans rejouer les parties déjà jouées, et tolère une coupure brutale
(``Ctrl+C``, extinction de la machine) sans corrompre les fichiers déjà
écrits : une dernière ligne JSON incomplète est silencieusement ignorée à
la relecture, toute ligne antérieure corrompue resterait, elle, une
anomalie réelle (jamais tolérée). La série REFUSE de reprendre si le commit
du code a changé depuis son début (``--forcer-reprise-commit-different``
pour passer outre, déconseillé : une série ne doit jamais mélanger deux
versions du jeu — la force des niveaux dépend du code).

**Limite de temps FERME** (``--limite-temps``, issue #220, même mécanisme
que ``scripts/echelle_niveaux.py``) : optionnelle (défaut : aucune, une
série est pensée pour tourner plusieurs jours) — si fournie, un garde-fou
EXTERNE (sous-processus surveillé, ``scripts/_limite_temps_ferme.py``)
termine TOUTE la série si elle dépasse cette limite malgré l'arrêt propre
interne attendu.

Usage (voir aussi ``--statut``/``--controle-rapide`` ci-dessous) ::

    python scripts/matrice_strategies.py --dossier /tmp/serie_228 \\
        --plan ablation --donnes 300 --seed 7 --budget-solveur 4.0
    python scripts/matrice_strategies.py --dossier /tmp/serie_228 --statut
"""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import datetime
import itertools
import json
import os
import platform
import subprocess
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
from rummikub.moteur import niveaux  # noqa: E402

import comparer_niveaux_ia as cni  # noqa: E402
import comparer_campagnes_appariees as cca  # noqa: E402
from _limite_temps_ferme import lancer_avec_limite_ferme  # noqa: E402
from _verif_solveur_exact import (  # noqa: E402
    exiger_solveur_exact_ou_quitter, version_installee,
)


# --------------------------------------------------------------------------- #
# Stratégie active de Champion du Monde, FORCÉE durant une configuration
# (même esprit que ``comparer_niveaux_ia._strategies_champion_forcees``,
# dupliqué ici pour ne pas dépendre d'un symbole privé d'un autre script).
# --------------------------------------------------------------------------- #

@contextlib.contextmanager
def _strategies_champion_forcees(strategies_actives):
    nom = "Champion du Monde"
    original = niveaux.BRIDAGES[nom]
    niveaux.BRIDAGES[nom] = niveaux.bridage_champion_personnalise(strategies_actives)
    try:
        yield
    finally:
        niveaux.BRIDAGES[nom] = original


# --------------------------------------------------------------------------- #
# Lecture/écriture robuste (reprise après coupure brutale, point 5)
# --------------------------------------------------------------------------- #

def _lire_json(chemin: Path):
    if not chemin.is_file():
        return None
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _ecrire_json_atomique(chemin: Path, donnees: dict) -> None:
    tmp = chemin.with_name(chemin.name + ".tmp")
    tmp.write_text(json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, chemin)


def _lire_lignes_tolerant(chemin: Path) -> list:
    """Relit un fichier JSON Lines en tolérant une DERNIÈRE ligne incomplète
    (coupure brutale en plein milieu d'une écriture) — toute ligne
    antérieure corrompue est, elle, une anomalie réelle (jamais tolérée,
    levée telle quelle)."""
    if not chemin.is_file():
        return []
    morceaux = chemin.read_text(encoding="utf-8").split("\n")
    lignes = []
    for i, brute in enumerate(morceaux):
        brute = brute.strip()
        if not brute:
            continue
        try:
            lignes.append(json.loads(brute))
        except json.JSONDecodeError:
            if i == len(morceaux) - 1:
                break
            raise
    return lignes


def _ecrire_lignes_jsonl_atomique(chemin: Path, lignes: list) -> None:
    tmp = chemin.with_name(chemin.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for ligne in lignes:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    os.replace(tmp, chemin)


def _commit_code() -> str:
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(RACINE),
                             capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "inconnu"


def _processus_vivant(pid) -> bool:
    if not pid:
        return False
    try:
        if sys.platform == "win32":
            res = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                                 capture_output=True, text=True)
            return str(pid) in res.stdout
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------- #
# Plans (point 5) : ablation, complet, personnalisé (fichier JSON)
# --------------------------------------------------------------------------- #

def construire_plan_ablation(strategies=None) -> tuple[list, str]:
    """Témoin (aucune) ; chaque stratégie SEULE ; Champion complet PRIVÉ de
    chaque stratégie ; Champion complet (référence) — méthode d'ablation
    décrite par Alain (CONTEXTE.md §13)."""
    ids = list(strategies or niveaux.strategies_champion_valides())
    configs = [{"nom": "temoin_sans_strategie", "strategies_champion": []}]
    for sid in ids:
        configs.append({"nom": f"champion_avec_{sid}_seule",
                        "strategies_champion": [sid]})
    for sid in ids:
        configs.append({"nom": f"champion_complet_sans_{sid}",
                        "strategies_champion": [s for s in ids if s != sid]})
    configs.append({"nom": "champion_complet", "strategies_champion": ids})
    return configs, "champion_complet"


def construire_plan_complet(strategies=None) -> tuple[list, str]:
    """Toutes les combinaisons de stratégies (2^n configurations) —
    avertit si elles sont nombreuses (point 5)."""
    ids = list(strategies or niveaux.strategies_champion_valides())
    if len(ids) > 10:
        print(f"[#228] ATTENTION : {len(ids)} stratégie(s) => "
             f"{2 ** len(ids)} combinaison(s) — série potentiellement très "
             f"longue.")
    configs = []
    for taille in range(len(ids) + 1):
        for combo in itertools.combinations(ids, taille):
            nom = "champion_" + ("_".join(combo) if combo else "aucune")
            configs.append({"nom": nom, "strategies_champion": list(combo)})
    reference = "champion_" + "_".join(ids) if ids else "champion_aucune"
    return configs, reference


def charger_plan_personnalise(chemin: str) -> tuple[list, str]:
    """Fichier JSON : soit une liste de ``{"nom": ..., "strategies_champion":
    [...]}  ``, soit ``{"configurations": [...]}``. Une entrée peut porter
    ``"reference": true`` pour désigner la configuration de référence du
    résumé final (défaut : la dernière de la liste)."""
    donnees = json.loads(Path(chemin).read_text(encoding="utf-8"))
    bruts = donnees["configurations"] if isinstance(donnees, dict) else donnees
    if not bruts:
        raise ValueError(f"{chemin} ne définit aucune configuration.")
    vus = set()
    reference = None
    configs = []
    for c in bruts:
        if "nom" not in c or "strategies_champion" not in c:
            raise ValueError(f"{chemin} : chaque configuration doit avoir "
                            f"'nom' et 'strategies_champion'.")
        if c["nom"] in vus:
            raise ValueError(f"{chemin} : nom de configuration dupliqué : "
                            f"{c['nom']!r}.")
        vus.add(c["nom"])
        niveaux.valider_noms_strategies(c["strategies_champion"])
        if c.get("reference"):
            reference = c["nom"]
        configs.append({"nom": c["nom"],
                        "strategies_champion": list(c["strategies_champion"])})
    return configs, (reference or configs[-1]["nom"])


def _construire_configs(args) -> tuple[list, str]:
    sous_ensemble = None
    if args.strategies:
        sous_ensemble = [s.strip() for s in args.strategies.split(",") if s.strip()]
        niveaux.valider_noms_strategies(sous_ensemble)
    if args.plan == "ablation":
        return construire_plan_ablation(sous_ensemble)
    if args.plan == "complet":
        return construire_plan_complet(sous_ensemble)
    return charger_plan_personnalise(args.plan)


# --------------------------------------------------------------------------- #
# Fusion de résumés de campagne (``comparer_niveaux_ia.comparer``) — une
# configuration reprise joue par TRANCHES d'UNE donne (point 5, résumé
# cumulé checkpointé après chaque donne) ; cette fusion recompose un résumé
# global identique à celui qu'un appel UNIQUE aurait produit.
# --------------------------------------------------------------------------- #

_CLES_SOMME_INT = ("matchs_nuls", "matchs_decides", "coups_invalides_total",
                   "coups_tuiles_disparues_total", "anomalies_conservation_total",
                   "aucun_coup_expert", "nb_donnes_jouees", "nb_parties")
_CLES_CONCAT_LISTE = ("penalites_perdant", "tuiles_perdant", "tours_decidees",
                      "perturbations_expert", "parties_garde_joker")
_CLES_DICT_SOMME = ("victoires", "fins", "replis_expert", "stats_garde_joker")
_CLES_DICT_CONCAT_LISTE = ("cumul_par_camp", "temps_par_niveau")


def _fusionner_resumes(a: dict, b: dict) -> dict:
    fusion = dict(b)
    for cle in _CLES_SOMME_INT:
        fusion[cle] = a.get(cle, 0) + b.get(cle, 0)
    for cle in _CLES_CONCAT_LISTE:
        fusion[cle] = list(a.get(cle) or []) + list(b.get(cle) or [])
    for cle in _CLES_DICT_SOMME:
        da, db = (a.get(cle) or {}), (b.get(cle) or {})
        fusion[cle] = {k: da.get(k, 0) + db.get(k, 0) for k in set(da) | set(db)}
    for cle in _CLES_DICT_CONCAT_LISTE:
        da, db = (a.get(cle) or {}), (b.get(cle) or {})
        fusion[cle] = {k: list(da.get(k) or []) + list(db.get(k) or [])
                      for k in set(da) | set(db)}
    sa, sb = (a.get("stats_verif_finition") or {}), (b.get("stats_verif_finition") or {})
    sf = {}
    for k in set(sa) | set(sb):
        if k == "appels_par_tour":
            sf[k] = list(sa.get(k) or []) + list(sb.get(k) or [])
        else:
            sf[k] = sa.get(k, 0) + sb.get(k, 0)
    fusion["stats_verif_finition"] = sf
    fusion["nb_donnes"] = b.get("nb_donnes", a.get("nb_donnes", 0))
    return fusion


def _resume_vide(niveau_a: str, niveau_b: str) -> dict:
    """Résumé « zéro » (même forme qu'un vrai résumé) : ``nb_donnes=0`` ne
    joue aucune partie ni n'appelle le solveur — juste la bonne structure à
    fusionner avec la première tranche réellement jouée."""
    return cni.comparer(niveau_a, niveau_b, 0, 0, 300)


# --------------------------------------------------------------------------- #
# Exécution d'UNE configuration — reprenable donne par donne (point 5)
# --------------------------------------------------------------------------- #

def executer_configuration(dossier_config: Path, config: dict, serie: dict) -> dict:
    """Joue (ou reprend) UNE configuration jusqu'à ``serie["nb_donnes"]``.

    Le fichier ``resultats.jsonl`` fait FOI du nombre de donnes déjà
    jouées (chaque donne y écrit exactement deux lignes, les deux ordres en
    miroir) : avant de reprendre, il est tronqué aux paires complètes —
    toute ligne isolée ou corrompue, laissée par une coupure brutale en
    plein milieu d'une écriture, est abandonnée (jamais rejouée depuis une
    écriture partielle). ``checkpoint.json`` (réécrit de façon ATOMIQUE
    après CHAQUE donne) porte le résumé cumulé et l'avancement, pour le
    résumé final et ``--statut``."""
    dossier_config.mkdir(parents=True, exist_ok=True)
    chemin_resultats = dossier_config / "resultats.jsonl"
    chemin_trace = dossier_config / "trace.jsonl" if serie.get("export_trace") else None
    chemin_checkpoint = dossier_config / "checkpoint.json"

    lignes = _lire_lignes_tolerant(chemin_resultats)
    donnes_completees = len(lignes) // 2
    _ecrire_lignes_jsonl_atomique(chemin_resultats, lignes[:donnes_completees * 2])
    if chemin_trace is not None:
        _ecrire_lignes_jsonl_atomique(chemin_trace, _lire_lignes_tolerant(chemin_trace))

    checkpoint = _lire_json(chemin_checkpoint) or {}
    resume_cumule = checkpoint.get("resume_cumule")
    if resume_cumule is None:
        resume_cumule = _resume_vide(serie["niveau_a"], serie["niveau_b"])
    debut_config = checkpoint.get("debut_config") or time.time()

    def _checkpointer(termine: bool) -> None:
        _ecrire_json_atomique(chemin_checkpoint, {
            "donnes_completees": donnes_completees, "resume_cumule": resume_cumule,
            "debut_config": debut_config, "derniere_maj": time.time(),
            "termine": termine,
        })

    if donnes_completees >= serie["nb_donnes"]:
        _checkpointer(True)
        return resume_cumule

    with _strategies_champion_forcees(config["strategies_champion"]):
        for k in range(donnes_completees, serie["nb_donnes"]):
            partiel = cni.comparer(
                serie["niveau_a"], serie["niveau_b"], serie["nb_donnes"],
                serie["seed"], serie["max_tours"], nb_manches=serie["nb_manches"],
                budget_temps=serie.get("budget_solveur"),
                export_resultats=str(chemin_resultats),
                export_trace=(str(chemin_trace) if chemin_trace else None),
                donnes_debut=k, donnes_fin=k + 1, mode_fichier="a")
            resume_cumule = _fusionner_resumes(resume_cumule, partiel)
            donnes_completees = k + 1
            _checkpointer(donnes_completees >= serie["nb_donnes"])
    return resume_cumule


# --------------------------------------------------------------------------- #
# Résumé final (point 5) — mis à jour après CHAQUE configuration terminée
# --------------------------------------------------------------------------- #

def construire_resume_final(dossier: Path, serie: dict, configs: list,
                            reference_nom: str) -> str:
    lignes = [
        "=" * 70,
        f"RÉSUMÉ DE SÉRIE — {serie['niveau_a']} (témoin) vs {serie['niveau_b']}",
        f"{serie['nb_donnes']} donne(s) demandée(s), seed {serie['seed']}, "
        f"référence : {reference_nom}",
        "=" * 70,
    ]
    chemin_ref = dossier / reference_nom / "resultats.jsonl"
    for config in configs:
        chk = _lire_json(dossier / config["nom"] / "checkpoint.json") or {}
        donnes = chk.get("donnes_completees", 0)
        statut = "TERMINÉE" if donnes >= serie["nb_donnes"] else f"{donnes}/{serie['nb_donnes']}"
        strategies_txt = ", ".join(config["strategies_champion"]) or "(aucune)"
        marque_ref = "  (RÉFÉRENCE)" if config["nom"] == reference_nom else ""
        lignes.append("-" * 70)
        lignes.append(f"{config['nom']} [{statut}] — stratégies : "
                     f"{strategies_txt}{marque_ref}")
        resume = chk.get("resume_cumule")
        if resume:
            v = resume.get("victoires", {})
            lignes.append(
                f"  Parties jouées : {resume.get('nb_parties', 0)} — "
                f"victoires A({serie['niveau_a']})={v.get('A', 0)} "
                f"B({serie['niveau_b']})={v.get('B', 0)}, nuls "
                f"{resume.get('matchs_nuls', 0)}")
            for sid, c in cni.compteurs_strategies(resume).items():
                lignes.append(f"    stratégie {sid:15s} : déclenchée "
                             f"{c['declenchee']}, a changé le coup "
                             f"{c['a_change_le_coup']}")
        chemin_config = dossier / config["nom"] / "resultats.jsonl"
        if (config["nom"] != reference_nom and chemin_ref.is_file()
                and chemin_config.is_file()):
            comp = cca.comparer_fichiers(str(chemin_config), str(chemin_ref))
            p = comp["p_value_signe"]
            lignes.append(
                f"  vs référence : {comp['identiques']} identique(s), "
                f"{comp['divergentes']} divergente(s) (config gagne "
                f"{comp['camp_a_gagne_fichier1_pas_fichier2']} / référence "
                f"gagne {comp['camp_a_gagne_fichier2_pas_fichier1']}) — test "
                f"des signes p=" + (f"{p:.4f}" if p is not None else "N/A"))
    return "\n".join(lignes) + "\n"


def mettre_a_jour_resume_final(dossier: Path, serie: dict, configs: list,
                               reference_nom: str) -> None:
    texte = construire_resume_final(dossier, serie, configs, reference_nom)
    tmp = dossier / "resume.txt.tmp"
    tmp.write_text(texte, encoding="utf-8")
    os.replace(tmp, dossier / "resume.txt")


# --------------------------------------------------------------------------- #
# Contrôle rapide (point 5) — petit nombre de donnes, résultats JETABLES
# --------------------------------------------------------------------------- #

def executer_controle_rapide(serie: dict, configs: list, dossier: Path) -> None:
    print(f"[#228] Contrôle rapide — {serie['nb_donnes']} donne(s) par "
         f"configuration ({len(configs)} configuration(s)), résultats "
         f"jetables (hors reprise, hors --dossier).")
    for config in configs:
        with _strategies_champion_forcees(config["strategies_champion"]):
            resume = cni.comparer(
                serie["niveau_a"], serie["niveau_b"], serie["nb_donnes"],
                serie["seed"], serie["max_tours"], nb_manches=serie["nb_manches"],
                budget_temps=serie.get("budget_solveur"))
        compteurs = cni.compteurs_strategies(resume)
        detail = ", ".join(
            f"{sid}(déclenchée={c['declenchee']},changé={c['a_change_le_coup']})"
            for sid, c in compteurs.items())
        print(f"  {config['nom']:30s} : {detail}")


# --------------------------------------------------------------------------- #
# Statut (point 5) — lecture seule, ne perturbe jamais la série
# --------------------------------------------------------------------------- #

def afficher_statut(dossier: Path) -> int:
    description = _lire_json(dossier / "description.json")
    if description is None:
        print(f"Aucune série dans {dossier} (description.json absent).")
        return 1
    configs = description["configurations"]
    nb_donnes = description["nb_donnes"]
    total = len(configs)
    termines = 0
    en_cours = None
    for config in configs:
        chk = _lire_json(dossier / config["nom"] / "checkpoint.json") or {}
        donnes = chk.get("donnes_completees", 0)
        if donnes >= nb_donnes:
            termines += 1
        elif en_cours is None:
            en_cours = (config, chk, donnes)

    print(f"Série : {dossier}")
    print(f"Plan : {description['plan']}  —  configurations terminées : "
         f"{termines}/{total}")
    if en_cours is not None:
        config, chk, donnes = en_cours
        print(f"En cours : {config['nom']} — {donnes}/{nb_donnes} donne(s)")
        debut, maj = chk.get("debut_config"), chk.get("derniere_maj")
        if debut and maj and donnes > 0 and maj > debut:
            taux = donnes / (maj - debut)
            if taux > 0:
                eta_min = (nb_donnes - donnes) / taux / 60
                print(f"  Rythme observé : {taux * 60:.2f} donne(s)/min — "
                     f"fin estimée de cette configuration dans "
                     f"~{eta_min:.1f} min")
    elif termines == total:
        print("Série TERMINÉE.")
    pid_info = _lire_json(dossier / "matrice.pid")
    if pid_info and _processus_vivant(pid_info.get("pid")):
        print(f"Un processus tourne (pid {pid_info['pid']}, démarré "
             f"{pid_info.get('demarre')}).")
    else:
        print("Aucun processus actif détecté sur cette machine.")
    return 0


# --------------------------------------------------------------------------- #
# Exécution de la série complète (séquentielle ou --processus 2)
# --------------------------------------------------------------------------- #

def executer_serie(serie: dict, configs: list, dossier: Path,
                   reference_nom: str, processus: int = 1) -> None:
    pid_path = dossier / "matrice.pid"
    _ecrire_json_atomique(pid_path, {
        "pid": os.getpid(),
        "demarre": datetime.datetime.now().isoformat(timespec="seconds"),
    })
    try:
        if processus <= 1:
            for config in configs:
                executer_configuration(dossier / config["nom"], config, serie)
                mettre_a_jour_resume_final(dossier, serie, configs, reference_nom)
        else:
            with concurrent.futures.ProcessPoolExecutor(max_workers=processus) as pool:
                futures = {
                    pool.submit(executer_configuration, dossier / c["nom"], c, serie): c
                    for c in configs
                }
                for fut in concurrent.futures.as_completed(futures):
                    fut.result()
                    mettre_a_jour_resume_final(dossier, serie, configs, reference_nom)
    finally:
        try:
            pid_path.unlink(missing_ok=True)
        except OSError:
            pass


def _demarrer_ou_reprendre_serie(dossier: Path, args, serie: dict, configs: list,
                                 reference_nom: str) -> int:
    description_path = dossier / "description.json"
    description = _lire_json(description_path)
    commit_actuel = _commit_code()

    if description is None:
        description = {
            "niveau_a": serie["niveau_a"], "niveau_b": serie["niveau_b"],
            "nb_donnes": serie["nb_donnes"], "seed": serie["seed"],
            "nb_manches": serie["nb_manches"], "max_tours": serie["max_tours"],
            "budget_solveur": serie["budget_solveur"], "plan": args.plan,
            "configurations": configs, "reference": reference_nom,
            "commit_depart": commit_actuel,
            "interpreteur_python": sys.executable,
            "version_python": platform.python_version(),
            "versions_dependances": {
                p: version_installee(p) for p in ("highspy", "numpy")},
            "machine": platform.node(),
            "debut": datetime.datetime.now().isoformat(timespec="seconds"),
            "fin": None,
        }
        _ecrire_json_atomique(description_path, description)
        print(f"[#228] Nouvelle série dans {dossier} — plan {args.plan}, "
             f"{len(configs)} configuration(s), référence « {reference_nom} ».")
    else:
        attendu = {"niveau_a": serie["niveau_a"], "niveau_b": serie["niveau_b"],
                  "nb_donnes": serie["nb_donnes"], "seed": serie["seed"],
                  "plan": args.plan}
        for cle, val in attendu.items():
            if description.get(cle) != val:
                print(f"ERREUR : {dossier} contient déjà une série avec "
                     f"{cle}={description.get(cle)!r}, incompatible avec "
                     f"{val!r} demandé ici — utiliser un autre --dossier.",
                     file=sys.stderr)
                return 1
        if description["commit_depart"] != commit_actuel:
            if not args.forcer_reprise_commit_different:
                print(f"ERREUR : le commit du code a changé depuis le "
                     f"début de la série ({description['commit_depart']} "
                     f"-> {commit_actuel}) — une série ne doit jamais "
                     f"mélanger deux versions du jeu. Relancer avec "
                     f"--forcer-reprise-commit-different pour reprendre "
                     f"malgré tout (déconseillé).", file=sys.stderr)
                return 1
            print(f"[#228] ATTENTION : reprise forcée malgré un commit "
                 f"différent ({description['commit_depart']} -> "
                 f"{commit_actuel}).")
        configs = description["configurations"]
        reference_nom = description["reference"]
        print(f"[#228] Reprise de la série dans {dossier}.")

    executer_serie(serie, configs, dossier, reference_nom, args.processus)

    description = _lire_json(description_path) or description
    description["fin"] = datetime.datetime.now().isoformat(timespec="seconds")
    _ecrire_json_atomique(description_path, description)
    print(f"[#228] Série terminée. Résumé : {dossier / 'resume.txt'}")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _construire_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Enchaîne une série de comparaisons de stratégies de "
                    "Champion du Monde, sans surveillance, reprenable "
                    "(issue #228).")
    parser.add_argument("--dossier", required=True,
                        help="Dossier de la série (hors du dépôt) — créé "
                             "s'il n'existe pas, réutilisé pour reprendre.")
    parser.add_argument("--statut", action="store_true",
                        help="Affiche l'état de la série dans --dossier et "
                             "quitte, sans rien jouer ni la perturber.")
    parser.add_argument("--niveau-a", default="Expert", choices=NIVEAUX,
                        help="Niveau témoin (défaut Expert, INCHANGÉ).")
    parser.add_argument("--niveau-b", default="Champion du Monde",
                        choices=NIVEAUX,
                        help="Niveau dont on fait varier les stratégies "
                             "(défaut Champion du Monde).")
    parser.add_argument("--donnes", type=int, default=50,
                        help="Nombre de donnes par configuration (défaut "
                             "50 ; chacune jouée 2 fois en miroir).")
    parser.add_argument("--seed", type=int, default=0,
                        help="Graine, la MÊME pour tous les bras (défaut 0).")
    parser.add_argument("--manches", type=int, default=1)
    parser.add_argument("--max-tours", type=int, default=300)
    parser.add_argument("--budget-solveur", type=float, default=None,
                        help="Budget du solveur par coup, en secondes, "
                             "appliqué à TOUS les bras de la série (défaut "
                             ": celui du jeu, 1,5 s) — à relever sur une "
                             "machine lente.")
    parser.add_argument("--plan", default="ablation",
                        help="'ablation' (défaut : témoin, chaque "
                             "stratégie seule, Champion complet privé de "
                             "chaque stratégie, Champion complet), "
                             "'complet' (toutes les combinaisons), ou le "
                             "chemin d'un fichier JSON de configurations "
                             "personnalisées.")
    parser.add_argument("--strategies", default=None,
                        help="Sous-ensemble du registre (séparé par des "
                             "virgules) pour les plans 'ablation'/'complet' "
                             "— défaut : tout le registre. Noms valides : "
                             + ", ".join(niveaux.strategies_champion_valides())
                             + ".")
    parser.add_argument("--processus", type=int, default=1, choices=(1, 2),
                        help="Configurations jouées en parallèle (1 ou 2 — "
                             "la machine cible n'a que deux cœurs).")
    parser.add_argument("--export-trace", action="store_true",
                        help="Écrit aussi une trace brute par tour "
                             "(scripts/analyser_phases.py) pour chaque "
                             "configuration.")
    parser.add_argument("--controle-rapide", type=int, nargs="?", const=50,
                        default=None, metavar="N",
                        help="Joue seulement N donnes (défaut 50) par "
                             "configuration et affiche les compteurs de "
                             "déclenchement de chaque stratégie, SANS "
                             "écrire dans --dossier (résultats jetables) — "
                             "à lancer avant la série complète.")
    parser.add_argument("--forcer-reprise-commit-different", action="store_true",
                        help="Autorise la reprise même si le commit du "
                             "code a changé depuis le début de la série "
                             "(déconseillé : mélange deux versions du jeu).")
    parser.add_argument("--limite-temps", type=float, default=None,
                        help="Limite de temps FERME pour TOUTE la série "
                             "(#220, même mécanisme que "
                             "scripts/echelle_niveaux.py) — défaut : "
                             "aucune (série pensée pour tourner plusieurs "
                             "jours sans surveillance).")
    parser.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    return parser


def _executer(args) -> int:
    dossier = Path(args.dossier)
    try:
        configs, reference_nom = _construire_configs(args)
    except (ValueError, OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1

    noms = [c["nom"] for c in configs]
    if len(set(noms)) != len(noms):
        print("ERREUR : noms de configuration dupliqués dans le plan.",
             file=sys.stderr)
        return 1

    dossier.mkdir(parents=True, exist_ok=True)

    serie = {
        "niveau_a": args.niveau_a, "niveau_b": args.niveau_b,
        "nb_manches": args.manches, "max_tours": args.max_tours,
        "budget_solveur": args.budget_solveur,
        "export_trace": args.export_trace, "seed": args.seed,
    }

    if args.controle_rapide is not None:
        nb = min(args.controle_rapide, args.donnes)
        executer_controle_rapide(dict(serie, nb_donnes=nb), configs, dossier)
        return 0

    serie["nb_donnes"] = args.donnes
    return _demarrer_ou_reprendre_serie(dossier, args, serie, configs, reference_nom)


def main(argv: list[str]) -> int:
    parser = _construire_parser()
    args = parser.parse_args(argv[1:])

    if args.donnes < 1:
        parser.error("--donnes doit être au moins 1")
    if args.manches < 1:
        parser.error("--manches doit être au moins 1")
    if args.budget_solveur is not None and args.budget_solveur <= 0:
        parser.error("--budget-solveur doit être > 0")

    if args.statut:
        return afficher_statut(Path(args.dossier))

    # Échec franc sans solveur exact (#223/#224) : AVANT toute relance
    # surveillée, pour échouer vite sans sous-processus inutile.
    exiger_solveur_exact_ou_quitter()

    if args._worker or args.limite_temps is None:
        return _executer(args)

    # Relance surveillée (garde-fou externe, #220) : plus de limite de
    # temps qui ne soit pas ferme, pour TOUTE la série.
    return lancer_avec_limite_ferme(Path(__file__), list(argv[1:]),
                                    args.limite_temps)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
