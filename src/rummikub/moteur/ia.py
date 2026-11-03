"""Intelligence artificielle des adversaires — 5 niveaux de jeu.

Toutes les fonctions de niveau ont la signature ::

    jouer_niveau_X(etat, joueur_index) -> dict

et retournent un dictionnaire d'action ::

    {"action": "jouer"|"piocher"|"passer",
     "ids_tuiles": [str],        # ids des tuiles du chevalet jouées
     "nouveau_plateau": list}    # plateau résultant (list of list of dict)

Le point d'entrée public est :func:`jouer_ia`.

Principe : les fonctions ne modifient JAMAIS l'état ; elles travaillent sur
des copies (objets ``Tuile`` reconstruits) et tout coup ``jouer`` proposé est
revalidé avant d'être renvoyé, de sorte que ``jouer_tour`` ne le rejette
jamais (ce qui, côté UI, provoquerait une boucle infinie du tour IA).
"""

import random
import time
from itertools import combinations

from rummikub.config import VALEUR_MIN, VALEUR_MAX, COULEURS
from rummikub.moteur.validation import (
    valider_combinaison, valider_suite, valider_plateau,
)
from rummikub.moteur.partie import (
    tuile_depuis_dict, plateau_depuis_dict, _plateau_vers_dict,
    _points_tuiles_posees,
)
from rummikub.moteur.solveur import (
    resoudre_coup, BudgetDepasse, PREFERER_SIMPLICITE, mesurer_perturbation,
)
from rummikub.moteur.solveur_exact import (
    resoudre_exact, SolveurExactIndisponible, BudgetExactDepasse,
)
from rummikub.moteur import evaluation_main
from rummikub.moteur import niveaux as _niveaux
from rummikub.moteur import verification_finition
from rummikub.moteur import sorties as _sorties
from rummikub.moteur import inconnues as _inconnues


# --------------------------------------------------------------------------- #
# Conversions
# --------------------------------------------------------------------------- #

def _to_tuiles(chevalet):
    """Convertit une liste de dicts (ou Tuiles) en liste d'objets Tuile."""
    return [tuile_depuis_dict(d) if isinstance(d, dict) else d for d in chevalet]


# --------------------------------------------------------------------------- #
# Génération de combinaisons candidates depuis le chevalet
# --------------------------------------------------------------------------- #

def _candidats_groupes(tuiles):
    """Groupes candidats (même valeur, couleurs distinctes, ±1 joker)."""
    combos = []
    jokers = [t for t in tuiles if t.est_joker]
    par_valeur = {}
    for t in tuiles:
        if t.est_joker:
            continue
        par_valeur.setdefault(t.valeur, {}).setdefault(t.couleur, t)
    for _valeur, par_couleur in par_valeur.items():
        distincts = list(par_couleur.values())
        for taille in (3, 4):
            if len(distincts) >= taille:
                for combo in combinations(distincts, taille):
                    combos.append(list(combo))
        # Variante avec un joker (2 ou 3 tuiles réelles + joker).
        if jokers:
            for taille_reel in (2, 3):
                if len(distincts) >= taille_reel:
                    for combo in combinations(distincts, taille_reel):
                        combos.append(list(combo) + [jokers[0]])
    return combos


def _candidats_suites(tuiles):
    """Suites candidates (même couleur, valeurs consécutives, jokers en comblement)."""
    combos = []
    jokers = [t for t in tuiles if t.est_joker]
    par_couleur = {}
    for t in tuiles:
        if t.est_joker:
            continue
        par_couleur.setdefault(t.couleur, {}).setdefault(t.valeur, t)

    for _couleur, vmap in par_couleur.items():
        for debut in range(VALEUR_MIN, VALEUR_MAX + 1):
            for fin in range(debut + 2, VALEUR_MAX + 1):
                combo = []
                joker_pool = list(jokers)
                ok = True
                for v in range(debut, fin + 1):
                    if v in vmap:
                        combo.append(vmap[v])
                    elif joker_pool:
                        combo.append(joker_pool.pop(0))
                    else:
                        ok = False
                        break
                if ok and valider_suite(combo)["valide"]:
                    combos.append(combo)
    return combos


def trouver_combinaisons_depuis_chevalet(chevalet, mise_initiale_min, deja_faite):
    """Recherche des combinaisons valides formables depuis le chevalet.

    Retourne une liste triée par nombre de tuiles décroissant ::

        [{"tuiles": [Tuile, ...], "type": str, "points": int}, ...]

    Si ``deja_faite`` est faux, seules les combinaisons dont ``points`` est
    ≥ ``mise_initiale_min`` sont conservées (mise initiale sur une seule
    combinaison).
    """
    tuiles = _to_tuiles(chevalet)
    candidats = _candidats_suites(tuiles) + _candidats_groupes(tuiles)
    resultats = []
    for combo in candidats:
        r = valider_combinaison(combo)
        if not r["valide"]:
            continue
        resultats.append({"tuiles": combo, "type": r["type"],
                          "points": r["points"]})
    if not deja_faite:
        resultats = [x for x in resultats if x["points"] >= mise_initiale_min]
    resultats.sort(key=lambda x: len(x["tuiles"]), reverse=True)
    return resultats


def trouver_extensions_plateau(chevalet, plateau):
    """Tuiles du chevalet ajoutables à l'une des extrémités d'une combinaison.

    Retourne ``[{"tuile": Tuile, "combi_index": int,
                 "position": "debut"|"fin"}, ...]``.
    """
    tuiles = _to_tuiles(chevalet)
    combos = plateau_depuis_dict(plateau) if plateau else []
    extensions = []
    for ci, combo in enumerate(combos):
        for t in tuiles:
            if valider_combinaison(combo + [t])["valide"]:
                extensions.append({"tuile": t, "combi_index": ci,
                                   "position": "fin"})
            if valider_combinaison([t] + combo)["valide"]:
                extensions.append({"tuile": t, "combi_index": ci,
                                   "position": "debut"})
    return extensions


# --------------------------------------------------------------------------- #
# Sélection et construction de coups
# --------------------------------------------------------------------------- #

def _selection_disjointe(resultats):
    """Sélectionne gloutonnement des combinaisons sans tuile en commun."""
    utilises = set()
    choisis = []
    for r in resultats:
        ids = {t.id for t in r["tuiles"]}
        if ids & utilises:
            continue
        utilises |= ids
        choisis.append(r)
    return choisis


def _coup_valide(etat, idx, nouveau_plateau_dict, ids):
    """Vrai si le coup passerait la validation de ``jouer_tour``."""
    plateau = plateau_depuis_dict(nouveau_plateau_dict)
    if not valider_plateau(plateau)["valide"]:
        return False
    joueur = etat["joueurs"][idx]
    if not joueur["mise_initiale_faite"]:
        points = _points_tuiles_posees(plateau, set(ids))
        if points < etat["config"]["mise_initiale_min"]:
            return False
    return True


def _combos_vers_coup(etat, idx, combos):
    """Construit et valide un coup 'jouer' à partir de combinaisons choisies."""
    plateau = plateau_depuis_dict(etat.get("plateau", []))
    ids = []
    for r in combos:
        plateau.append(list(r["tuiles"]))
        for t in r["tuiles"]:
            ids.append(t.id)
    nouveau = _plateau_vers_dict(plateau)
    if ids and _coup_valide(etat, idx, nouveau, ids):
        return {"action": "jouer", "ids_tuiles": ids, "nouveau_plateau": nouveau}
    return None


def _appliquer_extensions(plateau, restantes, ids):
    """Étend les combinaisons du plateau avec les tuiles restantes (en place)."""
    change = True
    while change and restantes:
        change = False
        plateau_dict = _plateau_vers_dict(plateau)
        chevalet_dict = [t.as_dict() for t in restantes]
        for e in trouver_extensions_plateau(chevalet_dict, plateau_dict):
            t = next((x for x in restantes if x.id == e["tuile"].id), None)
            if t is None:
                continue
            ci = e["combi_index"]
            cand = (plateau[ci] + [t]) if e["position"] == "fin" \
                else ([t] + plateau[ci])
            if valider_combinaison(cand)["valide"]:
                plateau[ci] = cand
                restantes.remove(t)
                ids.append(t.id)
                change = True
                break


def _coup_maximal(etat, idx, ordre_points=False):
    """Construit le coup posant le plus de tuiles (combinaisons + extensions)."""
    joueur = etat["joueurs"][idx]
    deja = joueur["mise_initiale_faite"]
    resultats = trouver_combinaisons_depuis_chevalet(
        joueur["chevalet"], etat["config"]["mise_initiale_min"], deja)
    if ordre_points:
        resultats = sorted(
            resultats, key=lambda r: (r["points"], len(r["tuiles"])),
            reverse=True)
    choisis = _selection_disjointe(resultats)

    plateau = plateau_depuis_dict(etat.get("plateau", []))
    ids = []
    utilises = set()
    for r in choisis:
        plateau.append(list(r["tuiles"]))
        for t in r["tuiles"]:
            ids.append(t.id)
            utilises.add(t.id)

    # La mise initiale doit être atteinte avant toute extension.
    mise_ok = deja
    if not deja and ids:
        mise_ok = _points_tuiles_posees(plateau, set(ids)) \
            >= etat["config"]["mise_initiale_min"]
    if mise_ok:
        restantes = [t for t in _to_tuiles(joueur["chevalet"])
                     if t.id not in utilises]
        _appliquer_extensions(plateau, restantes, ids)

    if not ids:
        return None
    nouveau = _plateau_vers_dict(plateau)
    if _coup_valide(etat, idx, nouveau, ids):
        return {"action": "jouer", "ids_tuiles": ids, "nouveau_plateau": nouveau}
    return None


def _coup_scission(etat, idx):
    """Scinde une suite longue pour libérer une tuile réelle et former un
    groupe — en BOUT (une seule suite restante) ou en position INTÉRIEURE
    (deux suites valides restantes, de part et d'autre de la tuile retirée).

    Ex. bout : suite rouge 4-5-6-7 et le chevalet un 7 bleu et un 7 jaune →
    on détache le 7 rouge (la suite 4-5-6 reste valide) pour former le
    groupe 7 rouge/bleu/jaune, posant 2 tuiles du chevalet.

    Ex. intérieur (#181) : suite rouge 1-2-3-4-5-6-7 et le chevalet un 4 bleu
    et un 4 jaune → on détache le 4 rouge (les suites 1-2-3 et 5-6-7 restent
    valides, remplaçant la suite d'origine) pour former le groupe 4
    rouge/bleu/jaune.
    """
    joueur = etat["joueurs"][idx]
    if not joueur["mise_initiale_faite"]:
        return None
    base = plateau_depuis_dict(etat.get("plateau", []))
    restantes = _to_tuiles(joueur["chevalet"])
    for ci, combo in enumerate(base):
        r = valider_combinaison(combo)
        if not r["valide"] or r["type"] != "suite" or len(combo) < 4:
            continue
        for pi, libre in enumerate(combo):
            if libre.est_joker:
                continue
            parties = [p for p in (combo[:pi], combo[pi + 1:]) if p]
            if not parties or any(
                    len(p) < 3 or not valider_combinaison(p)["valide"]
                    for p in parties):
                continue
            couleurs_vues = {libre.couleur}
            groupe = [libre]
            for t in restantes:
                if (not t.est_joker and t.valeur == libre.valeur
                        and t.couleur not in couleurs_vues):
                    groupe.append(t)
                    couleurs_vues.add(t.couleur)
                if len(groupe) == 4:
                    break
            if len(groupe) >= 3 and valider_combinaison(groupe)["valide"]:
                nouveau_plateau = [list(c) for c in base]
                nouveau_plateau[ci] = list(parties[0])
                for extra in parties[1:]:
                    nouveau_plateau.append(list(extra))
                nouveau_plateau.append(groupe)
                ids = [t.id for t in groupe if t.id != libre.id]
                nd = _plateau_vers_dict(nouveau_plateau)
                if ids and _coup_valide(etat, idx, nd, ids):
                    return {"action": "jouer", "ids_tuiles": ids,
                            "nouveau_plateau": nd}
    return None


def _tuile_correspond_au_joker(combo, r, position_index, tuile):
    """Vrai si ``tuile`` peut remplacer directement le joker en
    ``position_index`` de ``combo`` (même valeur/couleur pour une suite,
    même valeur et une couleur absente du groupe pour un groupe), sans
    changer la validité ni les points de la combinaison."""
    if tuile.est_joker:
        return False
    if r["type"] == "suite":
        i0, t0 = next((i, tt) for i, tt in enumerate(combo)
                      if not tt.est_joker)
        valeur_attendue = t0.valeur - i0 + position_index
        return tuile.valeur == valeur_attendue and tuile.couleur == t0.couleur
    else:  # groupe
        valeur_attendue = next(tt.valeur for tt in combo if not tt.est_joker)
        couleurs_utilisees = {tt.couleur for tt in combo if not tt.est_joker}
        return (tuile.valeur == valeur_attendue
                and tuile.couleur not in couleurs_utilisees)


