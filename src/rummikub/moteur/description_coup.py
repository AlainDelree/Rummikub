"""Résumé en français d'un coup de l'IA, et découpage en étapes cohérentes
pour le rejeu pas-à-pas, calculés à partir du plateau avant et après ce coup
(issue #189, puis #191 pour la cohérence des étapes et le cadre « tuiles à
placer »).

Fonctions pures : elles ne modifient jamais l'état de la partie, et prennent
en entrée/sortie les mêmes dicts JSON-sérialisables que le reste du moteur
(voir CONTEXTE.md §4). Utilisées par `ui/api.py` pour construire, à chaque
pose de l'IA, le résumé écrit (`decrire_coup_ia`) et les étapes du rejeu
pas-à-pas (`etapes_coup_ia`) stockés dans `etat["dernier_coup_ia"]`.

Principe commun aux deux fonctions (`_construire_operations`) : chaque tuile
du plateau d'avant est suivie individuellement par son identifiant jusqu'à sa
destination dans le plateau d'après, plutôt que de comparer seulement les
combinaisons avant/après. Cela permet de distinguer deux combinaisons de même
nom (« le groupe de 11 » apparu deux fois) et de reconstruire un ordre causal
où chaque tuile n'est qu'à un seul endroit à la fois : sur le plateau, ou
dans le cadre « tuiles à placer » (tant qu'elle n'a pas encore rejoint sa
combinaison finale).
"""

from rummikub.moteur.tuiles import tuile_depuis_dict
from rummikub.moteur.validation import valider_combinaison


# --------------------------------------------------------------- vocabulaire

def _decrire_tuile(d: dict) -> str:
    if d.get("est_joker"):
        return "joker"
    return f"{d['valeur']} {d['couleur']}"


def _joindre(mots: list) -> str:
    mots = [m for m in mots if m]
    if not mots:
        return ""
    if len(mots) == 1:
        return mots[0]
    return ", ".join(mots[:-1]) + " et " + mots[-1]


def _lister_tuiles(dicts: list) -> str:
    """Énumération nue, sans article (ex. « 11 bleu, 11 noir et 3 bleu »),
    utilisée après un deux-points (« tuiles posées : ... »)."""
    return _joindre([_decrire_tuile(d) for d in dicts])


def _lister_tuiles_def(dicts: list) -> str:
    """Énumération avec article défini devant chaque tuile (ex. « le 13
    jaune et le 13 bleu »), utilisée quand les tuiles sont sujet/objet d'une
    phrase plutôt qu'une simple liste après un deux-points."""
    return _joindre([f"le {_decrire_tuile(d)}" for d in dicts])


def _maj(phrase: str) -> str:
    """Majuscule initiale si la phrase commence par une lettre (laisse un
    chiffre tel quel, ex. « 11 bleu... » reste en l'état)."""
    if phrase and phrase[0].isalpha():
        return phrase[0].upper() + phrase[1:]
    return phrase


def _contracter(prep: str, groupe_nominal: str) -> str:
    """Fusionne une préposition (« de » ou « à ») avec un groupe nominal
    commençant par un article défini : de+le=du, à+le=au, de+les=des,
    à+les=aux. « la »/« l' » ne se contractent pas (de la, à la). « de »
    s'élide en « d' » devant un article indéfini à initiale vocalique
    (« un »/« une », ex. « Création d'un groupe » — issue #198) ; « à » ne
    s'élide jamais en français (« à un », « à une »)."""
    fusions = {"le ": {"de": "du ", "à": "au "},
               "les ": {"de": "des ", "à": "aux "}}
    for article, table in fusions.items():
        if groupe_nominal.startswith(article):
            return table[prep] + groupe_nominal[len(article):]
    if prep == "de" and groupe_nominal[:1] in "aeiouAEIOU":
        return "d'" + groupe_nominal
    return f"{prep} {groupe_nominal}"


def _aspect(d: dict):
    """Apparence visible d'une tuile, indépendante de son identifiant : deux
    tuiles de même aspect sont interchangeables à l'écran (issue #197). Les
    jokers partagent tous le même aspect (leur couleur n'est que cosmétique,
    cf. ``tuiles.py``) ; un échange entre deux jokers ne change donc rien."""
    if d.get("est_joker"):
        return "joker"
    return (d["valeur"], d["couleur"])


def _retrait_ajout_bruts(avant_dicts: list, apres_dicts: list) -> tuple:
    """Pour une combinaison qui garde son identité d'une étape à l'autre,
    sépare par IDENTIFIANT (sans tenir compte de l'aspect) les tuiles qui
    sont RÉELLEMENT parties (``retirees``) de celles RÉELLEMENT arrivées
    (``ajoutees``). C'est la vérité du suivi causal : le cadre « tuiles à
    placer » et le graphe de dépendances (issue #197) restent TOUJOURS basés
    sur ce résultat brut, jamais sur la version « affichée » après
    annulation par aspect (``_annuler_par_aspect``) — sinon une tuile
    réellement libérée ici, mais annulée à l'affichage, ne serait jamais
    déposée dans le cadre, et une opération plus loin qui la consomme
    échouerait (``KeyError``, bug d'origine de l'issue #197 point 0)."""
    ids_apres = {d["id"] for d in apres_dicts}
    ids_avant = {d["id"] for d in avant_dicts}
    retirees = [d for d in avant_dicts if d["id"] not in ids_apres]
    ajoutees = [d for d in apres_dicts if d["id"] not in ids_avant]
    return retirees, ajoutees


