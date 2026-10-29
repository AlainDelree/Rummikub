#!/usr/bin/env python3
"""Profil de jeu d'un joueur — HUMAIN (depuis les journaux) ou NIVEAU d'IA
(par simulation), affichés CÔTE À CÔTE, mêmes indicateurs (issue #213).

But : situer un joueur (Alain, p. ex.) sur l'échelle des niveaux d'IA en
comparant les MÊMES indicateurs de style, tous jugés par le solveur EXACT
maison (``moteur/solveur_exact.resoudre_coup_exact``, le « juge » qui donne
l'optimum d'un tour) :

  - tuiles posées par tour vs l'OPTIMUM du tour (max posable selon le juge
    exact) ;
  - part des tours où le joueur a PIOCHÉ/passé alors qu'un coup existait
    (le juge exact trouvait au moins une tuile posable) ;
  - répartition des POSES par TAILLE (petit / moyen / grand) selon le nombre
    de combinaisons du plateau TOUCHÉES par la pose — petit = 1 combinaison,
    moyen = 2, grand = 3 et plus (mesuré par
    ``moteur/description_coup.mesurer_coup_ia`` : combinaisons modifiées +
    créées) ;
  - nombre moyen de tours par partie ; taux de victoire ;
  - DEUX indicateurs de fin de partie, présentés SÉPARÉMENT (ne JAMAIS les
    confondre) :
      (a) tuiles restantes en main quand le joueur PERD — mesure à quel point
          il était proche de finir, c.-à-d. son NIVEAU ;
      (b) points restants (pénalité) quand il perd — n'a d'importance qu'en
          match à PLUSIEURS manches (c'est le score cumulé qui tranche).

Deux sources d'un profil :

  (a) HUMAIN — ``--journaux DIR [--joueur NOM]`` : lit les journaux
      ``partie_*.json`` (les fichiers d'une même partie reprise sont regroupés
      par ``partie_id``, voir ``persistance/parties_liees.py``), juge chaque
      décision du joueur avec le solveur EXACT maison. Comme l'AGENT n'a pas
      accès aux journaux d'Alain, ce chemin se DÉGRADE proprement quand le
      dossier est absent/vide (message clair + la commande exacte à lancer).
      Limite documentée : le journal ne stocke pas les POINTS restants en main
      ; l'indicateur (b) est donc « n/a » pour un profil humain (seules les
      tuiles restantes (a) sont disponibles).

  (b) NIVEAU d'IA — ``--niveau NOM[,NOM...] [--donnes N] [--seed S]`` : simule
      des parties EN MIROIR du niveau contre lui-même (``moteur``, jamais
      pywebview) et mesure les mêmes indicateurs sur tous ses tours. Le taux de
      victoire d'un niveau contre lui-même est ~50 % PAR CONSTRUCTION (signalé)
      ; l'indicateur de fin de partie qui situe le niveau est (a), les tuiles
      restantes du perdant.

Les deux chemins se combinent : ``--journaux DIR --joueur Alain --niveau
Facile,Expert`` affiche Alain à côté de chaque niveau. Le chemin NIVEAU
fonctionne seul, sans aucun journal.

Usage :

    python scripts/profil_joueur.py --niveau "Facile,Expert" --donnes 20
    python scripts/profil_joueur.py --journaux data/logs_parties --joueur Alain
    python scripts/profil_joueur.py --journaux data/logs_parties --joueur Alain \
        --niveau "Intermédiaire,Avancé,Expert"
"""

import argparse
import logging
import random
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
from rummikub.moteur.description_coup import mesurer_coup_ia  # noqa: E402
from rummikub.moteur.ia import jouer_ia  # noqa: E402
from rummikub.moteur.partie import (  # noqa: E402
    annuler_tour, backup_debut_tour, creer_partie, jouer_tour, passer_tour,
    piocher,
)
from rummikub.moteur import solveur_exact  # noqa: E402

# Réutilisation des helpers de formatage/CI (#213).
from comparer_niveaux_ia import intervalle_confiance_95, moyenne  # noqa: E402

logger = logging.getLogger("profil_joueur")

