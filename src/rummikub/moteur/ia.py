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


def jouer_niveau_expert(etat, idx):
    """Comme avancé + refuse de poser si un adversaire est à ≤ 3 tuiles.

    (sauf si le coup vide son propre chevalet).
    """
    coup = _meilleur_coup_avec_joker(etat, idx, ordre_points=True) or _coup_scission(etat, idx)
    if not coup:
        return _piocher_ou_passer(etat)
    joueur = etat["joueurs"][idx]
    reste = len(joueur["chevalet"]) - len(coup["ids_tuiles"])
    adversaire_proche = any(
        i != idx and len(j["chevalet"]) <= 3
        for i, j in enumerate(etat["joueurs"]))
    if adversaire_proche and reste > 0:
        return _piocher_ou_passer(etat)
    return coup


NIVEAUX_IA = {
    "Débutant": jouer_niveau_debutant,
    "Facile": jouer_niveau_facile,
    "Intermédiaire": jouer_niveau_intermediaire,
    "Avancé": jouer_niveau_avance,
    "Expert": jouer_niveau_expert,
}


def jouer_ia(etat, joueur_index):
    """Point d'entrée : délègue au niveau du joueur (défaut : débutant)."""
    niveau = etat["joueurs"][joueur_index].get("niveau")
    fn = NIVEAUX_IA.get(niveau, jouer_niveau_debutant)
    return fn(etat, joueur_index)
