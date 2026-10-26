"""Solveur de réarrangement global du plateau (issue #186, suite de #184).

Contrairement aux tactiques de `ia.py` (motifs locaux : échange de joker,
scission d'une suite...), ce solveur reconstruit l'intégralité du plateau
depuis zéro : toutes les tuiles actuellement posées + toutes celles du
chevalet forment un seul « sac » dans lequel on recherche une partition en
combinaisons valides qui respecte une seule contrainte dure — aucune tuile du
PLATEAU ne peut être oubliée (elle peut changer de combinaison, jamais
disparaître) — en posant le plus grand nombre possible de tuiles du
chevalet.

Principe de l'algorithme
------------------------
On ne raisonne jamais sur les tuiles physiques (``Tuile.id``) mais sur des
« emplacements » ``(couleur, valeur)`` — il existe au plus 2 tuiles réelles
par emplacement (deux jeux), interchangeables pour la validité d'une
combinaison. Chaque emplacement porte deux compteurs : ``total`` (nombre de
tuiles disponibles, plateau + chevalet) et ``obligatoire`` (nombre de tuiles
du PLATEAU parmi elles, qui doivent impérativement finir dans une
combinaison). Les 2 jokers du jeu sont suivis à part, de la même façon.

La recherche choisit à chaque étape un emplacement non encore traité :
- s'il reste un emplacement **obligatoire** (tuile du plateau pas encore
  replacée), on est FORCÉ de choisir une combinaison qui l'utilise (groupe ou
  suite) — si aucune n'existe, cette branche échoue (aucune tuile du plateau
  ne doit disparaître) ;
- sinon, les emplacements restants ne contiennent que des tuiles du
  chevalet : on peut soit les ignorer (elles restent en main), soit tenter de
  les poser dans une nouvelle combinaison — les deux branches sont
  explorées, la meilleure retenue.

Chaque choix réduit strictement l'état (compteurs décroissants), avec
mémoïsation sur une empreinte canonique de l'état pour éviter de ré-explorer
deux fois la même situation (fréquent : deux zones indépendantes du plateau
peuvent être traitées dans un ordre ou dans l'autre, menant au même état
résiduel).

Le nombre de combinaisons du plateau pertinentes pour la main (voir
``_separer_combos_figees``) grandit avec la partie, et avec lui le nombre de
branches à explorer — en milieu/fin de partie, l'arbre complet dépasse
largement ce qu'un budget d'une à deux secondes permet de parcourir en
entier. Deux mesures en atténuent l'effet plutôt que de le supprimer
(mesuré, documenté dans le rapport de clôture #186) :
- les candidats de chaque emplacement sont essayés dans l'ordre décroissant
  de tuiles de main consommées (:func:`_score_rapide`) — le plafond
  optimiste (:func:`_main_disponible`) est alors atteint, et la branche
  coupée (``break``), beaucoup plus tôt que dans un ordre arbitraire ;
- si le budget de temps s'épuise EN COURS d'exploration d'un nœud, la
  meilleure branche déjà trouvée À CE NIVEAU est conservée (réarrangement
  valide, pas nécessairement optimal) plutôt que de tout perdre en
  laissant :class:`BudgetDepasse` remonter jusqu'à l'appelant — l'ancien
  comportement (tout ou rien) revenait, dès que le budget était dépassé
  n'importe où dans l'arbre, à jouer EXACTEMENT comme le niveau Avancé pour
  ce tour, ce qui annulait l'essentiel de l'apport du solveur en
  milieu/fin de partie. :class:`BudgetDepasse` n'est donc plus levée que
  si AUCUNE branche n'a abouti nulle part dans l'arbre avant expiration du
  budget (repli sur Avancé toujours nécessaire dans ce cas précis — voir
  :func:`resoudre_coup`).

Une troisième mesure (#190, suite de #187) complète les deux ci-dessus sur
les plateaux chargés : sur un emplacement obligatoire (tuile du plateau à
replacer), la plupart des candidats ex-aequo au premier critère de tri
n'utilisent aucune tuile de la main — ils ne se distinguaient donc pas entre
eux, et la recherche pouvait en essayer un qui restructure inutilement une
zone du plateau étrangère à la main avant celui, trivial, qui reconduit la
combinaison déjà posée (voir ``_signatures_originales``). Chaque candidat
porte désormais une signature ``(type, couleur/valeur, taille)`` ; parmi les
ex-aequo, celui qui reproduit une combinaison déjà posée avant ce tour est
tenté EN PREMIER, ce qui réduit fortement les impasses/retours en arrière
sur ces zones et donc le temps nécessaire pour trouver un premier
réarrangement complet. Ni ce critère ni les deux précédents ne changent
jamais le résultat optimal trouvé avec un budget suffisant — seulement la
vitesse pour l'atteindre, et, en cas d'égalité stricte du critère de
départage ci-dessous, lequel des réarrangements équivalents est renvoyé.

Simplification volontaire (documentée, pas une approximation aléatoire) :
pour une suite ancrée sur une tuile réelle précise, les positions
intermédiaires utilisent la tuile réelle disponible dès qu'il y en a une, et
un joker seulement en son absence — on n'explore pas la variante « joker à
la place d'une tuile réelle disponible » (qui libérerait cette tuile pour
ailleurs) sous CE même angle de recherche : cette possibilité reste couverte
quand la recherche explore l'emplacement de cette tuile réelle sous un autre
angle (une autre combinaison, un autre intervalle). Ceci borne la
combinatoire sans empêcher de retrouver les tactiques déjà implémentées
(voir tests).

Critère de départage (quand plusieurs réarrangements posent le même nombre
de tuiles du chevalet) : on choisit d'abord celui qui rapporte le plus de
points posés (valeur des tuiles du chevalet effectivement jouées — voir
``mise_initiale_min``), puis, à égalité, celui qui utilise le MOINS de
jokers du chevalet — un joker reste une ressource précieuse même quand il
ne change pas le nombre de tuiles posées ce tour-ci, mieux vaut le garder en
main pour plus tard.
"""