def _annuler_par_aspect(retirees: list, ajoutees: list) -> tuple:
    """Retire deux à deux, d'une liste de tuiles parties et d'une liste de
    tuiles arrivées (même combinaison, résultat de ``_retrait_ajout_bruts``),
    celles qui s'échangent sans changement réel À L'ÉCRAN : une tuile partie
    appariée à une tuile arrivée de même aspect (même valeur/couleur, ou
    deux jokers quelconques — issue #197 points 1 et 3).

    Retourne ``(retirees_vues, ajoutees_vues)`` : les tuiles qui restent de
    chaque côté une fois ces annulations faites, dans leur ordre d'origine —
    à utiliser UNIQUEMENT pour la phrase/l'étape affichées, jamais pour le
    suivi causal (cf. ``_retrait_ajout_bruts``). Si les deux listes
    reviennent vides, la combinaison est inchangée à l'écran, même si les
    identifiants littéraux ont changé de place."""
    ajoutees = list(ajoutees)
    retirees_vues = []
    for d in retirees:
        aspect = _aspect(d)
        match = next((a for a in ajoutees if _aspect(a) == aspect), None)
        if match is not None:
            ajoutees.remove(match)
        else:
            retirees_vues.append(d)
    return retirees_vues, ajoutees


def _composantes_fortement_connexes(deps: dict, n: int) -> list:
    """Algorithme de Tarjan : regroupe les indices ``[0, n)`` en composantes
    fortement connexes du graphe de dépendances causales (``deps[k]`` =
    indices que l'opération ``k`` doit attendre). Une composante de taille
    supérieure à 1 signale un cycle de dépendances strictes : deux
    combinaisons (ou plus) qui s'échangent des tuiles de même aspect,
    chacune attendant une tuile libérée par l'autre (issue #197, point 1 —
    impossible à sérialiser normalement, cf. ``_detecter_blocs_silencieux``)."""
    compteur = [0]
    pile, sur_pile = [], [False] * n
    indices, liens_bas = [None] * n, [None] * n
    composantes = []

    def _lier(v):
        indices[v] = liens_bas[v] = compteur[0]
        compteur[0] += 1
        pile.append(v)
        sur_pile[v] = True
        for w in deps.get(v, ()):
            if indices[w] is None:
                _lier(w)
                liens_bas[v] = min(liens_bas[v], liens_bas[w])
            elif sur_pile[w]:
                liens_bas[v] = min(liens_bas[v], indices[w])
        if liens_bas[v] == indices[v]:
            composante = []
            while True:
                w = pile.pop()
                sur_pile[w] = False
                composante.append(w)
                if w == v:
                    break
            composantes.append(composante)

    for v in range(n):
        if indices[v] is None:
            _lier(v)
    return composantes


def _detecter_blocs_silencieux(ops: list, deps: dict) -> dict:
    """Repère, parmi les cycles de dépendances (``_composantes_fortement_
    connexes``), ceux où TOUTES les opérations impliquées sont des "update"
    entièrement sans effet visible (``retirees_vues``/``ajoutees_vues``
    vides) : un échange de tuiles identiques entre deux combinaisons (ou
    plus), où chacune attend une tuile libérée par l'autre — le cas réel qui
    a fait planter ``etapes_coup_ia`` (issue #197 point 0, ``KeyError`` sur
    une tuile jamais déposée dans le cadre avant d'être consommée).

    Retourne ``{indice_op: id_bloc, ...}`` pour les opérations concernées :
    traitées ensemble en un seul geste par l'appelant (toutes les tuiles
    libérées du bloc ajoutées au cadre, PUIS toutes les tuiles consommées du
    bloc retirées du cadre), sans jamais dépendre de l'ordre entre elles.
    Un cycle qui ne qualifie pas (opération "retrait"/"create", ou "update"
    avec un effet visible) reste géré par le repli déjà existant (ordre
    arbitraire) — cas resté hors de portée de #197, non rencontré en
    pratique avec un coup réellement joué."""
    bloc_de = {}
    for composante in _composantes_fortement_connexes(deps, len(ops)):
        if len(composante) < 2:
            continue
        qualifie = all(ops[k]["kind"] == "update"
                        and not ops[k]["retirees_vues"]
                        and not ops[k]["ajoutees_vues"]
                        for k in composante)
        if not qualifie:
            continue
        id_bloc = min(composante)
        for k in composante:
            bloc_de[k] = id_bloc
    return bloc_de


def _type_combo(tuiles_dicts: list) -> str:
    objs = [tuile_depuis_dict(d) for d in tuiles_dicts]
    return valider_combinaison(objs)["type"]


def _est_feminin(tuiles_dicts: list) -> bool:
    """« suite » est féminin, le reste (« groupe », combinaison invalide
    décrite comme « la combinaison ») est traité au masculin/par défaut."""
    return _type_combo(tuiles_dicts) == "suite"


# Accord au féminin de la couleur quand elle qualifie « suite » (féminin) —
# « rouge »/« jaune » sont déjà invariables. Jamais appliqué à « groupe »
# (masculin, ou liste de couleurs par tuile — point 3 de l'issue #198).
_COULEURS_FEMININES = {"noir": "noire", "bleu": "bleue"}


def _couleur_suite(couleur) -> str:
    if couleur is None:
        return couleur
    return _COULEURS_FEMININES.get(couleur, couleur)


