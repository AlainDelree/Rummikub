"""Brique « Inconnues » (issue #219) : à partir de ce qu'UN joueur voit (le
tapis, sa propre main, la taille de la pioche, le nombre de tuiles de chaque
adversaire), calcule l'ensemble des tuiles qui lui sont inconnues — c'est-à-
dire exactement les mains adverses et la pioche réunies — avec, pour chaque
tuile, le nombre d'exemplaires encore possibles (0, 1 ou 2 ; 2 pour les
jokers), et des probabilités de présence chez un adversaire donné ou dans la
pioche.

Module de pur calcul, SANS ÉTAT ni historique : tout se recalcule à chaque
appel à partir de l'état visible au moment de l'appel. Indépendant du
solveur, des niveaux d'IA et de l'interface — ne modifie AUCUN comportement
de jeu (voir CONTEXTE.md §13).

Garde-fou anti-triche : aucune fonction de ce module ne lit jamais le CONTENU
d'une main adverse — seules les TAILLES (``len(chevalet)``) sont utilisées.
``calculer_inconnues`` (le cœur du calcul) ne reçoit même pas les mains
adverses, seulement leurs tailles ; ``calculer_inconnues_depuis_etat`` (le
raccourci pratique à partir de l'état de partie complet) n'appelle que
``len(...)`` sur les chevalets adverses. Voir
``tests/test_inconnues.py::test_equite_pas_de_triche_contenu_main_adverse``.

Brique de base pour les stratégies multi-tours décrites en CONTEXTE.md §13
(Pistes 8 et 9) : « Indices » (affiner ces probabilités à partir du
comportement observé de l'adversaire), « Joker et réserve » (probabilité
qu'un joker soit récupérable chez l'adversaire), « Course » et « Rétention »
(probabilité qu'une tuile retenue prive réellement l'adversaire),
« Ouverture ». Aucune de ces stratégies n'est implémentée ici.

« Chances de poser au prochain tour » (issue #231, anciennement « tuiles
vivantes » — nom abandonné : au Rummikub, le tapis est réarrangeable, une
tuile posée n'est jamais « sortie » du jeu) EST implémentée, dans
``moteur/sorties.py``, à partir des probabilités calculées ici.
"""

from collections import Counter
from dataclasses import dataclass, field
from math import comb

from rummikub.config import COULEURS, VALEUR_MIN, VALEUR_MAX, NB_SERIES, NB_JOKERS

CLE_JOKER = ("joker", None)

TOTAL_TUILES = len(COULEURS) * (VALEUR_MAX - VALEUR_MIN + 1) * NB_SERIES + NB_JOKERS


def _champ(tuile, nom, defaut=None):
    """Lit un champ d'une tuile, qu'elle soit un dict (sérialisation de
    l'état de partie) ou un objet ``Tuile`` (dataclass)."""
    if isinstance(tuile, dict):
        return tuile.get(nom, defaut)
    return getattr(tuile, nom, defaut)


def _cle_tuile(tuile) -> tuple:
    """Clé de TYPE de tuile (``CLE_JOKER`` ou ``(couleur, valeur)``) — les deux
    jokers partagent la même clé : leur couleur est purement visuelle (voir
    ``moteur/tuiles.py``), la logique de jeu ne distingue jamais joker_1 de
    joker_2."""
    if _champ(tuile, "est_joker"):
        return CLE_JOKER
    return (_champ(tuile, "couleur"), _champ(tuile, "valeur"))


def _toutes_les_cles() -> list:
    cles = [(c, v) for c in COULEURS for v in range(VALEUR_MIN, VALEUR_MAX + 1)]
    cles.append(CLE_JOKER)
    return cles


def _exemplaires_max(cle: tuple) -> int:
    return NB_JOKERS if cle == CLE_JOKER else NB_SERIES


def _aplatir(tuiles) -> list:
    """Accepte indifféremment une liste plate de tuiles ou une liste de
    combinaisons (liste de listes, comme ``etat["plateau"]``)."""
    resultat = []
    for item in tuiles:
        if isinstance(item, list):
            resultat.extend(item)
        else:
            resultat.append(item)
    return resultat


@dataclass(frozen=True)
class TuileInconnue:
    """Une tuile (type) encore inconnue pour le joueur, et son nombre
    d'exemplaires encore possibles ailleurs (mains adverses + pioche)."""
    cle: tuple
    exemplaires_restants: int

    @property
    def est_joker(self) -> bool:
        return self.cle == CLE_JOKER

    @property
    def couleur(self):
        return None if self.est_joker else self.cle[0]

    @property
    def valeur(self):
        return None if self.est_joker else self.cle[1]