def _jokers_recuperables(plateau, chevalet):
    """Jokers du plateau échangeables contre une tuile identique de la main.

    Un joker est « récupérable » si le chevalet contient exactement la tuile
    qu'il représente dans sa combinaison (même valeur/couleur pour une suite,
    même valeur et une couleur absente du groupe pour un groupe) : l'échanger
    ne change ni la validité ni les points de la combinaison, et libère le
    joker pour un usage ailleurs sur le plateau.

    Retourne ``[{"combi_index", "position_index", "joker", "remplacement"}]``.
    """
    resultats = []
    for ci, combo in enumerate(plateau):
        r = valider_combinaison(combo)
        if not r["valide"]:
            continue
        for pi, t in enumerate(combo):
            if not t.est_joker:
                continue
            match = next((tt for tt in chevalet
                          if _tuile_correspond_au_joker(combo, r, pi, tt)),
                         None)
            if match is not None:
                resultats.append({"combi_index": ci, "position_index": pi,
                                  "joker": t, "remplacement": match})
    return resultats


def _jokers_detachables_par_extension(plateau, chevalet):
    """Jokers en bout de suite détachables grâce à une extension du bout opposé.

    Un joker à une extrémité d'une suite peut être détaché sans aucune tuile
    de remplacement si une tuile réelle du chevalet, jouée à l'AUTRE
    extrémité, allonge la portion de tuiles réelles (joker exclu) jusqu'à au
    moins 3 tuiles : cette portion reste alors valide seule une fois le
    joker retiré, qui devient libre pour un usage ailleurs sur le plateau.

    Contrairement à :func:`_coup_scission` (tuile réelle en bout, retirable
    sans rien y ajouter) et à :func:`_jokers_recuperables` (échange direct
    joker/tuile identique), ce cas porte sur un joker en bout de suite et
    nécessite de jouer une tuile à l'extrémité opposée pour y parvenir.

    Retourne ``[{"combi_index", "joker", "tuile_extension", "nouveau_combo"}]``.
    """
    resultats = []
    for ci, combo in enumerate(plateau):
        r = valider_combinaison(combo)
        if not r["valide"] or r["type"] != "suite" or len(combo) < 3:
            continue
        for bout_joker in ("debut", "fin"):
            joker = combo[0] if bout_joker == "debut" else combo[-1]
            if not joker.est_joker:
                continue
            reste = combo[1:] if bout_joker == "debut" else combo[:-1]
            if any(t.est_joker for t in reste):
                continue
            for t in chevalet:
                if t.est_joker:
                    continue
                nouveau_combo = [t] + reste if bout_joker == "fin" \
                    else reste + [t]
                if len(nouveau_combo) >= 3 \
                        and valider_suite(nouveau_combo)["valide"]:
                    resultats.append({"combi_index": ci, "joker": joker,
                                      "tuile_extension": t,
                                      "nouveau_combo": nouveau_combo})
    return resultats


def _jokers_liberables_par_reduction_groupe4(plateau, chevalet):
    """Tuile libérée en réduisant un groupe de 4 à un groupe de 3 valide,
    utilisée pour échanger directement un joker récupérable ailleurs sur
    le plateau.

    Un groupe de 4 tuiles de couleurs distinctes — déjà présent sur le
    plateau, ou obtenu en y ajoutant une tuile de la main de la 4e couleur
    manquante — peut perdre l'une de ses tuiles réelles tout en restant un
    groupe valide de 3. Si la tuile ainsi libérée correspond exactement au
    joker d'une AUTRE combinaison du plateau (même critère que
    :func:`_jokers_recuperables`), elle sert à l'échanger directement,
    libérant ce joker pour un usage ailleurs.

    Exemple : groupe plateau (11 bleu, 11 jaune, 11 noir) + 11 rouge de la
    main → groupe de 4 ; le 11 noir libéré (groupe restant : bleu/jaune/
    rouge, valide) correspond au joker d'une suite noire 10-joker-12-13
    ailleurs sur le plateau.

    Retourne ``[{"combi_index_groupe", "nouveau_groupe",
                "tuile_hand_utilisee", "tuile_liberee", "combi_index_joker",
                "position_index_joker", "joker"}, ...]``.
    """
    resultats = []
    for gi, groupe in enumerate(plateau):
        r = valider_combinaison(groupe)
        if not r["valide"] or r["type"] != "groupe":
            continue
        if len(groupe) == 4:
            candidats = [(groupe, None)]
        elif len(groupe) == 3 and not any(t.est_joker for t in groupe):
            valeur = groupe[0].valeur
            couleurs_utilisees = {t.couleur for t in groupe}
            candidats = [(groupe + [t], t) for t in chevalet
                         if not t.est_joker and t.valeur == valeur
                         and t.couleur not in couleurs_utilisees]
        else:
            continue
        for groupe4, tuile_hand in candidats:
            for libre in groupe4:
                if libre.est_joker or libre is tuile_hand:
                    continue
                nouveau_groupe = [t for t in groupe4 if t is not libre]
                if not valider_combinaison(nouveau_groupe)["valide"]:
                    continue
                for cj, combo_j in enumerate(plateau):
                    if cj == gi:
                        continue
                    rj = valider_combinaison(combo_j)
                    if not rj["valide"]:
                        continue
                    for pj, tj in enumerate(combo_j):
                        if not tj.est_joker:
                            continue
                        if _tuile_correspond_au_joker(combo_j, rj, pj, libre):
                            resultats.append({
                                "combi_index_groupe": gi,
                                "nouveau_groupe": nouveau_groupe,
                                "tuile_hand_utilisee": tuile_hand,
                                "tuile_liberee": libre,
                                "combi_index_joker": cj,
                                "position_index_joker": pj,
                                "joker": tj,
                            })
    return resultats


def _jokers_liberables_par_groupe4_sans_remplacement(plateau):
    """Joker libérable en retirant un groupe de 4 tuiles à 3, SANS aucune
    tuile de remplacement.

    Un groupe de 4 tuiles du plateau contenant un joker (3 tuiles réelles de
    couleurs distinctes + 1 joker) reste un groupe valide une fois le joker
    retiré : les 3 tuiles réelles suffisent seules. Contrairement à
    :func:`_jokers_recuperables` (qui exige une tuile identique en main pour
    remplacer le joker) et à :func:`_jokers_liberables_par_reduction_groupe4`
    (#180, qui retire une tuile RÉELLE, jamais le joker, pour l'échanger
    ailleurs), ici le joker est retiré sans qu'aucune tuile ne le remplace :
    le groupe de 4 devient simplement un groupe de 3, sans consommer de
    tuile du chevalet. Le joker ainsi libéré doit ensuite être rejoué
    ailleurs avec des tuiles de la main (cf. :func:`_liberations_possibles`).

    Retourne ``[{"combi_index", "joker", "nouveau_groupe"}, ...]``.
    """
    resultats = []
    for gi, groupe in enumerate(plateau):
        if len(groupe) != 4:
            continue
        r = valider_combinaison(groupe)
        if not r["valide"] or r["type"] != "groupe":
            continue
        for pi, joker in enumerate(groupe):
            if not joker.est_joker:
                continue
            nouveau_groupe = groupe[:pi] + groupe[pi + 1:]
            if not valider_combinaison(nouveau_groupe)["valide"]:
                continue
            resultats.append({"combi_index": gi, "joker": joker,
                              "nouveau_groupe": nouveau_groupe})
    return resultats


def _jokers_liberables_par_scission_milieu(plateau, chevalet):
    """Jokers en position INTÉRIEURE d'une suite, libérables en scindant
    celle-ci en deux suites valides (chacune d'au moins 3 tuiles) de part et
    d'autre du joker retiré.

    Ex. : suite bleue 3-4-5-joker-7-8-9 → retirer le joker laisse deux
    suites valides (3-4-5 et 7-8-9), qui remplacent la suite d'origine ; le
    joker libéré doit ensuite être rejoué ailleurs avec des tuiles de la
    main (cf. :func:`_liberations_possibles`).

    Contrairement à :func:`_jokers_detachables_par_extension` (joker en
    BOUT de suite, nécessitant une extension du bout opposé), ce cas porte
    sur un joker strictement intérieur et ne consomme aucune tuile du
    chevalet pour la scission elle-même : la combinaison d'origine devient
    DEUX combinaisons.

    Retourne ``[{"combi_index", "joker", "gauche", "droite"}, ...]``.
    """
    resultats = []
    for ci, combo in enumerate(plateau):
        r = valider_combinaison(combo)
        if not r["valide"] or r["type"] != "suite" or len(combo) < 7:
            continue
        for pi in range(1, len(combo) - 1):
            joker = combo[pi]
            if not joker.est_joker:
                continue
            gauche = combo[:pi]
            droite = combo[pi + 1:]
            if len(gauche) < 3 or len(droite) < 3:
                continue
            if not valider_suite(gauche)["valide"] \
                    or not valider_suite(droite)["valide"]:
                continue
            resultats.append({"combi_index": ci, "joker": joker,
                              "gauche": gauche, "droite": droite})
    return resultats


def _liberations_possibles(plateau, chevalet):
    """Toutes les libérations de joker possibles — échange direct,
    détachement en bout de suite, réduction d'un groupe de 4 à 3 (tuile
    réelle échangée contre un joker ailleurs, ou joker retiré sans
    remplacement), ou scission en milieu de suite — sous une forme
    uniforme ::

        [{"combis", "joker", "tuiles_consommees", "appliquer"}, ...]

    ``combis`` est la liste des ``combi_index`` du plateau modifiés par
    cette libération (un seul pour la plupart des mécanismes ; deux pour la
    réduction de groupe, qui modifie à la fois le groupe réduit et la
    combinaison du joker échangé). ``appliquer(plateau)`` modifie ces
    combinaisons en place pour effectuer la libération — pour la scission en
    milieu de suite, elle remplace la combinaison d'origine par sa moitié
    gauche et AJOUTE la moitié droite comme nouvelle combinaison du plateau
    (une combinaison devient deux). ``tuiles_consommees`` liste les tuiles du
    CHEVALET utilisées (remplacement, tuile d'extension, tuile complétant un
    groupe à 4 ; éventuellement aucune, comme pour la scission). Chaque
    entrée correspond à UNE libération ; en combiner plusieurs (sur des
    ``combis`` et ``tuiles_consommees`` disjoints) permet de récupérer
    plusieurs jokers en un seul coup.
    """
    liberations = []
    for rec in _jokers_recuperables(plateau, chevalet):
        ci = rec["combi_index"]
        pi = rec["position_index"]
        remplacement = rec["remplacement"]

        def appliquer(plateau_, ci=ci, pi=pi, remplacement=remplacement):
            plateau_[ci] = plateau_[ci][:pi] + [remplacement] \
                + plateau_[ci][pi + 1:]

        liberations.append({
            "combis": [ci],
            "joker": rec["joker"],
            "tuiles_consommees": [remplacement],
            "appliquer": appliquer,
        })
    for rec in _jokers_detachables_par_extension(plateau, chevalet):
        ci = rec["combi_index"]
        nouveau_combo = rec["nouveau_combo"]

        def appliquer(plateau_, ci=ci, nouveau_combo=nouveau_combo):
            plateau_[ci] = nouveau_combo

        liberations.append({
            "combis": [ci],
            "joker": rec["joker"],
            "tuiles_consommees": [rec["tuile_extension"]],
            "appliquer": appliquer,
        })
    for rec in _jokers_liberables_par_reduction_groupe4(plateau, chevalet):
        ci_groupe = rec["combi_index_groupe"]
        nouveau_groupe = rec["nouveau_groupe"]
        ci_joker = rec["combi_index_joker"]
        pj = rec["position_index_joker"]
        libre = rec["tuile_liberee"]
        tuile_hand = rec["tuile_hand_utilisee"]

        def appliquer(plateau_, ci_groupe=ci_groupe, nouveau_groupe=nouveau_groupe,
                      ci_joker=ci_joker, pj=pj, libre=libre):
            plateau_[ci_groupe] = nouveau_groupe
            plateau_[ci_joker] = plateau_[ci_joker][:pj] + [libre] \
                + plateau_[ci_joker][pj + 1:]

        liberations.append({
            "combis": [ci_groupe, ci_joker],
            "joker": rec["joker"],
            "tuiles_consommees": [tuile_hand] if tuile_hand is not None else [],
            "appliquer": appliquer,
        })
    for rec in _jokers_liberables_par_groupe4_sans_remplacement(plateau):
        ci = rec["combi_index"]
        nouveau_groupe = rec["nouveau_groupe"]

        def appliquer(plateau_, ci=ci, nouveau_groupe=nouveau_groupe):
            plateau_[ci] = nouveau_groupe

        liberations.append({
            "combis": [ci],
            "joker": rec["joker"],
            "tuiles_consommees": [],
            "appliquer": appliquer,
        })
    for rec in _jokers_liberables_par_scission_milieu(plateau, chevalet):
        ci = rec["combi_index"]
        gauche = rec["gauche"]
        droite = rec["droite"]

        def appliquer(plateau_, ci=ci, gauche=gauche, droite=droite):
            plateau_[ci] = list(gauche)
            plateau_.append(list(droite))

        liberations.append({
            "combis": [ci],
            "joker": rec["joker"],
            "tuiles_consommees": [],
            "appliquer": appliquer,
        })
    return liberations