# Budget de temps (s) du juge exact par tour — borne le temps de chaque appel au
# solveur exact (optimum du tour). 1,5 s = budget de production d'Expert : un bon
# compromis fiabilité/vitesse. À monter (``--budget-juge``) pour une mesure plus
# sûre sur de gros états, au prix de la durée.
BUDGET_JUGE_DEFAUT = 1.5


# --------------------------------------------------------------------------- #
# Un profil : mêmes champs quelle que soit la source (humain ou niveau d'IA).
# --------------------------------------------------------------------------- #

def _profil_vierge(libelle: str, est_ia: bool) -> dict:
    return {
        "libelle": libelle,
        "est_ia": est_ia,
        # Taux de victoire défini ? Faux pour un niveau joué EN MIROIR contre
        # lui-même (les deux sièges sont le même niveau → notion de victoire sans
        # objet). Vrai pour un humain (victoire vs l'IA).
        "taux_defini": True,
        "nb_parties": 0,
        "nb_tours": 0,                 # tours du joueur analysés
        "tours_par_partie": [],        # nb de tours du joueur par partie
        "victoires": 0,
        "parties_decidees": 0,         # parties avec vainqueur clair (pour taux)
        # Tuiles posées vs optimum (seulement sur les tours à optimum déterminé).
        "sum_posees": 0,
        "sum_optimum": 0,
        "tours_optimum_connu": 0,
        # Pioche/passe alors qu'un coup existait.
        "pioche_coup_possible": 0,
        "pioche_passe_total": 0,       # tours pioche/passe à optimum déterminé
        # Répartition des poses par taille (combinaisons touchées).
        "poses_petit": 0,
        "poses_moyen": 0,
        "poses_grand": 0,
        "poses_total": 0,
        # Fin de partie quand le joueur PERD.
        "tuiles_restantes_defaite": [],   # (a) niveau
        "points_restants_defaite": [],    # (b) multi-manches ; [] si indisponible
        "points_disponibles": True,       # False pour l'humain (journaux)
    }


def _taille_pose(nb_combinaisons_touchees: int) -> str:
    """Taille d'une pose d'après le nombre de combinaisons du plateau touchées
    (issue #213) : petit = 1, moyen = 2, grand = 3 et plus. Volontairement plus
    fin que le découpage « petit 1-2 » de ``coups_rates.py`` — ici une pose
    purement depuis la main (1 combinaison créée) est « petite »."""
    if nb_combinaisons_touchees <= 1:
        return "petit"
    if nb_combinaisons_touchees == 2:
        return "moyen"
    return "grand"


def _compter_pose(profil: dict, plateau_avant: list, plateau_apres: list) -> None:
    """Classe une pose par taille (combinaisons touchées = modifiées + créées,
    ``mesurer_coup_ia``) et l'ajoute au profil."""
    mesure = mesurer_coup_ia(plateau_avant, plateau_apres)
    touchees = mesure["nb_combinaisons_modifiees"] + mesure["nb_combinaisons_creees"]
    taille = _taille_pose(touchees)
    profil[f"poses_{taille}"] += 1
    profil["poses_total"] += 1


# --------------------------------------------------------------------------- #
# Profil d'un NIVEAU d'IA par simulation (miroir du niveau contre lui-même).
# --------------------------------------------------------------------------- #

def _optimum_tour(etat: dict, idx: int, budget: float):
    """Nombre maximal de tuiles de la main posables ce tour selon le juge EXACT
    maison, ou ``None`` si indéterminé (dépendances absentes, budget épuisé,
    résultat non valide, erreur)."""
    try:
        res = solveur_exact.resoudre_exact(etat, idx, budget_temps=budget)
    except Exception:
        return None
    if not res.valide_globalement:
        return None
    return res.nb_tuiles