def _label_combo(tuiles_dicts: list) -> str:
    """Étiquette courte sans bornes ni couleur détaillée, utilisée pour
    détecter deux combinaisons distinctes qui porteraient le même nom
    (ex. deux « groupe de 11 » créés à des moments différents du coup)."""
    objs = [tuile_depuis_dict(d) for d in tuiles_dicts]
    type_ = valider_combinaison(objs)["type"]
    if type_ == "groupe":
        valeur = next((t.valeur for t in objs if not t.est_joker), None)
        return f"groupe de {valeur}"
    if type_ == "suite":
        couleur = next((t.couleur for t in objs if not t.est_joker), None)
        return f"suite {_couleur_suite(couleur)}"
    return "combinaison"


def _decrire_combo(tuiles_dicts: list, indef: bool = False,
                    couleurs: bool = False) -> str:
    """Décrit une combinaison en langage naturel, ex. « le groupe de 7 »,
    « un groupe de 11 bleu, jaune et noir » (indef+couleurs) ou « la suite
    rouge (5 à 9) ». ``indef`` utilise un article indéfini (combinaison
    nouvellement formée), ``couleurs`` ajoute la liste des couleurs pour
    distinguer deux combinaisons de même nom à des moments différents."""
    objs = [tuile_depuis_dict(d) for d in tuiles_dicts]
    type_ = valider_combinaison(objs)["type"]
    if type_ == "groupe":
        valeur = next((t.valeur for t in objs if not t.est_joker), None)
        base = f"groupe de {valeur}" if valeur is not None else "groupe"
        if couleurs:
            noms = ["joker" if t.est_joker else t.couleur for t in objs]
            base += " " + _joindre(noms)
        return ("un " if indef else "le ") + base
    if type_ == "suite":
        couleur = next((t.couleur for t in objs if not t.est_joker), None)
        reels = [(i, t) for i, t in enumerate(objs) if not t.est_joker]
        if reels and couleur:
            i0, t0 = reels[0]
            base_val = t0.valeur - i0
            v_min, v_max = base_val, base_val + len(objs) - 1
            bornes = f"({v_min})" if v_min == v_max else f"({v_min} à {v_max})"
            return ("une " if indef else "la ") + f"suite {_couleur_suite(couleur)} {bornes}"
        return "une suite" if indef else "la suite"
    return "une combinaison" if indef else "la combinaison"


def _phrase_sujet(tuiles_dicts: list, participe: str, desc=_decrire_combo) -> str:
    """« <Description, majuscule initiale> est <participe accordé>. »"""
    description = desc(tuiles_dicts)
    sujet = description[0].upper() + description[1:]
    suffixe = "e" if _est_feminin(tuiles_dicts) else ""
    return f"{sujet} est {participe}{suffixe}."


# ------------------------------------------------------- moteur tuile-à-tuile

