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

from rummikub.config import VALEUR_MIN, VALEUR_MAX, NB_SERIES
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


def _coup_exact(etat, idx, budget_temps, preferer_simple, eval_config=None):
    """Modèle exact (#206). Ne lève JAMAIS. Retourne ``(statut, charge)`` :

    * ``("coup", coup)`` — un coup optimal a été trouvé ;
    * ``("aucun", None)`` — optimum PROUVÉ : aucune tuile posable (ou mise
      initiale inatteignable). Inutile de lancer la recherche de repli
      (incomplète) après un modèle COMPLET : Expert passe directement à Avancé
      pour décider pioche/passe ;
    * ``("echec", cause_timeout)`` — le modèle n'a pas pu conclure (dépendances
      absentes, budget dépassé sans solution, résultat non valide, erreur) :
      l'appelant se replie sur la recherche arborescente. ``cause_timeout``
      vaut ``True`` pour un dépassement de budget, ``False`` sinon."""
    try:
        res = resoudre_exact(etat, idx, budget_temps=budget_temps,
                             preferer_simple=preferer_simple,
                             eval_config=eval_config)
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

LIBELLES_SOLVEUR = {
    SOLVEUR_EXACT: "modèle exact",
    SOLVEUR_RECHERCHE: "recherche de repli",
    SOLVEUR_AVANCE: "Avancé en repli",
    SOLVEUR_SANS_REARR: "sans réarrangement (bridé)",
}


def _marquer_solveur(coup, code):
    """Annote le coup/action renvoyé par Expert du mécanisme qui l'a décidé
    (#211, 5bis). Tolère ``None`` (aucun coup)."""
    if isinstance(coup, dict):
        coup.setdefault("solveur", code)
    return coup


def jouer_niveau_expert(etat, idx, budget_temps=None, on_repli=None,
                        preferer_simple=None, utiliser_exact=None,
                        eval_config=None, on_aucun=None):
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
    aux deux moteurs (lus à l'appel pour rester ajustables en simulation)."""
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
                                     eval_config)
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
# Échelle des cinq niveaux : un SEUL moteur exact, réglé par des paramètres
# (issue #213). Voir moteur/niveaux.py pour les paramètres (le seul endroit à
# régler) et la structure de l'échelle.
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
        # aléa de jeu (tirage de l'oubli des niveaux), sans enjeu de sécurité
        return random.Random()  # noqa: S311  # nosec B311
    seed = int(graine) & 0xFFFFFFFF
    for v in (etat.get("manche_numero", 1), etat.get("tour_numero", 0), idx):
        seed = (seed * 1_000_003 + int(v)) & 0xFFFFFFFFFFFF
    # aléa de jeu (tirage de l'oubli des niveaux), sans enjeu de sécurité
    return random.Random(seed)  # noqa: S311  # nosec B311


def _coup_sans_rearrangement(etat, idx):
    """Meilleur coup qui ne DÉPLACE aucune tuile du plateau : pose depuis la
    main et prolonge les combinaisons existantes, sans jamais recomposer le
    plateau (perturbation garantie nulle, mesure #199). C'est exactement la
    portée d'un joueur à ``perturbation_max=0``."""
    coup = _coup_maximal(etat, idx, ordre_points=True)
    return _marquer_solveur(coup, SOLVEUR_SANS_REARR)


def _coup_selon_perturbation(etat, idx, perturbation_max, budget_temps, on_repli,
                             preferer_simple=None, eval_config=None,
                             on_aucun=None):
    """Meilleur coup « vu » compte tenu de la perturbation autorisée.

    ``perturbation_max is None`` → solveur complet (Avancé/Expert).
    ``perturbation_max == 0`` → coup sans réarrangement (jamais de déplacement).
    ``perturbation_max > 0`` → coup complet s'il ne déplace pas plus de
    ``perturbation_max`` tuiles du plateau, sinon on retombe sur le coup sans
    réarrangement (le joueur ne « voit » pas une recomposition plus ample).

    ``preferer_simple``/``eval_config``/``on_aucun`` (``None`` → réglages par
    défaut, comportement inchangé) : simples relais vers
    ``jouer_niveau_expert``, ajoutés par #223 pour que les scripts de mesure
    puissent faire jouer Expert par CE chemin (``jouer_niveau_bride``) plutôt
    que d'appeler ``jouer_niveau_expert`` directement en dupliquant la
    logique de ce niveau."""
    if perturbation_max is None:
        return jouer_niveau_expert(etat, idx, budget_temps=budget_temps,
                                   on_repli=on_repli,
                                   preferer_simple=preferer_simple,
                                   eval_config=eval_config,
                                   on_aucun=on_aucun)

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



# --------------------------------------------------------------------------- #
# Gestion du joker (issues #253/#254) — REMPLACE la règle d'attente de #252 :
# voir docs/contexte/ia_anti_don_joker.md pour la définition complète, l'arbre
# de décision exact et les limites. Règles, appliquées DANS CET ORDRE par
# ``jouer_niveau_bride`` à un coup déjà choisi par le niveau (jamais un coup
# gagnant — exception absolue, voir plus bas) :
#
#   1. joker en main UTILE, évalué SÉPARÉMENT pour chaque joker (#254, point
#      4 — REMPLACE l'évaluation collective de #253)
#      (``_appliquer_joker_utile``) : un joker de la main n'est joué que
#      s'il permet de poser STRICTEMENT plus de tuiles RÉELLES que le
#      meilleur coup sans lui (les autres jokers restant disponibles) —
#      SAUF en fin de match à plusieurs manches, où un joker inutile déjà
#      placé par le coup de base est posé quand même pour éviter sa
#      pénalité (#254, point 7) ;
#   2. échange différé (``_appliquer_echange_differe``) : un échange
#      facultatif « en réserve » (personne d'autre ne peut le prendre — test
#      complété par #254, point 1) que l'IA ne peut pas utiliser avec sa
#      main peut être différé ; toute pioche faute d'alternative compte
#      désormais dans le délai (#254, point 3) ; l'échange forcé par le
#      délai est désormais soumis à la règle 3 ci-dessous comme n'importe
#      quel autre coup (#254, point 2) ;
#   3. joker LIBRE évité (``_appliquer_joker_libre``) : parmi les coups
#      possibles, l'IA évite ceux qui rendent un NOUVEAU joker libre (nouvelle
#      définition d'Alain, ci-dessous — REMPLACE la notion de « joker
#      offert » de #252), y compris en posant moins de tuiles ; si aucune
#      alternative n'y échappe, elle pioche — SANS compteur ni limite (la
#      pioche bornée à 2 tours de #252 est SUPPRIMÉE) — SAUF si la pioche
#      est vide, où elle joue malgré tout le meilleur coup disponible (#254,
#      point 5), sans quoi passer n'apporterait rien de plus.
# --------------------------------------------------------------------------- #