def _jouer_un_tour_instrumente(etat: dict, idx: int, profil: dict,
                               budget_juge: float) -> dict:
    """Joue le tour de l'IA (``jouer_ia``, moteur bridé de #213) en mesurant,
    AVANT le coup, l'optimum du tour (juge exact), puis en observant la décision
    réelle. Même repli que l'UI en cas de coup invalide (pioche de secours)."""
    plateau_avant = etat["plateau"]
    optimum = _optimum_tour(etat, idx, budget_juge)

    backup_debut_tour(etat)
    try:
        res_ia = jouer_ia(etat, idx)
    except Exception:
        logger.exception("Exception IA au tour %d", etat["tour_numero"])
        annuler_tour(etat)
        return piocher(etat)["etat"]

    profil["nb_tours"] += 1
    action = res_ia.get("action")

    if action == "jouer":
        res = jouer_tour(etat, res_ia["ids_tuiles"], res_ia["nouveau_plateau"])
        if res["ok"]:
            if optimum is not None:
                profil["tours_optimum_connu"] += 1
                profil["sum_posees"] += len(res_ia["ids_tuiles"])
                profil["sum_optimum"] += optimum
            _compter_pose(profil, plateau_avant, res_ia["nouveau_plateau"])
            return res["etat"]
        # Coup refusé : repli pioche (comme l'UI).
        annuler_tour(etat)
        res = piocher(etat)
        action = "piocher"
    elif action == "piocher":
        res = piocher(etat)
    elif action == "passer":
        res = passer_tour(etat)
    else:
        annuler_tour(etat)
        res = piocher(etat)
        action = "piocher"

    # Pioche/passe : compte-t-elle une occasion manquée ?
    if optimum is not None:
        profil["tours_optimum_connu"] += 1
        profil["sum_optimum"] += optimum
        profil["pioche_passe_total"] += 1
        if optimum > 0:
            profil["pioche_coup_possible"] += 1
    return res["etat"]


def profiler_niveau(niveau: str, nb_donnes: int, seed: int, max_tours: int,
                    budget_juge: float) -> dict:
    """Simule ``nb_donnes`` parties d'une manche du niveau contre lui-même (2
    sièges, même niveau) et agrège les indicateurs. Le taux de victoire est
    ~50 % par construction (deux joueurs identiques) — signalé à l'affichage ;
    l'indicateur de fin qui situe le niveau est (a) les tuiles du perdant."""
    profil = _profil_vierge(f"{niveau} (IA)", est_ia=True)
    profil["taux_defini"] = False  # miroir contre soi : victoire sans objet
    rng_graines = random.Random(seed)

    for _ in range(nb_donnes):
        graine = rng_graines.randrange(2**32)
        random.seed(graine)
        config_joueurs = [
            {"nom": f"{niveau}#0", "est_ia": True, "niveau": niveau},
            {"nom": f"{niveau}#1", "est_ia": True, "niveau": niveau},
        ]
        etat = creer_partie(config_joueurs,
                            {"nb_manches": 1, "graine_ia": graine})
        backup_debut_tour(etat)

        tours = 0
        while not etat["manche_terminee"]:
            tours += 1
            if tours > max_tours:
                break
            idx = etat["index_joueur_actuel"]
            etat = _jouer_un_tour_instrumente(etat, idx, profil, budget_juge)
            backup_debut_tour(etat)

        profil["nb_parties"] += 1
        profil["tours_par_partie"].append(tours)

        # Fin de partie : le perdant de la manche (celui qui n'a pas le plus haut
        # score) renseigne (a) ses tuiles restantes et (b) sa pénalité, même si
        # la manche s'est terminée par blocage (pioche vide) plutôt que par un
        # chevalet vidé — comme ``comparer_niveaux_ia`` (jamais sur une égalité).
        gi = etat["gagnant_manche_index"]
        if gi is not None:
            perdant = 1 - gi
            scores = [j["score_manche"] for j in etat["joueurs"]]
            if scores[gi] != scores[perdant]:
                profil["parties_decidees"] += 1
                profil["tuiles_restantes_defaite"].append(
                    len(etat["joueurs"][perdant]["chevalet"]))
                # Points restants (pénalité) du perdant : -score_manche (voir
                # comparer_niveaux_ia). Dispo en simulation, pas dans un journal.
                profil["points_restants_defaite"].append(-scores[perdant])

    return profil