def _construire_operations(plateau_avant: list, plateau_apres: list) -> dict:
    """Construit, à partir d'une traque tuile-par-tuile, la liste ordonnée
    des opérations qui transforment ``plateau_avant`` en ``plateau_apres`` :
    chaque opération est UN SEUL changement visible (une combinaison qui
    gagne/perd des tuiles, qui se vide vers le cadre, ou qui se forme depuis
    le cadre). L'ordre respecte la causalité (une tuile est libérée avant
    d'être réutilisée) et privilégie les échanges de jokers dès qu'ils sont
    possibles (issue #191, point 3bis).

    Trois types d'opération :
    - "retrait" : une combinaison qui ne continue pas sous une autre forme
      (ses tuiles partent vers des destinations différentes, sans majorité)
      libère UN SOUS-ENSEMBLE de ses tuiles (celles qui partent ensemble vers
      la même destination) dans le cadre. Une même combinaison peut donner
      lieu à plusieurs opérations "retrait" successives si ses tuiles partent
      vers plusieurs destinations : elle reste alors affichée, rétrécie,
      entre ces opérations (état « provisoire »).
    - "update" : une combinaison garde son identité (majorité de ses tuiles
      continue ensemble) mais change de composition : elle peut à la fois
      perdre des tuiles (libérées dans le cadre) et en gagner (prises dans
      le cadre), en un seul changement visible.
    - "create" : une nouvelle combinaison apparaît, entièrement composée de
      tuiles venues du cadre (main ou libérées ailleurs).
    """
    id_vers_avant = {d["id"]: i for i, combo in enumerate(plateau_avant)
                      for d in combo}
    id_vers_apres = {d["id"]: j for j, combo in enumerate(plateau_apres)
                      for d in combo}
    id_vers_tuile = {d["id"]: d for combo in plateau_avant for d in combo}
    id_vers_tuile.update({d["id"]: d for combo in plateau_apres for d in combo})

    tuiles_posees = [d for combo in plateau_apres for d in combo
                      if d["id"] not in id_vers_avant]
    ids_main = {d["id"] for d in tuiles_posees}

    continuation = {}      # avant_idx -> apres_idx (majorité claire)
    dissolvantes = []       # avant_idx sans destination majoritaire
    for i, combo in enumerate(plateau_avant):
        if not combo:
            continue
        compte = {}
        for d in combo:
            j = id_vers_apres.get(d["id"])
            if j is not None:
                compte[j] = compte.get(j, 0) + 1
        if not compte:
            continue
        cible = max(compte, key=lambda j: (compte[j], -j))
        if compte[cible] * 2 > len(combo):
            continuation[i] = cible
        else:
            dissolvantes.append(i)

    origines_par_apres = {}
    for i, j in continuation.items():
        origines_par_apres.setdefault(j, []).append(i)

    ops = []
    id_vers_op_producteur = {}

    # 1) "retrait" : combinaisons qui se dissolvent, regroupées par
    #    destination (cause -> effet, jamais tout d'un coup si plusieurs
    #    destinations se partagent ses tuiles).
    for i in dissolvantes:
        combo = plateau_avant[i]
        par_dest = {}
        for pos, d in enumerate(combo):
            j = id_vers_apres.get(d["id"])
            par_dest.setdefault(j, []).append((pos, d))
        for j in sorted(par_dest, key=lambda x: (x is None, x)):
            paires = par_dest[j]
            tuiles = [d for _, d in paires]
            op = {"kind": "retrait", "avant_idx": i, "apres_idx": j,
                  "pos": min(p for p, _ in paires),
                  "tuiles_avant": combo, "tuiles": tuiles,
                  "consomme": set(), "libere": [d["id"] for d in tuiles]}
            ops.append(op)
            idx = len(ops) - 1
            for d in tuiles:
                id_vers_op_producteur[d["id"]] = idx

    # 2) "update" : toute continuation devient une opération, MÊME si elle
    #    n'a aucun effet visible une fois annulés les échanges de tuiles
    #    identiques (même aspect, issue #197) — le suivi causal (cadre,
    #    dépendances) reste basé sur les listes BRUTES (``retirees``,
    #    ``ajoutees``) ; seules les listes « vues » (``retirees_vues``,
    #    ``ajoutees_vues``), réduites par ``_annuler_par_aspect``, décident
    #    de ce qui est affiché (texte, étape). Une tuile libérée ici mais
    #    annulée à l'affichage reste ainsi normalement déposée dans le cadre
    #    pour une opération suivante qui la consomme (issue #197 point 0).
    for i, j in continuation.items():
        retirees, ajoutees = _retrait_ajout_bruts(plateau_avant[i], plateau_apres[j])
        retirees_vues, ajoutees_vues = _annuler_par_aspect(retirees, ajoutees)
        op = {"kind": "update", "avant_idx": i, "apres_idx": j,
              "tuiles_avant": plateau_avant[i], "tuiles_apres": plateau_apres[j],
              "retirees": retirees, "ajoutees": ajoutees,
              "retirees_vues": retirees_vues, "ajoutees_vues": ajoutees_vues,
              "consomme": {d["id"] for d in ajoutees},
              "libere": [d["id"] for d in retirees]}
        ops.append(op)
        idx = len(ops) - 1
        for d in retirees:
            id_vers_op_producteur[d["id"]] = idx

    # 3) "create" : combinaisons d'après sans continuation pointant vers elles.
    for j, combo in enumerate(plateau_apres):
        if j in origines_par_apres:
            continue
        op = {"kind": "create", "apres_idx": j, "tuiles_apres": combo,
              "ajoutees": list(combo),
              "consomme": {d["id"] for d in combo}, "libere": []}
        ops.append(op)

    # 4) dépendances causales : une opération dépend de celle qui libère une
    #    tuile qu'elle consomme (sauf tuile de la main, disponible dès le
    #    départ) et tri topologique qui privilégie les échanges de jokers.
    deps = {k: set() for k in range(len(ops))}
    for k, op in enumerate(ops):
        for tid in op["consomme"]:
            if tid in ids_main:
                continue
            prod = id_vers_op_producteur.get(tid)
            if prod is not None and prod != k:
                deps[k].add(prod)

    def touche_joker(op):
        ids = set(op.get("consomme", ())) | set(op.get("libere", ()))
        return any(id_vers_tuile.get(tid, {}).get("est_joker") for tid in ids)

    rang_kind = {"update": 0, "create": 1, "retrait": 2}

    def cle_tri(k):
        op = ops[k]
        tier_joker = 0 if touche_joker(op) else 1
        if op["kind"] == "retrait":
            primaire, secondaire = op["avant_idx"], op["pos"]
        else:
            primaire = op.get("avant_idx", op.get("apres_idx", 999))
            secondaire = op.get("apres_idx", 999)
        return (tier_joker, rang_kind[op["kind"]], primaire, secondaire)

    # Les cycles de dépendances entre "update" entièrement invisibles (deux
    # combinaisons qui s'échangent des tuiles de même aspect, chacune
    # attendant une tuile libérée par l'autre) sont regroupés en BLOCS : le
    # tri topologique les traite comme une unité unique (``_etapes_coup_ia``
    # applique alors les deux côtés d'un bloc en un seul geste, sans jamais
    # dépendre de l'ordre interne — issue #197 point 0).
    blocs = _detecter_blocs_silencieux(ops, deps)
    for k, op in enumerate(ops):
        op["bloc"] = blocs.get(k)

    unites = {}
    for k in range(len(ops)):
        unites.setdefault(blocs.get(k, k), []).append(k)

    deps_unite = {}
    for u, membres in unites.items():
        externes = set()
        for m in membres:
            externes |= {blocs.get(p, p) for p in deps[m]}
        deps_unite[u] = externes - {u}

    def cle_tri_unite(u):
        return min(cle_tri(m) for m in unites[u])

    restant = set(unites)
    faites_unites = set()
    ordre = []
    while restant:
        prets = [u for u in restant if deps_unite[u] <= faites_unites]
        if not prets:
            prets = list(restant)  # dépendance cyclique improbable : repli
        u = min(prets, key=cle_tri_unite)
        ordre.extend(sorted(unites[u]))
        faites_unites.add(u)
        restant.discard(u)

    # id_vers_op_producteur référence encore les index AVANT tri topologique ;
    # on les reporte vers leur nouvelle position dans la liste réordonnée.
    remap = {orig: nouveau for nouveau, orig in enumerate(ordre)}
    id_vers_op_producteur = {tid: remap[idx]
                              for tid, idx in id_vers_op_producteur.items()}

    return {
        "ops": [ops[k] for k in ordre],
        "tuiles_posees": tuiles_posees,
        "ids_main": ids_main,
        "id_vers_tuile": id_vers_tuile,
        "id_vers_op_producteur": id_vers_op_producteur,
        "dissolvantes": dissolvantes,
        "continuation": continuation,
    }