def _jokers_libres_par_bout_suite(plateau):
    """Jokers en BOUT de suite directement détachables SANS AUCUNE tuile de
    remplacement : la suite, privée de ce joker, reste une suite valide
    SEULE (au moins 3 tuiles restantes) — l'une des trois voies de la
    définition d'un joker « libre » (#253, nouvelle définition d'Alain, qui
    REMPLACE la notion de « joker offert » de #252).

    Distinct de :func:`_jokers_detachables_par_extension` (#150, #252) :
    cette dernière exige TOUJOURS une tuile du chevalet jouée à l'extrémité
    opposée (même quand la portion restante, sans extension, est déjà
    valide seule) — elle répond à la question « l'adversaire peut-il JOUER
    une tuile pour détacher ce joker », pas « peut-il le reprendre SANS
    rien poser », donc ne convient plus à la nouvelle définition. Ex. :
    suite rouge joker-7-8-9 (4 tuiles, joker en tête) → retirer le joker
    laisse 7-8-9 (valide, 3 tuiles) : le joker est libre, sans qu'aucune
    tuile ne soit nécessaire.

    Retourne ``[{"combi_index", "joker", "reste"}, ...]``."""
    resultats = []
    for ci, combo in enumerate(plateau):
        r = valider_combinaison(combo)
        if not r["valide"] or r["type"] != "suite" or len(combo) < 4:
            continue
        for bout in ("debut", "fin"):
            joker = combo[0] if bout == "debut" else combo[-1]
            if not joker.est_joker:
                continue
            reste = combo[1:] if bout == "debut" else combo[:-1]
            if len(reste) >= 3 and valider_suite(reste)["valide"]:
                resultats.append({"combi_index": ci, "joker": joker,
                                  "reste": reste})
    return resultats


def jokers_libres_sur_plateau(plateau):
    """Ids des jokers du ``plateau`` « libres » (issue #253, définition
    d'Alain qui REMPLACE la notion de « joker offert » de #252) : un joker
    est libre si N'IMPORTE QUI peut le reprendre à son tour SANS poser
    aucune tuile ET SANS recomposer le tapis — donc uniquement par une
    recombinaison du plateau SEUL, immédiatement disponible. Trois voies,
    toutes RÉUTILISÉES telles quelles (aucune ne consomme de tuile du
    chevalet, condition commune aux trois) :

    * ``_jokers_liberables_par_groupe4_sans_remplacement`` — joker d'un
      groupe de 4 tuiles (3 réelles de couleurs distinctes + le joker) : le
      groupe reste un groupe de 3 valide une fois le joker retiré ;
    * ``_jokers_liberables_par_scission_milieu`` — joker STRICTEMENT
      intérieur d'une suite d'au moins 7 tuiles : la suite se scinde en
      deux suites valides (au moins 3 tuiles chacune) de part et d'autre ;
    * :func:`_jokers_libres_par_bout_suite` — joker en BOUT d'une suite
      d'au moins 4 tuiles : la suite reste valide seule (au moins 3 tuiles)
      une fois le joker retiré.

    N'inclut JAMAIS l'échange direct (``_jokers_recuperables``) ni le
    détachement par extension (``_jokers_detachables_par_extension``) : ces
    deux voies exigent de JOUER une tuile (la tuile de remplacement, ou la
    tuile d'extension), donc ne rendent pas le joker libre au nouveau sens
    — même si l'IA elle-même peut s'en servir pour RÉCUPÉRER un joker lors
    de son propre coup (§8) ; elles ne comptent plus comme un « cadeau »
    (nuance d'Alain, #253, qui corrige la définition trop large de #252 :
    cf. docs/contexte/ia_anti_don_joker.md, exemple chiffré).

    Un joker au milieu d'une suite de 3 ou 4 tuiles, ou dans un groupe de 3,
    n'est PAS libre : aucune des trois voies ci-dessus ne s'applique (suite
    trop courte pour la scission milieu — qui exige 7 tuiles au moins —, et
    un groupe de 3 tomberait sous le minimum de 3 tuiles en perdant le
    joker). ``plateau`` : liste d'objets ``Tuile`` (pas de dicts)."""
    libres = set()
    for rec in _jokers_liberables_par_groupe4_sans_remplacement(plateau):
        libres.add(rec["joker"].id)
    for rec in _jokers_liberables_par_scission_milieu(plateau, []):
        libres.add(rec["joker"].id)
    for rec in _jokers_libres_par_bout_suite(plateau):
        libres.add(rec["joker"].id)
    return libres


def jokers_rendus_libres_par_coup(etat, idx, coup):
    """Ids des jokers NOUVELLEMENT libres (#253) après ``coup`` : libres
    (:func:`jokers_libres_sur_plateau`) sur le plateau résultant du coup,
    mais pas déjà libres sur le plateau AVANT ce coup — laisser en place un
    joker déjà libre avant ce coup n'est pas un cadeau fait PAR ce coup
    (même nuance qu'en #252). Compare donc deux PLATEAUX (celui d'``etat``
    et celui de ``coup``), jamais la main : la nouvelle définition ne
    dépend d'aucune tuile de main ou de pioche (contrairement à l'ancienne
    notion de « joker offert », #252, qui utilisait un chevalet
    hypothétique — devenue inutile, voir docs/contexte/
    ia_anti_don_joker.md)."""
    plateau_avant = plateau_depuis_dict(etat.get("plateau", []))
    plateau_apres = plateau_depuis_dict(coup.get("nouveau_plateau") or [])
    libres_avant = jokers_libres_sur_plateau(plateau_avant)
    libres_apres = jokers_libres_sur_plateau(plateau_apres)
    return libres_apres - libres_avant