# --------------------------------------------------------------------------- #
# Profil d'un joueur HUMAIN depuis les journaux (juge exact maison).
# --------------------------------------------------------------------------- #

def profiler_humain(dossier: Path, nom_joueur: str | None,
                    budget_juge: float) -> dict | None:
    """Profil d'un joueur humain lu dans les journaux de ``dossier``, jugé par
    le solveur EXACT maison. Retourne ``None`` si aucune donnée exploitable
    (dossier absent/vide ou joueur absent) — l'appelant affiche alors le
    message de dégradation."""
    from rummikub.persistance.bilan import (
        calculer_bilan, charger_toutes_parties,
    )
    from rummikub.persistance.coups_rates import (
        analyser_decision_complete, extraire_decisions_joueur,
    )
    from rummikub.persistance.parties_liees import fusionner_journaux
    from rummikub.persistance.bilan import charger_journal, lister_journaux

    if not dossier.is_dir():
        return None

    libelle = f"{nom_joueur or 'humain'} (humain)"
    profil = _profil_vierge(libelle, est_ia=False)
    profil["points_disponibles"] = False  # points en main non stockés au journal

    # --- Indicateurs de résultat (victoire, tours, tuiles restantes) via bilan.
    parties = charger_toutes_parties(dossier)
    bilan = calculer_bilan(parties, nom_joueur=nom_joueur)
    # Agrège sur tous les niveaux d'IA rencontrés par le joueur.
    tours_moy = []
    for stats in bilan.values():
        profil["nb_parties"] += stats["parties"]
        profil["victoires"] += stats["victoires_humain"]
        profil["parties_decidees"] += (stats["victoires_humain"]
                                       + stats["defaites_humain"])
        if stats["tours_moyens"] is not None:
            tours_moy.append((stats["tours_moyens"], stats["parties"]))
        if stats["marge_moyenne_defaite"] is not None:
            # marge moyenne de défaite = tuiles restantes de l'humain quand il
            # perd (une valeur agrégée par niveau ; pondérée par les défaites).
            for _ in range(stats["defaites_humain"]):
                profil["tuiles_restantes_defaite"].append(
                    stats["marge_moyenne_defaite"])
    # Moyenne pondérée des tours par partie (une seule valeur agrégée).
    if tours_moy:
        total_p = sum(p for _, p in tours_moy)
        moy = sum(t * p for t, p in tours_moy) / total_p if total_p else 0
        profil["tours_par_partie"] = [moy]  # déjà moyenné

    # --- Indicateurs de style (poses vs optimum, pioches, tailles) via le juge.
    journaux = []
    for chemin in lister_journaux(dossier):
        data = charger_journal(chemin)
        if data is not None:
            journaux.append({"nom": chemin.name, "data": data})

    a_des_decisions = False
    for partie in fusionner_journaux(journaux):
        decisions = extraire_decisions_joueur(
            partie["data"], nom_joueur, partie["debut_present"]) if nom_joueur \
            else []
        for d in decisions:
            resultat = analyser_decision_complete(
                d, budget_genereux=budget_juge,
                solveur=solveur_exact.resoudre_coup_exact)
            if resultat.get("mise_initiale_inconnue") or resultat["inconclusif"]:
                continue
            a_des_decisions = True
            profil["nb_tours"] += 1
            optimum = resultat["nb_tuiles_solveur"]
            profil["tours_optimum_connu"] += 1
            profil["sum_optimum"] += optimum
            if d["action"] == "pose":
                profil["sum_posees"] += resultat["nb_tuiles_reel"]
                plateau_apres = d.get("plateau_apres_reel")
                if plateau_apres is not None:
                    _compter_pose(profil, d["etat"].get("plateau") or [],
                                  plateau_apres)
            else:  # pioche / passe
                profil["pioche_passe_total"] += 1
                if optimum > 0:
                    profil["pioche_coup_possible"] += 1

    if profil["nb_parties"] == 0 and not a_des_decisions:
        return None
    return profil


# --------------------------------------------------------------------------- #
# Affichage côte à côte.
# --------------------------------------------------------------------------- #

