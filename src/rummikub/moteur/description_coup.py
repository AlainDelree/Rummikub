"""Résumé en français d'un coup de l'IA, calculé à partir du plateau avant et
après ce coup (issue #189, suite de #144/#149).

Fonctions pures : elles ne modifient jamais l'état de la partie, et prennent
en entrée/sortie les mêmes dicts JSON-sérialisables que le reste du moteur
(voir CONTEXTE.md §4). Utilisées par `ui/api.py` pour construire, à chaque
pose de l'IA, le résumé écrit (`decrire_coup_ia`) et les étapes du rejeu
pas-à-pas (`etapes_coup_ia`) stockés dans `etat["dernier_coup_ia"]`.
"""

from rummikub.moteur.tuiles import tuile_depuis_dict
from rummikub.moteur.validation import valider_combinaison


def _decrire_tuile(d: dict) -> str:
    if d.get("est_joker"):
        return "joker"
    return f"{d['valeur']} {d['couleur']}"


def _lister_tuiles(dicts: list) -> str:
    noms = [_decrire_tuile(d) for d in dicts]
    if not noms:
        return ""
    if len(noms) == 1:
        return noms[0]
    return ", ".join(noms[:-1]) + " et " + noms[-1]


def _type_combo(tuiles_dicts: list) -> str:
    objs = [tuile_depuis_dict(d) for d in tuiles_dicts]
    return valider_combinaison(objs)["type"]


def _est_feminin(tuiles_dicts: list) -> bool:
    """Genre de la description de la combinaison (pour l'accord des
    participes « défait(e) »/« complété(e) ») : « suite » est féminin, le
    reste (« groupe », ou combinaison invalide décrite comme « une
    combinaison ») est traité au masculin."""
    return _type_combo(tuiles_dicts) == "suite"


def _decrire_combo(tuiles_dicts: list) -> str:
    """Décrit une combinaison du plateau en langage simple, ex. « le groupe
    de 7 » ou « la suite rouge (5 à 9) »."""
    objs = [tuile_depuis_dict(d) for d in tuiles_dicts]
    type_ = valider_combinaison(objs)["type"]
    if type_ == "groupe":
        valeur = next((t.valeur for t in objs if not t.est_joker), None)
        return f"le groupe de {valeur}" if valeur is not None else "un groupe"
    if type_ == "suite":
        couleur = next((t.couleur for t in objs if not t.est_joker), None)
        reels = [(i, t) for i, t in enumerate(objs) if not t.est_joker]
        if reels and couleur:
            i0, t0 = reels[0]
            base = t0.valeur - i0
            v_min, v_max = base, base + len(objs) - 1
            if v_min == v_max:
                return f"la suite {couleur} ({v_min})"
            return f"la suite {couleur} ({v_min} à {v_max})"
        return "une suite"
    return "une combinaison"


def _phrase_sujet(tuiles_dicts: list, participe: str) -> str:
    """« <Description, majuscule initiale> est <participe accordé>. »"""
    desc = _decrire_combo(tuiles_dicts)
    sujet = desc[0].upper() + desc[1:]
    suffixe = "e" if _est_feminin(tuiles_dicts) else ""
    return f"{sujet} est {participe}{suffixe}."


def _analyser_coup(plateau_avant: list, plateau_apres: list) -> dict:
    """Compare les deux plateaux et classe les changements. Usage interne,
    partagé par `decrire_coup_ia` et `etapes_coup_ia`."""
    id_vers_combo_apres = {}
    for j, combo in enumerate(plateau_apres):
        for d in combo:
            id_vers_combo_apres[d["id"]] = j

    ids_avant = {d["id"] for combo in plateau_avant for d in combo}
    tuiles_posees = [d for combo in plateau_apres for d in combo
                     if d["id"] not in ids_avant]

    continuation = {}        # avant_idx -> apres_idx (majorité claire)
    defaites = []             # avant_idx sans majorité claire (dispersée)
    deplacements_jokers = []  # [{"depuis": str, "vers": str}, ...]

    for i, combo in enumerate(plateau_avant):
        if not combo:
            continue
        compte = {}
        for d in combo:
            j = id_vers_combo_apres.get(d["id"])
            if j is None:
                continue
            compte[j] = compte.get(j, 0) + 1
        if not compte:
            continue
        cible = max(compte, key=lambda j: (compte[j], -j))
        if compte[cible] * 2 > len(combo):
            # Majorité claire : la combinaison "survit" (elle peut tout de
            # même perdre/gagner des tuiles) à l'index apres `cible`.
            continuation[i] = cible
            for d in combo:
                j = id_vers_combo_apres.get(d["id"])
                if j is not None and j != cible and d.get("est_joker"):
                    deplacements_jokers.append({
                        "depuis": _decrire_combo(combo),
                        "vers": _decrire_combo(plateau_apres[j]),
                    })
        else:
            # Pas de destination majoritaire : la combinaison est dispersée.
            defaites.append(i)

    origines_par_apres = {}
    for i, j in continuation.items():
        origines_par_apres.setdefault(j, []).append(i)

    creees = []
    modifiees = []
    for j, combo in enumerate(plateau_apres):
        origines = origines_par_apres.get(j, [])
        if len(origines) == 1:
            i = origines[0]
            if {d["id"] for d in combo} != {d["id"] for d in plateau_avant[i]}:
                modifiees.append(j)
        else:
            creees.append(j)

    return {
        "tuiles_posees": tuiles_posees,
        "defaites": defaites,
        "creees": creees,
        "modifiees": modifiees,
        "origines_par_apres": origines_par_apres,
        "deplacements_jokers": deplacements_jokers,
    }


