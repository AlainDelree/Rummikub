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

import time

import pytest

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