def _desc_fabrique(r: dict):
    """Fabrique une fonction de description qui ajoute automatiquement les
    couleurs quand DEUX COMBINAISONS DISTINCTES du coup portent le même nom
    (issue #191, point 5 : « le groupe de 11 rouge, bleu et noir » vs « un
    nouveau groupe de 11 bleu, jaune et noir »). Une combinaison qui change
    de composition sans changer d'identité (une « update », mentionnée avant
    ET après le changement) ne compte qu'une seule fois : sinon son propre
    avant/après serait à tort pris pour deux combinaisons différentes."""
    vues = set()
    comptes = {}
    for op in r["ops"]:
        if op["kind"] == "update":
            if not op["retirees_vues"] and not op["ajoutees_vues"]:
                # Échange de tuiles identiques sans effet visible (issue
                # #197) : cette combinaison n'est jamais mentionnée, inutile
                # de la compter pour la désambiguïsation par couleurs.
                continue
            ident = frozenset(d["id"] for d in op["tuiles_avant"])
            reference = op["tuiles_apres"]
        elif op["kind"] == "create":
            ident = frozenset(d["id"] for d in op["tuiles_apres"])
            reference = op["tuiles_apres"]
        else:  # retrait : une seule instance par combinaison d'origine,
            # même si elle donne lieu à plusieurs opérations "retrait".
            ident = frozenset(d["id"] for d in op["tuiles_avant"])
            reference = op["tuiles_avant"]
        if ident in vues:
            continue
        vues.add(ident)
        comptes.setdefault(_label_combo(reference), set()).add(ident)
    besoin_couleurs = {label for label, idents in comptes.items()
                        if len(idents) > 1}

    def desc(tuiles_dicts, indef=False):
        couleurs = _label_combo(tuiles_dicts) in besoin_couleurs
        return _decrire_combo(tuiles_dicts, indef=indef, couleurs=couleurs)

    return desc


def _provenance(tid: str, ops: list, ids_main: set, id_vers_op_producteur: dict,
                 desc) -> str:
    """Décrit d'où vient une tuile du cadre : « de sa main » ou libérée
    d'une combinaison précise du plateau."""
    if tid in ids_main:
        return "de sa main"
    prod = id_vers_op_producteur.get(tid)
    if prod is not None:
        return f"venant {_contracter('de', desc(ops[prod]['tuiles_avant']))}"
    return "du plateau"


def _jokers_deplaces(ops: list, id_vers_tuile: dict) -> list:
    """Reconstitue, pour chaque joker déjà sur le plateau avant le coup et
    qui change VISIBLEMENT de combinaison, son trajet complet : origine,
    tuile(s) qui le remplacent dans la combinaison d'origine (s'il y a
    lieu), destination finale. Les descriptions restent à construire par
    l'appelant (l'article défini/indéfini dépend du contexte où la phrase
    est utilisée).

    Un joker libéré par une opération "update" sans effet visible (annulé
    par aspect contre l'autre joker arrivé à sa place, issue #197 point 3)
    n'est PAS considéré comme déplacé, même s'il réapparaît ailleurs : du
    point de vue du joueur, rien ne distingue les deux jokers, donc rien ne
    s'est produit à cette combinaison."""
    deplacements = []
    for op in ops:
        if op["kind"] == "update":
            liberes_vus = {d["id"] for d in op["retirees_vues"]}
        else:
            liberes_vus = set(op.get("libere", []))
        for tid in op.get("libere", []):
            if tid not in liberes_vus:
                continue
            if not id_vers_tuile.get(tid, {}).get("est_joker"):
                continue
            remplacant = (op["ajoutees_vues"]
                          if op["kind"] == "update" and op.get("ajoutees_vues")
                          else None)
            destination_tuiles = None
            for op2 in ops:
                if tid in op2.get("consomme", ()):
                    destination_tuiles = op2["tuiles_apres"]
                    break
            deplacements.append({
                "id": tid, "origine_tuiles": op["tuiles_avant"],
                "remplacant": remplacant,
                "destination_tuiles": destination_tuiles,
            })
    return deplacements


def _texte_update(op: dict, desc) -> str:
    """Texte d'un changement « update » (combinaison qui garde son identité
    mais change de composition), partagé par le résumé écrit et le pas-à-pas
    (issue #198) : toujours les TUILES qui sont sujet de la phrase, jamais un
    pronom (« il »/« elle ») qui présupposerait le genre du joueur."""
    cible = desc(op["tuiles_apres"])
    if op["retirees_vues"] and op["ajoutees_vues"]:
        verbe = "remplace" if len(op["ajoutees_vues"]) == 1 else "remplacent"
        return (f"{_maj(_lister_tuiles_def(op['ajoutees_vues']))} {verbe} "
                f"{_lister_tuiles_def(op['retirees_vues'])} dans {cible}.")
    if op["ajoutees_vues"]:
        verbe = "complète" if len(op["ajoutees_vues"]) == 1 else "complètent"
        return f"{_maj(_lister_tuiles_def(op['ajoutees_vues']))} {verbe} {cible}."
    verbe = "sort" if len(op["retirees_vues"]) == 1 else "sortent"
    return (f"{_maj(_lister_tuiles_def(op['retirees_vues']))} {verbe} "
            f"{_contracter('de', desc(op['tuiles_avant']))}.")


