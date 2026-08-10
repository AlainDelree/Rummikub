#!/usr/bin/env python3
"""Analyse un log de partie Rummikub et détecte les anomalies de tuiles.

Le journal de partie (voir ``src/rummikub/persistance/journal.py``, issues #97 et
#99) enregistre à chaque coup les mains de tous les joueurs, le contenu exact de
la pioche et le plateau. Ce script relit ce fichier JSON et vérifie, coup par
coup, que le jeu reste cohérent :

- **Conservation des 106 tuiles** : l'ensemble des IDs présents dans les mains,
  le plateau et la pioche doit être exactement l'ensemble des 106 tuiles du sac.
  Toute tuile manquante ou en trop est signalée.
- **Absence de doublon** : aucun ID ne doit apparaître à deux emplacements (ni
  deux fois au même endroit).
- **Localisation des jokers** : à chaque coup on indique où se trouvent
  ``joker_1`` et ``joker_2`` (main d'un joueur, plateau, pioche ou ABSENT).

Usage :

    python scripts/analyser_partie.py <chemin_fichier_log.json>

Le script est en lecture seule et n'importe rien d'obligatoire du back-end : il
tente d'utiliser ``rummikub.moteur.tuiles.creer_sac`` pour connaître les 106 IDs
de référence, et retombe sur une reconstruction locale si l'import échoue (par
exemple hors de l'arborescence du projet).
"""

import json
import sys
from pathlib import Path


# --------------------------------------------------------------------------- #
# Référence : les 106 IDs de tuiles du sac.
# --------------------------------------------------------------------------- #

def _ids_reference() -> set[str]:
    """Ensemble des 106 IDs de tuiles attendus.

    On privilégie ``creer_sac()`` (source de vérité du moteur) ; en cas d'échec
    d'import on reconstruit la même liste à partir des conventions d'ID
    documentées ("rouge_7_a", "joker_1", ...).
    """
    racine = Path(__file__).resolve().parent.parent
    src = racine / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))
    try:
        from rummikub.moteur.tuiles import creer_sac
        return {t.id for t in creer_sac()}
    except Exception:
        # Repli : mêmes conventions que creer_sac() (2 séries × 4 couleurs ×
        # 13 valeurs + 2 jokers).
        couleurs = ("rouge", "bleu", "jaune", "noir")
        ids = set()
        for label in ("a", "b"):
            for couleur in couleurs:
                for valeur in range(1, 14):
                    ids.add(f"{couleur}_{valeur}_{label}")
        for n in range(1, 3):
            ids.add(f"joker_{n}")
        return ids


# --------------------------------------------------------------------------- #
# Extraction des tuiles d'un coup, avec leur emplacement.
# --------------------------------------------------------------------------- #

def _ids_tuiles(tuiles) -> list[str]:
    """IDs d'une liste de tuiles-dict (tolère les entrées mal formées)."""
    ids = []
    if isinstance(tuiles, list):
        for t in tuiles:
            if isinstance(t, dict) and "id" in t:
                ids.append(t["id"])
    return ids


def _emplacements(action: dict) -> list[tuple[str, str]]:
    """Retourne la liste ``[(id_tuile, libelle_emplacement), ...]`` d'un coup.

    Un même ID peut apparaître plusieurs fois si le jeu est incohérent : c'est
    précisément ce que la détection de doublon exploite.
    """
    paires: list[tuple[str, str]] = []

    # Mains des joueurs : liste de {"nom": ..., "tuiles": [...]}.
    for joueur in action.get("mains_joueurs", []) or []:
        if not isinstance(joueur, dict):
            continue
        nom = joueur.get("nom") or "?"
        for tid in _ids_tuiles(joueur.get("tuiles")):
            paires.append((tid, f"main de {nom}"))

    # Plateau : liste de combinaisons, chaque combinaison est une liste de tuiles.
    plateau = action.get("plateau", []) or []
    if isinstance(plateau, list):
        for i, combo in enumerate(plateau, start=1):
            if isinstance(combo, list):
                for tid in _ids_tuiles(combo):
                    paires.append((tid, f"plateau (combinaison {i})"))
            elif isinstance(combo, dict) and "id" in combo:
                # Plateau exceptionnellement plat (liste de tuiles) : on reste
                # tolérant plutôt que de rater des IDs.
                paires.append((combo["id"], "plateau"))

    # Pioche : liste de tuiles.
    for tid in _ids_tuiles(action.get("pioche")):
        paires.append((tid, "pioche"))

    return paires


