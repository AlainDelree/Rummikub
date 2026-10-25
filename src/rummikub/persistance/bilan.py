"""Lecture des journaux de parties (``persistance/journal.py``) et calcul du
bilan par niveau d'IA (issue #185).

Ce module est pur (aucune I/O autre que la lecture des fichiers JSON passés en
argument) afin d'être testable facilement et réutilisable par
``scripts/bilan_parties.py``. Il ne dépend jamais de pywebview.

Tolérance aux formats anciens/corrompus : toute fonction de lecture retourne
``None`` (ou ignore l'entrée) plutôt que de lever une exception sur un fichier
JSON invalide, tronqué, ou écrit par une version antérieure du journal — voir
le docstring de ``journal.py`` pour le format actuel.
"""

import json
from pathlib import Path

# Actions qui représentent une vraie décision de tour (on exclut "annulation",
# qui annule la décision précédente plutôt que d'en être une nouvelle).
_DECISIONS = {"pose", "pioche", "passe"}


# --------------------------------------------------------------------------- #
# Lecture des fichiers de journal.
# --------------------------------------------------------------------------- #

def lister_journaux(dossier: Path) -> list:
    """Chemins ``partie_*.json`` du dossier, triés (chronologique par nom)."""
    if not dossier.is_dir():
        return []
    return sorted(dossier.glob("partie_*.json"))


def charger_journal(chemin: Path) -> dict:
    """Lit un fichier de journal. Retourne ``None`` si illisible/invalide."""
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


# --------------------------------------------------------------------------- #
# Normalisation d'une partie journalisée.
# --------------------------------------------------------------------------- #

def _joueurs_normalises(joueurs) -> list:
    """Tolère l'ancien format (liste de noms) et le nouveau (liste de dicts
    nom/est_ia/niveau). Retourne toujours une liste de dicts ; ``est_ia`` et
    ``niveau`` valent ``None``/``False`` si inconnus (ancien format)."""
    if not isinstance(joueurs, list):
        return []
    out = []
    for j in joueurs:
        if isinstance(j, dict):
            out.append({"nom": j.get("nom"), "est_ia": bool(j.get("est_ia")),
                        "niveau": j.get("niveau")})
        else:
            out.append({"nom": j, "est_ia": None, "niveau": None})
    return out


def extraire_partie(data: dict) -> dict:
    """Normalise un journal brut en un résumé exploitable pour le bilan.

    Retourne ``None`` si la partie n'est pas exploitable : format invalide,
    aucune action, ou **partie non terminée** (abandonnée en cours, ou
    toujours en cours au moment de la lecture) — reconnue par l'absence du
    champ ``termine: True`` sur la dernière action enregistrée. Un journal
    écrit par une version antérieure (sans ce champ) tombe naturellement dans
    ce cas et est donc ignoré proprement plutôt que de fausser le bilan.
    """
    if not isinstance(data, dict):
        return None
    actions = data.get("actions")
    if not isinstance(actions, list) or not actions:
        return None
    actions = [a for a in actions if isinstance(a, dict)]
    if not actions:
        return None

    derniere = actions[-1]
    if not derniere.get("termine"):
        return None

    joueurs = _joueurs_normalises(data.get("joueurs"))
    if not joueurs:
        return None

    gagnant_index = derniere.get("gagnant_index")
    nb_tours = derniere.get("tour")
    mains = derniere.get("mains_joueurs") or []
    tuiles_restantes = {}
    for m in mains:
        if isinstance(m, dict) and m.get("nom") is not None:
            tuiles_restantes[m["nom"]] = len(m.get("tuiles") or [])

    decisions = []
    vues_par_tour = {}
    for a in actions:
        if a.get("action") not in _DECISIONS:
            continue
        tour = a.get("tour")
        # Dédoublonnage (#185) : une décision annulée puis rejouée réutilise
        # le même numéro de tour — on ne garde que la dernière occurrence.
        vues_par_tour[tour] = {
            "tour": tour,
            "auteur_index": a.get("auteur_index"),
            "action": a.get("action"),
            "nb_tuiles_posees": a.get("nb_tuiles_posees") or 0,
        }
    decisions = [vues_par_tour[t] for t in sorted(
        vues_par_tour, key=lambda t: (t is None, t))]

    return {
        "partie_id": data.get("partie_id"),
        "debut": data.get("debut"),
        "joueurs": joueurs,
        "gagnant_index": gagnant_index,
        "nb_tours": nb_tours,
        "tuiles_restantes": tuiles_restantes,
        "decisions": decisions,
    }


# --------------------------------------------------------------------------- #
# Filtrage (nom de joueur humain / période).
# --------------------------------------------------------------------------- #

def _partie_concerne_joueur(partie: dict, nom: str) -> bool:
    if not nom:
        return True
    return any(j["nom"] == nom and not j["est_ia"] for j in partie["joueurs"])


def _partie_dans_periode(partie: dict, depuis: str, jusqu: str) -> bool:
    debut = partie.get("debut") or ""
    if depuis and debut < depuis:
        return False
    if jusqu and debut > jusqu:
        return False
    return True


# --------------------------------------------------------------------------- #
# Bilan par niveau d'IA.
# --------------------------------------------------------------------------- #