# ------------------------------------------------------- résumé écrit (gauche)

def _tuiles_posees_brut(plateau_avant: list, plateau_apres: list) -> list:
    """Calcul minimal (sans validation ni suivi causal) des tuiles posées
    depuis la main : toute tuile d'après dont l'identifiant n'apparaît dans
    aucune combinaison d'avant. Utilisé par les replis simplifiés (issue
    #197 point 0) : ne peut pas lever d'exception sur une entrée valide."""
    ids_avant = {d["id"] for combo in plateau_avant for d in combo}
    return [d for combo in plateau_apres for d in combo if d["id"] not in ids_avant]


def decrire_coup_ia(plateau_avant: list, plateau_apres: list,
                     nom: str = None) -> dict:
    """Résume en français naturel un coup de pose de l'IA, à partir du
    plateau juste avant et juste après ce coup. ``nom`` (optionnel) permet de
    commencer par « <Nom> a posé... » plutôt que par « A posé... » (sujet
    omis). Aucune phrase, avec ou sans ``nom``, n'utilise jamais de pronom
    « il »/« elle » pour désigner le joueur — cela présupposerait son genre
    (issue #198) : les phrases suivantes restent soit nominales (« Création
    de... »), soit portées par les tuiles elles-mêmes comme sujet (« Le 3
    bleu remplace... »).

    Retourne {"texte": str, "tuiles_posees": [dict,...],
              "nb_combinaisons_defaites": int, "nb_combinaisons_creees": int,
              "nb_combinaisons_modifiees": int, "jokers_deplaces": [...]}.
    Un coup simple (une seule combinaison touchée, aucun joker déplacé) est
    résumé en une courte phrase ; un coup plus complexe en plusieurs.

    Ne lève jamais d'exception sur un coup valide (issue #197 point 0) : si
    le calcul détaillé échoue de façon inattendue, se replie sur un résumé
    minimal construit à partir des seules tuiles posées."""
    plateau_avant = plateau_avant or []
    plateau_apres = plateau_apres or []
    try:
        return _decrire_coup_ia(plateau_avant, plateau_apres, nom)
    except Exception:
        posees = _tuiles_posees_brut(plateau_avant, plateau_apres)
        liste_posees = _lister_tuiles(posees)
        sujet_initial = f"{nom} a posé" if nom else "A posé"
        texte = (f"{sujet_initial} {liste_posees} depuis sa main."
                  if liste_posees else
                  f"{(nom + ' a joué') if nom else 'A joué'} un coup.")
        return {
            "texte": texte,
            "tuiles_posees": posees,
            "nb_combinaisons_defaites": 0,
            "nb_combinaisons_creees": 0,
            "nb_combinaisons_modifiees": 0,
            "jokers_deplaces": [],
        }


def _decrire_coup_ia(plateau_avant: list, plateau_apres: list,
                      nom: str = None) -> dict:
    plateau_avant = plateau_avant or []
    plateau_apres = plateau_apres or []
    r = _construire_operations(plateau_avant, plateau_apres)
    ops = r["ops"]
    desc = _desc_fabrique(r)

    # Seules les "update" avec un effet VISIBLE comptent : une opération
    # entièrement annulée par aspect (échange de tuiles identiques, issue
    # #197) ne touche aucune combinaison du point de vue du joueur.
    updates = [op for op in ops if op["kind"] == "update"
               and (op["retirees_vues"] or op["ajoutees_vues"])]
    creates = [op for op in ops if op["kind"] == "create"]
    nb_defaites = len(r["dissolvantes"])
    jokers = _jokers_deplaces(ops, r["id_vers_tuile"])

    liste_posees = _lister_tuiles(r["tuiles_posees"])
    nb_posees = len(r["tuiles_posees"])
    simple = (nb_defaites == 0 and not jokers and len(creates) + len(updates) <= 1)

    if simple:
        sujet_initial = f"{nom} a posé" if nom else "A posé"
        if creates:
            texte = (f"{sujet_initial} {liste_posees} depuis sa main pour "
                      f"former {desc(creates[0]['tuiles_apres'], indef=True)}."
                      if liste_posees else
                      f"{(nom + ' a formé') if nom else 'A formé'} "
                      f"{desc(creates[0]['tuiles_apres'], indef=True)}.")
        elif updates:
            texte = (f"{sujet_initial} {liste_posees} depuis sa main en "
                      f"complétant {desc(updates[0]['tuiles_apres'])}."
                      if liste_posees else
                      f"{(nom + ' a complété') if nom else 'A complété'} "
                      f"{desc(updates[0]['tuiles_apres'])}.")
        elif liste_posees:
            texte = f"{sujet_initial} {liste_posees} depuis sa main."
        else:
            texte = "N'a rien changé sur le plateau."
    else:
        phrases = []
        sujet_initial = f"{nom} a posé" if nom else "A posé"
        if liste_posees:
            mot = "tuile" if nb_posees == 1 else "tuiles"
            phrases.append(f"{sujet_initial} {nb_posees} {mot} de sa main : "
                            f"{liste_posees}.")
        for op in creates:
            # Jamais de pronom sujet ("il"/"elle") : présupposerait le genre
            # du joueur (issue #198) — tournure nominale impersonnelle.
            phrases.append(f"Création {_contracter('de', desc(op['tuiles_apres'], indef=True))}.")
        for op in updates:
            phrases.append(_texte_update(op, desc))
        for i in r["dissolvantes"]:
            phrases.append(_phrase_sujet(plateau_avant[i], "défait", desc))
        for n, depl in enumerate(jokers):
            qualif = "Le joker" if n == 0 else "Un autre joker"
            phrases.append(
                f"{qualif} est passé "
                f"{_contracter('de', desc(depl['origine_tuiles']))} "
                f"{_contracter('à', desc(depl['destination_tuiles']))}.")
        texte = " ".join(phrases) if phrases \
            else "Coup joué sans changement notable sur le plateau."

    return {
        "texte": texte,
        "tuiles_posees": r["tuiles_posees"],
        "nb_combinaisons_defaites": nb_defaites,
        "nb_combinaisons_creees": len(creates),
        "nb_combinaisons_modifiees": len(updates),
        "jokers_deplaces": [
            {"depuis": desc(d["origine_tuiles"]),
             "vers": desc(d["destination_tuiles"])} for d in jokers],
    }