def _coup_avec_chevalet(etat, idx, chevalet, bridage, budget_temps,
                        preferer_simple, eval_config):
    """Meilleur coup VU par ``bridage`` (même ``perturbation_max``) avec un
    CHEVALET DE REMPLACEMENT (#253) — ne mute jamais ``etat`` (construit un
    état temporaire, comme l'ancienne recherche d'alternative de #252)."""
    joueur = etat["joueurs"][idx]
    joueur2 = dict(joueur)
    joueur2["chevalet"] = chevalet
    joueurs2 = list(etat["joueurs"])
    joueurs2[idx] = joueur2
    etat2 = dict(etat)
    etat2["joueurs"] = joueurs2
    return _coup_selon_perturbation(
        etat2, idx, bridage.perturbation_max, budget_temps, None,
        preferer_simple=preferer_simple, eval_config=eval_config)


def _coup_sans_tuile_main(etat, idx, id_tuile, bridage, budget_temps,
                          preferer_simple, eval_config, deadline):
    """Meilleur coup du MÊME niveau en retirant ``id_tuile`` de la main
    (#253) — utilisé par la recherche d'alternative sans joker libre (point
    4) et par l'échange différé (point 6). Retourne ``None`` si ``deadline``
    (instant monotone) est déjà dépassée, sinon le coup (``dict``, jamais
    ``None`` au-delà — voir ``_coup_selon_perturbation``)."""
    restant = deadline - time.monotonic()
    if restant <= 0:
        return None
    chevalet = etat["joueurs"][idx]["chevalet"]
    chevalet2 = [t for t in chevalet if t["id"] != id_tuile]
    return _coup_avec_chevalet(
        etat, idx, chevalet2, bridage,
        min(budget_temps or BUDGET_TEMPS_EXPERT, restant),
        preferer_simple, eval_config)


# --------------------------------------------------------------------------- #
# Point 3 — joker en main UTILE
# --------------------------------------------------------------------------- #

def _adversaire_a_au_plus(etat, idx, seuil):
    """Vrai si au moins un AUTRE joueur a AU PLUS ``seuil`` tuiles en main —
    nombre de tuiles, visible de tous (longueur du chevalet), JAMAIS son
    contenu (#254, point 7 — même convention que :func:`_adversaire_a_moins_de`,
    mais borne LARGE, « au plus », pas stricte)."""
    return any(len(j["chevalet"]) <= seuil
              for j2, j in enumerate(etat["joueurs"]) if j2 != idx)


def _fin_de_match_proche_pour_debarras(etat, idx):
    """Vrai si les conditions de fin de match du point 7 (#254) sont
    réunies : match à PLUSIEURS manches (``nb_manches > 1`` —
    ``etat["config"]["nb_manches"]`` distingue toujours les deux types de
    match, posé à la création de la partie, voir ``moteur/partie.
    creer_partie`` : aucun cas où cette distinction serait indisponible),
    AU MOINS un autre joueur a AU PLUS ``niveaux.
    SEUIL_TUILES_ADVERSAIRE_FIN_MATCH`` tuiles en main, ET la pioche contient
    STRICTEMENT MOINS de ``niveaux.SEUIL_PIOCHE_FIN_MATCH`` tuiles.
    Désactivable en bloc par ``niveaux.DEBARRAS_JOKER_FIN_MATCH_ACTIF``."""
    if not _niveaux.DEBARRAS_JOKER_FIN_MATCH_ACTIF:
        return False
    if etat.get("config", {}).get("nb_manches", 1) <= 1:
        return False
    if not _adversaire_a_au_plus(
            etat, idx, _niveaux.SEUIL_TUILES_ADVERSAIRE_FIN_MATCH):
        return False
    return len(etat.get("pioche") or []) < _niveaux.SEUIL_PIOCHE_FIN_MATCH