def _moment(tour: int, nb_tours: int) -> str:
    """Place un tour dans début/milieu/fin de partie (tiers de ``nb_tours``)."""
    if not nb_tours:
        return "milieu"
    ratio = tour / nb_tours
    if ratio <= 1 / 3:
        return "debut"
    if ratio <= 2 / 3:
        return "milieu"
    return "fin"


def _stats_vierges() -> dict:
    return {
        "parties": 0,
        "victoires_humain": 0,
        "defaites_humain": 0,
        "_marges_victoire": [],
        "_marges_defaite": [],
        "_nb_tours": [],
        "_decisions_ia": [],  # [(action, moment)]
    }


def calculer_bilan(parties: list, nom_joueur: str = None,
                    depuis: str = None, jusqu: str = None) -> dict:
    """Calcule le bilan par niveau d'IA à partir de parties déjà normalisées
    (sorties de :func:`extraire_partie`, ``None`` tolérés/ignorés).

    ``nom_joueur`` : ne garde que les parties où ce joueur humain a participé.
    ``depuis``/``jusqu`` : bornes de date (``str`` comparables lexicalement à
    ``partie["debut"]``, ex. ``"2026-10-01"``).

    Retourne ``{niveau_ia: {parties, victoires_humain, defaites_humain,
    taux_victoire_humain, marge_moyenne_victoire, marge_moyenne_defaite,
    tours_moyens, part_pioche_ou_passe, repartition_moment}}``.
    """
    par_niveau: dict = {}

    for partie in parties:
        if not partie:
            continue
        if not _partie_concerne_joueur(partie, nom_joueur):
            continue
        if not _partie_dans_periode(partie, depuis, jusqu):
            continue

        humains = [(i, j) for i, j in enumerate(partie["joueurs"])
                   if j["est_ia"] is False]
        ias = [(i, j) for i, j in enumerate(partie["joueurs"])
               if j["est_ia"] is True]
        if not humains or not ias:
            continue
        if nom_joueur:
            humains = [(i, j) for i, j in humains if j["nom"] == nom_joueur]
            if not humains:
                continue

        gagnant_index = partie["gagnant_index"]
        nb_tours = partie["nb_tours"] or 0

        for idx_h, humain in humains:
            for idx_ia, ia in ias:
                niveau = ia["niveau"] or "(niveau inconnu)"
                stats = par_niveau.setdefault(niveau, _stats_vierges())
                stats["parties"] += 1
                stats["_nb_tours"].append(nb_tours)

                if gagnant_index == idx_h:
                    stats["victoires_humain"] += 1
                    marge = partie["tuiles_restantes"].get(ia["nom"])
                    if marge is not None:
                        stats["_marges_victoire"].append(marge)
                elif gagnant_index == idx_ia:
                    stats["defaites_humain"] += 1
                    marge = partie["tuiles_restantes"].get(humain["nom"])
                    if marge is not None:
                        stats["_marges_defaite"].append(marge)
                # Sinon (3e joueur vainqueur) : partie comptée, mais ni
                # victoire ni défaite attribuable à ce duel humain/IA.

                for d in partie["decisions"]:
                    if d["auteur_index"] == idx_ia:
                        moment = _moment(d["tour"] or 0, nb_tours)
                        stats["_decisions_ia"].append((d["action"], moment))

    return {niveau: _finaliser(stats) for niveau, stats in par_niveau.items()}


def _finaliser(stats: dict) -> dict:
    parties = stats["parties"]
    total_duels = stats["victoires_humain"] + stats["defaites_humain"]
    decisions = stats["_decisions_ia"]
    nb_decisions = len(decisions)
    nb_pioche_ou_passe = sum(1 for a, _ in decisions if a in ("pioche", "passe"))

    repartition = {"debut": 0, "milieu": 0, "fin": 0}
    for action, moment in decisions:
        if action in ("pioche", "passe"):
            repartition[moment] += 1

    def _moyenne(valeurs):
        return sum(valeurs) / len(valeurs) if valeurs else None

    return {
        "parties": parties,
        "victoires_humain": stats["victoires_humain"],
        "defaites_humain": stats["defaites_humain"],
        "taux_victoire_humain": (stats["victoires_humain"] / total_duels
                                 if total_duels else None),
        "marge_moyenne_victoire": _moyenne(stats["_marges_victoire"]),
        "marge_moyenne_defaite": _moyenne(stats["_marges_defaite"]),
        "tours_moyens": _moyenne(stats["_nb_tours"]),
        "part_pioche_ou_passe": (nb_pioche_ou_passe / nb_decisions
                                 if nb_decisions else None),
        "repartition_moment_pioche_ou_passe": (
            {k: v / nb_pioche_ou_passe for k, v in repartition.items()}
            if nb_pioche_ou_passe else None),
    }


def charger_toutes_parties(dossier: Path) -> list:
    """Lit et normalise tous les journaux du dossier (parties exploitables
    uniquement — voir :func:`extraire_partie`)."""
    out = []
    for chemin in lister_journaux(dossier):
        data = charger_journal(chemin)
        if data is None:
            continue
        partie = extraire_partie(data)
        if partie is not None:
            out.append(partie)
    return out
