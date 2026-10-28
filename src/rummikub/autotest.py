"""Autotest en ligne de commande (``--autotest``) — issue #208 (suite de #206).

Vérifie, **sans ouvrir aucune fenêtre** et **sans importer l'interface
graphique** (``pywebview``), que l'exécutable embarque bien le solveur exact
d'Expert (``highspy`` + ``numpy``, issue #206) et ses ressources, puis résout
une petite position intégrée avec le modèle exact (``moteur/solveur_exact.py``)
pour prouver qu'il fonctionne réellement.

Fonctionne **depuis les sources** (``python main.py --autotest``) comme **depuis
l'exécutable gelé** par PyInstaller (cas « frozen »). Comme l'exécutable Windows
est construit en mode fenêtré (``console=False`` dans ``rummikub.spec``), il n'a
pas de console attachée et sa sortie standard est perdue : on écrit donc aussi,
quand un chemin de rapport est fourni en argument
(``--autotest <chemin_rapport>``), le compte rendu complet dans ce fichier, que
le script de build récupère ensuite (``type`` / ``cat``).

**Ne modifie aucun fichier de données de l'utilisateur** : on n'importe ni la
persistance (SQLite), ni les réglages (``config.json``) ; seul l'éventuel
fichier de rapport explicitement demandé est écrit, et jamais sous le dossier de
données du jeu.

Code de sortie : ``0`` si le solveur exact fonctionne de bout en bout, ``1``
sinon — avec, à l'écran, la cause de l'échec.
"""

from __future__ import annotations

import sys
from pathlib import Path


# Position intégrée : un plateau vide + une main contenant une suite (rouge
# 5-6-7) et un groupe (10 rouge/bleu/jaune). Mise initiale réputée faite : le
# modèle doit pouvoir poser les 6 tuiles de la main (3 + 3). Entièrement
# autonome (aucun fichier lu), déterministe, et exerce les deux types
# d'ensembles (suite ET groupe) ainsi que les deux contrôles du solveur
# (validation + conservation).
_TUILES_ATTENDUES = 6


def _position_integree():
    """Renvoie ``(etat, idx, nb_tuiles_attendu)`` pour la résolution d'essai."""
    chevalet = [
        {"id": "rouge_5_a", "valeur": 5, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_6_a", "valeur": 6, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_7_a", "valeur": 7, "couleur": "rouge", "est_joker": False},
        {"id": "rouge_10_a", "valeur": 10, "couleur": "rouge", "est_joker": False},
        {"id": "bleu_10_a", "valeur": 10, "couleur": "bleu", "est_joker": False},
        {"id": "jaune_10_a", "valeur": 10, "couleur": "jaune", "est_joker": False},
    ]
    etat = {
        "plateau": [],
        "joueurs": [{"chevalet": chevalet, "mise_initiale_faite": True}],
        "config": {"mise_initiale_min": 30},
    }
    return etat, 0, _TUILES_ATTENDUES


def _chemin_rapport(argv):
    """Chemin de rapport optionnel : premier argument après ``--autotest`` qui
    ne commence pas par ``-`` (``--autotest C:\\Temp\\rapport.txt``)."""
    try:
        i = argv.index("--autotest")
    except ValueError:
        return None
    if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
        return argv[i + 1]
    return None


def _executer(emettre) -> int:
    """Cœur de l'autotest : émet le compte rendu ligne par ligne via
    ``emettre(str)`` et renvoie le code de sortie (0 succès, 1 échec)."""
    emettre("=== Rummikub --autotest ===")
    emettre(f"Python        : {sys.version.split()[0]} ({sys.platform})")
    gele = getattr(sys, "frozen", False)
    emettre(f"Execution     : {'executable gele (PyInstaller)' if gele else 'sources'}")

    # 1. numpy ---------------------------------------------------------------
    try:
        import numpy
        emettre(f"numpy         : {numpy.__version__}")
    except Exception as exc:
        emettre(f"[ECHEC] numpy introuvable : {exc!r}")
        return 1

    # 2. highspy -------------------------------------------------------------
    try:
        import highspy
        emettre(f"highspy       : {getattr(highspy, '__version__', '(version inconnue)')}")
    except Exception as exc:
        emettre(f"[ECHEC] highspy introuvable : {exc!r}")
        return 1

    # 3. ressources web du jeu ----------------------------------------------
    try:
        from rummikub.config import RACINE_WEB
    except Exception as exc:
        emettre(f"[ECHEC] import de rummikub.config impossible : {exc!r}")
        return 1
    racine_web = Path(RACINE_WEB)
    if racine_web.is_dir() and (racine_web / "accueil.html").exists() \
            and (racine_web / "jeu.html").exists():
        emettre(f"Ressources web : OK ({racine_web})")
    else:
        emettre(f"[ECHEC] Dossier des ressources web absent ou incomplet : {racine_web}")
        return 1

    # 4. solveur exact : import, disponibilite, puis resolution d'une position
    try:
        from rummikub.moteur import solveur_exact as se
    except Exception as exc:
        emettre(f"[ECHEC] import du solveur exact impossible : {exc!r}")
        return 1
    if not se.DISPONIBLE:
        emettre(f"[ECHEC] Solveur exact indisponible (repli silencieux sur la "
                f"recherche arborescente) : {se._ERREUR_IMPORT!r}")
        return 1

    etat, idx, attendu = _position_integree()
    try:
        res = se.resoudre_exact(etat, idx, budget_temps=5.0)
    except Exception as exc:
        emettre(f"[ECHEC] Resolution exacte echouee : {exc!r}")
        return 1

    emettre(f"Solveur exact  : backend {res.backend}, {res.nb_tuiles} tuiles "
            f"posees en {res.duree * 1000:.0f} ms "
            f"(optimum {'prouve' if res.optimal else 'non prouve'})")

    if not res.valide_globalement:
        emettre("[ECHEC] Resultat non valide : "
                f"toutes_valides={res.toutes_valides}, "
                f"conservation_ok={res.conservation_ok}")
        return 1
    if res.nb_tuiles != attendu:
        emettre(f"[ECHEC] Nombre de tuiles posees inattendu : {res.nb_tuiles} "
                f"(attendu {attendu}) — le solveur exact ne se comporte pas "
                f"comme prevu.")
        return 1

    emettre("=== Autotest reussi : le solveur exact d'Expert fonctionne. ===")
    return 0


def executer_autotest(argv=None) -> int:
    """Point d'entrée de ``--autotest``. Émet le compte rendu sur la sortie
    standard (si disponible) et, si un chemin de rapport est fourni après
    ``--autotest``, écrit le même compte rendu dans ce fichier. Renvoie le code
    de sortie (0/1)."""
    argv = list(sys.argv[1:] if argv is None else argv)
    rapport_path = _chemin_rapport(argv)

    lignes: list[str] = []

    def emettre(msg: str) -> None:
        lignes.append(msg)
        # sys.stdout peut être None dans un exécutable fenêtré sans console
        # (Windows) : on n'échoue jamais pour autant.
        try:
            if sys.stdout is not None:
                print(msg)
                sys.stdout.flush()
        except Exception:
            pass

    code = _executer(emettre)

    if rapport_path:
        try:
            Path(rapport_path).write_text("\n".join(lignes) + "\n", encoding="utf-8")
        except Exception as exc:  # pragma: no cover - dépend du système de fichiers
            try:
                if sys.stdout is not None:
                    print(f"[ATTENTION] Ecriture du rapport impossible ({exc!r}).")
            except Exception:
                pass

    return code
