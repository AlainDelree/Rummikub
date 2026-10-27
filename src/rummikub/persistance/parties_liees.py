"""Regroupement des journaux d'une même partie répartie sur plusieurs fichiers
(issue #202, suite de #201).

Quand le jeu est fermé puis rouvert, une partie reprise repart sur un NOUVEAU
fichier de journal (le cache mémoire de ``persistance/journal.py`` est perdu au
redémarrage). Ce module relie ces fichiers en une seule suite d'actions, afin
que l'analyse (``persistance/coups_rates.py``) et le bilan
(``persistance/bilan.py``) traitent la partie comme si elle avait été jouée
d'un seul tenant — sans quoi :
  - l'analyse croit à tort, sur un fichier de reprise, que la mise initiale
    n'est pas faite (elle ne voit aucune pose antérieure dans CE fichier), ce
    qui bride le solveur et fausse les coups ratés / cas « solveur battu » ;
  - le bilan compte le premier fichier comme une partie abandonnée et le
    second comme une partie distincte.

Principe (point 2 de l'issue) :
  - regrouper les journaux par ``partie_id`` (en-tête du journal) ;
  - à défaut (identifiant absent, ou changé à la reprise), relier en secours
    par la continuité des numéros de tour et l'identité des joueurs ;
  - classer chaque groupe dans l'ordre chronologique (``debut``, puis nom de
    fichier) ;
  - concaténer les ``actions`` : l'état de départ de la première action d'un
    fichier de reprise est alors l'état enregistré à la dernière action du
    fichier précédent (la reconstitution reste inchangée dans
    ``coups_rates.py``/``bilan.py``, qui lisent l'état de l'action précédente).

Ce module est PUR : il ne lit aucun fichier (on lui passe des journaux déjà
chargés, voir ``bilan.charger_journal``) et ne dépend jamais de pywebview.
"""

# Numéro de tour au-delà duquel le plus ancien fichier disponible d'une partie
# est considéré comme ne couvrant PAS le début de la partie (historique initial
# supprimé par la rotation du dossier — point 3 de l'issue). Un journal complet
# commence à enregistrer dès le premier tour joué ; en pratique le premier
# ``tour`` enregistré vaut 1 ou 2 (``moteur/partie.py`` incrémente ``tour_numero``
# en fin de tour). Au-delà de ce seuil, le fichier débute en plein milieu de
# partie : c'est un fichier de reprise dont le début est manquant.
SEUIL_DEBUT_PARTIE = 2


def _actions_valides(data: dict) -> list:
    actions = data.get("actions") if isinstance(data, dict) else None
    if not isinstance(actions, list):
        return []
    return [a for a in actions if isinstance(a, dict)]


def _signature_joueurs(data: dict) -> tuple:
    """Identité des joueurs (ordre compris) pour relier deux fichiers en
    secours. Tolère l'ancien format (liste de noms)."""
    joueurs = data.get("joueurs")
    if not isinstance(joueurs, list):
        return ()
    sig = []
    for j in joueurs:
        if isinstance(j, dict):
            sig.append((j.get("nom"), bool(j.get("est_ia")), j.get("niveau")))
        else:
            sig.append((j, None, None))
    return tuple(sig)


def _premier_tour(data: dict):
    for a in _actions_valides(data):
        t = a.get("tour")
        if isinstance(t, int):
            return t
    return None


def _dernier_tour(data: dict):
    dernier = None
    for a in _actions_valides(data):
        t = a.get("tour")
        if isinstance(t, int):
            dernier = t
    return dernier


def _cle_tri(entree: dict) -> tuple:
    data = entree["data"]
    return (data.get("debut") or "", entree.get("nom") or "")