def _coup_depuis_liberations(etat, idx, base_plateau, chevalet, liberations,
                              ordre_points):
    """Construit le coup résultant de l'application simultanée de
    ``liberations`` (un sous-ensemble non conflictuel renvoyé par
    :func:`_liberations_possibles`), puis tente de replacer chaque joker
    ainsi libéré ailleurs sur le plateau (nouvelle combinaison ou
    extension). Retourne ``None`` si un joker libéré ne peut être replacé.
    """
    plateau = [list(c) for c in base_plateau]
    consommees = set()
    jokers = []
    for lib in liberations:
        lib["appliquer"](plateau)
        for t in lib["tuiles_consommees"]:
            consommees.add(t.id)
        jokers.append(lib["joker"])

    disponibles = [t for t in chevalet if t.id not in consommees] + jokers
    resultats = trouver_combinaisons_depuis_chevalet(
        [t.as_dict() for t in disponibles],
        etat["config"]["mise_initiale_min"], True)
    if ordre_points:
        resultats = sorted(
            resultats, key=lambda r: (r["points"], len(r["tuiles"])),
            reverse=True)
    choisis = _selection_disjointe(resultats)

    ids = list(consommees)
    utilises = set(consommees)
    for r in choisis:
        plateau.append(list(r["tuiles"]))
        for t in r["tuiles"]:
            ids.append(t.id)
            utilises.add(t.id)

    restantes = [t for t in disponibles if t.id not in utilises]
    _appliquer_extensions(plateau, restantes, ids)

    places = {t.id for c in plateau for t in c}
    if not all(j.id in places for j in jokers):
        return None

    ids_joker = {j.id for j in jokers}
    ids_reel = [i for i in ids if i not in ids_joker]
    nouveau = _plateau_vers_dict(plateau)
    if ids_reel and _coup_valide(etat, idx, nouveau, ids_reel):
        return {"action": "jouer", "ids_tuiles": ids_reel,
                "nouveau_plateau": nouveau}
    return None


def _meilleur_coup_liberations(etat, idx, ordre_points=False):
    """Essaie toutes les combinaisons non conflictuelles de libérations de
    joker (échange direct, détachement, et/ou réduction de groupe de 4,
    sur des combinaisons distinctes du plateau) et retourne la meilleure,
    afin de récupérer plusieurs jokers en un seul coup quand c'est
    possible, plutôt que de n'en considérer qu'un seul à la fois.

    Retourne ``None`` si aucune combinaison de libérations n'est jouable.
    """
    joueur = etat["joueurs"][idx]
    if not joueur["mise_initiale_faite"]:
        return None
    base_plateau = plateau_depuis_dict(etat.get("plateau", []))
    chevalet = _to_tuiles(joueur["chevalet"])
    liberations = _liberations_possibles(base_plateau, chevalet)
    meilleur = None
    for taille in range(1, len(liberations) + 1):
        for sous_ensemble in combinations(liberations, taille):
            cis = [ci for lib in sous_ensemble for ci in lib["combis"]]
            ids_consommees = [t.id for lib in sous_ensemble
                              for t in lib["tuiles_consommees"]]
            if len(set(cis)) != len(cis) \
                    or len(set(ids_consommees)) != len(ids_consommees):
                continue  # deux libérations qui se marchent dessus
            coup = _coup_depuis_liberations(
                etat, idx, base_plateau, chevalet, sous_ensemble,
                ordre_points)
            if coup and (meilleur is None or (_valeur_coup(etat, idx, coup)
                                              > _valeur_coup(etat, idx, meilleur))):
                meilleur = coup
    return meilleur


def _valeur_coup(etat, idx, coup):
    """Valeur comparative d'un coup candidat : (nb tuiles jouées, points posés)."""
    plateau = plateau_depuis_dict(coup["nouveau_plateau"])
    ids = set(coup["ids_tuiles"])
    return (len(ids), _points_tuiles_posees(plateau, ids))


def _meilleur_coup_avec_joker(etat, idx, ordre_points=False):
    """Compare l'extension/combinaison évidente à la meilleure combinaison
    de libérations de joker (échange direct, détachement en bout de suite,
    et/ou réduction de groupe de 4, pouvant porter sur plusieurs jokers à
    la fois si le plateau en propose plusieurs) ; retourne le meilleur des
    coups trouvés (ou ``None`` si aucun n'est jouable).
    """
    simple = _coup_maximal(etat, idx, ordre_points=ordre_points)
    liberation = _meilleur_coup_liberations(etat, idx, ordre_points=ordre_points)
    candidats = [c for c in (simple, liberation) if c]
    if not candidats:
        return None
    return max(candidats, key=lambda c: _valeur_coup(etat, idx, c))


def _piocher_ou_passer(etat):
    """Pioche s'il reste des tuiles, sinon passe."""
    plateau = etat.get("plateau", [])
    if etat.get("pioche"):
        return {"action": "piocher", "ids_tuiles": [], "nouveau_plateau": plateau}
    return {"action": "passer", "ids_tuiles": [], "nouveau_plateau": plateau}


# --------------------------------------------------------------------------- #
# Les cinq niveaux
# --------------------------------------------------------------------------- #

def jouer_niveau_debutant(etat, idx):
    """Combinaisons pures depuis le chevalet ; choix aléatoire, sinon pioche."""
    joueur = etat["joueurs"][idx]
    resultats = trouver_combinaisons_depuis_chevalet(
        joueur["chevalet"], etat["config"]["mise_initiale_min"],
        joueur["mise_initiale_faite"])
    random.shuffle(resultats)
    for r in resultats:
        coup = _combos_vers_coup(etat, idx, [r])
        if coup:
            return coup
    return _piocher_ou_passer(etat)


def jouer_niveau_facile(etat, idx):
    """Comme débutant, mais pose le plus de tuiles + tente les extensions."""
    coup = _coup_maximal(etat, idx, ordre_points=False)
    if coup:
        return coup
    return _piocher_ou_passer(etat)


def jouer_niveau_intermediaire(etat, idx):
    """Comme facile + priorité aux tuiles de forte valeur (limite les pénalités)."""
    coup = _coup_maximal(etat, idx, ordre_points=True)
    if coup:
        return coup
    return _piocher_ou_passer(etat)


def jouer_niveau_avance(etat, idx):
    """Comme intermédiaire + peut scinder une suite longue pour libérer une
    tuile, et préfère récupérer (échange direct), détacher (extension du
    bout opposé), ou libérer en réduisant un groupe de 4 à 3, un joker
    exploitable du plateau si cela donne un coup plus riche que l'extension
    la plus évidente."""
    coup = _meilleur_coup_avec_joker(etat, idx, ordre_points=True)
    if coup:
        return coup
    coup = _coup_scission(etat, idx)
    if coup:
        return coup
    return _piocher_ou_passer(etat)


BUDGET_TEMPS_EXPERT = 1.5  # secondes ; voir solveur_exact / solveur (#206/#186).

# Réglage #206 : Expert joue avec le MODÈLE EXACT (programmation linéaire en
# nombres entiers, ``moteur/solveur_exact.py``), qui pose toujours le plus
# grand nombre de tuiles (y compris les victoires immédiates). ``False`` fige
# Expert sur l'ancienne recherche arborescente (``moteur/solveur.py``), utile
# pour comparer les deux versions par simulation (campagne « avant / après »,
# ``scripts/comparer_niveaux_ia.py --sans-exact``). Lu à l'appel.
UTILISER_SOLVEUR_EXACT = True

# Réglage #211 : évaluation de la main restante comme critère de départage du
# modèle exact (doublons, tuiles de bord, points selon le nombre de manches).
# ``evaluation_main.DEFAUT`` fixe les critères activés PAR DÉFAUT et tous les
# poids (réunis dans ``moteur/evaluation_main.py``). ``active=False`` par
# défaut : Expert départage comme avant #211 tant que la simulation n'a pas
# démontré de gain (voir CONTEXTE.md §13). Lu à l'appel.
EVAL_MAIN_DEFAUT = evaluation_main.DEFAUT


def _coup_recherche(etat, idx, budget_temps, preferer_simple):
    """Recherche arborescente conservée comme repli (``solveur.resoudre_coup``,
    #186). Retourne ``(coup | None, timeout_bool)`` ; ``timeout_bool`` est vrai
    si le budget a été dépassé sans qu'aucune branche n'aboutisse."""
    try:
        return resoudre_coup(etat, idx, budget_temps=budget_temps,
                             preferer_simple=preferer_simple), False
    except BudgetDepasse:
        return None, True


def _coup_exact(etat, idx, budget_temps, preferer_simple, eval_config=None,
                max_tuiles_posees=None, valeur_max_petits=None):
    """Modèle exact (#206). Ne lève JAMAIS. Retourne ``(statut, charge)`` :

    * ``("coup", coup)`` — un coup optimal a été trouvé ;
    * ``("aucun", None)`` — optimum PROUVÉ : aucune tuile posable (ou mise
      initiale inatteignable). Inutile de lancer la recherche de repli
      (incomplète) après un modèle COMPLET : Expert passe directement à Avancé
      pour décider pioche/passe ;
    * ``("echec", cause_timeout)`` — le modèle n'a pas pu conclure (dépendances
      absentes, budget dépassé sans solution, résultat non valide, erreur) :
      l'appelant se replie sur la recherche arborescente. ``cause_timeout``
      vaut ``True`` pour un dépassement de budget, ``False`` sinon.

    ``max_tuiles_posees`` (issue #229, ``retenue_debut``) : relais vers
    ``resoudre_exact``, ``None`` (défaut) → comportement inchangé.

    ``valeur_max_petits`` (issue #230, ``petits_chiffres``) : relais vers
    ``resoudre_exact``, ``None`` (défaut) → comportement inchangé."""
    try:
        res = resoudre_exact(etat, idx, budget_temps=budget_temps,
                             preferer_simple=preferer_simple,
                             eval_config=eval_config,
                             max_tuiles_posees=max_tuiles_posees,
                             valeur_max_petits=valeur_max_petits)
    except BudgetExactDepasse:
        return "echec", True
    except SolveurExactIndisponible:
        return "echec", False
    except Exception:  # pragma: no cover - filet, ne doit jamais bloquer le jeu
        return "echec", False
    if not res.valide_globalement:
        # Ne devrait jamais arriver (validation + conservation contrôlées) :
        # par prudence, on se replie sur la recherche plutôt que de jouer un
        # coup douteux.
        return "echec", False
    if res.nb_tuiles == 0 or not res.ids_tuiles:
        return "aucun", None
    return "coup", {"action": "jouer", "ids_tuiles": res.ids_tuiles,
                    "nouveau_plateau": res.nouveau_plateau}