def _appliquer_joker_utile(etat, idx, coup, bridage, budget_temps,
                           preferer_simple, eval_config):
    """Règle du joker en main UTILE (#253, point 3 ; #254, point 4 —
    ÉVALUATION PAR JOKER, remplace l'évaluation collective). Si ``coup`` ne
    joue aucun joker de la MAIN, rien à faire (``evalue=False`` — ne
    concerne jamais un joker repris du plateau, cf. points 5/6 plus bas).

    Sinon, pour CHAQUE joker de la main joué par ``coup`` (pas « tous les
    jokers à la fois » comme #253), SÉQUENTIELLEMENT : compare le nombre de
    tuiles RÉELLES (jokers exclus) du meilleur coup avec l'ensemble encore
    disponible (tous les jokers non encore jugés non-utiles) au nombre de
    tuiles RÉELLES du meilleur coup obtenu en retirant CE SEUL joker de cet
    ensemble (``_coup_avec_chevalet`` ; un coup ``"piocher"``/``"passer"``
    y compte pour 0, ce qui couvre aussi l'ouverture rendue possible par le
    joker). **Pourquoi séquentiel et pas « chacun contre l'ensemble complet
    indépendamment »** : deux jokers sont INTERCHANGEABLES pour le solveur ;
    si un seul des deux suffit à occuper le seul emplacement qui en a
    besoin, le retirer INDÉPENDAMMENT (en laissant toujours l'AUTRE
    disponible) montre à chaque fois « l'autre suffit », donc AUCUN des
    deux ne paraîtrait utile — alors qu'ENSEMBLE, les retirer TOUS LES DEUX
    ferait perdre cet emplacement. Retirer chaque joker confirmé non utile
    de l'ensemble AVANT de juger le suivant évite ce piège.

    * STRICTEMENT plus de tuiles réelles AVEC (l'ensemble encore
      disponible) que SANS ce joker → ce joker est UTILE (reste
      disponible, posé) ;
    * autant ou moins → NON utile — **sauf** fin de match à plusieurs
      manches (#254, point 7, :func:`_fin_de_match_proche_pour_debarras`) :
      si les conditions sont réunies ET que ``coup`` prévoyait déjà une
      place pour ce joker (même sans gain réel), il est posé quand même
      pour ne pas rester en main à la pénalité ; sinon, gardé en main.

    Le coup final rejoue le meilleur coup avec {tuiles réelles} ∪ {jokers
    utiles ou débarrassés en fin de match} UNIQUEMENT — un joker jugé non
    utile (et non débarrassé) reste en main même si l'AUTRE est posé.

    Retourne ``(coup_final, info)`` — ``info`` :
    ``{"evalue": bool, "jokers_main_en_jeu": int, "jokers_gardes": int,
    "jokers_debarrasses_fin_match": int}``."""
    chevalet = etat["joueurs"][idx]["chevalet"]
    est_joker_par_id = {t["id"]: bool(t.get("est_joker")) for t in chevalet}
    jokers_main_ids = [t["id"] for t in chevalet if t.get("est_joker")]
    ids_joues = set(coup.get("ids_tuiles") or [])
    jokers_en_jeu = [j for j in jokers_main_ids if j in ids_joues]
    if not jokers_en_jeu:
        return coup, {"evalue": False, "jokers_main_en_jeu": 0,
                      "jokers_gardes": 0, "jokers_debarrasses_fin_match": 0}

    def _reel(c):
        return (sum(1 for i in (c.get("ids_tuiles") or [])
                   if not est_joker_par_id.get(i))
               if isinstance(c, dict) and c.get("action") == "jouer" else 0)

    # Évaluation SÉQUENTIELLE (#254, point 4) : deux jokers étant
    # INTERCHANGEABLES pour le solveur, les retirer un par un en gardant
    # TOUJOURS l'autre disponible (comme s'ils étaient testés en parallèle,
    # chacun contre l'ensemble complet) ferait apparaître AUCUN des deux
    # comme utile dès qu'un seul suffit à occuper le seul emplacement qui
    # en a vraiment besoin (l'un couvrant cet emplacement à la place de
    # l'autre à chaque test) — alors qu'ENSEMBLE, en retirer les DEUX ferait
    # perdre cet emplacement. Retirer les jokers non utiles un par un, en
    # ÔTANT chaque joker confirmé non utile de l'ensemble disponible pour le
    # test du suivant, évite ce piège : le premier joker non nécessaire au
    # MEILLEUR coup restant disponible est retiré, puis le second est
    # réévalué SANS lui — seul le dernier joker réellement nécessaire à
    # l'emplacement reste donc jugé utile, quel qu'il soit.
    chevalet_disponible = chevalet
    reel_avec = _reel(coup)
    jokers_non_utiles = []
    for j in jokers_en_jeu:
        chevalet_sans_j = [t for t in chevalet_disponible if t["id"] != j]
        coup_sans_j = _coup_avec_chevalet(
            etat, idx, chevalet_sans_j, bridage, budget_temps,
            preferer_simple, eval_config)
        reel_sans_j = _reel(coup_sans_j)
        if reel_avec > reel_sans_j:
            continue  # utile : reste disponible pour le test suivant
        jokers_non_utiles.append(j)
        chevalet_disponible = chevalet_sans_j
        reel_avec = reel_sans_j

    jokers_debarrasses = []
    if jokers_non_utiles and _fin_de_match_proche_pour_debarras(etat, idx):
        # (#254, point 7) : un joker non utile, mais pour lequel ``coup``
        # (chevalet complet) prévoyait déjà une place, est posé quand même
        # — jamais une recherche supplémentaire pour lui EN TROUVER une.
        jokers_debarrasses = [j for j in jokers_non_utiles if j in ids_joues]
        jokers_non_utiles = [j for j in jokers_non_utiles
                             if j not in jokers_debarrasses]

    info = {"evalue": True, "jokers_main_en_jeu": len(jokers_en_jeu),
           "jokers_gardes": len(jokers_non_utiles),
           "jokers_debarrasses_fin_match": len(jokers_debarrasses)}

    if not jokers_non_utiles:
        return coup, info

    chevalet_filtre = [t for t in chevalet if t["id"] not in jokers_non_utiles]
    coup_final = _coup_avec_chevalet(etat, idx, chevalet_filtre, bridage,
                                     budget_temps, preferer_simple, eval_config)
    if isinstance(coup_final, dict) and coup_final.get("action") == "jouer":
        return coup_final, info
    return _piocher_ou_passer(etat), info


# --------------------------------------------------------------------------- #
# Point 6 — échange différé d'un échange facultatif « en réserve »
# --------------------------------------------------------------------------- #

def _joker_en_reserve(plateau, rec):
    """Vrai si le joker de ``rec`` (échange direct, ``_jokers_recuperables``)
    est EN RÉSERVE pour l'IA (#253, point 6 ; test complété par #254, point
    1) : l'AUTRE exemplaire de la tuile de remplacement (``NB_SERIES - 1``
    au total, soit 1 avec ``NB_SERIES=2``) est visible sur ``plateau`` — ET
    aucune recombinaison du plateau SEUL (sans aucune tuile de main, de
    quiconque) ne peut ni rendre ce joker libre, ni rendre une tuile de
    remplacement disponible ailleurs sur le plateau. Trois conditions
    cumulatives (toutes nécessaires) :

    1. ``vus_sur_plateau == NB_SERIES - 1`` : avec ``rec["remplacement"]``
       dans la main de l'IA (c'est de là qu'il vient, par construction de
       ``_jokers_recuperables``), cela comptabilise la TOTALITÉ des
       ``NB_SERIES`` exemplaires (1 en main + ``NB_SERIES - 1`` visibles) —
       AUCUN exemplaire ne peut donc se trouver ailleurs (main d'un
       adversaire, ou pioche). **Point explicitement vérifié (#254,
       point 1)** : la main de l'IA ELLE-MÊME ne peut PAS détenir un second
       exemplaire en plus de ``rec["remplacement"]`` — avec ``NB_SERIES=2``
       il n'existe que 2 exemplaires au total, déjà intégralement comptés
       (1 main + 1 plateau) ; la réserve n'en est donc que PLUS sûre
       (aucun autre joueur ne peut jamais y toucher), jamais moins sûre ;
    2. le joker n'est pas déjà libre (:func:`jokers_libres_sur_plateau`) ;
    3. **NOUVEAU (#254, point 1 — #253 ne vérifiait pas ce cas)** : aucune
       libération SANS tuile de main n'existe pour ce joker au sens LARGE
       de :func:`_liberations_possibles` (chevalet vide, donc seules les
       libérations GRATUITES comptent) — ce qui couvre, en plus des trois
       voies de :func:`jokers_libres_sur_plateau`, la réduction d'un groupe
       de 4 DÉJÀ COMPLET (:func:`_jokers_liberables_par_reduction_groupe4`,
       cas ``len(groupe) == 4``) : une tuile réelle libérée par cette
       réduction peut directement remplacer CE joker (ou tout autre),
       rendant la tuile de remplacement « disponible » par simple
       déplacement de l'autre exemplaire visible — exactement l'exemple de
       l'issue. Réutilise ``_liberations_possibles`` tel quel (aucune
       réécriture), avec un chevalet VIDE : par construction, seules les
       libérations qui ne consomment AUCUNE tuile de main peuvent y
       apparaître."""
    remplacement = rec["remplacement"]
    vus_sur_plateau = sum(
        1 for combo in plateau for t in combo
        if not t.est_joker and t.couleur == remplacement.couleur
        and t.valeur == remplacement.valeur)
    if vus_sur_plateau != NB_SERIES - 1:
        return False
    if rec["joker"].id in jokers_libres_sur_plateau(plateau):
        return False
    for lib in _liberations_possibles(plateau, []):
        if lib["joker"].id == rec["joker"].id:
            return False
    return True