def _fmt(valeur, spec=".2f", suffixe="") -> str:
    return "n/a" if valeur is None else f"{format(valeur, spec)}{suffixe}"


def _lignes_indicateurs(profil: dict) -> dict:
    """Calcule la valeur formatée de chaque indicateur (clé stable → str)."""
    nb_parties = profil["nb_parties"]
    taux_victoire = (profil["victoires"] / profil["parties_decidees"]
                     if profil["parties_decidees"] else None)
    tours_moy = moyenne(profil["tours_par_partie"]) if profil["tours_par_partie"] else None
    posees_moy = (profil["sum_posees"] / profil["tours_optimum_connu"]
                  if profil["tours_optimum_connu"] else None)
    optimum_moy = (profil["sum_optimum"] / profil["tours_optimum_connu"]
                   if profil["tours_optimum_connu"] else None)
    pct_pioche_ratee = (profil["pioche_coup_possible"] / profil["pioche_passe_total"]
                        if profil["pioche_passe_total"] else None)
    pt = profil["poses_total"]
    def _part(n):
        return (n / pt) if pt else None
    tuiles_def = (moyenne(profil["tuiles_restantes_defaite"])
                  if profil["tuiles_restantes_defaite"] else None)
    points_def = (moyenne(profil["points_restants_defaite"])
                  if profil["points_restants_defaite"] else None)

    if not profil["taux_defini"]:
        taux_txt = "— (miroir contre soi)"
    elif taux_victoire is not None:
        p, marge = intervalle_confiance_95(profil["victoires"],
                                           profil["parties_decidees"])
        taux_txt = f"{p * 100:.0f} % ± {marge * 100:.0f} pt"
    else:
        taux_txt = "n/a"

    return {
        "Parties analysées": str(nb_parties),
        "Tours analysés": str(profil["nb_tours"]),
        "Tours/partie (moy.)": _fmt(tours_moy, ".1f"),
        "Taux de victoire": taux_txt,
        "Tuiles posées/tour": _fmt(posees_moy, ".2f"),
        "Optimum/tour (juge)": _fmt(optimum_moy, ".2f"),
        "Pioche/passe alors qu'un coup existait": _fmt(
            None if pct_pioche_ratee is None else pct_pioche_ratee * 100,
            ".0f", " %"),
        "Poses petites (1 combo)": _fmt(
            None if _part(profil['poses_petit']) is None
            else _part(profil['poses_petit']) * 100, ".0f", " %"),
        "Poses moyennes (2 combos)": _fmt(
            None if _part(profil['poses_moyen']) is None
            else _part(profil['poses_moyen']) * 100, ".0f", " %"),
        "Poses grandes (3+ combos)": _fmt(
            None if _part(profil['poses_grand']) is None
            else _part(profil['poses_grand']) * 100, ".0f", " %"),
        "(a) Tuiles restantes en défaite": _fmt(tuiles_def, ".1f"),
        "(b) Points restants en défaite": (
            _fmt(points_def, ".1f") if profil["points_disponibles"]
            else "n/a (non journalisé)"),
    }


def afficher_profils(profils: list[dict]) -> None:
    if not profils:
        print("Aucun profil à afficher.")
        return
    colonnes = [_lignes_indicateurs(p) for p in profils]
    cles = list(colonnes[0].keys())
    libelle_col = max(len(c) for c in cles) + 1

    larg = max(22, max(len(p["libelle"]) for p in profils) + 2)
    print("=" * (libelle_col + larg * len(profils) + 4))
    print("PROFILS DE JOUEUR CÔTE À CÔTE (issue #213)")
    print("-" * (libelle_col + larg * len(profils) + 4))
    entete = " " * libelle_col + "  " + "".join(
        f"{p['libelle']:<{larg}s}" for p in profils)
    print(entete)
    print("-" * (libelle_col + larg * len(profils) + 4))
    for cle in cles:
        ligne = f"{cle:<{libelle_col}s}  "
        ligne += "".join(f"{col[cle]:<{larg}s}" for col in colonnes)
        print(ligne)
    print("=" * (libelle_col + larg * len(profils) + 4))
    print("Rappel (issue #213) : (a) tuiles restantes en défaite situe le "
          "NIVEAU (proximité de la sortie) ;")
    print("(b) points restants ne pèsent qu'en match à PLUSIEURS manches "
          "(score cumulé). Ne pas confondre les deux.")
    if any(p["est_ia"] for p in profils):
        print("Un niveau d'IA est simulé EN MIROIR contre lui-même : son taux "
              "de victoire est sans objet (« — ») ; c'est (a) qui situe le "
              "niveau (plus les tuiles restantes en défaite sont basses, plus "
              "le niveau finit près de la sortie).")