# Codes du mécanisme ayant décidé le coup d'Expert, enregistrés dans le journal
# de partie (issue #211, point 5bis) pour que l'analyse puisse exclure/signaler
# les coups joués en repli (le repli est silencieux quand highspy/numpy
# manquent). Libellés lisibles : voir ``LIBELLES_SOLVEUR``.
SOLVEUR_EXACT = "exact"          # modèle exact HiGHS (#206)
SOLVEUR_RECHERCHE = "recherche"  # recherche arborescente de repli (solveur.py)
SOLVEUR_AVANCE = "avance"        # Avancé en dernier repli
# Affaiblissement des niveaux bridés (issue #213) :
SOLVEUR_SANS_REARR = "sans-rearrangement"  # coup sans toucher au plateau (pert. max nulle)
# « Garder un joker en main » (issue #225, Champion du Monde seul) : meilleur
# coup qui ne joue PAS le joker du chevalet (voir _coup_sans_joker_chevalet).
SOLVEUR_SANS_JOKER = "sans-joker"
# « Réserve d'une tuile » (issue #229, hypothèse H2, Champion du Monde seul) :
# meilleur coup qui GARDE une tuile que le coup du solveur aurait posée
# (voir _coup_qui_garde_une_tuile).
SOLVEUR_RESERVE_TUILE = "reserve-tuile"
# « Retenue au début » (issue #229, hypothèse H1, Champion du Monde seul) :
# meilleur coup plafonné en nombre de tuiles posées (voir
# _appliquer_retenue_debut).
SOLVEUR_RETENUE_DEBUT = "retenue-debut"
# « Petits chiffres » (issue #230, hypothèse H4, Champion du Monde seul) :
# meilleur coup qui GARDE une petite tuile que le coup du solveur aurait
# posée (variante tolérante, voir _coup_qui_garde_une_petite_tuile).
SOLVEUR_PETITS_CHIFFRES = "petits-chiffres"
# « Chances de poser au prochain tour » (issue #231, Champion du Monde seul) :
# coup équivalent (même nombre de tuiles posées, ou une de moins avec la
# variante tolérante) qui laisse un chevalet de meilleur score (voir
# _appliquer_chances_prochain_tour, moteur/sorties.py).
SOLVEUR_CHANCES_PROCHAIN_TOUR = "chances-prochain-tour"
# « Placement du joker » (issue #232, Champion du Monde seul) : coup
# équivalent (même nombre de tuiles posées) qui place le joker du chevalet
# dans une combinaison moins exposée à une reprise par l'adversaire (voir
# _appliquer_placement_joker).
SOLVEUR_PLACEMENT_JOKER = "placement-joker"

LIBELLES_SOLVEUR = {
    SOLVEUR_EXACT: "modèle exact",
    SOLVEUR_RECHERCHE: "recherche de repli",
    SOLVEUR_AVANCE: "Avancé en repli",
    SOLVEUR_SANS_REARR: "sans réarrangement (bridé)",
    SOLVEUR_SANS_JOKER: "garde un joker en main",
    SOLVEUR_RESERVE_TUILE: "réserve d'une tuile",
    SOLVEUR_RETENUE_DEBUT: "retenue au début",
    SOLVEUR_PETITS_CHIFFRES: "garde une petite tuile",
    SOLVEUR_CHANCES_PROCHAIN_TOUR: "meilleures chances au prochain tour",
    SOLVEUR_PLACEMENT_JOKER: "placement du joker le moins exposé",
}


def _marquer_solveur(coup, code):
    """Annote le coup/action renvoyé par Expert du mécanisme qui l'a décidé
    (#211, 5bis). Tolère ``None`` (aucun coup)."""
    if isinstance(coup, dict):
        coup.setdefault("solveur", code)
    return coup


def jouer_niveau_expert(etat, idx, budget_temps=None, on_repli=None,
                        preferer_simple=None, utiliser_exact=None,
                        eval_config=None, on_aucun=None,
                        valeur_max_petits=None):
    """Niveau Expert : joue le coup qui pose le plus grand nombre de tuiles du
    chevalet, en conservant toutes les tuiles du plateau (#206).

    Depuis #206, le coup est calculé par un MODÈLE EXACT (programmation
    linéaire en nombres entiers résolue par HiGHS, ``moteur/solveur_exact.py``),
    qui trouve TOUJOURS le maximum du tour — y compris les victoires immédiates
    et les recombinaisons multi-zones que la recherche arborescente d'avant
    (``moteur/solveur.py``) ratait (Bruno tour 57, Ines tour 85 ; voir le
    rapport de #204). À nombre de tuiles égal, il départage par perturbation
    minimale du plateau (#199), puis points posés, puis économie de jokers.

    **Repli, sans jamais lever ni bloquer le jeu** : si ``highspy``/``numpy``
    est absent, si le budget de temps est dépassé sans solution, ou en cas
    d'erreur, Expert se replie sur la recherche arborescente conservée
    (``solveur.py``), puis sur Avancé. ``on_repli(timeout)``, si fourni, est
    appelé une fois lorsque le modèle exact ne produit pas le coup (``timeout``
    vrai si c'est un dépassement de budget, FAUX pour toute autre cause —
    dépendances absentes ou résultat/erreur invalide, voir
    ``scripts/comparer_niveaux_ia.py`` pour la façon de les distinguer à partir
    de ``solveur_exact.DISPONIBLE``) — uniquement pour la mesure, jamais
    utilisé en jeu normal. ``on_aucun()``, si fourni (#223, point 2), est
    appelé quand le modèle exact PROUVE qu'aucun coup n'est posable — cas
    légitime, distinct d'un repli : Expert reste décidé par le modèle exact,
    qui a simplement conclu qu'il n'y avait rien à jouer.

    ``utiliser_exact`` (``None`` → lit ``UTILISER_SOLVEUR_EXACT``) à ``False``
    rejoue l'ancien comportement (recherche seule) pour la comparaison
    « avant / après ». ``preferer_simple`` et ``budget_temps`` sont transmis
    aux deux moteurs (lus à l'appel pour rester ajustables en simulation).

    ``valeur_max_petits`` (issue #230, ``petits_chiffres``, Champion du
    Monde seul) : relais vers le modèle exact (voir ``solveur_exact.
    resoudre_exact``) — ``None`` (défaut) → comportement inchangé pour tout
    appelant existant, y compris le repli sur la recherche arborescente
    (qui ne connaît pas ce critère)."""
    if budget_temps is None:
        budget_temps = BUDGET_TEMPS_EXPERT
    if preferer_simple is None:
        preferer_simple = PREFERER_SIMPLICITE
    if utiliser_exact is None:
        utiliser_exact = UTILISER_SOLVEUR_EXACT
    if eval_config is None:
        eval_config = EVAL_MAIN_DEFAUT

    if utiliser_exact:
        statut, charge = _coup_exact(etat, idx, budget_temps, preferer_simple,
                                     eval_config,
                                     valeur_max_petits=valeur_max_petits)
        if statut == "coup":
            return _marquer_solveur(charge, SOLVEUR_EXACT)
        if statut == "aucun":
            # Optimum prouvé sans coup : pas de recherche redondante, Avancé
            # tranche directement entre pioche et passe (le modèle exact a
            # décidé qu'aucune pose n'était possible).
            if on_aucun is not None:
                on_aucun()
            return _marquer_solveur(jouer_niveau_avance(etat, idx), SOLVEUR_EXACT)
        # statut == "echec" : repli sur la recherche arborescente, puis Avancé.
        if on_repli is not None:
            on_repli(charge)  # charge = cause_timeout
        coup, _timeout = _coup_recherche(etat, idx, budget_temps, preferer_simple)
        if coup:
            return _marquer_solveur(coup, SOLVEUR_RECHERCHE)
        return _marquer_solveur(jouer_niveau_avance(etat, idx), SOLVEUR_AVANCE)

    # Mode « avant » (sans modèle exact) : recherche seule, puis Avancé.
    coup, timeout = _coup_recherche(etat, idx, budget_temps, preferer_simple)
    if coup:
        return _marquer_solveur(coup, SOLVEUR_RECHERCHE)
    if on_repli is not None:
        on_repli(timeout)
    return _marquer_solveur(jouer_niveau_avance(etat, idx), SOLVEUR_AVANCE)


# --------------------------------------------------------------------------- #
# Échelle des six niveaux : un SEUL moteur exact, réglé par des paramètres
# (issue #213). Voir moteur/niveaux.py pour les paramètres (le seul endroit à
# régler) et la structure cible de l'échelle.
# --------------------------------------------------------------------------- #

# Fonctions HEURISTIQUES historiques conservées (jouer_niveau_debutant/facile/
# intermediaire/avance) : elles ne portent plus l'échelle (c'est le moteur exact
# bridé qui le fait), mais restent le REPLI naturel quand highspy/numpy manquent
# (via jouer_niveau_expert) et le support des tests de tactiques de joker. Ne
# plus s'y référer pour juger de la force d'un NIVEAU : voir jouer_niveau_bride.


def _rng_oubli(etat, idx):
    """RNG du tirage d'oubli (issue #213). Déterministe — donc simulations
    reproductibles — dès que ``config.graine_ia`` est fixée : la graine combine
    (graine, manche, tour, joueur) pour être indépendante de l'ordre d'appel.
    Sans graine (jeu normal), tirage non reproductible."""
    graine = etat.get("config", {}).get("graine_ia")
    if graine is None:
        return random.Random()
    seed = int(graine) & 0xFFFFFFFF
    for v in (etat.get("manche_numero", 1), etat.get("tour_numero", 0), idx):
        seed = (seed * 1_000_003 + int(v)) & 0xFFFFFFFFFFFF
    return random.Random(seed)


def _coup_sans_rearrangement(etat, idx):
    """Meilleur coup qui ne DÉPLACE aucune tuile du plateau : pose depuis la
    main et prolonge les combinaisons existantes, sans jamais recomposer le
    plateau (perturbation garantie nulle, mesure #199). C'est exactement la
    portée d'un joueur à ``perturbation_max=0``."""
    coup = _coup_maximal(etat, idx, ordre_points=True)
    return _marquer_solveur(coup, SOLVEUR_SANS_REARR)


def _coup_selon_perturbation(etat, idx, perturbation_max, budget_temps, on_repli,
                             preferer_simple=None, eval_config=None,
                             on_aucun=None, valeur_max_petits=None):
    """Meilleur coup « vu » compte tenu de la perturbation autorisée.

    ``perturbation_max is None`` → solveur complet (Avancé/Expert/Champion).
    ``perturbation_max == 0`` → coup sans réarrangement (jamais de déplacement).
    ``perturbation_max > 0`` → coup complet s'il ne déplace pas plus de
    ``perturbation_max`` tuiles du plateau, sinon on retombe sur le coup sans
    réarrangement (le joueur ne « voit » pas une recomposition plus ample).

    ``preferer_simple``/``eval_config``/``on_aucun`` (``None`` → réglages par
    défaut, comportement inchangé) : simples relais vers
    ``jouer_niveau_expert``, ajoutés par #223 pour que les scripts de mesure
    puissent faire jouer Expert/Champion du Monde par CE chemin
    (``jouer_niveau_bride``) plutôt que d'appeler ``jouer_niveau_expert``
    directement en dupliquant la logique de vérification de finition.
    ``valeur_max_petits`` (issue #230, ``petits_chiffres``) : même relais,
    ``None`` par défaut."""
    if perturbation_max is None:
        return jouer_niveau_expert(etat, idx, budget_temps=budget_temps,
                                   on_repli=on_repli,
                                   preferer_simple=preferer_simple,
                                   eval_config=eval_config,
                                   on_aucun=on_aucun,
                                   valeur_max_petits=valeur_max_petits)

    sans_rearr = _coup_sans_rearrangement(etat, idx)
    if perturbation_max <= 0:
        return sans_rearr

    complet = jouer_niveau_expert(etat, idx, budget_temps=budget_temps,
                                  on_repli=on_repli,
                                  preferer_simple=preferer_simple,
                                  eval_config=eval_config)
    if not (isinstance(complet, dict) and complet.get("action") == "jouer"):
        return sans_rearr if sans_rearr is not None else complet
    deplacees, _combos = mesurer_perturbation(etat.get("plateau", []),
                                              complet["nouveau_plateau"])
    if deplacees <= perturbation_max:
        return complet
    return sans_rearr if sans_rearr is not None else _piocher_ou_passer(etat)


def _peut_tenter_garde_joker(etat, idx):
    """Portes d'activation de « garder un joker en main » (issue #225, point
    1, Champion du Monde seul) : le chevalet doit contenir un joker, ET aucun
    adversaire ne doit être trop proche de finir — en dessous de
    ``niveaux.SEUIL_PRUDENCE_ADVERSAIRE_GARDE_JOKER`` tuiles en main, il
    pourrait finir avant que garder le joker n'ait payé. Le nombre de tuiles
    d'un adversaire est une information PUBLIQUE (visible de tous les
    joueurs) : ce test ne lit JAMAIS le contenu de sa main."""
    chevalet = etat["joueurs"][idx]["chevalet"]
    if not any(t.get("est_joker") for t in chevalet):
        return False
    seuil = _niveaux.SEUIL_PRUDENCE_ADVERSAIRE_GARDE_JOKER
    for j, joueur in enumerate(etat["joueurs"]):
        if j == idx:
            continue
        if len(joueur["chevalet"]) < seuil:
            return False
    return True