import time
from collections import deque
from itertools import combinations

from rummikub.config import COULEURS, VALEUR_MIN, VALEUR_MAX
from rummikub.moteur.partie import tuile_depuis_dict, plateau_depuis_dict, \
    _plateau_vers_dict


class BudgetDepasse(Exception):
    """Levée quand le budget de temps s'épuise avant qu'AUCUNE branche de la
    recherche n'ait abouti (voir ``_resoudre``) — si au moins une branche a
    déjà trouvé un réarrangement valide ailleurs dans l'arbre, celui-ci est
    renvoyé normalement plutôt que de lever cette exception."""


# --------------------------------------------------------------------------- #
# Construction / manipulation de l'état (compteurs par emplacement)
# --------------------------------------------------------------------------- #

_COULEUR_IDX = {c: i for i, c in enumerate(COULEURS)}


def _ordre_slot(slot):
    return (_COULEUR_IDX[slot[0]], slot[1])


def _construire_etat(plateau, chevalet):
    """plateau/chevalet : listes de Tuile. Retourne (comptes, jokers) ::

        comptes : {(couleur, valeur): (total, obligatoire)}
        jokers  : (total, obligatoire)
    """
    comptes = {}
    jokers_total = 0
    jokers_obligatoire = 0

    def ajouter(t, obligatoire):
        nonlocal jokers_total, jokers_obligatoire
        if t.est_joker:
            jokers_total += 1
            if obligatoire:
                jokers_obligatoire += 1
            return
        cle = (t.couleur, t.valeur)
        total, obl = comptes.get(cle, (0, 0))
        total += 1
        if obligatoire:
            obl += 1
        comptes[cle] = (total, obl)

    for combo in plateau:
        for t in combo:
            ajouter(t, True)
    for t in chevalet:
        ajouter(t, False)
    return comptes, (jokers_total, jokers_obligatoire)


def _snapshot(comptes, jokers):
    """Empreinte canonique (pour mémoïsation) : un tuple de taille fixe,
    dans l'ordre COULEURS x VALEUR, bien moins coûteux à construire qu'un
    tri du dictionnaire (appelé à chaque nœud de la recherche)."""
    return (tuple(comptes.get((c, v), (0, 0))
                  for c in COULEURS for v in range(VALEUR_MIN, VALEUR_MAX + 1)),
            jokers)


