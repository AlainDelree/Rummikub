"""Calcul des scores de manche et pénalités Rummikub."""


def _penalite_tuile(tuile, valeur_joker: int) -> int:
    """Pénalité d'une tuile, qu'elle soit un dict (as_dict) ou un objet Tuile."""
    if hasattr(tuile, "valeur_penalite"):
        return tuile.valeur_penalite(valeur_joker)
    if tuile.get("est_joker"):
        return valeur_joker
    return tuile.get("valeur") or 0


def calculer_scores_manche(joueurs: list[dict], valeur_joker: int) -> list[dict]:
    """
    Calcule score_manche pour chaque joueur.
    Perdants : score_manche = -somme(valeur_penalite de chaque tuile du chevalet)
    Gagnant (chevalet vide) : score_manche = somme des |score_manche| des perdants
    Met à jour joueur["score_manche"] et joueur["score_cumul"] en place.
    Retourne la liste mise à jour.

    Manche BLOQUÉE (issue #255, vraie règle : plus personne ne peut jouer,
    pioche vide) : aucun chevalet n'est vide. Le gagnant est alors celui dont
    les tuiles restantes valent le MOINS de points (même barème de pénalité,
    joker compris) — reprend tel quel le barème ci-dessus pour les perdants ;
    en cas d'égalité stricte au plus bas total, le premier joueur dans
    l'ordre (``joueurs``) est désigné gagnant (même convention que
    :func:`trouver_gagnant_manche`/:func:`trouver_gagnant_match`, qui
    tranchent aussi par ordre à score égal). Point douteux signalé au
    rapport de clôture #255 : aucune règle d'égalité de manche n'existait
    avant cette issue (une manche se terminait jusqu'ici toujours par un
    chevalet vide, donc un gagnant unique par construction) ; ce choix n'est
    pas tiré des règles officielles du Rummikub, qui ne détaillent pas ce
    cas, mais c'est le plus simple cohérent avec le reste du barème.
    """
    gagnant_index = None
    for i, joueur in enumerate(joueurs):
        if len(joueur["chevalet"]) == 0:
            gagnant_index = i
            break

    penalites = [sum(_penalite_tuile(t, valeur_joker) for t in j["chevalet"])
                for j in joueurs]

    if gagnant_index is None:
        # Manche bloquée : personne n'a vidé son chevalet, le moins pénalisé
        # gagne (voir docstring ci-dessus).
        gagnant_index = min(range(len(joueurs)), key=lambda i: penalites[i])

    total_penalites = 0
    for i, joueur in enumerate(joueurs):
        if i == gagnant_index:
            continue
        joueur["score_manche"] = -penalites[i]
        total_penalites += penalites[i]

    joueurs[gagnant_index]["score_manche"] = total_penalites

    for joueur in joueurs:
        joueur["score_cumul"] = joueur.get("score_cumul", 0) + joueur["score_manche"]

    return joueurs


def trouver_gagnant_manche(joueurs: list[dict]) -> int:
    """Index du joueur avec le plus haut score_manche (= vainqueur)."""
    meilleur_index = 0
    meilleur_score = joueurs[0]["score_manche"]
    for i, joueur in enumerate(joueurs):
        if joueur["score_manche"] > meilleur_score:
            meilleur_score = joueur["score_manche"]
            meilleur_index = i
    return meilleur_index


def trouver_gagnant_match(joueurs: list[dict]) -> int:
    """Index du joueur au plus haut score cumulé (= vainqueur du MATCH, toutes
    manches confondues — issue #203). En cas d'égalité au sommet, retourne le
    premier dans l'ordre des joueurs ; voir :func:`egalite_sommet_match` pour
    savoir si le sommet est partagé."""
    meilleur_index = 0
    meilleur_score = joueurs[0].get("score_cumul", 0)
    for i, joueur in enumerate(joueurs):
        if joueur.get("score_cumul", 0) > meilleur_score:
            meilleur_score = joueur.get("score_cumul", 0)
            meilleur_index = i
    return meilleur_index


def egalite_sommet_match(joueurs: list[dict]) -> bool:
    """Vrai si au moins deux joueurs partagent le plus haut score cumulé
    (égalité en tête du classement final — issue #203)."""
    if len(joueurs) < 2:
        return False
    meilleur = max(j.get("score_cumul", 0) for j in joueurs)
    return sum(1 for j in joueurs if j.get("score_cumul", 0) == meilleur) >= 2
