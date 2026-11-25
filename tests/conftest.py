"""Configuration pytest partagée.

Calibration de la vitesse machine (issue #206, point 8 de #204 enfin traité)
----------------------------------------------------------------------------
Plusieurs tests de la **recherche arborescente conservée comme repli**
(``moteur/solveur.py``) vérifient qu'un coup est trouvé dans un budget de
temps donné. Leur résultat dépend alors de la vitesse de la machine : un
budget calibré sur la machine de développement peut être trop court sur une
machine de CI plus lente, rendant le test instable (flaky) — sans qu'il y ait
la moindre régression réelle.

On mesure donc, une fois par session, un micro-benchmark CPU déterministe, et
on en déduit un **facteur multiplicatif** ``facteur_machine`` (≥ 1) appliqué
aux budgets de ces tests. Sur la machine de référence (celle de
développement), le facteur vaut ≈ 1 (budgets inchangés, l'objectif de vitesse
reste donc réellement testé) ; sur une machine N fois plus lente, les budgets
sont multipliés par ≈ N, ce qui compense exactement la lenteur sans RIEN
relâcher de l'assertion de résultat. Le facteur est plafonné pour éviter des
tests interminables en cas d'anomalie.

Le modèle exact d'Expert (``moteur/solveur_exact.py``, HiGHS) ne dépend PAS de
ce facteur : il prouve l'optimum, et ses tests le vérifient à un budget
confortable, indépendant de la vitesse machine (voir
``tests/test_solveur_exact_maison.py``).
"""

import faulthandler
import tempfile
import time
from pathlib import Path

import pytest

from rummikub.moteur import niveaux as _niveaux
from rummikub.moteur import solveur as _solveur

# Durée du micro-benchmark ci-dessous sur la machine de développement (#206).
# Mesurée best-of-3 : ~0,107 s pour 1 000 000 d'itérations.
_REFERENCE_DEV_S = 0.107
_ITERATIONS = 1_000_000
_FACTEUR_MIN, _FACTEUR_MAX = 1.0, 30.0


def _micro_benchmark() -> float:
    """Durée (s) d'un calcul entier déterministe — best-of-3 pour lisser le
    bruit d'ordonnancement. Ne dépend d'aucune bibliothèque tierce."""
    best = float("inf")
    for _ in range(3):
        debut = time.perf_counter()
        x = 0
        for i in range(_ITERATIONS):
            x = (x + i * 2654435761) & 0xFFFFFFFF
        best = min(best, time.perf_counter() - debut)
    return best


def _calibrer() -> float:
    facteur = _micro_benchmark() / _REFERENCE_DEV_S
    return min(_FACTEUR_MAX, max(_FACTEUR_MIN, facteur))


# Calibré une seule fois à l'import (réutilisé par la fixture et importable
# directement par les tests qui en ont besoin).
FACTEUR_MACHINE = _calibrer()


@pytest.fixture(scope="session")
def facteur_machine() -> float:
    """Facteur multiplicatif (≥ 1) à appliquer aux budgets des tests de la
    recherche de repli dont le résultat dépend de la vitesse machine."""
    return FACTEUR_MACHINE


# --------------------------------------------------------------------------- #
# Horloge déterministe pour les tests de dépassement de budget (issue #244)
# --------------------------------------------------------------------------- #

class _HorlogeDeterministe:
    """Remplace ``time.monotonic`` dans ``moteur.solveur`` : garantit une
    valeur strictement croissante à CHAQUE appel.

    ``_Contexte.verifier_budget`` compare ``time.monotonic() > self.limite``
    (comparaison STRICTE). Avec un budget de temps nul ou très petit, cette
    comparaison n'est fiable que si l'horloge a réellement avancé entre la
    pose de ``limite`` et sa vérification. Sous Windows, ``time.monotonic()``
    réel n'avance que par paliers d'environ 15 ms : deux appels très
    rapprochés peuvent renvoyer la même valeur, et une recherche très courte
    peut alors se terminer sans jamais déclencher ``BudgetDepasse`` — défaut
    du TEST (horloge réelle instable), pas du moteur."""

    def __init__(self, pas: float = 0.001):
        self._valeur = 0.0
        self._pas = pas

    def monotonic(self) -> float:
        self._valeur += self._pas
        return self._valeur


@pytest.fixture
def horloge_solveur_deterministe(monkeypatch):
    """Substitue l'horloge de ``moteur.solveur`` par ``_HorlogeDeterministe``
    pour la durée du test : un budget de temps nul (ou très petit) dépasse
    alors de façon fiable, quelle que soit la résolution de l'horloge réelle
    de l'OS (voir issue #244)."""
    monkeypatch.setattr(_solveur, "time", _HorlogeDeterministe())


# --------------------------------------------------------------------------- #
# Réglage de TEST rapide pour un joueur FAIBLE (issue #268)
# --------------------------------------------------------------------------- #