def _prochaine_cible(comptes, jokers):
    """Prochain emplacement à traiter : (nature, info, obligatoire) ou None
    si plus rien ne reste. Priorité stricte aux emplacements obligatoires
    (tuiles du plateau), jokers obligatoires compris."""
    if jokers[1] > 0:
        return ("joker", None, True)
    slots_obligatoires = [s for s, (_, obl) in comptes.items() if obl > 0]
    if slots_obligatoires:
        return ("slot", min(slots_obligatoires, key=_ordre_slot), True)
    if jokers[0] > 0:
        return ("joker", None, False)
    if comptes:
        return ("slot", min(comptes, key=_ordre_slot), False)
    return None


# --------------------------------------------------------------------------- #
# Génération des combinaisons candidates
# --------------------------------------------------------------------------- #
#
# Chaque candidat porte une « signature » (type, couleur/valeur, taille) —
# voir ``_signatures_originales`` : elle sert uniquement à repérer, parmi
# les candidats qui n'utilisent AUCUNE tuile de la main (ex-aequo à 0 sur
# ``_score_rapide``), ceux qui reproduisent une combinaison déjà posée sur
# le plateau avant ce tour. Les tenter en premier parmi ces ex-aequo évite
# à la recherche de restructurer, par essais-erreurs coûteux, des zones du
# plateau que la main ne concerne pas vraiment (voir rapport #190).


def _candidats_groupe(comptes, jokers_total, valeur, couleur_forcee):
    """Groupes contenant obligatoirement ``(couleur_forcee, valeur)``."""
    disponibles = [c for c in COULEURS if comptes.get((c, valeur), (0, 0))[0] > 0]
    if couleur_forcee not in disponibles:
        return []
    autres = [c for c in disponibles if c != couleur_forcee]
    resultats = []
    for taille in (3, 4):
        for avec_joker in (False, True):
            if avec_joker and jokers_total <= 0:
                continue
            nb_reel = taille - (1 if avec_joker else 0)
            nb_autres = nb_reel - 1
            if nb_autres < 0 or nb_autres > len(autres):
                continue
            for combo in combinations(autres, nb_autres):
                tokens = [("T", c, valeur) for c in (couleur_forcee,) + combo]
                if avec_joker:
                    tokens.append(("J",))
                resultats.append({"tokens": tokens,
                                  "signature": ("groupe", valeur, taille)})
    return resultats


def _candidats_groupe_joker(comptes, jokers_total):
    """Groupes utilisant obligatoirement un joker (pas d'emplacement réel
    forcé — recherché quand un joker lui-même doit être replacé)."""
    if jokers_total <= 0:
        return []
    resultats = []
    for valeur in range(VALEUR_MIN, VALEUR_MAX + 1):
        disponibles = [c for c in COULEURS if comptes.get((c, valeur), (0, 0))[0] > 0]
        for taille in (3, 4):
            nb_reel = taille - 1
            if nb_reel < 2 or nb_reel > len(disponibles):
                continue
            for combo in combinations(disponibles, nb_reel):
                tokens = [("T", c, valeur) for c in combo] + [("J",)]
                resultats.append({"tokens": tokens,
                                  "signature": ("groupe", valeur, taille)})
    return resultats


# Largeur maximale, de part et d'autre de l'ancre, des suites candidates
# (``_candidats_suite``) : limite volontaire pour borner la combinatoire —
# toutes les tactiques couvertes (détachement en bout, scission en milieu,
# démantèlement #175...) ne déplacent jamais la frontière d'une suite de
# plus de quelques valeurs par rapport à la tuile/joker concerné·e ; une
# suite plus longue que cette fenêtre reste couverte en la redécoupant en
# plusieurs plus courtes au fil de la récursion (résultat toujours valide,
# simplement découpé différemment quand aucune tuile de la main n'est en
# jeu sur la portion éloignée de l'ancre).
_FENETRE_SUITE = 5


def _candidats_suite(comptes, jokers_total, couleur, valeur_ancre):
    """Suites contenant obligatoirement une tuile réelle en
    ``(couleur, valeur_ancre)``. Les autres positions de l'intervalle
    utilisent la tuile réelle disponible, sinon un joker (voir docstring du
    module)."""
    resultats = []
    for v1 in range(max(VALEUR_MIN, valeur_ancre - _FENETRE_SUITE), valeur_ancre + 1):
        for v2 in range(valeur_ancre,
                         min(VALEUR_MAX, valeur_ancre + _FENETRE_SUITE) + 1):
            if v2 - v1 + 1 < 3:
                continue
            tokens, nb_jokers, ok, precedent_joker = [], 0, True, False
            for v in range(v1, v2 + 1):
                if v == valeur_ancre or comptes.get((couleur, v), (0, 0))[0] > 0:
                    tokens.append(("T", couleur, v))
                    precedent_joker = False
                else:
                    if precedent_joker:
                        ok = False
                        break
                    tokens.append(("J",))
                    nb_jokers += 1
                    precedent_joker = True
            if ok and nb_jokers <= jokers_total:
                resultats.append({"tokens": tokens,
                                  "signature": ("suite", couleur, v2 - v1 + 1)})
    return resultats


