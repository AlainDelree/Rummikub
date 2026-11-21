"""Tests directs de ``moteur/score.py`` (issue #255 : gagnant d'une manche
BLOQUÉE — aucun chevalet vide, le moins pénalisé gagne, même barème)."""

from rummikub.moteur.tuiles import Tuile
from rummikub.moteur.score import calculer_scores_manche, trouver_gagnant_manche


def t(v, c): return Tuile(f"{c}_{v}_a", v, c).as_dict()
def joker(n=1): return Tuile(f"joker_{n}", None, None, est_joker=True).as_dict()


def _joueurs(*chevalets):
    return [{"chevalet": list(c), "score_manche": 0, "score_cumul": 0}
           for c in chevalets]


def test_gagnant_chevalet_vide_inchange():
    """Non-régression : le barème d'un chevalet vidé reste celui d'avant
    #255 (gagnant = somme des pénalités des perdants)."""
    joueurs = _joueurs([], [t(10, "rouge"), t(11, "rouge")])
    calculer_scores_manche(joueurs, valeur_joker=30)
    assert joueurs[0]["score_manche"] == 21
    assert joueurs[1]["score_manche"] == -21
    assert trouver_gagnant_manche(joueurs) == 0


def test_gagnant_manche_bloquee_est_le_moins_penalise():
    """Manche bloquée (#255) : aucun chevalet vide, le gagnant est celui dont
    les tuiles restantes valent le moins de points — même barème que pour un
    chevalet vidé, appliqué au joueur le moins pénalisé."""
    joueurs = _joueurs([t(1, "noir")], [t(13, "rouge"), t(13, "bleu")])
    calculer_scores_manche(joueurs, valeur_joker=30)
    assert joueurs[0]["score_manche"] == 26    # gagne : +pénalité de l'autre
    assert joueurs[1]["score_manche"] == -26   # perd : -sa propre pénalité
    assert trouver_gagnant_manche(joueurs) == 0


def test_gagnant_manche_bloquee_compte_le_joker_au_bareme():
    """Un joker en main compte à la valeur du réglage (``valeur_joker``),
    comme pour un chevalet vidé — inchangé par #255."""
    joueurs = _joueurs([joker()], [t(5, "rouge")])
    calculer_scores_manche(joueurs, valeur_joker=30)
    # Joueur 1 (5 pts) est le moins pénalisé : il gagne, crédité de la
    # pénalité de l'autre (30, le joker) ; joueur 0 perd sa propre pénalité.
    assert trouver_gagnant_manche(joueurs) == 1
    assert joueurs[0]["score_manche"] == -30
    assert joueurs[1]["score_manche"] == 30


def test_gagnant_manche_bloquee_egalite_prend_le_premier_dans_l_ordre():
    """Égalité stricte au plus bas total (#255, point douteux signalé au
    rapport) : aucune règle officielle connue pour ce cas précis — choix le
    plus simple retenu, cohérent avec le reste du moteur (trouver_gagnant_
    manche/trouver_gagnant_match) : le premier joueur dans l'ordre gagne."""
    joueurs = _joueurs([t(5, "rouge")], [t(5, "bleu")], [t(13, "noir")])
    calculer_scores_manche(joueurs, valeur_joker=30)
    assert trouver_gagnant_manche(joueurs) == 0
    assert joueurs[0]["score_manche"] == 5 + 13     # pénalités des 2 autres
    assert joueurs[1]["score_manche"] == -5
    assert joueurs[2]["score_manche"] == -13


def test_manche_bloquee_a_trois_joueurs_score_cumul_coherent():
    """``score_cumul`` s'accumule normalement pour une manche bloquée à 3
    joueurs (pas seulement 2), sans traitement spécial."""
    joueurs = _joueurs([t(2, "noir")], [t(1, "noir")], [t(13, "rouge")])
    for jr in joueurs:
        jr["score_cumul"] = 100   # score cumulé déjà existant (manche > 1)
    calculer_scores_manche(joueurs, valeur_joker=30)
    assert trouver_gagnant_manche(joueurs) == 1   # 1 pt : le moins pénalisé
    assert joueurs[1]["score_cumul"] == 100 + (2 + 13)
    assert joueurs[0]["score_cumul"] == 100 - 2
    assert joueurs[2]["score_cumul"] == 100 - 13