# Anciennes valeurs rapides de Débutant (#216/#217, avant la calibration par
# duels de #267) : perturbation 0 → jamais de recours au solveur exact
# (``ia._coup_selon_perturbation`` prend directement le coup sans
# réarrangement), donc un joueur FAIBLE et RAPIDE. Depuis #267, Débutant vaut
# perturbation 1 (appelle le solveur exact à chaque tour pour mesurer le
# déplacement, ≈ 1 s/tour) — correct pour l'échelle réelle, mais rend lente
# toute campagne de test qui ne voulait qu'un adversaire faible et rapide
# (voir docs/contexte/niveaux_ia_calibrage.md, règle ajoutée par #268).
BRIDAGE_DEBUTANT_RAPIDE = _niveaux.Bridage(
    perturbation_max=0, taux_oubli=0.42, eviter_don_joker=False)


@pytest.fixture(autouse=True)
def _bridages_restaures():
    """Filet de sécurité AUTOUSE (issue #268, à distinguer de
    ``niveau_debutant_rapide`` ci-dessous, qui elle N'EST PAS autouse) :
    sauvegarde ``niveaux.BRIDAGES`` avant chaque test et le restaure après,
    quoi qu'il arrive. ``scripts/calibrer_echelle.py`` (``_jouer_tache``)
    installe un ``--reglage`` candidat directement dans ce dict GLOBAL, sans
    jamais le restaurer lui-même (comportement voulu hors tests, pour que la
    campagne en cours l'utilise) — un test qui invoque cet outil (p. ex.
    ``test_calibrer_echelle.py::test_refuse_de_melanger_deux_jeux_de_
    reglages``, réglage ``Facile=1/0.30``) laissait sinon ce réglage actif
    pour TOUTE la session, faisant ensuite échouer ``test_niveaux.py::
    test_reglages_calibres_267`` (découvert en mesurant la suite complète
    pour #268, une fois le blocage de ``test_export_trace.py`` corrigé et la
    suite capable d'atteindre ce test)."""
    avant = dict(_niveaux.BRIDAGES)
    try:
        yield
    finally:
        _niveaux.BRIDAGES.clear()
        _niveaux.BRIDAGES.update(avant)


@pytest.fixture
def niveau_debutant_rapide(monkeypatch):
    """Installe, pour la durée du test SEULEMENT, l'ancien réglage rapide de
    Débutant (:data:`BRIDAGE_DEBUTANT_RAPIDE`) dans ``niveaux.BRIDAGES`` — à
    utiliser quand un test (campagne ``comparer_niveaux_ia.comparer`` par
    exemple) n'a besoin que d'un joueur faible et rapide, PAS du réglage
    calibré réel de Débutant (issue #267). Jamais sur un test qui vérifie le
    comportement RÉEL de Débutant (``tests/test_niveaux.py``,
    ``test_ia_anti_don_joker.py::test_debutant_et_facile_inchanges``...).
    ``monkeypatch.setitem`` restaure automatiquement l'ancienne valeur à la
    fin du test, y compris en cas d'échec."""
    monkeypatch.setitem(_niveaux.BRIDAGES, "Débutant", BRIDAGE_DEBUTANT_RAPIDE)


# --------------------------------------------------------------------------- #
# Garde-fou de durée par test (issue #268) : un test qui boucle échoue vite
# avec une trace de piles au lieu de bloquer la suite des dizaines de
# minutes. ``faulthandler`` (bibliothèque standard, aucune dépendance
# ajoutée — voir test_requirements_epinglees.py) tourne dans un thread
# dédié : fonctionne aussi bien sous Linux que sous Windows, contrairement à
# ``signal.alarm`` (absent de Windows). ``exit=True`` : la pile est d'abord
# déchargée, puis le processus s'arrête net (``os._exit``) — un test qui
# boucle peut être coincé dans un appel C (solveur) qu'aucun signal Python ne
# peut interrompre proprement ; arrêter la suite avec un diagnostic vaut
# mieux qu'un blocage silencieux.
#
# La trace est écrite dans un fichier RÉEL sur disque (``tempfile``), pas sur
# ``sys.stderr`` : la capture de sortie de pytest (mode ``fd`` par défaut)
# redirige le descripteur de fichier 2 vers un fichier temporaire PAR test,
# jamais relu puisque ``os._exit`` saute le rapport final de pytest — la
# trace y serait écrite mais jamais vue. Écrire dans un fichier fixe, ouvert
# en dehors de toute capture, la rend lisible après coup quel que soit le
# mode de capture.
# --------------------------------------------------------------------------- #

_LIMITE_TEMPS_TEST_S = 60.0
_LIMITE_TEMPS_TEST_LENT_S = 240.0
FICHIER_TRACE_DEPASSEMENT = Path(tempfile.gettempdir()) / "rummikub_tests_depassement_limite_temps.log"


@pytest.fixture(autouse=True)
def _limite_temps_par_test(request):
    limite = (_LIMITE_TEMPS_TEST_LENT_S
              if request.node.get_closest_marker("lent")
              else _LIMITE_TEMPS_TEST_S)
    fichier = open(FICHIER_TRACE_DEPASSEMENT, "w", encoding="utf-8")
    fichier.write(f"Test en dépassement (> {limite:.0f}s) : {request.node.nodeid}\n")
    fichier.flush()
    faulthandler.dump_traceback_later(limite, file=fichier, exit=True)
    try:
        yield
    finally:
        faulthandler.cancel_dump_traceback_later()
        fichier.close()