# ---------------------------------------------------- étapes du pas-à-pas

def _snapshot_plateau(working: dict) -> list:
    return [list(combo) for combo in working.values() if combo]


def _combo_est_provisoire(tuiles_dicts: list) -> bool:
    objs = [tuile_depuis_dict(d) for d in tuiles_dicts]
    return not valider_combinaison(objs)["valide"]


def _snapshot_cadre(cadre: dict) -> list:
    return [{"tuile": info["tuile"], "origine": info["origine"]}
            for info in cadre.values()]


def etapes_coup_ia(plateau_avant: list, plateau_apres: list) -> list:
    """Découpe un coup de l'IA en une suite d'états cohérents pour le rejeu
    pas-à-pas : à chaque étape, chaque tuile n'est qu'à un seul endroit à la
    fois (sur le plateau, instantané ``plateau``, ou dans le cadre « tuiles à
    placer », instantané ``cadre``). La suite commence par un écran
    « Départ » (plateau d'avant, cadre rempli des tuiles de la main), suivi
    si besoin d'un écran de synthèse « Les jokers », puis d'une étape par
    changement visible (une seule combinaison modifiée/créée/vidée à la
    fois). La toute dernière étape correspond exactement à ``plateau_apres``,
    avec un cadre vide. Le bouton « Pas à pas » du front-end ne s'affiche que
    si au moins 2 étapes sont renvoyées.

    Chaque étape est un dict {"titre": str, "texte": str, "plateau": [...],
    "cadre": [{"tuile": dict, "origine": "main"|"plateau"}, ...],
    "provisoires": [index dans "plateau"...], "surbrillance": [id, ...]}.

    Ne lève jamais d'exception sur un coup valide (issue #197 point 0) : si
    le calcul détaillé échoue de façon inattendue, se replie sur une version
    simplifiée à deux étapes (départ puis arrivée)."""
    plateau_avant = plateau_avant or []
    plateau_apres = plateau_apres or []
    try:
        return _etapes_coup_ia(plateau_avant, plateau_apres)
    except Exception:
        return _etapes_coup_ia_repli(plateau_avant, plateau_apres)


def _memes_ids_par_combinaison(a: list, b: list) -> bool:
    cle = lambda plateau: sorted(sorted(d["id"] for d in c) for c in plateau if c)
    return cle(a) == cle(b)


def _etapes_coup_ia_repli(plateau_avant: list, plateau_apres: list) -> list:
    if _memes_ids_par_combinaison(plateau_avant, plateau_apres):
        return []  # rien à rejouer
    posees = _tuiles_posees_brut(plateau_avant, plateau_apres)
    ids_posees = [d["id"] for d in posees]
    depart = {
        "titre": "Départ", "texte": "Avant le coup.",
        "plateau": [list(c) for c in plateau_avant if c],
        "cadre": [{"tuile": d, "origine": "main"} for d in posees],
        "provisoires": [], "surbrillance": ids_posees,
    }
    arrivee = {
        "titre": "", "texte": "Après le coup.",
        "plateau": [list(c) for c in plateau_apres if c],
        "cadre": [], "provisoires": [], "surbrillance": ids_posees,
    }
    return [depart, arrivee]