def _coup_sans_joker_chevalet(etat, idx, budget_temps):
    """Meilleur coup qui ne joue AUCUN joker du chevalet (issue #225, point
    2) : résout la position avec un joker du chevalet retiré pour ce calcul
    seulement (le joker réapparaît dans le chevalet restant une fois ce coup
    appliqué par ``verification_finition._etat_apres_coup`` sur l'ÉTAT
    D'ORIGINE, qui le contient toujours — c'est bien ce joker-là qui doit
    permettre de finir au tour suivant).

    Retourne un coup ``{"action": "jouer", ...}`` marqué ``SOLVEUR_SANS_JOKER``,
    ou ``None`` si aucun joker en main, budget nul, ou si le modèle exact ne
    produit pas de coup (dépendances absentes, budget dépassé, aucun coup
    posable sans le joker)."""
    if budget_temps is None or budget_temps <= 0:
        return None
    joueur = etat["joueurs"][idx]
    chevalet = joueur["chevalet"]
    idx_joker = next((i for i, t in enumerate(chevalet) if t.get("est_joker")),
                     None)
    if idx_joker is None:
        return None
    chevalet_sans_joker = chevalet[:idx_joker] + chevalet[idx_joker + 1:]
    joueur2 = dict(joueur)
    joueur2["chevalet"] = chevalet_sans_joker
    joueurs2 = list(etat["joueurs"])
    joueurs2[idx] = joueur2
    etat2 = dict(etat)
    etat2["joueurs"] = joueurs2
    statut, charge = _coup_exact(etat2, idx, budget_temps, PREFERER_SIMPLICITE,
                                 EVAL_MAIN_DEFAUT)
    if statut != "coup":
        return None
    return _marquer_solveur(charge, SOLVEUR_SANS_JOKER)


# --------------------------------------------------------------------------- #
# « Réserve d'une tuile » (issue #229, hypothèse H2, Champion du Monde seul)
# --------------------------------------------------------------------------- #

def _coup_qui_garde_une_tuile(etat, idx, coup_solveur, deadline):
    """Premier coup valide, parmi les tuiles posées par ``coup_solveur``,
    obtenu en retirant CETTE tuile du chevalet avant de résoudre à nouveau —
    même mécanisme que ``_coup_sans_joker_chevalet``, généralisé à une tuile
    quelconque plutôt qu'un joker. Pas de recherche exhaustive du meilleur
    candidat parmi toutes les tuiles possibles (budget) : même
    simplification assumée que pour le joker (#225) — le premier qui
    produit un coup valide est retenu, dans l'ordre où le solveur les a
    posées.

    Retourne ``(coup, id_tuile_gardee)`` marqué ``SOLVEUR_RESERVE_TUILE``,
    ou ``(None, None)`` si budget insuffisant ou si aucune tuile ne
    convient."""
    ids_jouees = list(coup_solveur.get("ids_tuiles") or [])
    if not ids_jouees:
        return None, None
    joueur = etat["joueurs"][idx]
    chevalet = joueur["chevalet"]
    for id_tuile in ids_jouees:
        restant = deadline - time.monotonic()
        if restant <= 0:
            return None, None
        idx_t = next((i for i, t in enumerate(chevalet) if t["id"] == id_tuile),
                     None)
        if idx_t is None:
            continue
        chevalet2 = chevalet[:idx_t] + chevalet[idx_t + 1:]
        joueur2 = dict(joueur)
        joueur2["chevalet"] = chevalet2
        joueurs2 = list(etat["joueurs"])
        joueurs2[idx] = joueur2
        etat2 = dict(etat)
        etat2["joueurs"] = joueurs2
        statut, charge = _coup_exact(etat2, idx, restant, PREFERER_SIMPLICITE,
                                     EVAL_MAIN_DEFAUT)
        if statut != "coup" or not charge.get("ids_tuiles"):
            continue
        return _marquer_solveur(charge, SOLVEUR_RESERVE_TUILE), id_tuile
    return None, None


def _appliquer_reserve_tuile(etat, idx, coup, taille_main, deadline):
    """Stratégie ``reserve_tuile`` (#229, hypothèse H2, Champion du Monde
    seul) : après le coup du solveur (``coup``, qui ne vide PAS la main —
    seul appelant, voir ``jouer_niveau_bride``), essaie de jouer un coup
    qui GARDE une tuile que ``coup`` aurait posée, pour disposer d'un coup
    au tour suivant plutôt que de piocher.

    Joué à la place de ``coup`` seulement si TOUTES les conditions de
    l'issue sont réunies : (a) le candidat pose au moins une tuile ; (b) il
    pose au plus ``niveaux.ECART_MAX_RESERVE`` tuiles de moins que ``coup``;
    (c) sur la position résultante (tapis supposé inchangé), le même
    solveur peut poser au moins une tuile au tour suivant ; (d) le
    chevalet après le coup reste plus grand que
    ``niveaux.SEUIL_FIN_PARTIE_VERIF_FINITION`` (la stratégie ne gêne pas
    la fin de partie, zone déjà couverte par ``verif_finition``/
    ``garde_joker``). La condition (e) (« le meilleur coup ne vide pas la
    main ») est déjà garantie par l'appelant.

    Retourne ``(coup, info)`` — ``coup`` inchangé si la stratégie n'a pas
    pu s'appliquer ; ``info`` un dict de compteurs (#229, point 4) :
    ``{"declenchee": bool, "candidat_existe": bool,
    "peut_jouer_au_tour_suivant": bool | None, "choisi": bool,
    "nb_tuiles_gardees": int, "id_tuile_gardee": str | None}``."""
    info = {"declenchee": True, "candidat_existe": False,
           "peut_jouer_au_tour_suivant": None, "choisi": False,
           "nb_tuiles_gardees": 0, "id_tuile_gardee": None}
    restant = deadline - time.monotonic()
    if restant <= 0:
        return coup, info
    candidat, id_tuile = _coup_qui_garde_une_tuile(etat, idx, coup, deadline)
    if candidat is None:
        return coup, info

    ids_best = coup.get("ids_tuiles") or []
    nb_candidat = len(candidat.get("ids_tuiles") or [])
    if nb_candidat < 1:                                       # condition (a)
        return coup, info
    ecart = len(ids_best) - nb_candidat
    if ecart > _niveaux.ECART_MAX_RESERVE:                    # condition (b)
        return coup, info

    info["candidat_existe"] = True
    info["nb_tuiles_gardees"] = ecart
    info["id_tuile_gardee"] = id_tuile

    restant = deadline - time.monotonic()
    peut_jouer = verification_finition.peut_poser_au_tour_suivant(
        etat, idx, candidat, restant)
    info["peut_jouer_au_tour_suivant"] = peut_jouer
    if not peut_jouer:                                        # condition (c)
        return coup, info

    chevalet_apres = taille_main - nb_candidat
    if chevalet_apres <= _niveaux.SEUIL_FIN_PARTIE_VERIF_FINITION:  # condition (d)
        return coup, info

    info["choisi"] = True
    return candidat, info


# --------------------------------------------------------------------------- #
# « Retenue au début » (issue #229, hypothèse H1, Champion du Monde seul)
# --------------------------------------------------------------------------- #

def _nb_tours_joueur_depuis_ouverture(etat, idx):
    """Nombre de tours déjà joués par le joueur ``idx`` depuis SA PROPRE
    ouverture (mise initiale), sans compter l'ouverture elle-même.

    Dérivé de ``etat["historique"]`` (déjà tenu par ``moteur/partie.py``
    pour CHAQUE tour, tous niveaux et joueur humain confondus, voir
    ``_ajouter_historique``) à partir d'un seul signal NUMÉRIQUE, jamais
    du texte des descriptions : une pose (« jouer ») y est journalisée
    avec ``points`` > 0 (la règle du jeu exige au moins
    ``mise_initiale_min`` points pour la toute première, et toute pose
    retient au moins la valeur d'une tuile réelle ensuite), alors qu'une
    pioche/passe l'est TOUJOURS à 0 points (``partie.piocher``/
    ``passer_tour``). La première entrée de ce joueur à ``points`` > 0 est
    donc forcément son ouverture (elle ne peut pas avoir été précédée d'une
    autre pose : la mise initiale n'était pas encore faite).

    Retourne ``None`` si l'ouverture de ce joueur n'est pas retrouvée dans
    l'historique (mise initiale pas encore faite, partie reprise sans
    historique complet...) — l'appelant doit alors se replier sans
    activer la stratégie (#229, point 3)."""
    entrees = [h for h in (etat.get("historique") or [])
              if h.get("joueur_index") == idx]
    tour_ouverture = next((h.get("tour") for h in entrees
                          if h.get("points", 0) > 0), None)
    if tour_ouverture is None:
        return None
    return sum(1 for h in entrees if h.get("tour", 0) > tour_ouverture)


def _appliquer_retenue_debut(etat, idx, coup, taille_main, budget_temps):
    """Stratégie ``retenue_debut`` (#229, hypothèse H1, Champion du Monde
    seul) : pendant les ``niveaux.TOURS_RETENUE_DEBUT`` premiers tours qui
    suivent SA PROPRE ouverture, tant que le tapis compte moins de
    ``niveaux.TUILES_TAPIS_MAX_RETENUE`` tuiles et que le chevalet compte
    plus de 8 tuiles, plafonne le coup à ``niveaux.POSE_MAX_DEBUT`` tuiles
    posées au plus (et au moins une — jamais de pioche si un coup existe,
    voir la contrainte de l'issue).

    N'a aucun effet (``coup`` inchangé) avant l'ouverture du joueur, hors
    de la fenêtre, hors des seuils de tapis/chevalet, si ``coup`` pose
    déjà au plus le plafond, ou si le modèle exact ne trouve, SOUS LE
    PLAFOND, aucun coup : ``coup`` (potentiellement au-delà du plafond)
    reste alors joué, pour ne jamais remplacer une pose par une pioche.

    Retourne ``(coup, info)`` — ``info`` un dict de compteurs (#229, point
    4) : ``{"declenchee": bool, "choisi": bool, "nb_tuiles_posees": int}``."""
    info = {"declenchee": False, "choisi": False,
           "nb_tuiles_posees": len(coup.get("ids_tuiles") or [])}
    joueur = etat["joueurs"][idx]
    if not joueur.get("mise_initiale_faite"):
        return coup, info
    nb_tours = _nb_tours_joueur_depuis_ouverture(etat, idx)
    if nb_tours is None or nb_tours >= _niveaux.TOURS_RETENUE_DEBUT:
        return coup, info
    nb_tuiles_tapis = sum(len(combo) for combo in etat.get("plateau", []))
    if nb_tuiles_tapis >= _niveaux.TUILES_TAPIS_MAX_RETENUE:
        return coup, info
    if taille_main <= 8:
        return coup, info

    info["declenchee"] = True
    nb_best = len(coup.get("ids_tuiles") or [])
    if nb_best <= _niveaux.POSE_MAX_DEBUT:
        return coup, info
    if budget_temps is None or budget_temps <= 0:
        return coup, info

    statut, charge = _coup_exact(etat, idx, budget_temps, PREFERER_SIMPLICITE,
                                 EVAL_MAIN_DEFAUT,
                                 max_tuiles_posees=_niveaux.POSE_MAX_DEBUT)
    if statut != "coup" or not charge.get("ids_tuiles"):
        # Aucun coup dans le plafond : on garde le coup normal (jamais de
        # pioche si un coup existe, contrainte de l'issue).
        return coup, info

    info["choisi"] = True
    info["nb_tuiles_posees"] = len(charge["ids_tuiles"])
    return _marquer_solveur(charge, SOLVEUR_RETENUE_DEBUT), info


# --------------------------------------------------------------------------- #
# « Petits chiffres » (issue #230, hypothèse H4, Champion du Monde seul)
# --------------------------------------------------------------------------- #

def _ids_petites_tuiles(ids, chevalet):
    """Sous-ensemble de ``ids`` dont la tuile — retrouvée dans ``chevalet``
    — est RÉELLE (jamais un joker) et de valeur 1 à ``niveaux.
    VALEUR_MAX_PETITS``, dans l'ORDRE de ``ids``."""
    par_id = {t["id"]: t for t in chevalet}
    petites = []
    for id_t in ids:
        t = par_id.get(id_t)
        if (t is not None and not t.get("est_joker")
                and (t.get("valeur") or 0) <= _niveaux.VALEUR_MAX_PETITS):
            petites.append(id_t)
    return petites


