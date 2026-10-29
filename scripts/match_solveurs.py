#!/usr/bin/env python3
"""Match « notre solveur d'Expert » contre la bibliothèque externe
``rummikub-solver`` sur des parties ENTIÈRES (issue #212, suite de #206).

But
---
Nos deux solveurs trouvent le même NOMBRE de tuiles posables à chaque tour
(vérifié en #204 sur les cas de référence et par recherche exhaustive). Mais, à
nombre de tuiles égal, ils **départagent** différemment : le nôtre préfère la
perturbation minimale du plateau (#199) puis économise les jokers ; la
bibliothèque applique ses propres règles. Ce script fait jouer une partie
entière pilotée par chaque solveur pour voir si NOS critères de départage nous
désavantagent au fil d'une partie.

Portée (à ne PAS sur-interpréter)
---------------------------------
Les deux solveurs n'optimisent qu'UN tour. Ce match ne mesure donc PAS la
valeur d'une stratégie sur plusieurs tours (réserve, joker gardé, rétention —
pistes de ``CONTEXTE.md`` §13) ; il mesure seulement si, à jeu « un tour »
équivalent, nos critères de départage tiennent la route. Il ne dit rien non
plus sur la force absolue d'un humain.

Protocole « miroir »
--------------------
Chaque *donne* (sac mélangé + distribution, fixée par une graine) est jouée
DEUX fois, places échangées :
  - partie A : notre solveur en siège 0 (ouvre), bibliothèque en siège 1 ;
  - partie B : bibliothèque en siège 0 (ouvre), notre solveur en siège 1.
La graine est réappliquée avant chaque ``creer_partie`` : les deux parties
partent donc EXACTEMENT de la même donne. Ainsi chaque solveur joue une fois
chaque main et une fois chaque position : l'avantage de la main et celui
d'ouvrir sont neutralisés.

Le « joueur bibliothèque » (point 1 de l'issue)
-----------------------------------------------
Construit sur ``scripts/solveur_exact.py`` (adaptateur #204). Il renvoie un
coup complet (tuiles posées + nouveau plateau) déjà remis dans l'ordre et
validé par ``valider_combinaison``, avec conservation du plateau contrôlée.
**Mise initiale** : la bibliothèque, en mode INITIAL, réarrange table + main au
second temps, ce que les règles interdisent avant la mise. On la contraint donc
à n'utiliser QUE la main tant que la mise n'est pas faite (on résout sur un
plateau vide, puis on recolle le plateau existant intact). Les coups où la
bibliothèque voudrait quand même toucher le plateau avant la mise sont ainsi
écartés par construction (comptés : ``mise_contrainte``).

Contrôles
---------
- conservation des 106 tuiles à CHAQUE coup (pioche + chevalets + plateau) ;
- à chaque tour, le nombre maximal de tuiles posables selon NOTRE solveur et
  selon la bibliothèque est comparé sur le MÊME état : tout écart est signalé
  (ne devrait jamais arriver — ce serait un écart d'optimalité à investiguer).

Dépendance de DÉVELOPPEMENT seulement
-------------------------------------
``rummikub-solver`` n'est ni dans ``requirements.txt`` ni dans le build Windows
(voir ``CONTEXTE.md`` §14). Ce script est un OUTIL D'ANALYSE. Il se saute
proprement si la bibliothèque est absente (message d'installation, code 2).

Usage
-----
    .venv-solveur-exact/bin/python scripts/match_solveurs.py \
        --donnes 100 --limite-temps 3600 --sortie resultats_match_212.txt

Options principales : ``--donnes N`` (N donnes = 2N parties), ``--limite-temps
S`` (limite ferme en secondes ; on s'arrête proprement entre deux parties et on
exploite les résultats partiels), ``--sortie FICHIER`` (rapport texte ; un
``.json`` frère reçoit les données brutes), ``--max-tours`` (garde-fou de
blocage), ``--seed`` (graine de base, reproductible), ``--budget-expert``.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "src"
SCRIPTS = RACINE / "scripts"
for p in (SRC, SCRIPTS):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from rummikub.moteur.partie import (  # noqa: E402
    annuler_tour, backup_debut_tour, creer_partie, jouer_tour, passer_tour,
    piocher,
)
from rummikub.moteur.ia import jouer_niveau_expert  # noqa: E402
from rummikub.moteur import solveur_exact as solveur_maison  # noqa: E402

import solveur_exact as solveur_biblio  # noqa: E402  (scripts/solveur_exact.py)


NB_TUILES_TOTAL = 106
NOM_NOTRE = "notre"
NOM_BIBLIO = "biblio"


# --------------------------------------------------------------------------- #
# Décideurs de coup
# --------------------------------------------------------------------------- #

@dataclass
class Decision:
    """Coup décidé par un solveur pour un tour donné."""
    action: str                      # "jouer" | "piocher" | "passer"
    ids_tuiles: list = field(default_factory=list)
    nouveau_plateau: list = field(default_factory=list)
    nb_posees: int = 0               # tuiles de la main posées (0 si pioche/passe)
    duree: float = 0.0               # durée de la décision (s)
    mise_contrainte: bool = False    # coup biblio écarté/contraint avant la mise


def decider_notre_solveur(etat: dict, idx: int, budget_temps: float) -> Decision:
    """« Notre solveur » = niveau Expert livré (``jouer_niveau_expert``), qui
    calcule le coup par le modèle exact maison (``moteur/solveur_exact.py``) et,
    s'il n'y a rien à poser, laisse Avancé trancher pioche/passe. C'est le
    joueur réellement embarqué dans le jeu."""
    debut = time.monotonic()
    coup = jouer_niveau_expert(etat, idx, budget_temps=budget_temps)
    duree = time.monotonic() - debut
    action = coup.get("action", "piocher")
    if action == "jouer":
        ids = list(coup.get("ids_tuiles", []))
        return Decision("jouer", ids, coup.get("nouveau_plateau", []),
                        nb_posees=len(ids), duree=duree)
    return Decision(action, duree=duree)


def _etat_main_seule(etat: dict, idx: int) -> dict:
    """Copie de l'état où le plateau est vidé POUR LE SEUL calcul du joueur
    ``idx`` : avant la mise initiale, la bibliothèque ne doit toucher qu'à sa
    main. En résolvant sur un plateau vide, on la contraint à ne former ses
    combinaisons qu'avec la main ; le plateau réel (intact) est recollé ensuite.
    """
    e = copy.copy(etat)
    e["plateau"] = []
    e["config"] = etat.get("config", {})
    return e


def decider_bibliotheque(etat: dict, idx: int) -> Decision:
    """« Joueur bibliothèque » (point 1 de l'issue), bâti sur l'adaptateur
    ``scripts/solveur_exact.py`` (#204).

    Renvoie un coup complet (tuiles posées + nouveau plateau remis dans l'ordre
    et validé par ``valider_combinaison``, conservation du plateau contrôlée par
    l'adaptateur). Si rien n'est posable (ou mise initiale inatteignable), ou si
    la bibliothèque proposerait un coup invalide / non conservatif, on pioche.

    Mise initiale : on contraint la bibliothèque à n'utiliser que la main
    (plateau vidé pour le calcul, voir :func:`_etat_main_seule`), puis on recolle
    le plateau existant intact. ``mise_contrainte`` marque ce cas.
    """
    joueur = etat["joueurs"][idx]
    mise_faite = bool(joueur.get("mise_initiale_faite", True))

    debut = time.monotonic()
    try:
        if mise_faite:
            res = solveur_biblio.resoudre_exact(etat, idx)
        else:
            res = solveur_biblio.resoudre_exact(_etat_main_seule(etat, idx), idx)
    except Exception:
        duree = time.monotonic() - debut
        return Decision("piocher", duree=duree)
    duree = time.monotonic() - debut

    if res.nb_tuiles == 0 or not res.ids_tuiles:
        return Decision("piocher", duree=duree, mise_contrainte=not mise_faite)
    if not res.valide_globalement:
        # Coup invalide ou non conservatif : écarté proprement (on pioche).
        return Decision("piocher", duree=duree, mise_contrainte=not mise_faite)

    if mise_faite:
        nouveau_plateau = res.nouveau_plateau
    else:
        # Plateau existant (intact) + nouvelles combinaisons de la main seule.
        nouveau_plateau = list(etat.get("plateau", [])) + res.nouveau_plateau

    return Decision("jouer", list(res.ids_tuiles), nouveau_plateau,
                    nb_posees=len(res.ids_tuiles), duree=duree,
                    mise_contrainte=not mise_faite)


# --------------------------------------------------------------------------- #
# Maximum posable par chaque solveur sur un MÊME état (contrôle d'optimalité)
# --------------------------------------------------------------------------- #

def max_posable_notre(etat: dict, idx: int, budget_temps: float):
    """Nb maximal de tuiles de la main que NOTRE modèle exact pose sur ``etat``
    (``None`` si le solveur n'a pas pu conclure)."""
    try:
        res = solveur_maison.resoudre_exact(etat, idx, budget_temps=budget_temps)
    except Exception:
        return None
    if not res.valide_globalement:
        return None
    return res.nb_tuiles


def max_posable_biblio(etat: dict, idx: int):
    """Nb maximal de tuiles de la main que la BIBLIOTHÈQUE pose sur ``etat``,
    avec la même contrainte « main seule avant la mise » que le décideur."""
    joueur = etat["joueurs"][idx]
    mise_faite = bool(joueur.get("mise_initiale_faite", True))
    try:
        cible = etat if mise_faite else _etat_main_seule(etat, idx)
        res = solveur_biblio.resoudre_exact(cible, idx)
    except Exception:
        return None
    if not res.valide_globalement:
        return None
    return res.nb_tuiles


# --------------------------------------------------------------------------- #
# Contrôle de conservation des 106 tuiles
# --------------------------------------------------------------------------- #

def conservation_ok(etat: dict) -> tuple[bool, str]:
    """Vérifie que les 106 tuiles sont toutes présentes et uniques (pioche +
    chevalets + plateau). Retourne ``(ok, message)``."""
    ids: list[str] = [t["id"] for t in etat["pioche"]]
    for j in etat["joueurs"]:
        ids += [t["id"] for t in j["chevalet"]]
    for combo in etat["plateau"]:
        ids += [t["id"] for t in combo]
    n = len(ids)
    uniques = len(set(ids))
    if n != NB_TUILES_TOTAL:
        return False, f"{n} tuiles au lieu de {NB_TUILES_TOTAL}"
    if uniques != NB_TUILES_TOTAL:
        return False, f"{n - uniques} doublon(s) d'id"
    return True, ""


# --------------------------------------------------------------------------- #
# Déroulement d'une partie (une donne, un sens)
# --------------------------------------------------------------------------- #

def jouer_une_partie(etat: dict, roles: list[str],
                     max_tours: int, budget_temps: float) -> dict:
    """Joue une manche complète à deux joueurs. ``roles[s]`` est l'étiquette du
    siège ``s`` (``notre``/``biblio``), qui désigne le solveur décidant pour ce
    siège.

    Retourne un dict de statistiques de la partie (voir le code pour les clés).
    """
    backup_debut_tour(etat)

    stats = {
        "tours": 0,
        "bloquee": False,
        "gagnant_role": None,          # notre / biblio / None (égalité)
        "egalite": False,
        "perdant_tuiles_restantes": None,
        "conservation_erreurs": [],
        "ecarts_optimalite": [],       # écarts de nb posables sur même état
        "par_role": {NOM_NOTRE: _stats_role(), NOM_BIBLIO: _stats_role()},
    }

    while not etat["manche_terminee"]:
        stats["tours"] += 1
        if stats["tours"] > max_tours:
            stats["bloquee"] = True
            break

        idx = etat["index_joueur_actuel"]
        role = roles[idx]
        autre_role = roles[1 - idx]

        # Contrôle d'optimalité : nb posables des DEUX solveurs sur le même état.
        if role == NOM_NOTRE:
            nb_actif = max_posable_notre(etat, idx, budget_temps)
            nb_autre = max_posable_biblio(etat, idx)
            nb_notre, nb_biblio = nb_actif, nb_autre
        else:
            nb_actif = max_posable_biblio(etat, idx)
            nb_autre = max_posable_notre(etat, idx, budget_temps)
            nb_notre, nb_biblio = nb_autre, nb_actif
        if (nb_notre is not None and nb_biblio is not None
                and nb_notre != nb_biblio):
            stats["ecarts_optimalite"].append({
                "tour": etat["tour_numero"], "siege_actif": idx,
                "role_actif": role, "nb_notre": nb_notre, "nb_biblio": nb_biblio,
            })

        # Décision réelle du siège actif.
        if role == NOM_NOTRE:
            dec = decider_notre_solveur(etat, idx, budget_temps)
        else:
            dec = decider_bibliotheque(etat, idx)

        sr = stats["par_role"][role]
        sr["tours"] += 1
        sr["duree_totale"] += dec.duree
        sr["duree_max"] = max(sr["duree_max"], dec.duree)
        if dec.mise_contrainte:
            sr["mise_contrainte"] += 1

        anomalie = _appliquer_decision(etat, idx, dec, role, autre_role, stats)
        if anomalie:
            # Coup refusé par le moteur : on annule et on pioche (comme en jeu).
            annuler_tour(etat)
            etat = piocher(etat)["etat"]
        # Contrôle de conservation après le coup.
        ok, msg = conservation_ok(etat)
        if not ok:
            stats["conservation_erreurs"].append(
                {"tour": etat["tour_numero"], "message": msg})
        backup_debut_tour(etat)

    _finaliser_partie(etat, roles, stats)
    return stats


def _stats_role() -> dict:
    return {"tours": 0, "tuiles_posees": 0, "poses": 0,
            "duree_totale": 0.0, "duree_max": 0.0, "mise_contrainte": 0}


def _appliquer_decision(etat, idx, dec: Decision, role, autre_role,
                        stats) -> bool:
    """Applique la décision au moteur. Retourne ``True`` si le coup « jouer » a
    été refusé par le moteur (anomalie), ``False`` sinon."""
    sr = stats["par_role"][role]
    if dec.action == "jouer":
        res = jouer_tour(etat, dec.ids_tuiles, dec.nouveau_plateau)
        if not res["ok"]:
            stats.setdefault("coups_refuses", []).append(
                {"tour": etat["tour_numero"], "role": role,
                 "erreur": res.get("erreur", "?")})
            return True
        sr["tuiles_posees"] += dec.nb_posees
        sr["poses"] += 1
        return False
    if dec.action == "passer":
        passer_tour(etat)
        return False
    piocher(etat)
    return False


def _finaliser_partie(etat, roles, stats) -> None:
    """Détermine le gagnant (rôle), l'égalité éventuelle et les tuiles restantes
    du perdant à la fin de la manche."""
    gi = etat.get("gagnant_manche_index")
    scores = [j["score_manche"] for j in etat["joueurs"]]
    chevalets = [len(j["chevalet"]) for j in etat["joueurs"]]

    # Un vrai gagnant a vidé son chevalet ; sinon (blocage / pioche vide) on
    # tranche au score de manche, avec détection d'égalité.
    if gi is not None and scores[gi] == scores[1 - gi] and 0 not in chevalets:
        stats["egalite"] = True
        stats["gagnant_role"] = None
        stats["perdant_tuiles_restantes"] = None
    elif gi is not None:
        stats["gagnant_role"] = roles[gi]
        perdant = 1 - gi
        stats["perdant_tuiles_restantes"] = chevalets[perdant]
        stats["perdant_role"] = roles[perdant]
    for siege, role in enumerate(roles):
        stats["par_role"][role]["tuiles_finales"] = chevalets[siege]


# --------------------------------------------------------------------------- #
# Match complet (plusieurs donnes, miroir)
# --------------------------------------------------------------------------- #

def jouer_match(nb_donnes: int, seed_base: int, max_tours: int,
                budget_temps: float, limite_temps: float | None,
                journal=None) -> dict:
    """Joue ``nb_donnes`` donnes en miroir (2 parties par donne). S'arrête
    proprement si ``limite_temps`` (secondes) est atteinte entre deux parties,
    en exploitant les résultats partiels."""
    debut = time.monotonic()
    parties: list[dict] = []
    donnes_jouees = 0
    interrompu = False

    for d in range(nb_donnes):
        seed = seed_base + d
        # Partie A : notre solveur ouvre (siège 0), bibliothèque siège 1.
        # Partie B : bibliothèque ouvre (siège 0), notre solveur siège 1.
        # Même donne : la graine est réappliquée avant chaque creer_partie.
        for sens, roles in (("A", [NOM_NOTRE, NOM_BIBLIO]),
                            ("B", [NOM_BIBLIO, NOM_NOTRE])):
            if limite_temps is not None and \
                    time.monotonic() - debut >= limite_temps:
                interrompu = True
                break
            random.seed(seed)
            config_joueurs = [
                {"nom": f"{roles[0]}#0", "est_ia": True, "niveau": "Expert"},
                {"nom": f"{roles[1]}#1", "est_ia": True, "niveau": "Expert"},
            ]
            etat = creer_partie(config_joueurs, {"nb_manches": 1})
            st = jouer_une_partie(etat, roles, max_tours, budget_temps)
            st["donne"] = d
            st["sens"] = sens
            st["seed"] = seed
            parties.append(st)
            if journal is not None:
                journal(parties, debut)
        donnes_jouees = d + 1
        if interrompu:
            break

    duree = time.monotonic() - debut
    return {
        "parties": parties,
        "donnes_demandees": nb_donnes,
        "donnes_jouees": donnes_jouees,
        "parties_jouees": len(parties),
        "interrompu": interrompu,
        "duree_s": duree,
        "seed_base": seed_base,
        "max_tours": max_tours,
        "budget_temps": budget_temps,
    }


# --------------------------------------------------------------------------- #
# Agrégation et statistiques
# --------------------------------------------------------------------------- #

def _wilson(succes: int, total: int) -> tuple[float, float, float]:
    """Proportion + intervalle de confiance de Wilson à 95 % (``p, bas, haut``).
    Robuste aux petits échantillons, contrairement à l'approximation normale."""
    if total == 0:
        return 0.0, 0.0, 0.0
    z = 1.959963984540054
    p = succes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    demi = (z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
            ) / denom
    return p, max(0.0, centre - demi), min(1.0, centre + demi)


def agreger(resultat: dict) -> dict:
    """Calcule les indicateurs demandés (point 3 de l'issue) à partir des
    parties jouées."""
    parties = resultat["parties"]
    n = len(parties)
    victoires = {NOM_NOTRE: 0, NOM_BIBLIO: 0}
    egalites = 0
    bloquees = 0
    tuiles_restantes_perdant = {NOM_NOTRE: [], NOM_BIBLIO: []}
    tours_par_partie = []
    ecarts_optimalite = []
    conservation_erreurs = []
    coups_refuses = []
    mise_contrainte = {NOM_NOTRE: 0, NOM_BIBLIO: 0}
    roles_stats = {
        NOM_NOTRE: {"tuiles_posees": 0, "tours": 0, "poses": 0,
                    "duree_totale": 0.0, "duree_max": 0.0},
        NOM_BIBLIO: {"tuiles_posees": 0, "tours": 0, "poses": 0,
                     "duree_totale": 0.0, "duree_max": 0.0},
    }

    for p in parties:
        tours_par_partie.append(p["tours"])
        if p["bloquee"]:
            bloquees += 1
        if p["egalite"]:
            egalites += 1
        elif p["gagnant_role"] is not None:
            victoires[p["gagnant_role"]] += 1
            perdant = p.get("perdant_role")
            if perdant and p["perdant_tuiles_restantes"] is not None:
                tuiles_restantes_perdant[perdant].append(
                    p["perdant_tuiles_restantes"])
        for e in p["ecarts_optimalite"]:
            ecarts_optimalite.append({**e, "donne": p["donne"],
                                      "sens": p["sens"]})
        for e in p["conservation_erreurs"]:
            conservation_erreurs.append({**e, "donne": p["donne"],
                                         "sens": p["sens"]})
        for e in p.get("coups_refuses", []):
            coups_refuses.append({**e, "donne": p["donne"], "sens": p["sens"]})
        for role in (NOM_NOTRE, NOM_BIBLIO):
            sr = p["par_role"][role]
            rs = roles_stats[role]
            rs["tuiles_posees"] += sr["tuiles_posees"]
            rs["tours"] += sr["tours"]
            rs["poses"] += sr["poses"]
            rs["duree_totale"] += sr["duree_totale"]
            rs["duree_max"] = max(rs["duree_max"], sr["duree_max"])
            mise_contrainte[role] += sr["mise_contrainte"]

    decisives = victoires[NOM_NOTRE] + victoires[NOM_BIBLIO]
    taux = {}
    for role in (NOM_NOTRE, NOM_BIBLIO):
        # Taux de victoire sur l'ensemble des parties jouées (égalités incluses
        # au dénominateur : elles ne sont une victoire pour personne).
        p_hat, bas, haut = _wilson(victoires[role], n)
        taux[role] = {"victoires": victoires[role], "parties": n,
                      "taux": p_hat, "ic95_bas": bas, "ic95_haut": haut}

    def moyenne(xs):
        return sum(xs) / len(xs) if xs else None

    indicateurs = {}
    for role in (NOM_NOTRE, NOM_BIBLIO):
        rs = roles_stats[role]
        indicateurs[role] = {
            "tuiles_posees_par_tour": (rs["tuiles_posees"] / rs["tours"]
                                       if rs["tours"] else None),
            "tuiles_posees_par_pose": (rs["tuiles_posees"] / rs["poses"]
                                       if rs["poses"] else None),
            "duree_moyenne_coup": (rs["duree_totale"] / rs["tours"]
                                   if rs["tours"] else None),
            "duree_max_coup": rs["duree_max"],
            "tuiles_restantes_quand_perd": moyenne(
                tuiles_restantes_perdant[role]),
            "parties_perdues": len(tuiles_restantes_perdant[role]),
            "mise_contrainte": mise_contrainte[role],
        }

    return {
        "parties_jouees": n,
        "victoires": victoires,
        "decisives": decisives,
        "egalites": egalites,
        "bloquees": bloquees,
        "taux_victoire": taux,
        "tours_par_partie_moyen": moyenne(tours_par_partie),
        "indicateurs": indicateurs,
        "ecarts_optimalite": ecarts_optimalite,
        "conservation_erreurs": conservation_erreurs,
        "coups_refuses": coups_refuses,
    }


# --------------------------------------------------------------------------- #
# Rapport texte
# --------------------------------------------------------------------------- #

def formater_rapport(resultat: dict, agr: dict) -> str:
    L = []
    w = L.append
    w("=" * 72)
    w("MATCH — notre solveur d'Expert  vs  bibliothèque rummikub-solver")
    w("(issue #212, suite de #206)")
    w("=" * 72)
    w("")
    w(f"Donnes demandées   : {resultat['donnes_demandees']}")
    w(f"Donnes jouées      : {resultat['donnes_jouees']} "
      f"({resultat['parties_jouees']} parties, miroir places échangées)")
    if resultat["interrompu"]:
        w("  (!) Limite de temps atteinte : résultats PARTIELS exploités.")
    w(f"Durée totale       : {resultat['duree_s']:.1f} s")
    w(f"Graine de base     : {resultat['seed_base']}   "
      f"max_tours={resultat['max_tours']}   "
      f"budget Expert={resultat['budget_temps']} s")
    w("")
    w("-" * 72)
    w("TAUX DE VICTOIRE (IC 95 %, Wilson ; dénominateur = parties jouées)")
    w("-" * 72)
    for role, lib in ((NOM_NOTRE, "Notre solveur (Expert)"),
                      (NOM_BIBLIO, "Bibliothèque")):
        t = agr["taux_victoire"][role]
        w(f"  {lib:26s} : {t['victoires']:4d} / {t['parties']:<4d} = "
          f"{t['taux']*100:5.1f} %  "
          f"[{t['ic95_bas']*100:4.1f} % ; {t['ic95_haut']*100:4.1f} %]")
    w(f"  Égalités                   : {agr['egalites']}")
    w(f"  Parties bloquées           : {agr['bloquees']}")
    w("")
    w("-" * 72)
    w("INDICATEURS DE MARGE ET DE JEU")
    w("-" * 72)
    w(f"  Tours par partie (moyen)   : "
      f"{_fmt(agr['tours_par_partie_moyen'], '.1f')}")
    for role, lib in ((NOM_NOTRE, "Notre solveur (Expert)"),
                      (NOM_BIBLIO, "Bibliothèque")):
        ind = agr["indicateurs"][role]
        w(f"  • {lib}")
        w(f"      tuiles restantes en main quand il PERD (moy.) : "
          f"{_fmt(ind['tuiles_restantes_quand_perd'], '.2f')} "
          f"(sur {ind['parties_perdues']} défaites)")
        w(f"      tuiles posées par tour (moy.)                 : "
          f"{_fmt(ind['tuiles_posees_par_tour'], '.3f')}")
        w(f"      temps par coup — moyen / max                  : "
          f"{_fmt(ind['duree_moyenne_coup'], '.4f')} s / "
          f"{_fmt(ind['duree_max_coup'], '.4f')} s")
        if ind["mise_contrainte"]:
            w(f"      coups « main seule » avant la mise (biblio)   : "
              f"{ind['mise_contrainte']}")
    w("")
    w("-" * 72)
    w("CONTRÔLES")
    w("-" * 72)
    ne = len(agr["ecarts_optimalite"])
    w(f"  Écarts d'optimalité (nb posables différent même état) : {ne}")
    if ne:
        w("   (!) À INVESTIGUER — ne devrait jamais arriver :")
        for e in agr["ecarts_optimalite"][:20]:
            w(f"     donne {e['donne']}{e['sens']} tour {e['tour']} "
              f"(actif={e['role_actif']}) : "
              f"notre={e['nb_notre']} biblio={e['nb_biblio']}")
    nc = len(agr["conservation_erreurs"])
    w(f"  Erreurs de conservation des 106 tuiles                : {nc}")
    for e in agr["conservation_erreurs"][:20]:
        w(f"     donne {e['donne']}{e['sens']} tour {e['tour']} : {e['message']}")
    ncr = len(agr["coups_refuses"])
    w(f"  Coups refusés par le moteur (repli pioche)            : {ncr}")
    for e in agr["coups_refuses"][:10]:
        w(f"     donne {e['donne']}{e['sens']} tour {e['tour']} "
          f"({e['role']}) : {e['erreur']}")
    w("")
    w("-" * 72)
    w("INTERPRÉTATION")
    w("-" * 72)
    for ligne in _interpreter(agr):
        w("  " + ligne)
    w("")
    w("PORTÉE — à ne pas sur-interpréter : les deux solveurs n'optimisent")
    w("qu'UN tour. Ce match ne mesure PAS les stratégies sur plusieurs tours")
    w("(réserve, joker gardé, rétention — CONTEXTE.md §13), ni la force d'un")
    w("humain : seulement si, à jeu « un tour » égal, nos critères de")
    w("départage (simplicité #199, économie de jokers) tiennent la route.")
    w("=" * 72)
    return "\n".join(L)


def _fmt(x, spec):
    return format(x, spec) if x is not None else "n/a"


def _interpreter(agr: dict) -> list[str]:
    """Verdict factuel, sans sur-vendre (point 4 de l'issue)."""
    tn = agr["taux_victoire"][NOM_NOTRE]
    tb = agr["taux_victoire"][NOM_BIBLIO]
    n = agr["parties_jouees"]
    if n == 0:
        return ["Aucune partie jouée : rien à conclure."]
    lignes = []
    # Chevauchement des IC 95 % des deux taux de victoire.
    chevauche = not (tn["ic95_bas"] > tb["ic95_haut"]
                     or tb["ic95_bas"] > tn["ic95_haut"])
    if chevauche:
        lignes.append(
            "Les intervalles de confiance à 95 % des deux taux de victoire se "
            "CHEVAUCHENT : à ce stade, aucun solveur n'a d'avantage démontré "
            "au jeu « un tour ».")
        lignes.append(
            "Conséquence : nos critères de départage (simplicité, économie de "
            "jokers) ne nous désavantagent pas de façon mesurable ; le progrès "
            "est à chercher dans le jeu sur plusieurs tours (CONTEXTE.md §13).")
    elif tn["taux"] < tb["taux"]:
        lignes.append(
            "Notre solveur perd NETTEMENT (IC 95 % disjoints) : nos critères de "
            "départage (simplicité, jokers) nous désavantagent sur une partie "
            "entière et sont à revoir.")
    else:
        lignes.append(
            "Notre solveur gagne NETTEMENT (IC 95 % disjoints) : nos critères de "
            "départage ne nous désavantagent pas — ils semblent même aider.")
    if agr["ecarts_optimalite"]:
        lignes.append(
            f"ATTENTION : {len(agr['ecarts_optimalite'])} écart(s) d'optimalité "
            "détecté(s) (les deux solveurs ne posent pas le même nombre de "
            "tuiles sur un même état) — à investiguer, cela fausserait le match.")
    else:
        lignes.append(
            "Aucun écart d'optimalité : sur chaque état rencontré, les deux "
            "solveurs posent le même nombre de tuiles (seul le départage "
            "diffère), ce qui valide l'équité du match.")
    return lignes


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _ecrire_sorties(sortie: Path, resultat: dict, agr: dict) -> None:
    rapport = formater_rapport(resultat, agr)
    sortie.write_text(rapport + "\n", encoding="utf-8")
    json_path = sortie.with_suffix(".json")
    json_path.write_text(
        json.dumps({"resultat": resultat, "agregat": agr},
                   ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--donnes", type=int, default=100,
                        help="Nombre de donnes (2 parties chacune ; défaut 100).")
    parser.add_argument("--seed", type=int, default=20212,
                        help="Graine de base (reproductibilité ; défaut 20212).")
    parser.add_argument("--max-tours", type=int, default=400,
                        help="Garde-fou anti-blocage par partie (défaut 400).")
    parser.add_argument("--budget-expert", type=float, default=1.5,
                        help="Budget de temps du solveur d'Expert (s ; défaut 1.5).")
    parser.add_argument("--limite-temps", type=float, default=None,
                        help="Limite ferme en secondes (arrêt propre entre deux "
                             "parties, résultats partiels exploités).")
    parser.add_argument("--sortie", type=str, default="resultats_match_212.txt",
                        help="Fichier de rapport texte (+ .json frère).")
    parser.add_argument("--silencieux", action="store_true",
                        help="N'affiche pas le rapport sur stdout.")
    args = parser.parse_args(argv[1:])

    if not solveur_biblio.DISPONIBLE:
        print(solveur_biblio.MESSAGE_INSTALLATION, file=sys.stderr)
        return 2

    sortie = Path(args.sortie)
    if not sortie.is_absolute():
        sortie = RACINE / sortie

    def journal(parties, debut):
        # Sauvegarde incrémentale : à chaque partie, on réécrit le rapport pour
        # que les résultats partiels soient exploitables même si on interrompt.
        partiel = {
            "parties": parties, "donnes_demandees": args.donnes,
            "donnes_jouees": (len(parties) + 1) // 2,
            "parties_jouees": len(parties), "interrompu": False,
            "duree_s": time.monotonic() - debut, "seed_base": args.seed,
            "max_tours": args.max_tours, "budget_temps": args.budget_expert,
        }
        _ecrire_sorties(sortie, partiel, agreger(partiel))

    resultat = jouer_match(args.donnes, args.seed, args.max_tours,
                           args.budget_expert, args.limite_temps, journal=journal)
    agr = agreger(resultat)
    _ecrire_sorties(sortie, resultat, agr)

    if not args.silencieux:
        print(formater_rapport(resultat, agr))
    print(f"\nRapport écrit dans {sortie} (+ {sortie.with_suffix('.json')})",
          file=sys.stderr)
    # Code de sortie : 1 si un contrôle a échoué (écart d'optimalité,
    # conservation), 0 sinon.
    if agr["ecarts_optimalite"] or agr["conservation_erreurs"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