def decrire_coup_ia(plateau_avant: list, plateau_apres: list) -> dict:
    """Résume en français un coup de pose de l'IA, à partir du plateau juste
    avant et juste après ce coup.

    Retourne {"texte": str, "tuiles_posees": [dict,...],
              "nb_combinaisons_defaites": int, "nb_combinaisons_creees": int,
              "nb_combinaisons_modifiees": int, "jokers_deplaces": [...]}.
    Un coup simple (une seule combinaison touchée, aucun joker déplacé) est
    résumé en une courte phrase ; un coup plus complexe en plusieurs.
    """
    plateau_avant = plateau_avant or []
    plateau_apres = plateau_apres or []
    a = _analyser_coup(plateau_avant, plateau_apres)

    liste_posees = _lister_tuiles(a["tuiles_posees"])
    nb_defaites = len(a["defaites"])
    creees, modifiees = a["creees"], a["modifiees"]
    simple = (nb_defaites == 0 and not a["deplacements_jokers"]
              and len(creees) + len(modifiees) <= 1)

    if simple:
        if creees:
            desc = _decrire_combo(plateau_apres[creees[0]])
            texte = (f"A posé {liste_posees} depuis sa main pour former "
                     f"{desc}." if liste_posees else f"A formé {desc}.")
        elif modifiees:
            desc = _decrire_combo(plateau_apres[modifiees[0]])
            texte = (f"A posé {liste_posees} depuis sa main en complétant "
                      f"{desc}." if liste_posees else
                      f"A complété {desc}.")
        elif liste_posees:
            texte = f"A posé {liste_posees} depuis sa main."
        else:
            texte = "N'a rien changé sur le plateau."
    else:
        phrases = []
        if liste_posees:
            phrases.append(f"Tuiles posées depuis sa main : {liste_posees}.")
        if nb_defaites:
            descs = ", ".join(_decrire_combo(plateau_avant[i])
                               for i in a["defaites"])
            mot = "Combinaison défaite" if nb_defaites == 1 \
                else "Combinaisons défaites"
            phrases.append(f"{mot} : {descs}.")
        if creees:
            descs = ", ".join(_decrire_combo(plateau_apres[j]) for j in creees)
            mot = "Nouvelle combinaison créée" if len(creees) == 1 \
                else "Nouvelles combinaisons créées"
            phrases.append(f"{mot} : {descs}.")
        if modifiees:
            descs = ", ".join(_decrire_combo(plateau_apres[j])
                               for j in modifiees)
            mot = "Combinaison modifiée" if len(modifiees) == 1 \
                else "Combinaisons modifiées"
            phrases.append(f"{mot} : {descs}.")
        for depl in a["deplacements_jokers"]:
            phrases.append(f"Joker déplacé de {depl['depuis']} vers "
                            f"{depl['vers']}.")
        texte = " ".join(phrases) if phrases \
            else "Coup joué sans changement notable sur le plateau."

    return {
        "texte": texte,
        "tuiles_posees": a["tuiles_posees"],
        "nb_combinaisons_defaites": nb_defaites,
        "nb_combinaisons_creees": len(creees),
        "nb_combinaisons_modifiees": len(modifiees),
        "jokers_deplaces": a["deplacements_jokers"],
    }


def etapes_coup_ia(plateau_avant: list, plateau_apres: list) -> list:
    """Découpe un coup de l'IA en étapes successives pour le rejeu pas-à-pas :
    chaque étape porte une phrase descriptive et un instantané du plateau à
    ce stade (``plateau``, même format que `etat["plateau"]`). La dernière
    étape correspond exactement à `plateau_apres`. Le bouton « Pas à pas » du
    front-end ne s'affiche que si au moins 2 étapes sont renvoyées."""
    plateau_avant = plateau_avant or []
    plateau_apres = plateau_apres or []
    a = _analyser_coup(plateau_avant, plateau_apres)
    defaites_set = set(a["defaites"])

    working = [list(combo) for combo in plateau_avant]
    etapes = []

    for i in sorted(defaites_set):
        working[i] = []
        etapes.append({
            "texte": _phrase_sujet(plateau_avant[i], "défait"),
            "plateau": _snapshot(working),
        })

    cibles = sorted(set(a["creees"]) | set(a["modifiees"]))
    for j in cibles:
        origines = a["origines_par_apres"].get(j, [])
        origine_simple = next((i for i in origines if i not in defaites_set),
                               None)
        if origine_simple is not None:
            working[origine_simple] = list(plateau_apres[j])
        else:
            working.append(list(plateau_apres[j]))
        if j in a["creees"]:
            etapes.append({
                "texte": "Une nouvelle combinaison est formée : "
                         f"{_decrire_combo(plateau_apres[j])}.",
                "plateau": _snapshot(working),
            })
        else:
            etapes.append({
                "texte": _phrase_sujet(plateau_apres[j], "complété"),
                "plateau": _snapshot(working),
            })

    for depl in a["deplacements_jokers"]:
        etapes.append({
            "texte": f"Le joker est déplacé de {depl['depuis']} vers "
                     f"{depl['vers']}.",
            "plateau": _snapshot(working),
        })

    return etapes


def _snapshot(working: list) -> list:
    return [list(combo) for combo in working if combo]