def _message_degradation_humain(dossier: Path, nom_joueur: str | None) -> None:
    cible = f'--joueur "{nom_joueur}" ' if nom_joueur else ""
    print("-" * 70)
    print(f"Profil HUMAIN indisponible : aucun journal exploitable dans "
          f"{dossier}" + (f" pour le joueur « {nom_joueur} »." if nom_joueur
                          else "."))
    print("Pour obtenir ce profil, Alain doit lancer, sur sa machine où sont "
          "ses journaux :")
    print(f"    PYTHONPATH=src python3 scripts/profil_joueur.py \\")
    print(f"        --journaux data/logs_parties {cible}\\")
    print(f"        --niveau \"Facile,Intermédiaire,Avancé\"")
    print("(activez le journal des parties via la config, clé \"log_parties\".)")
    print("-" * 70)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _parse_niveaux(valeur: str | None) -> list[str]:
    if not valeur:
        return []
    niveaux = []
    for n in valeur.split(","):
        n = n.strip()
        if not n:
            continue
        if n not in NIVEAUX:
            raise argparse.ArgumentTypeError(
                f"niveau inconnu : {n!r} (valides : {', '.join(NIVEAUX)})")
        niveaux.append(n)
    return niveaux


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Profil de jeu d'un joueur humain et/ou de niveaux d'IA, "
                    "côte à côte (issue #213).")
    parser.add_argument("--journaux", default=None,
                        help="Dossier des journaux de parties (profil HUMAIN).")
    parser.add_argument("--joueur", default=None,
                        help="Nom du joueur humain à profiler (avec --journaux).")
    parser.add_argument("--niveau", default=None,
                        help="Niveau(x) d'IA à profiler (liste séparée par des "
                             "virgules, ex. \"Facile,Expert\").")
    parser.add_argument("--donnes", type=int, default=20,
                        help="Parties simulées par niveau d'IA (défaut 20).")
    parser.add_argument("--seed", type=int, default=0,
                        help="Graine aléatoire (défaut 0, reproductible).")
    parser.add_argument("--max-tours", type=int, default=300,
                        help="Garde-fou anti-blocage par manche (défaut 300).")
    parser.add_argument("--budget-juge", type=float, default=BUDGET_JUGE_DEFAUT,
                        help=f"Budget du juge exact par tour, en secondes "
                             f"(défaut {BUDGET_JUGE_DEFAUT}).")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Journalise le détail de la simulation.")
    args = parser.parse_args(argv[1:])

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        niveaux = _parse_niveaux(args.niveau)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
        return 2

    if not niveaux and not args.journaux:
        parser.error("Fournir au moins --niveau et/ou --journaux.")

    debut = time.monotonic()
    profils: list[dict] = []

    # Profil humain (en premier, pour apparaître à gauche), dégradé si absent.
    if args.journaux:
        dossier = Path(args.journaux)
        profil_h = profiler_humain(dossier, args.joueur, args.budget_juge)
        if profil_h is None:
            _message_degradation_humain(dossier, args.joueur)
        else:
            profils.append(profil_h)

    # Profils de niveaux d'IA (fonctionnent seuls).
    for niveau in niveaux:
        logger.info("Simulation du niveau %s (%d partie(s))...", niveau,
                    args.donnes)
        profils.append(profiler_niveau(niveau, args.donnes, args.seed,
                                       args.max_tours, args.budget_juge))

    if profils:
        afficher_profils(profils)
    print(f"Temps total : {time.monotonic() - debut:.1f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