def grouper_journaux(journaux: list) -> list:
    """Regroupe les fichiers d'une même partie.

    ``journaux`` : liste de ``{"nom": str, "data": dict}`` (journaux déjà
    chargés). Retourne une liste de groupes, chaque groupe étant la liste
    ordonnée chronologiquement des ``{"nom", "data"}`` d'une même partie (un
    seul élément si la partie tient dans un fichier). Les journaux vides ou
    invalides (sans action exploitable) sont ignorés.

    Rattachement d'un fichier à un groupe existant, par ordre de priorité :
      (a) même ``partie_id`` non nul : lien direct, fiable (l'identifiant est
          conservé à la reprise car l'état restauré garde le même ``id``) ;
      (b) repli : mêmes joueurs et continuité des tours — le fichier commence
          au tour où le dernier fichier du groupe s'est arrêté (ou juste
          après) et n'est pas lui-même un début de partie (tour <=
          :data:`SEUIL_DEBUT_PARTIE`), ce qui le distingue d'une nouvelle
          partie entre les mêmes joueurs.
    """
    entrees = [e for e in journaux
               if isinstance(e, dict) and isinstance(e.get("data"), dict)
               and _actions_valides(e["data"])]
    entrees = sorted(entrees, key=_cle_tri)

    groupes = []  # [{"items": [...], "pid": ..., "sig": ...}]
    for e in entrees:
        data = e["data"]
        pid = data.get("partie_id")
        sig = _signature_joueurs(data)
        ptour = _premier_tour(data)

        rattache = None
        # (a) Priorité absolue au partie_id : chercher d'abord un groupe de
        # même identifiant, sur TOUS les groupes.
        if pid is not None:
            for g in groupes:
                if g["pid"] == pid:
                    rattache = g
                    break
        # (b) Repli par continuité, seulement si aucun lien par identifiant.
        if rattache is None and sig and ptour is not None and ptour > SEUIL_DEBUT_PARTIE:
            for g in groupes:
                if g["sig"] != sig:
                    continue
                dt = _dernier_tour(g["items"][-1]["data"])
                if dt is not None and ptour >= dt:
                    rattache = g
                    break

        if rattache is None:
            groupes.append({"items": [e], "pid": pid, "sig": sig})
        else:
            rattache["items"].append(e)
            if rattache["pid"] is None and pid is not None:
                rattache["pid"] = pid

    return [g["items"] for g in groupes]


def fusionner_groupe(groupe: list) -> dict:
    """Fusionne un groupe (sortie de :func:`grouper_journaux`, liste ordonnée
    de ``{"nom", "data"}``) en un unique journal.

    Retourne ``{"data": <journal fusionné>, "debut_present": bool,
    "fichiers": [noms...], "partie_id": ...}``. Le journal fusionné réutilise
    l'en-tête du PREMIER fichier (``joueurs``, ``debut``, ``partie_id``) et
    concatène les ``actions`` de tous les fichiers dans l'ordre.

    ``debut_present`` est ``False`` si le plus ancien fichier ne couvre pas le
    début de la partie (premier ``tour`` enregistré au-delà de
    :data:`SEUIL_DEBUT_PARTIE`) : l'historique initial a été supprimé par la
    rotation du dossier et la mise initiale des joueurs ne pourra pas toujours
    être déterminée sur les anciens journaux (point 3 de l'issue)."""
    premier = groupe[0]["data"]
    actions = []
    for item in groupe:
        actions.extend(_actions_valides(item["data"]))
    data = dict(premier)
    data["actions"] = actions
    ptour = _premier_tour(premier)
    debut_present = ptour is None or ptour <= SEUIL_DEBUT_PARTIE
    return {
        "data": data,
        "debut_present": debut_present,
        "fichiers": [item.get("nom") for item in groupe],
        "partie_id": premier.get("partie_id"),
    }


def fusionner_journaux(journaux: list) -> list:
    """Raccourci : :func:`grouper_journaux` puis :func:`fusionner_groupe` sur
    chaque groupe. Retourne la liste des parties fusionnées (dicts décrits par
    :func:`fusionner_groupe`), une par partie réelle."""
    return [fusionner_groupe(groupe) for groupe in grouper_journaux(journaux)]