def _etapes_coup_ia(plateau_avant: list, plateau_apres: list) -> list:
    r = _construire_operations(plateau_avant, plateau_apres)
    ops = r["ops"]
    if not ops and not r["tuiles_posees"]:
        return []  # rien à rejouer
    desc = _desc_fabrique(r)

    working = {}
    for i, combo in enumerate(plateau_avant):
        if combo:
            working[f"a{i}"] = list(combo)
    cadre = {d["id"]: {"tuile": d, "origine": "main"} for d in r["tuiles_posees"]}

    def etat_courant(titre, texte, surbrillance):
        provisoires = [idx for idx, combo in enumerate(_snapshot_plateau(working))
                        if _combo_est_provisoire(combo)]
        return {
            "titre": titre,
            "texte": texte,
            "plateau": _snapshot_plateau(working),
            "cadre": _snapshot_cadre(cadre),
            "provisoires": provisoires,
            "surbrillance": list(surbrillance),
        }

    etapes = []

    # Écran « Départ » : plateau d'avant, cadre rempli des tuiles de la main.
    if r["tuiles_posees"]:
        texte_depart = ("Avant le coup. Tuiles prêtes à être posées : "
                         f"{_lister_tuiles(r['tuiles_posees'])}.")
    else:
        texte_depart = "Avant le coup."
    etapes.append(etat_courant("Départ", texte_depart,
                                [d["id"] for d in r["tuiles_posees"]]))

    # Écran « Les jokers » : vue d'ensemble si des jokers changent de main.
    jokers = _jokers_deplaces(ops, r["id_vers_tuile"])
    if jokers:
        phrases = []
        for depl in jokers:
            origine = desc(depl["origine_tuiles"])
            destination = desc(depl["destination_tuiles"], indef=True)
            if depl["remplacant"]:
                liste = _lister_tuiles_def(depl["remplacant"])
                prov = _joindre([
                    _provenance(d["id"], ops, r["ids_main"],
                                 r["id_vers_op_producteur"], desc)
                    for d in depl["remplacant"]])
                phrases.append(
                    f"Le joker {_contracter('de', origine)} est "
                    f"remplacé par {liste} ({prov}) "
                    f"et rejoint {destination}.")
            else:
                phrases.append(
                    f"Le joker {_contracter('de', origine)} est "
                    f"libéré et rejoint {destination}.")
        etapes.append(etat_courant("Les jokers", " ".join(phrases),
                                    [depl["id"] for depl in jokers]))

    # Une étape par opération, dans l'ordre causal déjà calculé. Pour une
    # "update", le cadre/plateau sont TOUJOURS mis à jour avec les listes
    # BRUTES (suivi causal exact, issue #197) ; seules les listes « vues »
    # décident si une étape est effectivement affichée. Les opérations d'un
    # même BLOC (échange cyclique entre deux combinaisons ou plus, issue
    # #197 point 0) sont regroupées : impossible de les sérialiser (chacune
    # attend une tuile libérée par l'autre), donc traitées en un seul geste
    # — toutes les tuiles libérées du bloc ajoutées au cadre, PUIS toutes
    # les tuiles consommées du bloc retirées, sans jamais dépendre de
    # l'ordre entre elles. Un bloc est par construction entièrement
    # invisible (aucune étape affichée pour ses membres).
    i = 0
    while i < len(ops):
        bloc = ops[i].get("bloc")
        if bloc is not None:
            membres = [ops[i]]
            i += 1
            while i < len(ops) and ops[i].get("bloc") == bloc:
                membres.append(ops[i])
                i += 1
            for op in membres:
                for d in op["retirees"]:
                    cadre[d["id"]] = {"tuile": d, "origine": "plateau"}
            for op in membres:
                for d in op["ajoutees"]:
                    del cadre[d["id"]]
                working[f"a{op['avant_idx']}"] = list(op["tuiles_apres"])
            continue

        op = ops[i]
        i += 1
        ids_touchees = []
        invisible = False
        if op["kind"] == "retrait":
            ids_touchees = [d["id"] for d in op["tuiles"]]
            slot = f"a{op['avant_idx']}"
            ids_set = set(ids_touchees)
            for tid, d in zip(ids_touchees, op["tuiles"]):
                cadre[tid] = {"tuile": d, "origine": "plateau"}
            working[slot] = [d for d in working[slot] if d["id"] not in ids_set]
            if not working[slot]:
                del working[slot]
            donneur = desc(op["tuiles_avant"])
            verbe = "sort" if len(op["tuiles"]) == 1 else "sortent"
            texte = (f"{_maj(_lister_tuiles_def(op['tuiles']))} {verbe} "
                      f"{_contracter('de', donneur)}.")

        elif op["kind"] == "update":
            slot = f"a{op['avant_idx']}"
            for d in op["ajoutees"]:
                del cadre[d["id"]]
            for d in op["retirees"]:
                cadre[d["id"]] = {"tuile": d, "origine": "plateau"}
            working[slot] = list(op["tuiles_apres"])
            if not op["retirees_vues"] and not op["ajoutees_vues"]:
                # Échange de tuiles identiques sans effet visible (issue
                # #197) : le cadre/plateau ci-dessus restent à jour pour les
                # opérations suivantes, mais aucune étape n'est affichée.
                invisible = True
            else:
                ids_touchees = [d["id"] for d in op["retirees_vues"] + op["ajoutees_vues"]]
                texte = _texte_update(op, desc)

        else:  # create
            slot = f"c{op['apres_idx']}"
            for d in op["ajoutees"]:
                del cadre[d["id"]]
            working[slot] = list(op["tuiles_apres"])
            ids_touchees = [d["id"] for d in op["ajoutees"]]
            texte = (f"{_maj(_lister_tuiles_def(op['ajoutees']))} forment "
                      f"{desc(op['tuiles_apres'], indef=True)}.")

        if not invisible:
            etapes.append(etat_courant("", texte, ids_touchees))

    return _sans_etapes_sans_effet(etapes)


def _empreinte_affichage(etape: dict) -> tuple:
    """Signature du contenu visible (plateau + cadre) d'une étape, insensible
    à l'ordre des combinaisons/tuiles : deux étapes de même empreinte sont
    indiscernables à l'écran."""
    combos = tuple(sorted(tuple(sorted(d["id"] for d in combo))
                            for combo in etape["plateau"]))
    cadre_ids = tuple(sorted(c["tuile"]["id"] for c in etape["cadre"]))
    return (combos, cadre_ids)


def _sans_etapes_sans_effet(etapes: list) -> list:
    """Filet de sécurité (issue #197 point 4) : supprime toute étape de
    changement (titre vide) dont le contenu affiché est identique à celui de
    la dernière étape conservée — un garde-fou en plus des annulations déjà
    faites en amont, au cas où un cas non prévu laisserait passer une étape
    sans effet visible."""
    nettoyees = []
    for etape in etapes:
        if (etape["titre"] == "" and nettoyees
                and _empreinte_affichage(etape) == _empreinte_affichage(nettoyees[-1])):
            continue
        nettoyees.append(etape)
    return nettoyees