def _coup_qui_garde_une_petite_tuile(etat, idx, ids_petites, deadline):
    """Même mécanisme que ``_coup_qui_garde_une_tuile`` (#229), restreint aux
    PETITES tuiles posées par le coup du solveur (``ids_petites``, voir
    ``_ids_petites_tuiles``) : premier coup valide obtenu en retirant CETTE
    petite tuile du chevalet avant de résoudre à nouveau (réapplique aussi
    le critère de départage ``petits_chiffres`` sur cette nouvelle
    résolution, pour rester cohérent avec la stratégie).

    Retourne ``(coup, id_tuile_gardee)`` marqué ``SOLVEUR_PETITS_CHIFFRES``,
    ou ``(None, None)`` si budget insuffisant ou si aucune petite tuile ne
    convient."""
    joueur = etat["joueurs"][idx]
    chevalet = joueur["chevalet"]
    for id_tuile in ids_petites:
        restant = deadline - time.monotonic()
        if restant <= 0:
            return None, None
        idx_t = next((i for i, t in enumerate(chevalet) if t["id"] == id_tuile),
                     None)
        if idx_t is None:
            continue
        chevalet2 = chevalet[:idx_t] + chevalet[idx_t + 1:]
        joueur2 = dict(joueur)
        joueur2["chevalet"] = chevalet2
        joueurs2 = list(etat["joueurs"])
        joueurs2[idx] = joueur2
        etat2 = dict(etat)
        etat2["joueurs"] = joueurs2
        statut, charge = _coup_exact(
            etat2, idx, restant, PREFERER_SIMPLICITE, EVAL_MAIN_DEFAUT,
            valeur_max_petits=_niveaux.VALEUR_MAX_PETITS)
        if statut != "coup" or not charge.get("ids_tuiles"):
            continue
        return _marquer_solveur(charge, SOLVEUR_PETITS_CHIFFRES), id_tuile
    return None, None


def _appliquer_petits_chiffres(etat, idx, coup, taille_main, deadline):
    """Stratégie ``petits_chiffres`` (#230, hypothèse H4, Champion du Monde
    seul), variante tolérante (point 3 de l'issue) : au-delà du départage à
    nombre de tuiles posées égal (déjà intégré au modèle exact, voir
    ``jouer_niveau_bride``), essaie de jouer un coup qui GARDE au moins une
    petite tuile que ``coup`` aurait posée, MÊME s'il pose moins de tuiles
    — dans la limite de ``niveaux.ECART_TUILES_PETITS`` (``0`` par défaut :
    variante désactivée, ``coup`` toujours inchangé).

    Joué à la place de ``coup`` seulement si : (a) le candidat pose au
    moins une tuile ; (b) il pose au plus ``niveaux.ECART_TUILES_PETITS``
    tuiles de moins que ``coup`` ; (c) il pose STRICTEMENT moins de petites
    tuiles que ``coup`` (sinon rien n'est gagné à le préférer) ; (d) le
    chevalet après le coup reste strictement supérieur à ``niveaux.
    SEUIL_FIN_PARTIE_VERIF_FINITION`` (ne gêne pas la fin de partie, zone
    déjà couverte par ``verif_finition``/``garde_joker``).

    Retourne ``(coup, info)`` — ``coup`` inchangé si la stratégie n'a pas
    pu s'appliquer ; ``info`` un dict de compteurs (point 5 de l'issue) :
    ``{"declenchee": bool, "candidat_existe": bool, "choisi": bool,
    "nb_petites_posees_avant": int, "nb_petites_posees_apres": int}``."""
    ids_poses = list(coup.get("ids_tuiles") or [])
    chevalet = etat["joueurs"][idx]["chevalet"]
    ids_petites = _ids_petites_tuiles(ids_poses, chevalet)
    info = {"declenchee": True, "candidat_existe": False, "choisi": False,
           "nb_petites_posees_avant": len(ids_petites),
           "nb_petites_posees_apres": len(ids_petites)}
    if _niveaux.ECART_TUILES_PETITS <= 0 or not ids_petites:
        return coup, info
    restant = deadline - time.monotonic()
    if restant <= 0:
        return coup, info

    candidat, _id_tuile = _coup_qui_garde_une_petite_tuile(
        etat, idx, ids_petites, deadline)
    if candidat is None:
        return coup, info

    ids_candidat = candidat.get("ids_tuiles") or []
    nb_candidat = len(ids_candidat)
    if nb_candidat < 1:                                       # condition (a)
        return coup, info
    ecart = len(ids_poses) - nb_candidat
    if ecart > _niveaux.ECART_TUILES_PETITS:                  # condition (b)
        return coup, info

    ids_petites_candidat = _ids_petites_tuiles(ids_candidat, chevalet)
    info["candidat_existe"] = True
    if len(ids_petites_candidat) >= len(ids_petites):          # condition (c)
        return coup, info

    chevalet_apres = taille_main - nb_candidat
    if chevalet_apres <= _niveaux.SEUIL_FIN_PARTIE_VERIF_FINITION:  # (d)
        return coup, info

    info["choisi"] = True
    info["nb_petites_posees_apres"] = len(ids_petites_candidat)
    return candidat, info


# --------------------------------------------------------------------------- #
# « Chances de poser au prochain tour » (issue #231, Champion du Monde seul,
# anciennement « tuiles vivantes » — voir moteur/sorties.py, CONTEXTE.md §13)
# --------------------------------------------------------------------------- #

def _chevalet_restant(chevalet, ids_poses):
    """Chevalet qui resterait après avoir posé les tuiles d'identifiants
    ``ids_poses`` — ``chevalet`` inchangé (nouvelle liste)."""
    ids = set(ids_poses)
    return [t for t in chevalet if t["id"] not in ids]


def _candidats_sorties(etat, idx, coup, deadline, ecart_max):
    """Coups obtenus en retirant, tour à tour, CHACUNE des tuiles que
    ``coup`` pose, puis en résolvant à nouveau — même mécanisme que
    ``_coup_qui_garde_une_tuile``/``_coup_qui_garde_une_petite_tuile``
    (#229/#230), ici pour trouver des arrangements DIFFÉRENTS du MÊME coup
    (pas une main réduite exprès) : retirer une tuile de la pose peut forcer
    le solveur à composer une combinaison concurrente, posant le MÊME
    nombre de tuiles (un véritable « coup équivalent », découvert sans
    reformuler le modèle exact — #231, point 2 : calcul direct en dehors du
    solveur, celui-ci n'étant appelé que pour RETROUVER le coup, jamais pour
    noter les chevalets).

    Ne garde que les candidats posant au plus ``ecart_max`` tuiles de moins
    que ``coup`` (``0`` → seulement les coups à nombre de tuiles STRICTEMENT
    égal, les véritables « coups équivalents » du point 4 de l'issue ;
    ``niveaux.ECART_TUILES_SORTIES`` au-delà, pour la variante tolérante).
    Retourne une liste de coups marqués ``SOLVEUR_CHANCES_PROCHAIN_TOUR``
    (doublons possibles, l'appelant ne garde que le meilleur score)."""
    ids_jouees = list(coup.get("ids_tuiles") or [])
    nb_best = len(ids_jouees)
    joueur = etat["joueurs"][idx]
    chevalet = joueur["chevalet"]
    candidats = []
    for id_tuile in ids_jouees:
        restant = deadline - time.monotonic()
        if restant <= 0:
            break
        idx_t = next((i for i, t in enumerate(chevalet) if t["id"] == id_tuile),
                     None)
        if idx_t is None:
            continue
        chevalet2 = chevalet[:idx_t] + chevalet[idx_t + 1:]
        joueur2 = dict(joueur)
        joueur2["chevalet"] = chevalet2
        joueurs2 = list(etat["joueurs"])
        joueurs2[idx] = joueur2
        etat2 = dict(etat)
        etat2["joueurs"] = joueurs2
        statut, charge = _coup_exact(etat2, idx, restant, PREFERER_SIMPLICITE,
                                     EVAL_MAIN_DEFAUT)
        if statut != "coup" or not charge.get("ids_tuiles"):
            continue
        ecart = nb_best - len(charge["ids_tuiles"])
        if 0 <= ecart <= ecart_max:
            candidats.append((_marquer_solveur(charge, SOLVEUR_CHANCES_PROCHAIN_TOUR),
                              ecart))
    return candidats


def _appliquer_chances_prochain_tour(etat, idx, coup, taille_main, deadline):
    """Stratégie ``chances_prochain_tour`` (#231) : à nombre de tuiles posées
    égal, entre ``coup`` et les coups équivalents trouvés par
    ``_candidats_sorties`` (écart 0), préfère celui qui laisse le chevalet
    au score ``moteur/sorties.score_chevalet`` le plus élevé.

    Variante tolérante (``niveaux.ECART_TUILES_SORTIES``, ``0`` par défaut =
    désactivée) : accepte aussi un candidat posant UNE tuile de moins (écart
    1) si son score dépasse le meilleur score déjà trouvé de plus de
    ``niveaux.SEUIL_GAIN_SORTIES``.

    N'a aucun effet (point 5 de l'issue) si le chevalet qui resterait après
    ``coup`` compte au plus une tuile — rien à comparer (les sorties
    exigent une PAIRE). ``coup`` qui vide la main : déjà écarté par
    l'appelant (``jouer_niveau_bride``), jamais modifié ici.

    Retourne ``(coup, info)`` — ``info`` un dict de compteurs (point 6 de
    l'issue) : ``{"declenchee": bool, "score_avant": float,
    "meilleur_score": float, "choisi": bool,
    "nb_candidats_equivalents": int}``."""
    ids_poses = list(coup.get("ids_tuiles") or [])
    chevalet = etat["joueurs"][idx]["chevalet"]
    chevalet_restant = _chevalet_restant(chevalet, ids_poses)
    info = {"declenchee": False, "score_avant": 0.0, "meilleur_score": 0.0,
           "choisi": False, "nb_candidats_equivalents": 0}
    if len(chevalet_restant) <= 1:
        return coup, info

    info["declenchee"] = True
    plateau_avant = coup.get("nouveau_plateau") or []
    score_avant = _sorties.score_chevalet(chevalet_restant, plateau_avant,
                                          etat, idx)
    info["score_avant"] = score_avant
    info["meilleur_score"] = score_avant

    restant = deadline - time.monotonic()
    if restant <= 0:
        return coup, info

    ecart_max = max(0, _niveaux.ECART_TUILES_SORTIES)
    candidats = _candidats_sorties(etat, idx, coup, deadline, ecart_max)

    meilleur_coup = coup
    meilleur_score = score_avant
    for candidat, ecart in sorted(candidats, key=lambda c: c[1]):
        info["nb_candidats_equivalents"] += 1
        ids_cand = candidat.get("ids_tuiles") or []
        chevalet_cand = _chevalet_restant(chevalet, ids_cand)
        if len(chevalet_cand) <= 1:
            continue
        plateau_cand = candidat.get("nouveau_plateau") or []
        score_cand = _sorties.score_chevalet(chevalet_cand, plateau_cand,
                                              etat, idx)
        if ecart == 0:
            if score_cand > meilleur_score:
                meilleur_score = score_cand
                meilleur_coup = candidat
        elif score_cand - meilleur_score > _niveaux.SEUIL_GAIN_SORTIES:
            meilleur_score = score_cand
            meilleur_coup = candidat

    info["meilleur_score"] = meilleur_score
    if meilleur_coup is not coup:
        info["choisi"] = True
    return meilleur_coup, info


# --------------------------------------------------------------------------- #
# « Placement du joker » (issue #232, Champion du Monde seul) : à nombre de
# tuiles posées égal, préfère le placement d'un joker DEPUIS LE CHEVALET le
# moins exposé à une reprise par l'adversaire — voir CONTEXTE.md §13 pour les
# règles de libération d'un joker VÉRIFIÉES dans ce moteur (échange direct
# uniquement ; les libérations sans remplacement, réservées aux combinaisons
# de 4 tuiles ou plus, sont hors de portée de cette stratégie, déjà évitées
# par le solveur de base).
# --------------------------------------------------------------------------- #

def _ids_jokers_poses(ids_poses, chevalet):
    """Sous-ensemble (dans l'ordre de ``ids_poses``) des ids qui, retrouvés
    dans ``chevalet``, sont des jokers."""
    par_id = {t["id"]: t for t in chevalet}
    return [id_t for id_t in ids_poses
           if (t := par_id.get(id_t)) is not None and t.get("est_joker")]


def _localiser_tuile_sur_plateau(plateau, id_tuile):
    """Position ``(combi_index, position_index)`` de ``id_tuile`` sur
    ``plateau`` (liste de combinaisons de dicts), ou ``(None, None)``."""
    for ci, combo in enumerate(plateau):
        for pi, t in enumerate(combo):
            if t.get("id") == id_tuile:
                return ci, pi
    return None, None