def _joker_repris_utilise_avec_main(plateau_apres, ids_joues, joker_id,
                                    id_exclu):
    """Vrai si le joker ``joker_id``, dans sa position APRÈS ``coup``
    (``plateau_apres``), est combiné avec au moins une tuile RÉELLE jouée
    depuis la main CE tour (``ids_joues``) autre que ``id_exclu`` (la tuile
    de remplacement de l'échange lui-même) — càd que l'IA « peut utiliser
    le joker avec sa main » (#253, points 5/6), par opposition à un simple
    repositionnement structurel (extension seule, sans tuile de main)."""
    for combo in plateau_apres:
        if any(t.id == joker_id for t in combo):
            return any(t.id in ids_joues and t.id != id_exclu and not t.est_joker
                      for t in combo)
    return False


def _adversaire_a_moins_de(etat, idx, seuil):
    """Vrai si au moins un AUTRE joueur a STRICTEMENT moins de ``seuil``
    tuiles en main — nombre de tuiles, visible de tous (longueur du
    chevalet), JAMAIS son contenu (#253, point 6)."""
    return any(len(j["chevalet"]) < seuil
              for j2, j in enumerate(etat["joueurs"]) if j2 != idx)


def _appliquer_echange_differe(etat, idx, coup, bridage, budget_temps,
                               preferer_simple, eval_config):
    """Échange différé (#253, point 6). Pour le premier échange direct
    facultatif (``_jokers_recuperables`` sur le plateau et la main AVANT ce
    tour) effectivement joué par ``coup`` dont le joker récupéré N'EST PAS
    utilisé avec le reste de la main
    (:func:`_joker_repris_utilise_avec_main`) ET qui est EN RÉSERVE
    (:func:`_joker_en_reserve`) :

    * si le compteur d'attente de CE joker (propre à chaque joker, ``dict``
      ``niveaux.CLE_ATTENTE_ECHANGE_DIFFERE``) n'a pas atteint la limite
      (``niveaux.LIMITE_ECHANGE_DIFFERE``, réduite à
      ``niveaux.LIMITE_ECHANGE_DIFFERE_ADVERSAIRE_FAIBLE`` si au moins un
      AUTRE joueur a STRICTEMENT moins de
      ``niveaux.SEUIL_TUILES_ADVERSAIRE_FAIBLE`` tuiles en main) : cherche
      le meilleur coup SANS la tuile de remplacement
      (:func:`_coup_sans_tuile_main`) — s'il existe (action ``"jouer"``), le
      joue à la place (l'échange est différé, le compteur incrémenté) ;
      s'il n'existe pas (l'échange était le SEUL coup possible), pioche
      plutôt que d'échanger (compteur inchangé — ce tour de pioche ne
      compte pas comme un tour d'attente « joué ») ;
    * au-delà de la limite, ``coup`` est joué TEL QUEL (l'échange est fait,
      compteur de CE joker remis à 0) — ``info["force"]=True``. **Changement
      #254 (point 2)** : ce cas N'EST PLUS exempté de la règle du joker
      libre du point 4 (``_appliquer_joker_libre``, voir
      ``jouer_niveau_bride``) — #253 l'exemptait par crainte que le point 4
      ne trouve SYSTÉMATIQUEMENT l'alternative sans l'échange et n'annule la
      décision de forcer ; or le point 4 ne se déclenche QUE si ``coup``
      rend RÉELLEMENT un nouveau joker libre (``jokers_rendus_libres_par_
      coup`` non vide) — ce qui n'est pas automatique (le joker récupéré
      peut très bien retomber dans une position non libre). Le point 4
      s'applique donc désormais normalement, y compris à un échange forcé :
      s'il laisse réellement un joker libre et qu'une alternative existe,
      l'alternative est prise (le joker reste alors « en réserve » sur le
      tapis, ce qui ne coûte rien puisque personne d'autre ne peut le
      prendre) ; si aucune alternative n'existe, le point 4 pioche SANS
      compteur ni limite (comportement générique inchangé, voir §5) — ce
      n'est PAS une réouverture du délai de CE point 6 (son propre compteur
      reste remis à 0 par ce tour), seulement l'application normale, à
      n'importe quel coup, de la protection générique contre un joker
      laissé libre sans alternative.

    **Point 3 (#254)** : le compteur avance aussi pendant un tour où
    l'échange était le SEUL coup possible (la pioche qui en résultait ne
    comptait PAS comme un tour d'attente sous #253, ce qui permettait une
    attente sans limite) — voir ci-dessous.

    Un joker qui n'est plus en réserve (ses conditions ne tiennent plus,
    p. ex. le plateau a été recomposé par un adversaire) voit son compteur
    retiré du ``dict``, qu'il ait été concerné par ``coup`` ou non.

    MUTE ``etat["joueurs"][idx][niveaux.CLE_ATTENTE_ECHANGE_DIFFERE]`` en
    place (même exception que l'ancien compteur de #252 : métadonnée de
    décision multi-tours, jamais le plateau ni la main).

    Retourne ``(coup_final, info)`` — ``info`` :
    ``{"differe": bool, "pioche": bool, "force": bool}``."""
    joueur = etat["joueurs"][idx]
    plateau_avant = plateau_depuis_dict(etat.get("plateau", []))
    chevalet_avant = _to_tuiles(joueur["chevalet"])
    ids_joues = set(coup.get("ids_tuiles") or [])
    plateau_apres = plateau_depuis_dict(coup.get("nouveau_plateau") or [])
    ids_sur_plateau_apres = {t.id for c in plateau_apres for t in c}

    compteurs = dict(joueur.get(_niveaux.CLE_ATTENTE_ECHANGE_DIFFERE) or {})
    limite = (_niveaux.LIMITE_ECHANGE_DIFFERE_ADVERSAIRE_FAIBLE
             if _adversaire_a_moins_de(
                 etat, idx, _niveaux.SEUIL_TUILES_ADVERSAIRE_FAIBLE)
             else _niveaux.LIMITE_ECHANGE_DIFFERE)

    recuperables = _jokers_recuperables(plateau_avant, chevalet_avant)
    resultat = None
    for rec in recuperables:
        if rec["remplacement"].id not in ids_joues:
            continue
        if rec["joker"].id not in ids_sur_plateau_apres:
            continue  # pas repositionné par CE coup
        if _joker_repris_utilise_avec_main(
                plateau_apres, ids_joues, rec["joker"].id,
                rec["remplacement"].id):
            continue  # utile avec la main : échange normal, rien à différer
        if not _joker_en_reserve(plateau_avant, rec):
            continue  # pas en réserve : la règle #253 ne s'y applique pas
        n = compteurs.get(rec["joker"].id, 0)
        if n >= limite:
            compteurs.pop(rec["joker"].id, None)
            resultat = (coup, {"differe": False, "pioche": False, "force": True})
            break
        deadline = time.monotonic() + (budget_temps or BUDGET_TEMPS_EXPERT)
        alternative = _coup_sans_tuile_main(
            etat, idx, rec["remplacement"].id, bridage, budget_temps,
            preferer_simple, eval_config, deadline)
        if not (isinstance(alternative, dict)
                and alternative.get("action") == "jouer"):
            # Seul coup possible (#254, point 3 — CORRIGE #253, qui ne
            # comptait PAS ce tour comme un tour d'attente, permettant une
            # attente sans limite) : ce tour compte quand même dans la
            # limite, même s'il se solde par une pioche plutôt qu'un coup.
            compteurs[rec["joker"].id] = n + 1
            if not etat.get("pioche"):
                # (#254, point 5) Pioche vide : passer n'apporterait rien de
                # mieux (impossible de piocher au tour suivant non plus) —
                # l'échange est fait quand même, plutôt que de passer sans
                # fin ; compteur retiré (l'échange est fait).
                compteurs.pop(rec["joker"].id, None)
                resultat = (coup, {"differe": False, "pioche": False,
                                   "force": False, "force_pioche_vide": True})
            else:
                resultat = (_piocher_ou_passer(etat),
                           {"differe": True, "pioche": True, "force": False})
            break
        compteurs[rec["joker"].id] = n + 1
        resultat = (alternative, {"differe": True, "pioche": False,
                                  "force": False})
        break

    # Réserve cessée (recomposition adverse) : compteur retiré, que CE coup
    # ait concerné ce joker ou non.
    for rec in recuperables:
        if rec["joker"].id in compteurs and not _joker_en_reserve(
                plateau_avant, rec):
            compteurs.pop(rec["joker"].id, None)

    if compteurs != (joueur.get(_niveaux.CLE_ATTENTE_ECHANGE_DIFFERE) or {}):
        joueur[_niveaux.CLE_ATTENTE_ECHANGE_DIFFERE] = compteurs
    return resultat if resultat is not None else (
        coup, {"differe": False, "pioche": False, "force": False})


