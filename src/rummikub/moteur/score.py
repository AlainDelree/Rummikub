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
    """
    gagnant_index = None
    for i, joueur in enumerate(joueurs):
        if len(joueur["chevalet"]) == 0:
            gagnant_index = i
            break

    total_penalites = 0
    for i, joueur in enumerate(joueurs):
        if i == gagnant_index:
            continue
        penalite = sum(_penalite_tuile(t, valeur_joker) for t in joueur["chevalet"])
        joueur["score_manche"] = -penalite
        total_penalites += penalite

    if gagnant_index is not None:
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
