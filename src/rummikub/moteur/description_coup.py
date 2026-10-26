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
    à+les=aux. « la »/« l' » ne se contractent pas (de la, à la)."""
    fusions = {"le ": {"de": "du ", "à": "au "},
               "les ": {"de": "des ", "à": "aux "}}
    for article, table in fusions.items():
        if groupe_nominal.startswith(article):
            return table[prep] + groupe_nominal[len(article):]
    return f"{prep} {groupe_nominal}"


def _type_combo(tuiles_dicts: list) -> str:
    objs = [tuile_depuis_dict(d) for d in tuiles_dicts]
    return valider_combinaison(objs)["type"]


def _est_feminin(tuiles_dicts: list) -> bool:
    """« suite » est féminin, le reste (« groupe », combinaison invalide
    décrite comme « la combinaison ») est traité au masculin/par défaut."""
    return _type_combo(tuiles_dicts) == "suite"


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
        return f"suite {couleur}"
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
            return ("une " if indef else "la ") + f"suite {couleur} {bornes}"
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

    # 2) "update" : continuations dont la composition change réellement.
    for i, j in continuation.items():
        avant_ids = {d["id"] for d in plateau_avant[i]}
        apres_ids = {d["id"] for d in plateau_apres[j]}
        if avant_ids == apres_ids:
            continue  # combinaison totalement inchangée : rien à montrer
        retirees = [d for d in plateau_avant[i] if d["id"] not in apres_ids]
        ajoutees = [d for d in plateau_apres[j] if d["id"] not in avant_ids]
        op = {"kind": "update", "avant_idx": i, "apres_idx": j,
              "tuiles_avant": plateau_avant[i], "tuiles_apres": plateau_apres[j],
              "retirees": retirees, "ajoutees": ajoutees,
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

    restant = set(range(len(ops)))
    faites = set()
    ordre = []
    while restant:
        prets = [k for k in restant if deps[k] <= faites]
        if not prets:
            prets = list(restant)  # dépendance cyclique improbable : repli
        k = min(prets, key=cle_tri)
        ordre.append(k)
        faites.add(k)
        restant.discard(k)

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
    qui change de combinaison, son trajet complet : origine, tuile(s) qui le
    remplacent dans la combinaison d'origine (s'il y a lieu), destination
    finale. Les descriptions restent à construire par l'appelant (l'article
    défini/indéfini dépend du contexte où la phrase est utilisée)."""
    deplacements = []
    for op in ops:
        for tid in op.get("libere", []):
            if not id_vers_tuile.get(tid, {}).get("est_joker"):
                continue
            remplacant = (op["ajoutees"]
                          if op["kind"] == "update" and op.get("ajoutees")
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


# ------------------------------------------------------- résumé écrit (gauche)

def decrire_coup_ia(plateau_avant: list, plateau_apres: list,
                     nom: str = None) -> dict:
    """Résume en français naturel un coup de pose de l'IA, à partir du
    plateau juste avant et juste après ce coup. ``nom`` (optionnel) permet de
    commencer par « <Nom> a posé... » plutôt que par un « Il » impersonnel.

    Retourne {"texte": str, "tuiles_posees": [dict,...],
              "nb_combinaisons_defaites": int, "nb_combinaisons_creees": int,
              "nb_combinaisons_modifiees": int, "jokers_deplaces": [...]}.
    Un coup simple (une seule combinaison touchée, aucun joker déplacé) est
    résumé en une courte phrase ; un coup plus complexe en plusieurs.
    """
    plateau_avant = plateau_avant or []
    plateau_apres = plateau_apres or []
    r = _construire_operations(plateau_avant, plateau_apres)
    ops = r["ops"]
    desc = _desc_fabrique(r)

    updates = [op for op in ops if op["kind"] == "update"]
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
        sujet = nom if nom else "Il"
        if liste_posees:
            mot = "tuile" if nb_posees == 1 else "tuiles"
            phrases.append(f"{sujet} a posé {nb_posees} {mot} de sa main : "
                            f"{liste_posees}.")
        for op in creates:
            phrases.append(f"Il a créé {desc(op['tuiles_apres'], indef=True)}.")
        for op in updates:
            if op["retirees"] and op["ajoutees"]:
                phrases.append(
                    f"Il a complété {desc(op['tuiles_apres'])} en remplaçant "
                    f"{_lister_tuiles_def(op['retirees'])} par "
                    f"{_lister_tuiles_def(op['ajoutees'])}.")
            elif op["ajoutees"]:
                phrases.append(f"Il a complété {desc(op['tuiles_apres'])} "
                                f"avec {_lister_tuiles_def(op['ajoutees'])}.")
            elif op["retirees"]:
                phrases.append(
                    f"Il a retiré {_lister_tuiles_def(op['retirees'])} "
                    f"{_contracter('de', desc(op['tuiles_avant']))}.")
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
    """
    plateau_avant = plateau_avant or []
    plateau_apres = plateau_apres or []
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

    # Une étape par opération, dans l'ordre causal déjà calculé.
    for op in ops:
        ids_touchees = []
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
            ids_touchees = [d["id"] for d in op["retirees"] + op["ajoutees"]]
            cible = desc(op["tuiles_apres"])
            if op["retirees"] and op["ajoutees"]:
                verbe = "remplace" if len(op["ajoutees"]) == 1 else "remplacent"
                texte = (f"{_maj(_lister_tuiles_def(op['ajoutees']))} {verbe} "
                          f"{_lister_tuiles_def(op['retirees'])} dans {cible}.")
            elif op["ajoutees"]:
                verbe = "complète" if len(op["ajoutees"]) == 1 else "complètent"
                texte = (f"{_maj(_lister_tuiles_def(op['ajoutees']))} {verbe} "
                          f"{cible}.")
            else:
                verbe = "sort" if len(op["retirees"]) == 1 else "sortent"
                texte = (f"{_maj(_lister_tuiles_def(op['retirees']))} {verbe} "
                          f"{_contracter('de', desc(op['tuiles_avant']))}.")

        else:  # create
            slot = f"c{op['apres_idx']}"
            for d in op["ajoutees"]:
                del cadre[d["id"]]
            working[slot] = list(op["tuiles_apres"])
            ids_touchees = [d["id"] for d in op["ajoutees"]]
            texte = (f"{_maj(_lister_tuiles_def(op['ajoutees']))} forment "
                      f"{desc(op['tuiles_apres'], indef=True)}.")

        etapes.append(etat_courant("", texte, ids_touchees))

    return etapes
