"""Évaluation de la main restante d'Expert — critère de départage (issue #211).

À nombre de tuiles posées **égal**, deux coups d'Expert ne se valent pas
forcément : la main qu'ils laissent peut être plus ou moins facile à écouler au
tour suivant, et plus ou moins coûteuse si la manche se termine. Ce module
chiffre cette qualité de la main **restante** (ce qui resterait au chevalet
après le coup) par une pénalité — *plus elle est basse, meilleure est la main* —
combinant trois idées d'Alain (CONTEXTE.md §13, pistes 2/5/6/7) :

1. **Doublons** : deux tuiles identiques (même valeur, même couleur) ne peuvent
   jamais entrer dans la même combinaison, donc se placent plus difficilement.
   Pénalité par doublon restant.
2. **Tuiles de bord** : une tuile de valeur 1 ou 13 n'entre que dans **une**
   suite de trois (1-2-3, 11-12-13), une tuile 2 ou 12 dans deux, les valeurs
   3–11 dans trois. Moins une valeur entre dans de suites, plus elle est dure à
   placer : pénalité **graduée** ``penalite_bord(v) = 3 − nb_suites_trois(v)``
   (2 pour 1/13, 1 pour 2/12, 0 pour 3–11). Les groupes de même valeur sont
   possibles pour toutes les valeurs, donc n'entrent pas dans ce calcul.
3. **Points restants** : les tuiles de forte valeur restées en main s'ajoutent
   au score négatif du perdant. Le poids dépend du **nombre de manches** du
   match : quasi nul en une seule manche (les points ne départagent qu'une
   partie bloquée), non nul à partir de deux (score cumulé, issue #203).

Les **tuiles isolées** (sans voisine de même couleur ni de même valeur dans la
main) sont une quatrième idée ; elle ne se met PAS sous forme linéaire simple
dans le modèle exact (elle dépend du reste de la main, pas seulement des tuiles
posées), donc elle est **laissée de côté par défaut** (``POIDS_ISOLEE = 0``) et
seulement calculée par :func:`evaluer_main` à titre indicatif/pour les tests —
voir le rapport de #211 et la docstring de ``moteur/solveur_exact.py``.

Les **jokers** restants sont traités à part : un joker en main est une ressource
(il remplace n'importe quelle tuile), mais coûte 30 points en cas de défaite.
L'économie de jokers posés est déjà un critère de départage du modèle exact
(ne pas poser un joker de la main si une solution équivalente s'en passe) ; on
ne lui ajoute donc par défaut aucune pénalité de main (``POIDS_JOKER = 0``).

Deux usages, cohérents par construction :

* :func:`evaluer_main` — fonction **indépendante** du solveur : prend la main
  qui resterait et renvoie une pénalité. Sert aux tests sur mains fabriquées et
  à l'affichage ; **n'est pas** appelée en boucle par le solveur.
* Le modèle exact (``moteur/solveur_exact.py``) n'applique PAS cette fonction
  après coup : il **linéarise** les mêmes termes sur les tuiles qui resteraient
  en main (variables de tuiles non posées, + une variable auxiliaire par type
  pour les doublons) et les ajoute comme objectif secondaire, JAMAIS avant le
  nombre de tuiles posées. Les poids ci-dessous sont partagés par les deux.

**Tous les poids réglables sont réunis ici**, en tête de module (point 4 de
l'issue : réglages faciles à modifier, en un seul endroit).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from rummikub.config import VALEUR_MIN, VALEUR_MAX


# --------------------------------------------------------------------------- #
# POIDS RÉGLABLES — tout est ici (issue #211, point 4)
# --------------------------------------------------------------------------- #
# Poids ENTIERS : le modèle exact fixe l'optimum de l'évaluation par une
# contrainte d'égalité sur la valeur (entière) de l'objectif entre deux passes
# lexicographiques. Des coefficients entiers garantissent un départage exact
# (pas d'arrondi), comme les autres critères du solveur.

#: Pénalité par doublon restant (paire identique, même valeur même couleur).
POIDS_DOUBLON = 3

#: Multiplicateur de la pénalité graduée de bord (voir :func:`penalite_bord`).
POIDS_BORD = 2

#: Poids des points restants en match d'**une seule** manche (quasi nul : les
#: points ne départagent qu'une partie bloquée — CONTEXTE.md §13, piste 5).
POIDS_POINTS_1_MANCHE = 0

#: Poids des points restants à partir de **deux** manches (score cumulé — les
#: points comptent vraiment, issue #203). Réglable ; la simulation de #211
#: mesure à partir de quel poids attacher trop d'importance aux points fait
#: perdre des parties (voir CONTEXTE.md §13).
POIDS_POINTS_N_MANCHES = 1

#: Pénalité par tuile isolée. Laissée à 0 : approximation documentée, non
#: linéarisable simplement dans le modèle exact (voir l'en-tête du module).
POIDS_ISOLEE = 0

#: Pénalité par joker restant en main. Laissée à 0 : le joker est une ressource,
#: et l'économie de jokers POSÉS est déjà un critère de départage du solveur.
POIDS_JOKER = 0

#: Position par défaut de l'évaluation parmi les départages du modèle exact,
#: relativement à la simplicité/perturbation (#199). Deux ordres sont testés par
#: simulation (issue #211, point 2) : ``"apres_simplicite"`` ne complique jamais
#: le plateau pour un gain d'évaluation ; ``"avant_simplicite"`` privilégie la
#: main au prix d'un plateau éventuellement plus remué.
POSITION_DEFAUT = "apres_simplicite"


# --------------------------------------------------------------------------- #
# Primitives de bord
# --------------------------------------------------------------------------- #

def nb_suites_trois(valeur: int) -> int:
    """Nombre de suites de **trois** tuiles consécutives (d'une couleur donnée)
    contenant ``valeur`` : 1 pour 1 et 13, 2 pour 2 et 12, 3 pour 3 à 11."""
    bas = max(VALEUR_MIN, valeur - 2)
    haut = min(VALEUR_MAX - 2, valeur)
    return max(0, haut - bas + 1)


def penalite_bord(valeur: int) -> int:
    """Pénalité de bord d'une valeur : ``3 − nb_suites_trois(valeur)`` →
    2 pour 1/13, 1 pour 2/12, 0 pour 3–11 (un bord entre dans moins de suites,
    donc se place plus difficilement)."""
    return 3 - nb_suites_trois(valeur)


# --------------------------------------------------------------------------- #
# Configuration (poids + critères actifs + nombre de manches)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ConfigEvaluation:
    """Réglage de l'évaluation de la main pour un coup donné.

    ``active`` : si faux, l'évaluation n'est pas appliquée du tout (Expert
    départage comme avant #211 : simplicité, points posés, jokers). ``doublons``
    / ``bords`` / ``points`` : active chaque critère séparément (pour mesurer
    lequel apporte un gain). ``poids_points`` à ``None`` dérive le poids du
    nombre de manches ; sinon il le force (sweep de la simulation)."""

    active: bool = False
    doublons: bool = True
    bords: bool = True
    points: bool = True
    isolees: bool = False
    poids_doublon: int = POIDS_DOUBLON
    poids_bord: int = POIDS_BORD
    poids_points: int | None = None      # None → dérivé de nb_manches
    poids_isolee: int = POIDS_ISOLEE
    poids_joker: int = POIDS_JOKER
    position: str = POSITION_DEFAUT
    nb_manches: int = 1

    def poids_points_effectif(self) -> int:
        """Poids des points réellement appliqué : ``poids_points`` s'il est
        fixé, sinon le poids selon le nombre de manches."""
        if self.poids_points is not None:
            return self.poids_points
        return (POIDS_POINTS_N_MANCHES if self.nb_manches >= 2
                else POIDS_POINTS_1_MANCHE)

    def avec_manches(self, nb_manches: int) -> "ConfigEvaluation":
        """Copie du réglage ajustée au nombre de manches du match courant."""
        return replace(self, nb_manches=max(1, int(nb_manches)))

    @property
    def avant_simplicite(self) -> bool:
        return self.position == "avant_simplicite"


#: Réglage par défaut d'Expert (issue #211, point 4 : n'activer par défaut que
#: les critères au gain démontré). Voir CONTEXTE.md §13 et le rapport de #211
#: pour la justification chiffrée du choix ``active``.
DEFAUT = ConfigEvaluation(active=False)


# --------------------------------------------------------------------------- #
# Fabrique de configurations nommées (presets de la simulation)
# --------------------------------------------------------------------------- #

def depuis_preset(nom: str, nb_manches: int = 1) -> ConfigEvaluation:
    """Construit une :class:`ConfigEvaluation` à partir d'un nom de preset,
    utilisé par ``scripts/comparer_niveaux_ia.py`` (options ``--eval-a/-b``)
    pour comparer, en miroir, deux réglages d'Expert dans une même campagne.

    Presets : ``off`` (base, #211 désactivé) ; ``complet`` (doublons+bords+
    points, poids par défaut) ; ``doublons`` / ``bords`` / ``points`` (un seul
    critère) ; ``points-nul`` / ``points-faible`` / ``points-moyen`` /
    ``points-fort`` (points seuls, poids 0/1/3/8) ; suffixe ``-avant`` pour
    placer l'évaluation AVANT la simplicité (ex. ``complet-avant``)."""
    base = nom
    position = POSITION_DEFAUT
    if base.endswith("-avant"):
        base = base[: -len("-avant")]
        position = "avant_simplicite"
    elif base.endswith("-apres"):
        base = base[: -len("-apres")]
        position = "apres_simplicite"

    presets = {
        "off": dict(active=False),
        "complet": dict(active=True, doublons=True, bords=True, points=True),
        "doublons": dict(active=True, doublons=True, bords=False, points=False),
        "bords": dict(active=True, doublons=False, bords=True, points=False),
        "points": dict(active=True, doublons=False, bords=False, points=True),
        "points-nul": dict(active=True, doublons=False, bords=False,
                           points=True, poids_points=0),
        "points-faible": dict(active=True, doublons=False, bords=False,
                              points=True, poids_points=1),
        "points-moyen": dict(active=True, doublons=False, bords=False,
                             points=True, poids_points=3),
        "points-fort": dict(active=True, doublons=False, bords=False,
                            points=True, poids_points=8),
    }
    if base not in presets:
        raise ValueError(f"preset d'évaluation inconnu : {nom!r}")
    return ConfigEvaluation(position=position, nb_manches=max(1, int(nb_manches)),
                            **presets[base])


PRESETS = ("off", "complet", "doublons", "bords", "points",
           "points-nul", "points-faible", "points-moyen", "points-fort")


# --------------------------------------------------------------------------- #
# Évaluation d'une main (fonction indépendante du solveur — tests & affichage)
# --------------------------------------------------------------------------- #

def _compter(tuiles):
    """``({(couleur, valeur): compte}, nb_jokers)`` d'une liste de Tuile."""
    comptes: dict = {}
    njok = 0
    for t in tuiles:
        if getattr(t, "est_joker", False):
            njok += 1
        else:
            cle = (t.couleur, t.valeur)
            comptes[cle] = comptes.get(cle, 0) + 1
    return comptes, njok


def nb_doublons(tuiles) -> int:
    """Nombre de doublons restants : une paire identique compte pour 1."""
    comptes, _ = _compter(tuiles)
    return sum(c - 1 for c in comptes.values() if c >= 2)


def tuiles_isolees(tuiles) -> list:
    """Tuiles sans voisine de même couleur (valeur ±1) NI de même valeur (autre
    couleur) dans la main. Les jokers ne sont jamais isolés. Sert à
    :func:`evaluer_main` et aux tests ; non utilisée par le modèle exact."""
    comptes, _ = _compter(tuiles)
    isolees = []
    for t in tuiles:
        if getattr(t, "est_joker", False):
            continue
        c, v = t.couleur, t.valeur
        voisin_couleur = (comptes.get((c, v - 1), 0) > 0
                          or comptes.get((c, v + 1), 0) > 0)
        # Voisine de même valeur : une autre couleur, ou un second exemplaire.
        meme_valeur = sum(n for (cc, vv), n in comptes.items() if vv == v)
        voisin_valeur = meme_valeur - comptes.get((c, v), 0) > 0 \
            or comptes.get((c, v), 0) >= 2
        if not voisin_couleur and not voisin_valeur:
            isolees.append(t)
    return isolees


def evaluer_main(tuiles, config: ConfigEvaluation = DEFAUT) -> float:
    """Pénalité de la main ``tuiles`` (plus basse = meilleure main), selon les
    critères actifs de ``config`` et son poids de points effectif.

    Cohérente par construction avec la linéarisation du modèle exact : la somme
    des pénalités par tuile (bords, points) retirées en posant des tuiles
    correspond exactement aux termes maximisés par le solveur ; les doublons
    suivent la même règle (une paire = 1). Indépendante du solveur : utilisable
    sur n'importe quelle liste de Tuile."""
    comptes, njok = _compter(tuiles)
    score = 0.0
    if config.doublons:
        score += config.poids_doublon * sum(
            c - 1 for c in comptes.values() if c >= 2)
    if config.bords:
        score += config.poids_bord * sum(
            penalite_bord(v) * n for (_c, v), n in comptes.items())
    if config.points:
        score += config.poids_points_effectif() * sum(
            v * n for (_c, v), n in comptes.items())
    if config.isolees and config.poids_isolee:
        score += config.poids_isolee * len(tuiles_isolees(tuiles))
    if config.poids_joker:
        score += config.poids_joker * njok
    return score