def _candidats_suite_joker(comptes, jokers_total):
    """Suites utilisant obligatoirement un joker, toutes couleurs/intervalles
    confondus (recherché quand un joker lui-même doit être replacé)."""
    if jokers_total <= 0:
        return []
    resultats = []
    for couleur in COULEURS:
        for v1 in range(VALEUR_MIN, VALEUR_MAX + 1):
            for v2 in range(v1 + 2, VALEUR_MAX + 1):
                tokens, nb_jokers, ok, precedent_joker = [], 0, True, False
                for v in range(v1, v2 + 1):
                    if comptes.get((couleur, v), (0, 0))[0] > 0:
                        tokens.append(("T", couleur, v))
                        precedent_joker = False
                    else:
                        if precedent_joker:
                            ok = False
                            break
                        tokens.append(("J",))
                        nb_jokers += 1
                        precedent_joker = True
                if ok and 1 <= nb_jokers <= jokers_total:
                    resultats.append({"tokens": tokens,
                                      "signature": ("suite", couleur, v2 - v1 + 1)})
    return resultats


# --------------------------------------------------------------------------- #
# Application d'une combinaison candidate à l'état
# --------------------------------------------------------------------------- #

def _appliquer(comptes, jokers, cand):
    """Retire les tuiles de ``cand`` de l'état ; retourne le nouvel état et
    le gain ``(tuiles_main, points, -jokers_main)`` apporté par ce choix."""
    comptes = dict(comptes)
    jt, jo = jokers
    tuiles_main = 0
    points = 0
    jokers_main = 0
    for tok in cand["tokens"]:
        if tok[0] == "T":
            _, c, v = tok
            total, obl = comptes[(c, v)]
            if obl > 0:
                obl -= 1
            else:
                tuiles_main += 1
                points += v
            total -= 1
            if total == 0:
                del comptes[(c, v)]
            else:
                comptes[(c, v)] = (total, obl)
        else:
            if jo > 0:
                jo -= 1
            else:
                tuiles_main += 1
                jokers_main += 1
            jt -= 1
    return comptes, (jt, jo), (tuiles_main, points, -jokers_main)


# --------------------------------------------------------------------------- #
# Recherche mémoïsée avec budget de temps
# --------------------------------------------------------------------------- #

class _Contexte:
    def __init__(self, budget_temps, cle=lambda v: v, signatures_originales=frozenset()):
        self.limite = time.monotonic() + budget_temps
        self.appels = 0
        self.memo = {}
        self.cle = cle  # fonction de comparaison du triplet de valeur
        # Signatures (voir ``_signatures_originales``) des combinaisons déjà
        # posées sur le plateau avant ce tour — utilisées pour prioriser les
        # candidats ex-aequo sur ``_score_rapide`` (voir ``_resoudre``).
        self.signatures_originales = signatures_originales

    def verifier_budget(self):
        self.appels += 1
        # Vérifié dès le 1er appel (budget nul ou déjà expiré : utile pour
        # les plateaux triviaux, qui ne feraient sinon jamais 50 appels),
        # puis tous les 50 — l'horloge coûte plus cher qu'un nœud de
        # recherche, pas la peine de la lire à chaque appel.
        if (self.appels == 1 or self.appels % 50 == 0) \
                and time.monotonic() > self.limite:
            raise BudgetDepasse()