# --------------------------------------------------------------------------- #
# Point 4 — joker LIBRE évité (remplace la pioche bornée de #252)
# --------------------------------------------------------------------------- #

def _chercher_coup_sans_joker_libre(etat, idx, coup, bridage, budget_temps,
                                    preferer_simple, eval_config, deadline):
    """Cherche un coup ÉQUIVALENT (même mécanisme que ``coup``, quitte à
    poser moins de tuiles) qui ne rend NOUVEAU libre aucun joker (#253,
    point 4). Essaie, dans l'ordre :

    1. le coup SANS réarrangement du plateau (``_coup_sans_rearrangement``) —
       ne peut jamais rendre libre un joker déjà en place sur le plateau ;
    2. pour chaque tuile jouée par ``coup`` (les jokers joués d'abord — la
       cause la plus probable), le meilleur coup du MÊME niveau obtenu en
       retirant CETTE tuile de la main (:func:`_coup_sans_tuile_main`).

    S'arrête au premier coup trouvé qui n'en laisse aucun libre (pas
    nécessairement le plus riche) — borné par ``deadline``, pour rester
    dans la même échéance de temps que le coup normal. Retourne ``None`` si
    rien n'y échappe."""
    sans_rearr = _coup_sans_rearrangement(etat, idx)
    if (isinstance(sans_rearr, dict) and sans_rearr.get("action") == "jouer"
            and not jokers_rendus_libres_par_coup(etat, idx, sans_rearr)):
        return sans_rearr

    chevalet = etat["joueurs"][idx]["chevalet"]
    par_id = {t["id"]: t for t in chevalet}
    ids_joues = list(coup.get("ids_tuiles") or [])
    ids_jokers_joues = [i for i in ids_joues
                        if par_id.get(i, {}).get("est_joker")]
    ordre = ids_jokers_joues + [i for i in ids_joues if i not in ids_jokers_joues]

    for id_tuile in ordre:
        candidat = _coup_sans_tuile_main(etat, idx, id_tuile, bridage,
                                         budget_temps, preferer_simple,
                                         eval_config, deadline)
        if candidat is None:
            break
        if (isinstance(candidat, dict) and candidat.get("action") == "jouer"
                and not jokers_rendus_libres_par_coup(etat, idx, candidat)):
            return candidat
    return None


