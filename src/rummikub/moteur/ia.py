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
    """Scinde une suite longue pour libérer une tuile et former un groupe.

    Ex. : le plateau contient une suite rouge 4-5-6-7 et le chevalet un 7 bleu
    et un 7 jaune → on détache le 7 rouge (la suite 4-5-6 reste valide) pour
    former le groupe 7 rouge/bleu/jaune, posant 2 tuiles du chevalet.
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
        for bout in ("debut", "fin"):
            reste = combo[1:] if bout == "debut" else combo[:-1]
            libre = combo[0] if bout == "debut" else combo[-1]
            if libre.est_joker or not valider_combinaison(reste)["valide"]:
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
                nouveau_plateau[ci] = list(reste)
                nouveau_plateau.append(groupe)
                ids = [t.id for t in groupe if t.id != libre.id]
                nd = _plateau_vers_dict(nouveau_plateau)
                if ids and _coup_valide(etat, idx, nd, ids):
                    return {"action": "jouer", "ids_tuiles": ids,
                            "nouveau_plateau": nd}
    return None


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
            if r["type"] == "suite":
                i0, t0 = next((i, tt) for i, tt in enumerate(combo)
                              if not tt.est_joker)
                valeur_attendue = t0.valeur - i0 + pi
                couleur_attendue = t0.couleur
                match = next((tt for tt in chevalet if not tt.est_joker
                              and tt.valeur == valeur_attendue
                              and tt.couleur == couleur_attendue), None)
            else:  # groupe
                valeur_attendue = next(tt.valeur for tt in combo
                                       if not tt.est_joker)
                couleurs_utilisees = {tt.couleur for tt in combo
                                      if not tt.est_joker}
                match = next((tt for tt in chevalet if not tt.est_joker
                              and tt.valeur == valeur_attendue
                              and tt.couleur not in couleurs_utilisees), None)
            if match is not None:
                resultats.append({"combi_index": ci, "position_index": pi,
                                  "joker": t, "remplacement": match})
    return resultats


def _coup_avec_joker_recupere(etat, idx, ordre_points=False):
    """Échange un joker récupérable contre sa tuile équivalente en main, puis
    tente de replacer le joker libéré ailleurs (nouvelle combinaison ou
    extension) pour un coup plus riche que la simple extension évidente.

    Retourne le meilleur coup obtenu (ou ``None`` si aucun joker n'est
    récupérable, ou si aucun ne peut être replacé ailleurs sur le plateau).
    """
    joueur = etat["joueurs"][idx]
    if not joueur["mise_initiale_faite"]:
        return None
    base_plateau = plateau_depuis_dict(etat.get("plateau", []))
    chevalet = _to_tuiles(joueur["chevalet"])
    meilleur = None
    for rec in _jokers_recuperables(base_plateau, chevalet):
        ci, pi = rec["combi_index"], rec["position_index"]
        joker, remplacement = rec["joker"], rec["remplacement"]

        plateau = [list(c) for c in base_plateau]
        combo = list(plateau[ci])
        combo[pi] = remplacement
        plateau[ci] = combo

        disponibles = [t for t in chevalet if t.id != remplacement.id] + [joker]
        resultats = trouver_combinaisons_depuis_chevalet(
            [t.as_dict() for t in disponibles],
            etat["config"]["mise_initiale_min"], True)
        if ordre_points:
            resultats = sorted(
                resultats, key=lambda r: (r["points"], len(r["tuiles"])),
                reverse=True)
        choisis = _selection_disjointe(resultats)

        ids = [remplacement.id]
        utilises = {remplacement.id}
        for r in choisis:
            plateau.append(list(r["tuiles"]))
            for t in r["tuiles"]:
                ids.append(t.id)
                utilises.add(t.id)

        restantes = [t for t in disponibles if t.id not in utilises]
        _appliquer_extensions(plateau, restantes, ids)

        joker_place = any(t.id == joker.id for c in plateau for t in c)
        if not joker_place:
            continue

        ids_reel = [i for i in ids if i != joker.id]
        nouveau = _plateau_vers_dict(plateau)
        if ids_reel and _coup_valide(etat, idx, nouveau, ids_reel):
            coup = {"action": "jouer", "ids_tuiles": ids_reel,
                    "nouveau_plateau": nouveau}
            if meilleur is None or (_valeur_coup(etat, idx, coup)
                                    > _valeur_coup(etat, idx, meilleur)):
                meilleur = coup
    return meilleur


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


def _coup_avec_joker_detache(etat, idx, ordre_points=False):
    """Étend une suite d'un bout pour libérer le joker de l'autre bout, puis
    tente de replacer ce joker ailleurs (nouvelle combinaison ou extension)
    pour un coup plus riche que la simple extension évidente.

    Retourne le meilleur coup obtenu (ou ``None`` si aucun joker n'est
    détachable ainsi, ou si aucun ne peut être replacé ailleurs).
    """
    joueur = etat["joueurs"][idx]
    if not joueur["mise_initiale_faite"]:
        return None
    base_plateau = plateau_depuis_dict(etat.get("plateau", []))
    chevalet = _to_tuiles(joueur["chevalet"])
    meilleur = None
    for rec in _jokers_detachables_par_extension(base_plateau, chevalet):
        ci = rec["combi_index"]
        joker, t_ext = rec["joker"], rec["tuile_extension"]

        plateau = [list(c) for c in base_plateau]
        plateau[ci] = rec["nouveau_combo"]

        disponibles = [t for t in chevalet if t.id != t_ext.id] + [joker]
        resultats = trouver_combinaisons_depuis_chevalet(
            [t.as_dict() for t in disponibles],
            etat["config"]["mise_initiale_min"], True)
        if ordre_points:
            resultats = sorted(
                resultats, key=lambda r: (r["points"], len(r["tuiles"])),
                reverse=True)
        choisis = _selection_disjointe(resultats)

        ids = [t_ext.id]
        utilises = {t_ext.id}
        for r in choisis:
            plateau.append(list(r["tuiles"]))
            for t in r["tuiles"]:
                ids.append(t.id)
                utilises.add(t.id)

        restantes = [t for t in disponibles if t.id not in utilises]
        _appliquer_extensions(plateau, restantes, ids)

        joker_place = any(t.id == joker.id for c in plateau for t in c)
        if not joker_place:
            continue

        ids_reel = [i for i in ids if i != joker.id]
        nouveau = _plateau_vers_dict(plateau)
        if ids_reel and _coup_valide(etat, idx, nouveau, ids_reel):
            coup = {"action": "jouer", "ids_tuiles": ids_reel,
                    "nouveau_plateau": nouveau}
            if meilleur is None or (_valeur_coup(etat, idx, coup)
                                    > _valeur_coup(etat, idx, meilleur)):
                meilleur = coup
    return meilleur


def _valeur_coup(etat, idx, coup):
    """Valeur comparative d'un coup candidat : (nb tuiles jouées, points posés)."""
    plateau = plateau_depuis_dict(coup["nouveau_plateau"])
    ids = set(coup["ids_tuiles"])
    return (len(ids), _points_tuiles_posees(plateau, ids))


def _meilleur_coup_avec_joker(etat, idx, ordre_points=False):
    """Compare l'extension/combinaison évidente à un coup récupérant un
    joker par échange direct et à un coup détachant un joker en bout de
    suite via une extension du bout opposé ; retourne le meilleur des coups
    trouvés (ou ``None`` si aucun n'est jouable).
    """
    simple = _coup_maximal(etat, idx, ordre_points=ordre_points)
    recupere = _coup_avec_joker_recupere(etat, idx, ordre_points=ordre_points)
    detache = _coup_avec_joker_detache(etat, idx, ordre_points=ordre_points)
    candidats = [c for c in (simple, recupere, detache) if c]
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
    tuile, et préfère récupérer (échange direct) ou détacher (extension du
    bout opposé) un joker exploitable du plateau si cela donne un coup plus
    riche que l'extension la plus évidente."""
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