@dataclass(frozen=True)
class Inconnues:
    """Résultat de :func:`calculer_inconnues` pour UN joueur à UN instant
    donné. ``tailles_mains_adversaires`` conserve l'ordre fourni en entrée
    (les fonctions de probabilité ``*_chez_adversaire`` y font référence par
    position, 0-based, dans cet ordre)."""
    tuiles: dict = field(default_factory=dict)          # cle -> TuileInconnue (restants > 0 seulement)
    tailles_mains_adversaires: tuple = ()
    taille_pioche: int = 0

    @property
    def nb_total_inconnues(self) -> int:
        return sum(t.exemplaires_restants for t in self.tuiles.values()) \
            if self.tuiles else 0

    @property
    def nb_adversaires(self) -> int:
        return len(self.tailles_mains_adversaires)

    def lister(self) -> list:
        """Liste des tuiles inconnues (exemplaires_restants > 0), triée pour
        un affichage stable."""
        return sorted(self.tuiles.values(),
                      key=lambda t: (t.est_joker, t.cle))

    def exemplaires_restants(self, cle_ou_tuile) -> int:
        """Nombre d'exemplaires encore possibles d'une tuile donnée (0, 1 ou
        2 ; 2 pour un joker). Accepte une clé ``(couleur, valeur)``/
        ``CLE_JOKER`` ou directement une tuile (dict/``Tuile``). Permet de
        détecter qu'une tuile n'a plus de voisines utilisables (restants == 0,
        voir « Tuiles vivantes », CONTEXTE.md §13)."""
        cle = cle_ou_tuile if isinstance(cle_ou_tuile, tuple) \
            else _cle_tuile(cle_ou_tuile)
        t = self.tuiles.get(cle)
        return t.exemplaires_restants if t else 0


def calculer_inconnues(plateau, main, tailles_mains_adversaires,
                       taille_pioche) -> Inconnues:
    """Cœur du calcul : à partir du tapis (``plateau``, liste de tuiles ou de
    combinaisons), de la main du joueur (``main``, liste de tuiles) et des
    TAILLES des mains adverses + de la pioche (jamais leur contenu), calcule
    l'ensemble des tuiles inconnues avec leur nombre d'exemplaires restants.

    ``tailles_mains_adversaires`` : liste d'entiers (1 à 3 adversaires),
    nombre de tuiles de chaque adversaire, dans un ordre quelconque mais
    stable (voir :class:`Inconnues`).
    """
    vues = Counter(_cle_tuile(t) for t in _aplatir(plateau))
    vues.update(_cle_tuile(t) for t in main)

    tuiles = {}
    for cle in _toutes_les_cles():
        restants = _exemplaires_max(cle) - vues.get(cle, 0)
        if restants > 0:
            tuiles[cle] = TuileInconnue(cle, restants)

    return Inconnues(tuiles, tuple(tailles_mains_adversaires), taille_pioche)


def calculer_inconnues_depuis_etat(etat: dict, index_joueur: int) -> Inconnues:
    """Raccourci pratique : calcule les inconnues du joueur ``index_joueur``
    directement depuis l'état de partie complet (``moteur/partie.py``).

    N'utilise JAMAIS le contenu des chevalets adverses, seulement leur
    longueur (``len(...)``) — voir le garde-fou anti-triche en tête de ce
    module.
    """
    joueurs = etat.get("joueurs", [])
    main = joueurs[index_joueur].get("chevalet", [])
    tailles_adversaires = [len(j.get("chevalet", []))
                           for i, j in enumerate(joueurs) if i != index_joueur]
    taille_pioche = len(etat.get("pioche", []))
    return calculer_inconnues(etat.get("plateau", []), main,
                              tailles_adversaires, taille_pioche)


# --------------------------------------------------------------------------- #
# Probabilités
# --------------------------------------------------------------------------- #

def _hypergeometrique_au_moins_un(k: int, n: int, total: int) -> float:
    """Probabilité qu'au moins un exemplaire, parmi ``k`` répartis de façon
    uniforme (sans autre information) dans un ensemble de ``total`` tuiles
    inconnues, se trouve dans un sous-ensemble de taille ``n`` (une main
    adverse ou la pioche) : ``1 - C(total-k, n) / C(total, n)``."""
    if k <= 0 or n <= 0 or total <= 0:
        return 0.0
    if n >= total or total - k < n:
        return 1.0
    return 1.0 - (comb(total - k, n) / comb(total, n))