def _meilleur_candidat_si_pioche_impossible(etat, idx, coup, bridage,
                                            budget_temps, preferer_simple,
                                            eval_config, deadline):
    """(#254, point 5) La pioche est VIDE (plus aucune tuile à tirer) et
    aucun coup sans nouveau joker libre n'a été trouvé : passer n'apporte
    rien de mieux (la pioche restera vide au tour suivant — voir docs/
    contexte/ia_anti_don_joker.md pour la façon dont ceci est détecté),
    alors que jouer réduit le chevalet (ou gagne) — l'IA joue donc malgré
    tout, en comptant pouvoir récupérer le joker ensuite.

    Parmi ``coup`` et les MÊMES candidats que
    :func:`_chercher_coup_sans_joker_libre` (sans réarrangement, puis le
    meilleur coup sans chacune des tuiles jouées), choisit celui qui laisse
    le MOINS de nouveaux jokers libres (camouflage BEST-EFFORT, #254
    point 6 : une approximation — minimiser le nombre de jokers libres,
    PAS la préférence « recombinaison la plus profonde » parmi plusieurs
    placements d'un même joker repris, non implémentée ici non plus que
    dans #253, limite connue documentée dans le rapport), puis le plus
    riche en tuiles (:func:`_valeur_coup`). Ne manque jamais de candidat :
    ``coup`` lui-même y figure toujours."""
    candidats = [coup]
    sans_rearr = _coup_sans_rearrangement(etat, idx)
    if isinstance(sans_rearr, dict) and sans_rearr.get("action") == "jouer":
        candidats.append(sans_rearr)
    for id_tuile in (coup.get("ids_tuiles") or []):
        candidat = _coup_sans_tuile_main(etat, idx, id_tuile, bridage,
                                         budget_temps, preferer_simple,
                                         eval_config, deadline)
        if isinstance(candidat, dict) and candidat.get("action") == "jouer":
            candidats.append(candidat)

    def _cle(c):
        nb_libres = len(jokers_rendus_libres_par_coup(etat, idx, c))
        nb_tuiles, points = _valeur_coup(etat, idx, c)
        return (nb_libres, -nb_tuiles, -points)

    return min(candidats, key=_cle)


def _appliquer_joker_libre(etat, idx, coup, bridage, budget_temps,
                          preferer_simple, eval_config):
    """Règle du joker LIBRE évité (#253, point 4 — remplace la pioche
    bornée de #252). Si ``coup`` ne rend libre aucun NOUVEAU joker
    (:func:`jokers_rendus_libres_par_coup`), rien à faire. Sinon, cherche
    une alternative (:func:`_chercher_coup_sans_joker_libre`) ; si elle en
    trouve une, la joue à la place (quitte à poser moins de tuiles).

    Si AUCUNE alternative n'en évite — le seul coup possible laisse un
    joker libre — et que la pioche n'est PAS vide, l'IA pioche plutôt que
    de jouer, SANS compteur ni limite (contrairement à l'attente bornée à 2
    tours de #252, supprimée). **Changement #254 (point 5)** : si la pioche
    EST vide, cette pioche est remplacée par le meilleur coup disponible
    (:func:`_meilleur_candidat_si_pioche_impossible`) — passer n'aurait
    servi à rien de plus.

    Retourne ``(coup_final, info)`` — ``info`` :
    ``{"declenchee": bool, "evite": bool, "pioche": bool,
    "force_pioche_vide": bool}``."""
    nouveaux = jokers_rendus_libres_par_coup(etat, idx, coup)
    if not nouveaux:
        return coup, {"declenchee": False, "evite": False, "pioche": False,
                      "force_pioche_vide": False}

    deadline = time.monotonic() + (budget_temps or BUDGET_TEMPS_EXPERT)
    alternative = _chercher_coup_sans_joker_libre(
        etat, idx, coup, bridage, budget_temps, preferer_simple,
        eval_config, deadline)
    if alternative is not None:
        return alternative, {"declenchee": True, "evite": True,
                             "pioche": False, "force_pioche_vide": False}

    if not etat.get("pioche"):
        meilleur = _meilleur_candidat_si_pioche_impossible(
            etat, idx, coup, bridage, budget_temps, preferer_simple,
            eval_config, deadline)
        return meilleur, {"declenchee": True, "evite": False,
                          "pioche": False, "force_pioche_vide": True}
    return _piocher_ou_passer(etat), {"declenchee": True, "evite": False,
                                      "pioche": True, "force_pioche_vide": False}