def _somme(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _score_rapide(comptes, jokers, cand):
    """Estimation rapide (sans appliquer ``cand``) du nombre de tuiles du
    CHEVALET que cette combinaison consommerait. Utilisée uniquement pour
    trier les candidats avant de les explorer (voir ``_resoudre``) : essayer
    d'abord les combinaisons qui utilisent le plus la main fait atteindre le
    plafond optimiste (``_main_disponible``) bien plus vite, ce qui
    déclenche le `break` de coupure beaucoup plus tôt sur les plateaux
    chargés — l'ordre d'exploration ne change jamais le résultat trouvé,
    seulement la vitesse pour l'atteindre."""
    _, jo = jokers
    score = 0
    for tok in cand["tokens"]:
        if tok[0] == "T":
            if comptes.get((tok[1], tok[2]), (0, 0))[1] == 0:
                score += 1
        elif jo == 0:
            score += 1
    return score


def _main_disponible(comptes, jokers):
    """Nombre total de tuiles du CHEVALET encore posables depuis cet état
    (borne optimiste : aucun réarrangement ne peut en poser davantage).
    Utilisée pour arrêter la recherche dès qu'une branche l'atteint —
    aucune autre branche ne pourra alors faire mieux."""
    total = jokers[0] - jokers[1]
    for total_slot, obl_slot in comptes.values():
        total += total_slot - obl_slot
    return total


def _resoudre(comptes, jokers, ctx):
    ctx.verifier_budget()
    etat = _snapshot(comptes, jokers)
    if etat in ctx.memo:
        return ctx.memo[etat]

    cible = _prochaine_cible(comptes, jokers)
    if cible is None:
        resultat = ((0, 0, 0), [])
        ctx.memo[etat] = resultat
        return resultat

    nature, info, obligatoire = cible
    meilleur = None
    plafond = _main_disponible(comptes, jokers)

    if not obligatoire:
        # Branche « abandon » : cette ressource optionnelle reste en main.
        if nature == "joker":
            sous = _resoudre(comptes, (0, 0), ctx)
        else:
            comptes_sans = dict(comptes)
            del comptes_sans[info]
            sous = _resoudre(comptes_sans, jokers, ctx)
        meilleur = sous

    if nature == "slot":
        couleur, valeur = info
        candidats = (_candidats_groupe(comptes, jokers[0], valeur, couleur)
                     + _candidats_suite(comptes, jokers[0], couleur, valeur))
    else:
        candidats = (_candidats_groupe_joker(comptes, jokers[0])
                     + _candidats_suite_joker(comptes, jokers[0]))
    # Essayer d'abord les candidats qui consomment le plus la main : atteint
    # le plafond optimiste (donc le `break` ci-dessous) beaucoup plus vite
    # sur les plateaux chargés (voir _score_rapide). Parmi les ex-aequo (le
    # plus souvent des candidats à 0, qui ne consomment aucune tuile de la
    # main pour CE nœud), préférer ceux qui reproduisent une combinaison
    # déjà posée avant ce tour (voir ``_signatures_originales``) : cela
    # évite de restructurer, par essais-erreurs, des zones du plateau que
    # la main ne concerne pas — c'est la principale source de backtracking
    # coûteux sur un plateau chargé (voir rapport #190). Ni l'un ni l'autre
    # critère ne change le résultat OPTIMAL trouvé, seulement la vitesse et,
    # en cas d'égalité stricte sur la valeur de départage, lequel des
    # réarrangements équivalents est renvoyé.
    candidats.sort(key=lambda c: (_score_rapide(comptes, jokers, c),
                                  c["signature"] in ctx.signatures_originales),
                   reverse=True)

    for cand in candidats:
        if meilleur is not None and meilleur[0][0] >= plafond:
            break  # aucune autre branche ne peut faire mieux (borne atteinte)
        nouveaux_comptes, nouveaux_jokers, gain = _appliquer(comptes, jokers, cand)
        try:
            sous = _resoudre(nouveaux_comptes, nouveaux_jokers, ctx)
        except BudgetDepasse:
            # Budget épuisé en cours d'exploration de ce nœud : si une
            # branche précédente a déjà abouti, on la garde (réarrangement
            # valide mais pas nécessairement optimal) plutôt que de perdre
            # tout le travail accompli par la remontée de l'exception
            # jusqu'au tour de jeu (ancien comportement : repli total sur
            # Avancé) — voir rapport de clôture #186. Rien à garder → on
            # relaie l'échec au nœud parent, qui prendra la même décision.
            if meilleur is None:
                raise
            break
        if sous is None:
            continue
        valeur_totale = _somme(gain, sous[0])
        if meilleur is None or ctx.cle(valeur_totale) > ctx.cle(meilleur[0]):
            meilleur = (valeur_totale, [cand] + sous[1])

    ctx.memo[etat] = meilleur
    return meilleur


# --------------------------------------------------------------------------- #
# Reconstruction des tuiles physiques depuis la solution abstraite
# --------------------------------------------------------------------------- #

def _reconstruire(plateau, chevalet, combos_solution):
    pools = {}
    jokers_plateau, jokers_main = deque(), deque()

    def ranger(t, depuis_plateau):
        if t.est_joker:
            (jokers_plateau if depuis_plateau else jokers_main).append(t)
            return
        cle = (t.couleur, t.valeur)
        p, m = pools.setdefault(cle, ([], []))
        (p if depuis_plateau else m).append(t)

    for combo in plateau:
        for t in combo:
            ranger(t, True)
    for t in chevalet:
        ranger(t, False)

    ids_main = []
    nouveau_plateau = []
    for spec in combos_solution:
        combo_tuiles = []
        for tok in spec["tokens"]:
            if tok[0] == "T":
                _, c, v = tok
                p, m = pools[(c, v)]
                if p:
                    t = p.pop()
                else:
                    t = m.pop()
                    ids_main.append(t.id)
            else:
                if jokers_plateau:
                    t = jokers_plateau.pop()
                else:
                    t = jokers_main.pop()
                    ids_main.append(t.id)
            combo_tuiles.append(t)
        nouveau_plateau.append(combo_tuiles)
    return nouveau_plateau, ids_main


def _signatures_originales(plateau):
    """Ensemble des signatures ``(type, couleur/valeur, taille)`` des
    combinaisons FLEXIBLES du plateau avant ce tour (voir ``_resoudre`` et
    la génération des candidats). Une signature n'identifie pas une
    combinaison précise (deux suites rouges de 4 tuiles à des intervalles
    différents partagent la même signature) : c'est volontaire, il s'agit
    seulement de repérer « une forme qui existait déjà », pas de retrouver
    LA combinaison d'origine tuile pour tuile."""
    signatures = set()
    for combo in plateau:
        non_jokers = [t for t in combo if not t.est_joker]
        if not non_jokers:
            continue
        valeurs = {t.valeur for t in non_jokers}
        if len(valeurs) == 1:
            signatures.add(("groupe", next(iter(valeurs)), len(combo)))
        else:
            signatures.add(("suite", non_jokers[0].couleur, len(combo)))
    return signatures


# --------------------------------------------------------------------------- #
# Réduction de la taille du problème : combinaisons « gelées »
# --------------------------------------------------------------------------- #

def _separer_combos_figees(plateau, chevalet):
    """Sépare le plateau en combinaisons flexibles (soumises à la
    recherche) et gelées (reconduites telles quelles, en dehors de la
    recherche).

    Un réarrangement ne peut poser plus de tuiles que n'en offre le
    chevalet : une combinaison qui ne partage AUCUNE couleur ni valeur avec
    la moindre tuile du chevalet ne peut jamais être exploitée par les
    tactiques couvertes ici (échange, détachement, scission...), qui
    exigent toutes une tuile de la main de même couleur (suite) ou même
    valeur (groupe) que la combinaison modifiée. La geler évite à la
    recherche de re-découper inutilement tout le plateau à chaque tour — le
    principal facteur de ralentissement en milieu/fin de partie, quand de
    nombreuses combinaisons déjà posées n'ont plus rien à voir avec la main
    courante. Simplification documentée : un réarrangement qui ne
    s'enclencherait qu'à travers une chaîne de plusieurs combinaisons sans
    aucune ne partageant couleur/valeur avec la main ne sera pas trouvé
    (cas non rencontré par les scénarios couverts par les tests).

    Si la main contient un joker, AUCUNE combinaison n'est gelée : un joker
    peut compléter n'importe quelle couleur ou valeur. De même, une
    combinaison du plateau contenant déjà un joker n'est JAMAIS gelée,
    même sans aucune couleur/valeur commune avec la main : le libérer par
    détachement ou scission (#150/#181) ne consomme aucune tuile de la
    main sur CETTE combinaison, seule sa destination (ailleurs) dépend de
    la main.
    """
    if any(t.est_joker for t in chevalet):
        return list(plateau), []
    couleurs_main = {t.couleur for t in chevalet if not t.est_joker}
    valeurs_main = {t.valeur for t in chevalet if not t.est_joker}
    flexibles, gelees = [], []
    for combo in plateau:
        pertinent = any(
            t.est_joker
            or t.couleur in couleurs_main or t.valeur in valeurs_main
            for t in combo)
        (flexibles if pertinent else gelees).append(combo)
    return flexibles, gelees


# --------------------------------------------------------------------------- #
# API publique
# --------------------------------------------------------------------------- #

def _meilleur_rearrangement(plateau, chevalet, budget_temps, mise_min=None,
                             deux_passes=False):
    """Lance la recherche. Si ``deux_passes``, fait d'abord une passe
    maximisant le nombre de tuiles, puis, si ses points posés sont
    insuffisants (< ``mise_min``), une seconde passe maximisant les points —
    seule façon d'ouvrir quand le réarrangement le plus large ne couvre pas
    la mise initiale (voir docstring du module : limite documentée, pas
    nécessairement l'optimum exact sous cette contrainte)."""
    comptes, jokers = _construire_etat(plateau, chevalet)
    signatures = _signatures_originales(plateau)
    limite = time.monotonic() + budget_temps

    def passe(cle):
        ctx = _Contexte(max(0.0, limite - time.monotonic()), cle=cle,
                        signatures_originales=signatures)
        return _resoudre(comptes, jokers, ctx)

    resultat = passe(lambda v: v)
    if mise_min is not None and resultat is not None and resultat[0][1] < mise_min \
            and deux_passes:
        resultat_points = passe(lambda v: (v[1], v[0], v[2]))
        if resultat_points is not None and resultat_points[0][1] >= mise_min:
            resultat = resultat_points
    return resultat


def resoudre_coup(etat, idx, budget_temps=1.5):
    """Point d'entrée du solveur pour le niveau Expert.

    Retourne un coup ``{"action": "jouer", "ids_tuiles": [...],
    "nouveau_plateau": [...]}`` ou ``None`` si aucun réarrangement ne pose la
    moindre tuile du chevalet (ou, mise initiale non faite, aucun n'atteint
    le minimum requis). Si le budget de temps s'épuise, le meilleur
    réarrangement déjà trouvé est renvoyé normalement (pas nécessairement
    optimal — voir docstring du module) ; :class:`BudgetDepasse` n'est levée
    que si RIEN n'a été trouvé nulle part avant expiration du budget,
    auquel cas l'appelant doit se replier sur un autre niveau pour ce tour.
    """
    joueur = etat["joueurs"][idx]
    deja_faite = joueur["mise_initiale_faite"]
    plateau = plateau_depuis_dict(etat.get("plateau", []))
    chevalet = [tuile_depuis_dict(d) if isinstance(d, dict) else d
                for d in joueur["chevalet"]]
    mise_min = etat["config"]["mise_initiale_min"]

    if deja_faite:
        plateau_flexible, plateau_gele = _separer_combos_figees(plateau, chevalet)
    else:
        # Mise initiale pas faite : une règle du jeu interdit de toucher aux
        # combinaisons déjà posées (par d'autres joueurs) — tout le plateau
        # est donc gelé, hors recherche (qui ne porte que sur le chevalet),
        # mais reconduit à l'identique dans le résultat (voir issue #187 :
        # auparavant le plateau était simplement ignoré, y compris dans le
        # résultat renvoyé, ce qui faisait disparaître ses tuiles).
        plateau_flexible, plateau_gele = [], plateau

    resultat = _meilleur_rearrangement(
        plateau_flexible, chevalet, budget_temps,
        mise_min=None if deja_faite else mise_min,
        deux_passes=not deja_faite)

    if resultat is None or resultat[0][0] == 0:
        return None
    valeur, combos_solution = resultat

    if not deja_faite and valeur[1] < mise_min:
        return None

    nouveau_plateau_tuiles, ids_main = _reconstruire(
        plateau_flexible, chevalet, combos_solution)
    nouveau_plateau_tuiles = plateau_gele + nouveau_plateau_tuiles
    if not ids_main:
        return None
    nouveau_plateau = _plateau_vers_dict(nouveau_plateau_tuiles)
    return {"action": "jouer", "ids_tuiles": ids_main,
            "nouveau_plateau": nouveau_plateau}