def _types_remplacement_joker(combo_dicts, position_index):
    """Types de tuile (``(couleur, valeur)``) qui remplaceraient directement
    le joker en ``position_index`` de ``combo_dicts`` SANS changer la
    validité de la combinaison (voir ``_tuile_correspond_au_joker``, même
    règle de position pour une suite).

    Restreint aux combinaisons de EXACTEMENT 3 tuiles (``None`` sinon) : une
    combinaison de 4 tuiles ou plus peut libérer son joker SANS tuile de
    remplacement (voir CONTEXTE.md §8, ``_jokers_liberables_par_
    groupe4_sans_remplacement``) — hors de portée de cette stratégie (issue
    #232, déjà évité par le solveur de base). Pour une suite de 3, UNE seule
    valeur convient (même règle de position, qu'elle soit au milieu ou au
    bout — voir CONTEXTE.md §13, point 1 : ce moteur ne distingue PAS les
    deux cas, contrairement à l'intuition de l'énoncé de l'issue). Pour une
    série (groupe) de 3, les DEUX couleurs encore absentes conviennent."""
    combo = [tuile_depuis_dict(d) for d in combo_dicts]
    if len(combo) != 3:
        return None
    r = valider_combinaison(combo)
    if not r["valide"]:
        return None
    if r["type"] == "suite":
        i0, t0 = next((i, t) for i, t in enumerate(combo) if not t.est_joker)
        valeur_attendue = t0.valeur - i0 + position_index
        if valeur_attendue < VALEUR_MIN or valeur_attendue > VALEUR_MAX:
            return None
        return [(t0.couleur, valeur_attendue)]
    valeur = next(t.valeur for t in combo if not t.est_joker)
    couleurs_utilisees = {t.couleur for t in combo if not t.est_joker}
    return [(c, valeur) for c in COULEURS if c not in couleurs_utilisees]


def _exposition_coup_joker(etat, idx, coup):
    """Exposition totale d'un coup qui pose un ou plusieurs jokers DEPUIS LE
    CHEVALET (issue #232, point 3) : pour chacun, la somme des exemplaires
    encore INCONNUS (brique « Inconnues », #219 — jamais la main adverse,
    seulement sa taille) des types de tuile qui pourraient le remplacer dans
    sa combinaison (voir ``_types_remplacement_joker``). Une exposition
    nulle signifie que l'adversaire ne peut pas le reprendre (tous les
    exemplaires sont déjà connus, sur le plateau ou dans NOTRE main).

    Nuance d'Alain (point 4 de l'issue) : si, APRÈS le coup, notre propre
    main contient encore la tuile qui remplacerait l'un des jokers posés,
    ce placement est EXCLU du critère (``info["exclu"] = True``) — un bon
    joueur jouerait cette tuile plutôt que le joker, question de génération
    de coup hors de portée de cette stratégie de départage.

    Retourne ``(score, info)`` — ``score`` est ``None`` si ``coup`` ne pose
    aucun joker mesurable (aucun joker posé, ou chacun atterrit dans une
    combinaison hors de portée — voir ``_types_remplacement_joker``) :
    ``info`` vaut alors ``{"a_pose_un_joker": bool, "exclu": False,
    "details": []}``. Sinon ``info`` contient aussi ``"exposition_brute"``
    (somme, sans la variante d'asymétrie) et ``"details"`` (une entrée par
    joker mesurable : ``{"id_joker", "combi_index", "position_index",
    "types", "exposition", "en_main", "ids_autres"}``).

    Variante d'asymétrie (point 5 de l'issue, ``niveaux.
    ASYMETRIE_JOKER_ACTIVE``, ``False`` par défaut) : ``score`` devient
    ``exposition - niveaux.POIDS_ASYMETRIE_JOKER * ma_chance_de_reprise``,
    où ``ma_chance_de_reprise`` est la probabilité (brique « Inconnues »)
    que CE JOUEUR pioche lui-même une tuile de remplacement — sans effet
    tant que la variante reste désactivée (``score == exposition_brute``)."""
    ids_poses = list(coup.get("ids_tuiles") or [])
    chevalet = etat["joueurs"][idx]["chevalet"]
    ids_jokers = _ids_jokers_poses(ids_poses, chevalet)
    if not ids_jokers:
        return None, {"a_pose_un_joker": False, "exclu": False, "details": []}

    nouveau_plateau = coup.get("nouveau_plateau") or []
    ids_poses_set = set(ids_poses)
    chevalet_apres = [t for t in chevalet if t["id"] not in ids_poses_set]
    tailles_adv = [len(j.get("chevalet", [])) for i, j in enumerate(etat["joueurs"])
                  if i != idx]
    taille_pioche = len(etat.get("pioche", []))
    inconnues = _inconnues.calculer_inconnues(nouveau_plateau, chevalet_apres,
                                              tailles_adv, taille_pioche)

    total = 0
    asym_total = 0.0
    exclu = False
    details = []
    for id_j in ids_jokers:
        ci, pi = _localiser_tuile_sur_plateau(nouveau_plateau, id_j)
        if ci is None:
            continue
        combo = nouveau_plateau[ci]
        types = _types_remplacement_joker(combo, pi)
        if not types:
            continue
        expo = sum(inconnues.exemplaires_restants(t) for t in types)
        en_main = any(not tt.get("est_joker") and (tt.get("couleur"), tt.get("valeur")) == t
                     for t in types for tt in chevalet_apres)
        total += expo
        if _niveaux.ASYMETRIE_JOKER_ACTIVE:
            asym_total += sum(_inconnues.proba_tuile_dans_pioche(inconnues, t)
                              for t in types)
        if en_main:
            exclu = True
        ids_autres = sorted(t["id"] for t in combo if t["id"] != id_j)
        details.append({"id_joker": id_j, "combi_index": ci, "position_index": pi,
                        "types": types, "exposition": expo, "en_main": en_main,
                        "ids_autres": ids_autres})

    if not details:
        return None, {"a_pose_un_joker": True, "exclu": False, "details": []}

    score = total
    if _niveaux.ASYMETRIE_JOKER_ACTIVE:
        score = total - _niveaux.POIDS_ASYMETRIE_JOKER * asym_total
    return score, {"a_pose_un_joker": True, "exclu": exclu,
                   "exposition_brute": total, "details": details}


def _candidats_placement_joker(etat, idx, coup, deadline):
    """Coups équivalents (MÊME nombre de tuiles posées, strictement — pas de
    variante tolérante pour cette stratégie) obtenus en retirant, tour à
    tour, CHACUNE des tuiles que ``coup`` pose, puis en résolvant à nouveau —
    même mécanisme que ``_candidats_sorties`` (#231). Retourne une liste de
    coups marqués ``SOLVEUR_PLACEMENT_JOKER``."""
    ids_jouees = list(coup.get("ids_tuiles") or [])
    nb_best = len(ids_jouees)
    joueur = etat["joueurs"][idx]
    chevalet = joueur["chevalet"]
    candidats = []
    for id_tuile in ids_jouees:
        restant = deadline - time.monotonic()
        if restant <= 0:
            break
        idx_t = next((i for i, t in enumerate(chevalet) if t["id"] == id_tuile),
                     None)
        if idx_t is None:
            continue
        chevalet2 = chevalet[:idx_t] + chevalet[idx_t + 1:]
        joueur2 = dict(joueur)
        joueur2["chevalet"] = chevalet2
        joueurs2 = list(etat["joueurs"])
        joueurs2[idx] = joueur2
        etat2 = dict(etat)
        etat2["joueurs"] = joueurs2
        statut, charge = _coup_exact(etat2, idx, restant, PREFERER_SIMPLICITE,
                                     EVAL_MAIN_DEFAUT)
        if statut != "coup" or not charge.get("ids_tuiles"):
            continue
        if len(charge["ids_tuiles"]) != nb_best:
            continue
        candidats.append(_marquer_solveur(charge, SOLVEUR_PLACEMENT_JOKER))
    return candidats


def _appliquer_placement_joker(etat, idx, coup, taille_main, deadline):
    """Stratégie ``placement_joker`` (#232) : à nombre de tuiles posées égal,
    entre ``coup`` et les coups équivalents trouvés par
    ``_candidats_placement_joker``, préfère celui dont l'exposition du/des
    joker(s) posé(s) (``_exposition_coup_joker``) est la plus faible.

    N'a aucun effet (``coup`` inchangé) si : ``coup`` ne pose aucun joker
    mesurable depuis le chevalet ; ou si ``coup`` est lui-même EXCLU du
    critère (point 4 de l'issue — notre main contient encore la tuile de
    remplacement, voir ``_exposition_coup_joker``) ; ou si aucun candidat
    équivalent n'a une exposition strictement meilleure. Les candidats
    eux-mêmes EXCLUS (même nuance) ne sont jamais choisis.

    Retourne ``(coup, info)`` — ``info`` un dict de compteurs (point 6 de
    l'issue) : ``{"declenchee": bool, "exclu": bool,
    "nb_candidats_equivalents": int, "choisi": bool,
    "exposition_avant": float|None, "meilleure_exposition": float|None,
    "details": [...]}`` (``details``, voir ``_exposition_coup_joker``, du
    coup FINALEMENT retenu)."""
    expo_avant, info_expo = _exposition_coup_joker(etat, idx, coup)
    info = {"declenchee": bool(info_expo.get("details")),
           "exclu": info_expo.get("exclu", False),
           "nb_candidats_equivalents": 0, "choisi": False,
           "exposition_avant": expo_avant, "meilleure_exposition": expo_avant,
           "details": info_expo.get("details", [])}
    if expo_avant is None or not info["declenchee"]:
        return coup, info
    if info_expo["exclu"]:
        return coup, info

    restant = deadline - time.monotonic()
    if restant <= 0:
        return coup, info

    candidats = _candidats_placement_joker(etat, idx, coup, deadline)

    meilleur_coup = coup
    meilleure_expo = expo_avant
    meilleure_info_expo = info_expo
    for candidat in candidats:
        info["nb_candidats_equivalents"] += 1
        expo_cand, info_expo_cand = _exposition_coup_joker(etat, idx, candidat)
        if expo_cand is None or info_expo_cand["exclu"]:
            continue
        if expo_cand < meilleure_expo:
            meilleure_expo = expo_cand
            meilleur_coup = candidat
            meilleure_info_expo = info_expo_cand

    info["meilleure_exposition"] = meilleure_expo
    info["details"] = meilleure_info_expo.get("details", [])
    if meilleur_coup is not coup:
        info["choisi"] = True
    return meilleur_coup, info


def _candidats_finition(etat, idx, coup_solveur, budget_temps=None,
                        garder_joker=False):
    """Coups candidats pour la vérification de finition (#221, point 2 ;
    troisième candidat ajouté par #225, point 2) : toujours ``coup_solveur``
    (le meilleur coup du solveur, en premier — voir
    ``verification_finition.verifier``) puis, s'ils existent et diffèrent :

    1. le meilleur coup SANS réarrangement du plateau
       (``_coup_sans_rearrangement``) — qui, ne déplaçant AUCUNE tuile du
       plateau, ne reprend jamais un joker déjà posé. Approximation
       documentée du point 2 de #221 (« le meilleur coup qui laisse en place
       les jokers du tapis ») : plus restrictive qu'exigé (elle exclut aussi
       les coups qui déplaceraient des tuiles RÉELLES sans toucher aux
       jokers), mais réutilise un mécanisme déjà existant et testé sans
       dupliquer de logique ;
    2. si ``garder_joker`` (Champion du Monde seul, #225) et que les portes
       d'activation (``_peut_tenter_garde_joker``) le permettent, le meilleur
       coup qui NE JOUE PAS le joker du chevalet (``_coup_sans_joker_chevalet``).

    Retourne ``(candidats, idx_garde_joker)`` — ``idx_garde_joker`` est
    l'index, dans ``candidats``, du candidat « garder un joker en main »
    s'il a été ajouté, sinon ``None``."""
    candidats = [coup_solveur]
    sans_rearr = _coup_sans_rearrangement(etat, idx)
    if (isinstance(sans_rearr, dict) and sans_rearr.get("action") == "jouer"
            and sans_rearr.get("ids_tuiles")
            and verification_finition.coups_differents(sans_rearr, coup_solveur)):
        candidats.append(sans_rearr)

    idx_garde_joker = None
    if garder_joker and _peut_tenter_garde_joker(etat, idx):
        sans_joker = _coup_sans_joker_chevalet(etat, idx, budget_temps)
        if (isinstance(sans_joker, dict) and sans_joker.get("action") == "jouer"
                and sans_joker.get("ids_tuiles")
                and verification_finition.coups_differents(sans_joker, coup_solveur)):
            candidats.append(sans_joker)
            idx_garde_joker = len(candidats) - 1
    return candidats, idx_garde_joker