def jouer_niveau_bride(etat, idx, nom_niveau, budget_temps=None, rng=None,
                       on_repli=None, preferer_simple=None, eval_config=None,
                       on_aucun=None, eviter_don_joker=None):
    """Joue le tour du niveau ``nom_niveau`` avec le moteur exact RÉGLÉ par les
    paramètres de ``moteur/niveaux.py`` (issue #213).

    1. calcule le meilleur coup que le niveau « voit » (borné par
       ``perturbation_max``) ;
    2. un coup qui VIDE la main gagne la partie : renvoyé tel quel, jamais
       oublié, ni dégradé, ni soumis à la gestion du joker ci-dessous (§13) ;
    2bis. gestion du joker (issue #253, Intermédiaire/Avancé/Expert, voir
       ``niveaux.Bridage.eviter_don_joker`` et docs/contexte/
       ia_anti_don_joker.md — REMPLACE la règle d'attente de #252), DANS CET
       ORDRE :
       a. joker en main UTILE (``_appliquer_joker_utile``) — un joker de la
          main n'est joué que s'il pose strictement plus de tuiles réelles
          que sans lui, sinon le coup sans joker est joué et le joker gardé ;
       b. échange différé (``_appliquer_echange_differe``) — un échange
          facultatif en réserve, inemployable avec la main, peut être
          différé quelques tours plutôt que fait tout de suite ;
       c. joker LIBRE évité (``_appliquer_joker_libre``) — si le coup
          résultant rend un nouveau joker libre, cherche une alternative qui
          l'évite, ou pioche sans compteur ni limite si aucune n'existe ;
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
    de production que le jeu. ``on_aucun`` : voir ``jouer_niveau_expert`` —
    cas légitime (aucun coup posable, prouvé par le modèle exact), distinct
    d'un repli. ``eviter_don_joker`` (``None`` → suit ``bridage.
    eviter_don_joker`` ; ``True``/``False`` → force l'activation/
    désactivation ; nom du paramètre conservé de #252, gouverne maintenant
    l'ensemble de la gestion du joker de #253) : permet à ``scripts/
    comparer_niveaux_ia.py`` de comparer, pour un MÊME niveau, une campagne
    avec et sans la règle."""
    bridage = _niveaux.bridage_pour(nom_niveau)
    applique_regle_joker = (bridage.eviter_don_joker
                            if eviter_don_joker is None else eviter_don_joker)
    if rng is None:
        rng = _rng_oubli(etat, idx)
    taille_main = len(etat["joueurs"][idx]["chevalet"])

    coup = _coup_selon_perturbation(
        etat, idx, bridage.perturbation_max, budget_temps, on_repli,
        preferer_simple=preferer_simple, eval_config=eval_config,
        on_aucun=on_aucun)

    if not (isinstance(coup, dict) and coup.get("action") == "jouer"):
        # Aucun coup posable : pioche/passe (déjà décidé par le moteur).
        return coup if isinstance(coup, dict) else _piocher_ou_passer(etat)

    # Un coup qui vide la main gagne : jamais oublié, ni soumis à la gestion
    # du joker (§13, exception absolue de #252/#253).
    vide_la_main = (taille_main - len(coup.get("ids_tuiles") or [])) <= 0
    if vide_la_main:
        return coup

    if applique_regle_joker:
        coup, info_utile = _appliquer_joker_utile(
            etat, idx, coup, bridage, budget_temps, preferer_simple,
            eval_config)
        joker_info = {
            "jokers_main_gardes": info_utile.get("jokers_gardes", 0),
            "jokers_debarrasses_fin_match": info_utile.get(
                "jokers_debarrasses_fin_match", 0),
            "echange_differe": False, "echange_differe_pioche": False,
            "echange_differe_force_pioche_vide": False,
            "joker_libre_declenche": False, "joker_libre_evite": False,
            "joker_libre_pioche": False, "joker_libre_force_pioche_vide": False,
        }
        if not (isinstance(coup, dict) and coup.get("action") == "jouer"):
            # Pioche/passe décidé par la règle : jamais soumis à l'oubli
            # (qui ne s'applique qu'à un coup JOUÉ).
            coup["joker"] = joker_info
            return coup

        coup, info_differe = _appliquer_echange_differe(
            etat, idx, coup, bridage, budget_temps, preferer_simple,
            eval_config)
        joker_info["echange_differe"] = bool(info_differe.get("differe"))
        joker_info["echange_differe_pioche"] = bool(info_differe.get("pioche"))
        joker_info["echange_differe_force_pioche_vide"] = bool(
            info_differe.get("force_pioche_vide"))
        if not (isinstance(coup, dict) and coup.get("action") == "jouer"):
            coup["joker"] = joker_info
            return coup

        if joker_info["jokers_debarrasses_fin_match"]:
            # (#254, point 7) : un joker vient d'être délibérément posé
            # pour s'en débarrasser en fin de match à plusieurs manches
            # (sa pénalité compterait dans le score cumulé) — le point 4
            # N'EST PAS appliqué à CE coup : il chercherait sinon
            # systématiquement l'alternative SANS ce joker (le garder en
            # main), ce qui annulerait toujours la décision de ce point 7
            # (tout placement « gratuit » d'un joker — pure extension —
            # étant quasi systématiquement libre par construction, voir
            # docs/contexte/ia_anti_don_joker.md). Point douteux (choix de
            # l'agent) : l'issue ne précise pas cette interaction ; le
            # risque d'un joker libre est jugé secondaire face à la
            # pénalité certaine en toute fin de match.
            pass
        else:
            # Échange différé FORCÉ (délai épuisé ou pioche vide, #253/#254
            # point 6) : désormais SOUMIS normalement au point 4
            # (``_appliquer_joker_libre``, #254 point 2 — CORRIGE #253, qui
            # l'exemptait par crainte qu'il n'annule systématiquement la
            # décision de forcer ; en réalité le point 4 ne se déclenche QUE
            # si ``coup`` rend RÉELLEMENT un nouveau joker libre, ce qui n'a
            # rien d'automatique — voir docstring de
            # ``_appliquer_echange_differe``).
            coup, info_libre = _appliquer_joker_libre(
                etat, idx, coup, bridage, budget_temps, preferer_simple,
                eval_config)
            joker_info["joker_libre_declenche"] = bool(info_libre.get("declenchee"))
            joker_info["joker_libre_evite"] = bool(info_libre.get("evite"))
            joker_info["joker_libre_pioche"] = bool(info_libre.get("pioche"))
            joker_info["joker_libre_force_pioche_vide"] = bool(
                info_libre.get("force_pioche_vide"))
        if isinstance(coup, dict):
            coup["joker"] = joker_info
        if not (isinstance(coup, dict) and coup.get("action") == "jouer"):
            return coup

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


# NIVEAUX_IA : les cinq niveaux (issue #213), tous branchés sur le moteur
# exact bridé. Clés = libellés de ``config.NIVEAUX``.
NIVEAUX_IA = {nom: _fabriquer_niveau(nom) for nom in _niveaux.ECHELLE}


def jouer_ia(etat, joueur_index):
    """Point d'entrée : joue le tour selon le niveau du joueur (défaut : le
    niveau le plus faible). Tous les niveaux passent par le même moteur exact
    réglé par ``moteur/niveaux.py`` (issue #213). ``NIVEAU_RETIRE`` (« Champion
    du Monde », #235) est d'abord traduit par ``niveaux.niveau_compatible``,
    pour qu'une partie sauvegardée ou un réglage antérieur reste valide."""
    niveau = etat["joueurs"][joueur_index].get("niveau")
    niveau = _niveaux.niveau_compatible(niveau)
    if niveau not in NIVEAUX_IA:
        niveau = _niveaux.ECHELLE[0]
    return jouer_niveau_bride(etat, joueur_index, niveau)
