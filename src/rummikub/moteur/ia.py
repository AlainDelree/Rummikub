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
from itertools import combinations

from rummikub.config import VALEUR_MIN, VALEUR_MAX
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
                        eval_config=None):
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
    vrai si c'est un dépassement de budget) — uniquement pour la mesure (voir
    ``scripts/comparer_niveaux_ia.py``), jamais utilisé en jeu normal.

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


def _coup_selon_perturbation(etat, idx, perturbation_max, budget_temps, on_repli):
    """Meilleur coup « vu » compte tenu de la perturbation autorisée.

    ``perturbation_max is None`` → solveur complet (Avancé/Expert/Champion).
    ``perturbation_max == 0`` → coup sans réarrangement (jamais de déplacement).
    ``perturbation_max > 0`` → coup complet s'il ne déplace pas plus de
    ``perturbation_max`` tuiles du plateau, sinon on retombe sur le coup sans
    réarrangement (le joueur ne « voit » pas une recomposition plus ample)."""
    if perturbation_max is None:
        return jouer_niveau_expert(etat, idx, budget_temps=budget_temps,
                                   on_repli=on_repli)

    sans_rearr = _coup_sans_rearrangement(etat, idx)
    if perturbation_max <= 0:
        return sans_rearr

    complet = jouer_niveau_expert(etat, idx, budget_temps=budget_temps,
                                  on_repli=on_repli)
    if not (isinstance(complet, dict) and complet.get("action") == "jouer"):
        return sans_rearr if sans_rearr is not None else complet
    deplacees, _combos = mesurer_perturbation(etat.get("plateau", []),
                                              complet["nouveau_plateau"])
    if deplacees <= perturbation_max:
        return complet
    return sans_rearr if sans_rearr is not None else _piocher_ou_passer(etat)


def jouer_niveau_bride(etat, idx, nom_niveau, budget_temps=None, rng=None,
                       on_repli=None):
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
    traçable (``recherche``/``avance`` au lieu de ``exact``)."""
    bridage = _niveaux.bridage_pour(nom_niveau)
    if rng is None:
        rng = _rng_oubli(etat, idx)
    taille_main = len(etat["joueurs"][idx]["chevalet"])

    coup = _coup_selon_perturbation(
        etat, idx, bridage.perturbation_max, budget_temps, on_repli)

    if not (isinstance(coup, dict) and coup.get("action") == "jouer"):
        # Aucun coup posable : pioche/passe (déjà décidé par le moteur).
        return coup if isinstance(coup, dict) else _piocher_ou_passer(etat)

    # Un coup qui vide la main gagne : jamais oublié (§13).
    vide_la_main = (taille_main - len(coup.get("ids_tuiles") or [])) <= 0
    if vide_la_main:
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