def proba_instance_chez_adversaire(inconnues: Inconnues,
                                   index_adversaire: int) -> float:
    """Probabilité uniforme qu'UNE tuile inconnue prise au hasard (un
    exemplaire précis) soit dans la main de l'adversaire ``index_adversaire``
    (position 0-based dans ``tailles_mains_adversaires``) : sans autre
    information, c'est la taille de sa main divisée par le nombre total de
    tuiles inconnues. Par linéarité, la somme de cette probabilité sur toutes
    les tuiles inconnues égale la taille de cette main — voir
    ``tests/test_inconnues.py::test_somme_probabilites_egale_taille_main``."""
    if inconnues.nb_total_inconnues == 0:
        return 0.0
    return (inconnues.tailles_mains_adversaires[index_adversaire]
            / inconnues.nb_total_inconnues)


def proba_instance_dans_pioche(inconnues: Inconnues) -> float:
    """Symétrique de :func:`proba_instance_chez_adversaire` pour la pioche."""
    if inconnues.nb_total_inconnues == 0:
        return 0.0
    return inconnues.taille_pioche / inconnues.nb_total_inconnues


def proba_tuile_chez_adversaire(inconnues: Inconnues, cle_ou_tuile,
                                index_adversaire: int) -> float:
    """Probabilité qu'AU MOINS UN exemplaire de la tuile (type) donnée soit
    dans la main de l'adversaire ``index_adversaire``."""
    k = inconnues.exemplaires_restants(cle_ou_tuile)
    n = inconnues.tailles_mains_adversaires[index_adversaire]
    return _hypergeometrique_au_moins_un(k, n, inconnues.nb_total_inconnues)


def proba_tuile_chez_un_adversaire_quelconque(inconnues: Inconnues,
                                              cle_ou_tuile) -> float:
    """Probabilité qu'AU MOINS UN exemplaire de la tuile (type) donnée soit
    chez N'IMPORTE LEQUEL des adversaires (pas la pioche)."""
    k = inconnues.exemplaires_restants(cle_ou_tuile)
    n = sum(inconnues.tailles_mains_adversaires)
    return _hypergeometrique_au_moins_un(k, n, inconnues.nb_total_inconnues)


def proba_tuile_dans_pioche(inconnues: Inconnues, cle_ou_tuile) -> float:
    """Probabilité qu'AU MOINS UN exemplaire de la tuile (type) donnée soit
    encore dans la pioche."""
    k = inconnues.exemplaires_restants(cle_ou_tuile)
    n = inconnues.taille_pioche
    return _hypergeometrique_au_moins_un(k, n, inconnues.nb_total_inconnues)


def proba_joker_chez_adversaire(inconnues: Inconnues,
                                index_adversaire: int) -> float:
    """Probabilité qu'au moins un des jokers encore inconnus soit chez
    l'adversaire ``index_adversaire`` (voir « Joker et réserve », §13)."""
    return proba_tuile_chez_adversaire(inconnues, CLE_JOKER, index_adversaire)


def proba_joker_chez_un_adversaire_quelconque(inconnues: Inconnues) -> float:
    """Probabilité qu'au moins un des jokers encore inconnus soit chez l'un
    quelconque des adversaires."""
    return proba_tuile_chez_un_adversaire_quelconque(inconnues, CLE_JOKER)


# --------------------------------------------------------------------------- #
# Diagnostic (vérification sur des parties réelles, issue #219 point 4)
# --------------------------------------------------------------------------- #

def diagnostiquer_coherence(plateau, main, tailles_mains_adversaires,
                            taille_pioche) -> list:
    """Liste des anomalies détectées dans les entrées (liste vide si tout est
    cohérent) : jamais d'exception levée, pour pouvoir passer en revue des
    journaux de parties incomplets ou corrompus sans interrompre l'analyse.

    Vérifie : qu'aucune tuile n'est vue plus de fois que son nombre
    d'exemplaires réels (2, 2 pour les jokers) ; que le nombre de tuiles
    inconnues calculé égale bien la somme des tailles de mains adverses et de
    la pioche (sinon, le tapis + la main contenaient déjà trop de tuiles
    d'un type donné, typiquement une incohérence du journal)."""
    anomalies = []
    vues = Counter(_cle_tuile(t) for t in _aplatir(plateau))
    vues.update(_cle_tuile(t) for t in main)
    for cle, n in vues.items():
        maxi = _exemplaires_max(cle)
        if n > maxi:
            anomalies.append(
                f"tuile {cle} vue {n} fois sur le tapis/en main (max {maxi})")

    inconnues = calculer_inconnues(plateau, main, tailles_mains_adversaires,
                                   taille_pioche)
    attendu = sum(tailles_mains_adversaires) + taille_pioche
    if inconnues.nb_total_inconnues != attendu:
        anomalies.append(
            f"nb de tuiles inconnues ({inconnues.nb_total_inconnues}) != "
            f"mains adverses + pioche ({attendu})")
    return anomalies