def _verifier_finition_fin_de_partie(etat, idx, coup, taille_main, deadline,
                                     garder_joker=False):
    """Vérification de finition en fin de partie (issue #221, étape 1 de la
    brique « Deux tours » — voir ``moteur/verification_finition.py`` ;
    ``garder_joker`` ajouté par #225, point 2, ``False`` par défaut →
    comportement strictement inchangé pour tout appelant existant).

    Ne s'applique (appelée uniquement pour Expert/Champion du Monde, et
    seulement si le coup du solveur ne vide pas déjà le chevalet — voir
    ``jouer_niveau_bride``) que si le chevalet compte au plus
    ``niveaux.SEUIL_FIN_PARTIE_VERIF_FINITION`` tuiles ET que ``coup`` a été
    décidé par le modèle exact (``SOLVEUR_EXACT``) — si ce n'est pas le cas
    (dépendances absentes, repli déjà survenu pour ce tour faute de budget),
    la vérification, qui s'appuie sur CE MÊME solveur, ne peut de toute façon
    pas s'exécuter non plus : repli silencieux, statut ``SOLVEUR_NON_EXACT``
    (distingué de ``BUDGET_EPUISE`` depuis #223 — un budget réellement épuisé
    PENDANT la vérification est une situation différente, voir
    ``verification_finition.verifier``).

    Si ``garder_joker`` est actif (Champion du Monde seul) ET que le chevalet
    contient un joker, annote le coup choisi de la clé ``garde_joker_info``
    (issue #225, point 3 — compteurs de campagne) : ``{"joker_en_main": True,
    "candidat_existe": bool, "permet_de_finir": bool | None, "choisi": bool}``.
    ``permet_de_finir`` vaut ``None`` quand la question n'a pas été tranchée
    (le candidat n'a jamais été atteint par ``verifier`` — ``candidats[0]``
    ou le candidat sans réarrangement suffisait déjà — ou budget épuisé avant
    de l'atteindre) : ce cas n'est compté ni comme « permet de finir » ni
    comme « ne permet pas ». Clé TOUJOURS absente pour Expert/Avancé (
    ``garder_joker=False``) : décisions et forme du coup strictement
    inchangées pour ces niveaux.

    Retourne ``(coup, statut)`` — ``coup`` inchangé si la vérification ne
    s'applique pas ou n'aboutit à rien de nouveau."""
    if taille_main > _niveaux.SEUIL_FIN_PARTIE_VERIF_FINITION:
        return coup, verification_finition.NON_APPLICABLE
    if coup.get("solveur") != SOLVEUR_EXACT:
        return coup, verification_finition.SOLVEUR_NON_EXACT

    budget_restant = deadline - time.monotonic()
    candidats, idx_garde_joker = _candidats_finition(
        etat, idx, coup, budget_restant, garder_joker)
    coup_choisi, statut = verification_finition.verifier(
        etat, idx, candidats, deadline, idx_garde_joker)

    joker_en_main = garder_joker and any(
        t.get("est_joker") for t in etat["joueurs"][idx]["chevalet"])
    if joker_en_main:
        if statut == verification_finition.APPLIQUEE_GARDE_JOKER:
            permet_de_finir = True
        elif (statut == verification_finition.APPLIQUEE_AUCUN_CANDIDAT
              and idx_garde_joker is not None):
            permet_de_finir = False
        else:
            permet_de_finir = None
        coup_choisi["garde_joker_info"] = {
            "joker_en_main": True,
            "candidat_existe": idx_garde_joker is not None,
            "permet_de_finir": permet_de_finir,
            "choisi": statut == verification_finition.APPLIQUEE_GARDE_JOKER,
        }
    return coup_choisi, statut


def jouer_niveau_bride(etat, idx, nom_niveau, budget_temps=None, rng=None,
                       on_repli=None, preferer_simple=None, eval_config=None,
                       on_aucun=None):
    """Joue le tour du niveau ``nom_niveau`` avec le moteur exact RÉGLÉ par les
    paramètres de ``moteur/niveaux.py`` (issue #213).

    1. calcule le meilleur coup que le niveau « voit » (borné par
       ``perturbation_max``) ;
    2. un coup qui VIDE la main gagne la partie : renvoyé tel quel, jamais
       oublié ni dégradé (§13) ;
    3. sinon, avec la probabilité ``taux_oubli`` (réduite si la main est petite,
       voir ``niveaux.taux_oubli_effectif``), le joueur « oublie » le coup et
       pioche à la place (tour raté). Tirage reproductible sous ``graine_ia``.

    Le mécanisme ayant décidé le coup est annoté sur l'action (clé ``solveur``,
    journalisée) : le repli silencieux quand highspy/numpy manquent reste donc
    traçable (``recherche``/``avance`` au lieu de ``exact``).

    ``preferer_simple``/``eval_config`` (``None`` → réglages par défaut,
    comportement inchangé pour ``jouer_ia`` et tout appelant existant) : relais
    vers ``_coup_selon_perturbation``, ajoutés par #223 (point 3) pour que
    ``scripts/comparer_niveaux_ia.py`` fasse jouer Expert par ce MÊME chemin
    de production que le jeu, sans dupliquer la logique de vérification de
    finition ci-dessous avec sa propre échéance. ``on_aucun`` : voir
    ``jouer_niveau_expert`` — cas légitime (aucun coup posable, prouvé par le
    modèle exact), distinct d'un repli.

    ``petits_chiffres`` (#230, hypothèse H4, Champion du Monde seul) :
    limité, comme toutes les stratégies ci-dessous, au chevalet strictement
    supérieur à ``niveaux.SEUIL_FIN_PARTIE_VERIF_FINITION`` AVANT de jouer
    (point 4 de l'issue — garder une petite tuile gêne la fin de partie) ;
    le critère de départage à nombre de tuiles posées égal (point 2) est
    intégré DIRECTEMENT au modèle exact ci-dessous (``valeur_max_petits``) ;
    la variante tolérante (point 3) est appliquée plus bas, après le coup
    normal, comme ``reserve_tuile``/``retenue_debut``."""
    bridage = _niveaux.bridage_pour(nom_niveau)
    if rng is None:
        rng = _rng_oubli(etat, idx)
    taille_main = len(etat["joueurs"][idx]["chevalet"])

    petits_chiffres_actif = (
        bridage.petits_chiffres
        and taille_main > _niveaux.SEUIL_FIN_PARTIE_VERIF_FINITION)
    valeur_max_petits = (_niveaux.VALEUR_MAX_PETITS
                         if petits_chiffres_actif else None)

    debut_tour = time.monotonic()
    coup = _coup_selon_perturbation(
        etat, idx, bridage.perturbation_max, budget_temps, on_repli,
        preferer_simple=preferer_simple, eval_config=eval_config,
        on_aucun=on_aucun, valeur_max_petits=valeur_max_petits)

    if not (isinstance(coup, dict) and coup.get("action") == "jouer"):
        # Aucun coup posable : pioche/passe (déjà décidé par le moteur). Tracé
        # comme « pas de coup à comparer » (#223, point 4) uniquement pour les
        # niveaux où la vérification de finition est active, dans le même
        # esprit que l'annotation ``solveur`` : un repli silencieux, mais
        # traçable pour les rapports de campagne — jamais utilisé par le jeu.
        repli = coup if isinstance(coup, dict) else _piocher_ou_passer(etat)
        if bridage.verif_finition and isinstance(repli, dict):
            repli["verif_finition"] = verification_finition.PAS_DE_COUP_A_COMPARER
        return repli

    # Un coup qui vide la main gagne : jamais oublié (§13), et JAMAIS soumis
    # à la vérification de finition ci-dessous (issue #221, point 4 : « si le
    # meilleur coup du solveur vide déjà le chevalet, il est joué, sans
    # aucune vérification »).
    vide_la_main = (taille_main - len(coup.get("ids_tuiles") or [])) <= 0
    if vide_la_main:
        return coup

    # Limite de calcul PARTAGÉE avec le coup normal (#221, point 5), désormais
    # commune à TOUTES les stratégies ci-dessous (#229) : une seule échéance
    # pour tout le tour — ``debut_tour`` a été relevé avant le calcul du coup
    # normal ci-dessus, qui en a donc déjà consommé une partie.
    budget_total = budget_temps if budget_temps is not None \
        else BUDGET_TEMPS_EXPERT
    deadline = debut_tour + budget_total

    if bridage.chances_prochain_tour:
        # #231 : à nombre de tuiles posées égal (le départage "petits_
        # chiffres" ci-dessus, s'il est actif, est déjà intégré au coup
        # normal via ``valeur_max_petits``), préfère le chevalet restant au
        # meilleur score ``sorties.score_chevalet``. Appliqué AVANT les
        # variantes tolérantes ci-dessous (``reserve_tuile``/``retenue_
        # debut``/``petits_chiffres``), qui peuvent réduire le nombre de
        # tuiles posées : les comparer à CE stade reviendrait à comparer des
        # coups qui ne posent déjà plus le même nombre de tuiles.
        coup, info_sorties = _appliquer_chances_prochain_tour(
            etat, idx, coup, taille_main, deadline)
        coup["chances_prochain_tour_info"] = info_sorties

    if bridage.placement_joker:
        # #232 : à nombre de tuiles posées égal, préfère le placement d'un
        # joker du chevalet le moins exposé à une reprise par l'adversaire.
        # Même raisonnement d'ordre que ``chances_prochain_tour`` ci-dessus :
        # appliqué AVANT les variantes tolérantes qui peuvent réduire le
        # nombre de tuiles posées (``reserve_tuile``/``retenue_debut``/
        # ``petits_chiffres``).
        coup, info_joker = _appliquer_placement_joker(
            etat, idx, coup, taille_main, deadline)
        coup["placement_joker_info"] = info_joker

    if bridage.reserve_tuile:
        # #229, hypothèse H2 : garder une tuile que le coup aurait posée.
        # Appliqué AVANT la vérification de finition ci-dessous — les deux
        # zones ne se recoupent jamais par construction (la condition (d)
        # de ``_appliquer_reserve_tuile`` exige un chevalet après coup
        # strictement supérieur à ``SEUIL_FIN_PARTIE_VERIF_FINITION`` : si
        # elle change le coup, la main AVANT ce tour est donc elle aussi
        # au-delà de ce seuil, et la vérification de finition sera de toute
        # façon ``NON_APPLICABLE``).
        coup, info_reserve = _appliquer_reserve_tuile(
            etat, idx, coup, taille_main, deadline)
        coup["reserve_tuile_info"] = info_reserve

    if bridage.retenue_debut:
        # #229, hypothèse H1 : plafonner la pose pendant les premiers tours
        # qui suivent l'ouverture — seuil chevalet > 8 utilisé par la
        # stratégie elle-même place aussi cette zone au-delà de
        # ``SEUIL_FIN_PARTIE_VERIF_FINITION``, même raisonnement que ci-dessus.
        restant = deadline - time.monotonic()
        coup, info_retenue = _appliquer_retenue_debut(
            etat, idx, coup, taille_main, restant)
        coup["retenue_debut_info"] = info_retenue

    if petits_chiffres_actif:
        # #230, hypothèse H4, variante tolérante (point 3) : le départage à
        # nombre de tuiles posées égal est déjà intégré au coup normal
        # ci-dessus (``valeur_max_petits``) — ceci est l'essai SUPPLÉMENTAIRE
        # qui peut poser moins de tuiles pour garder une petite tuile,
        # désactivé par défaut (``ECART_TUILES_PETITS == 0``).
        coup, info_petits = _appliquer_petits_chiffres(
            etat, idx, coup, taille_main, deadline)
        coup["petits_chiffres_info"] = info_petits

    if bridage.verif_finition:
        coup, statut_verif = _verifier_finition_fin_de_partie(
            etat, idx, coup, taille_main, deadline,
            garder_joker=bridage.garder_joker_fin_partie)
        coup["verif_finition"] = statut_verif

    p = _niveaux.taux_oubli_effectif(bridage.taux_oubli, taille_main)
    if p > 0 and rng.random() < p:
        repli = _piocher_ou_passer(etat)
        # On conserve la trace du mécanisme + marque explicite d'oubli.
        repli["solveur"] = coup.get("solveur")
        repli["oubli"] = True
        return repli
    return coup


def _fabriquer_niveau(nom_niveau):
    """Fabrique la fonction de niveau (signature ``(etat, idx)``) branchée sur
    le moteur bridé pour ``nom_niveau``."""
    def _jouer(etat, idx):
        return jouer_niveau_bride(etat, idx, nom_niveau)
    _jouer.__name__ = "jouer_niveau_bride_" + nom_niveau.replace(" ", "_")
    return _jouer


# NIVEAUX_IA : les six niveaux (issue #213), tous branchés sur le moteur exact
# bridé. Clés = libellés de ``config.NIVEAUX`` (« Champion du Monde » inclus).
NIVEAUX_IA = {nom: _fabriquer_niveau(nom) for nom in _niveaux.ECHELLE}


def jouer_ia(etat, joueur_index):
    """Point d'entrée : joue le tour selon le niveau du joueur (défaut : le
    niveau le plus faible). Tous les niveaux passent par le même moteur exact
    réglé par ``moteur/niveaux.py`` (issue #213)."""
    niveau = etat["joueurs"][joueur_index].get("niveau")
    if niveau not in NIVEAUX_IA:
        niveau = _niveaux.ECHELLE[0]
    return jouer_niveau_bride(etat, joueur_index, niveau)