# --------------------------------------------------------------------------- #
# Analyse d'un coup.
# --------------------------------------------------------------------------- #

def analyser_coup(action: dict, reference: set[str], jokers: list[str]) -> dict:
    """Analyse un coup et retourne un dict de résultat.

    Clés : ``anomalies`` (liste de str), ``jokers`` (dict id -> emplacement(s)).
    """
    paires = _emplacements(action)

    # id -> liste des emplacements où il apparaît.
    localisation: dict[str, list[str]] = {}
    for tid, empl in paires:
        localisation.setdefault(tid, []).append(empl)

    presents = set(localisation)
    anomalies: list[str] = []

    # Doublons (même ID à plusieurs endroits ou plusieurs fois).
    for tid in sorted(localisation):
        if len(localisation[tid]) > 1:
            anomalies.append(
                f"doublon : {tid} présent {len(localisation[tid])} fois "
                f"({', '.join(localisation[tid])})"
            )

    # Tuiles manquantes / en trop par rapport aux 106 de référence.
    manquantes = reference - presents
    en_trop = presents - reference
    for tid in sorted(manquantes):
        anomalies.append(f"tuile manquante : {tid}")
    for tid in sorted(en_trop):
        anomalies.append(f"tuile inconnue (en trop) : {tid}")

    # Localisation des jokers.
    loc_jokers: dict[str, str] = {}
    for jk in jokers:
        empls = localisation.get(jk)
        loc_jokers[jk] = " + ".join(empls) if empls else "ABSENT"

    return {"anomalies": anomalies, "jokers": loc_jokers}


# --------------------------------------------------------------------------- #
# Rapport.
# --------------------------------------------------------------------------- #

def analyser_partie(chemin: Path) -> int:
    """Analyse le fichier de log et écrit le rapport sur stdout.

    Retourne un code de sortie : 0 si la partie est saine, 1 si au moins une
    anomalie est détectée, 2 en cas d'erreur de lecture du fichier.
    """
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Erreur : fichier introuvable : {chemin}")
        return 2
    except (OSError, json.JSONDecodeError) as e:
        print(f"Erreur : impossible de lire {chemin} : {e}")
        return 2

    reference = _ids_reference()
    jokers = sorted(t for t in reference if t.startswith("joker_"))

    actions = data.get("actions", []) if isinstance(data, dict) else []

    print(f"=== Analyse de {chemin.name} ===")
    if isinstance(data, dict):
        pid = data.get("partie_id")
        joueurs = data.get("joueurs")
        if pid is not None:
            print(f"Partie #{pid}"
                  + (f" — joueurs : {', '.join(str(j) for j in joueurs)}"
                     if joueurs else ""))
        print(f"Tuiles de référence : {len(reference)}  "
              f"| jokers suivis : {', '.join(jokers)}")
    print(f"Coups enregistrés : {len(actions)}")
    print("-" * 60)

    premier_suspect = None
    total_anomalies = 0

    for i, action in enumerate(actions, start=1):
        if not isinstance(action, dict):
            print(f"Coup {i:>3} : entrée invalide (ignorée)")
            if premier_suspect is None:
                premier_suspect = i
            continue

        res = analyser_coup(action, reference, jokers)
        libelle_action = action.get("action", "?")
        tour = action.get("tour")
        entete = f"Coup {i:>3} | tour {tour} | {libelle_action}"

        jok = "  ".join(f"{jk}={loc}" for jk, loc in res["jokers"].items())

        if res["anomalies"]:
            total_anomalies += len(res["anomalies"])
            if premier_suspect is None:
                premier_suspect = i
            print(f"{entete} : ANOMALIE ({len(res['anomalies'])})")
            for a in res["anomalies"]:
                print(f"        - {a}")
            print(f"        jokers : {jok}")
        else:
            print(f"{entete} : OK   [jokers : {jok}]")

    print("-" * 60)
    if premier_suspect is None:
        print("RÉSUMÉ : partie SAINE — aucune anomalie détectée sur "
              f"{len(actions)} coup(s).")
        return 0
    print(f"RÉSUMÉ : partie SUSPECTE — {total_anomalies} anomalie(s) au total. "
          f"Premier coup suspect : coup {premier_suspect}.")
    return 1


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage : python scripts/analyser_partie.py "
              "<chemin_fichier_log.json>")
        return 2
    return analyser_partie(Path(argv[1]))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
