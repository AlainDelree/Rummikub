"""Vérification de finition en fin de partie — étape 1 de la brique « Deux
tours » (issue #221, suite de #219 « Inconnues »).

Le solveur exact d'Expert (#206) pose toujours le maximum de tuiles à chaque
tour, sans jamais se demander si ce coup aide ou gêne le tour SUIVANT. Alain a
identifié une situation où cela coûte la partie : en fin de partie, prendre un
joker tout de suite pour poser une tuile de plus peut empêcher de finir d'un
coup au tour suivant, alors que jouer un autre coup — qui laisse le joker en
place — le permettrait.

Ce module ajoute une vérification BORNÉE à la fin de partie (chevalet d'au
plus :data:`moteur.niveaux.SEUIL_FIN_PARTIE_VERIF_FINITION` tuiles) : parmi
quelques coups candidats, choisit celui qui permet de vider le chevalet au
tour SUIVANT, si un tel coup existe et que le meilleur coup du solveur n'y
parvient pas.

**Hypothèse optimiste, assumée (limite connue — voir CONTEXTE.md §13)** :
la vérification suppose que l'ADVERSAIRE NE TOUCHE PAS au tapis entre les
deux tours. C'est faux en général (l'adversaire joue aussi), mais c'est la
seule hypothèse qu'on puisse vérifier à coût raisonnable sans implémenter les
briques « Indices »/« Main restante » prévues plus tard dans la feuille de
route (§13). Elle ne peut jamais DÉGRADER le jeu : la règle qui prime sur tout
(``verifier`` ci-dessous, et le garde-fou de ``ia.jouer_niveau_bride``) est
qu'un coup qui vide déjà le chevalet CE tour-ci n'est jamais remis en cause.

**Remarque de conception, retenue après expérimentation (#221)** : dans ce
moteur, un tour peut librement recomposer la TOTALITÉ du plateau (seule
contrainte : ne perdre aucune tuile déjà posée, voir CONTEXTE.md §4). Il en
découle une propriété mathématique vérifiée empiriquement pendant cette
issue : si le meilleur coup EXACT (prouvé optimal) ne vide pas le chevalet,
AUCUN coup candidat ne peut jamais permettre de le vider au tour suivant (sous
l'hypothèse ci-dessus) — parce que tout enchaînement de deux coups valides
équivaut à un seul coup valide direct, que le solveur aurait alors déjà trouvé
en cherchant le maximum. La vérification ne peut donc apporter un changement
réel que lorsque le coup marqué comme venant du modèle exact n'est PAS prouvé
optimal (budget de temps serré) — un cas rare mais réel, qui justifie de
garder le mécanisme : il ne coûte rien (repli silencieux) le reste du temps.
"""

from __future__ import annotations

import time

from rummikub.moteur.solveur_exact import (
    resoudre_exact, SolveurExactIndisponible, BudgetExactDepasse,
)

# Statuts journalisés (issue #221, point 5 ; affinés par #223, point 4, pour
# que les campagnes de mesure puissent expliquer POURQUOI la vérification ne
# change rien, au lieu de tout regrouper sous deux statuts fourre-tout) —
# dans le même esprit que l'indication du solveur utilisé ajoutée par #211.
#
# Repli / non-exécution (aucun verdict de finition rendu) :
#   NON_APPLICABLE        chevalet trop grand (> SEUIL_FIN_PARTIE_VERIF_FINITION).
#   PAS_DE_COUP_A_COMPARER aucun coup « jouer » à comparer (pioche ou passe),
#                          ou liste de candidats vide.
#   SOLVEUR_NON_EXACT      le coup du tour n'a pas été décidé par le modèle
#                          exact (dépendances highspy/numpy absentes, ou repli
#                          déjà survenu pour ce tour faute de budget) — la
#                          vérification, qui s'appuie sur CE MÊME solveur, ne
#                          peut de toute façon pas s'exécuter non plus.
#   BUDGET_EPUISE          le budget de temps partagé a été réellement
#                          épuisé PENDANT la vérification elle-même.
#
# Vérification exécutée jusqu'au bout (verdict rendu) :
#   APPLIQUEE_MEILLEUR_SUFFIT  le meilleur coup du solveur (candidats[0])
#                              permet déjà de finir au tour suivant.
#   APPLIQUEE_AUCUN_CANDIDAT   aucun candidat ne permet de finir au tour
#                              suivant : candidats[0] est joué comme avant.
#   APPLIQUEE_AUTRE_COUP       un autre candidat permet de finir là où
#                              candidats[0] ne le permet pas : il est préféré.
#   APPLIQUEE_GARDE_JOKER      le candidat « garder un joker en main » (#225,
#                              Champion du Monde seul) a été choisi — cas
#                              particulier d'``APPLIQUEE_AUTRE_COUP``, distingué
#                              pour les compteurs de campagne (issue #225,
#                              point 3).
NON_APPLICABLE = "non_applicable"
PAS_DE_COUP_A_COMPARER = "pas_de_coup_a_comparer"
SOLVEUR_NON_EXACT = "solveur_non_exact"
BUDGET_EPUISE = "budget_epuise"
APPLIQUEE_MEILLEUR_SUFFIT = "appliquee_meilleur_suffit"
APPLIQUEE_AUCUN_CANDIDAT = "appliquee_aucun_candidat"
APPLIQUEE_AUTRE_COUP = "appliquee_autre_coup"
APPLIQUEE_GARDE_JOKER = "appliquee_garde_joker"

# Libellés français, dans l'ordre d'affichage attendu des rapports de
# campagne (#223, point 4 ; #225 pour le dernier).
LIBELLES = {
    NON_APPLICABLE: "non applicable (chevalet trop grand)",
    PAS_DE_COUP_A_COMPARER: "pas de coup à comparer (pioche ou passe)",
    SOLVEUR_NON_EXACT: "solveur non exact ou dépendances absentes",
    BUDGET_EPUISE: "budget réellement épuisé",
    APPLIQUEE_MEILLEUR_SUFFIT: "appliquée : le meilleur coup suffit déjà",
    APPLIQUEE_AUCUN_CANDIDAT: "appliquée : aucun candidat ne permet de finir",
    APPLIQUEE_AUTRE_COUP: "appliquée : un autre coup a été choisi",
    APPLIQUEE_GARDE_JOKER: "appliquée : un coup qui garde le joker a été choisi",
}


def _id_tuile(t):
    return t["id"] if isinstance(t, dict) else t.id


def ids_coup(coup) -> set:
    """Identifiants des tuiles de la main posées par ``coup``."""
    return set(coup.get("ids_tuiles") or [])


def coups_differents(coup_a, coup_b) -> bool:
    """Vrai si les deux coups posent un ensemble de tuiles différent (même
    main résultante). Deux coups qui posent exactement les mêmes tuiles sont
    traités comme un seul et même candidat, même si leur plateau résultant
    diffère dans le détail."""
    if coup_a is None or coup_b is None:
        return coup_a is not coup_b
    return ids_coup(coup_a) != ids_coup(coup_b)


def _etat_apres_coup(etat: dict, idx: int, coup: dict) -> dict:
    """État minimal après avoir joué ``coup`` : chevalet du joueur réduit des
    tuiles posées, plateau remplacé par celui du coup, mise initiale forcée à
    faite (jouer un coup valide l'implique forcément). Ne reconstruit QUE ce
    dont le solveur a besoin (``joueurs[idx]``, ``plateau``, ``config``) —
    plus léger qu'une copie complète de l'état (historique, pioche...),
    inutile ici."""
    joueur = etat["joueurs"][idx]
    ids_joues = ids_coup(coup)
    chevalet_restant = [t for t in joueur["chevalet"]
                        if _id_tuile(t) not in ids_joues]
    joueur2 = dict(joueur)
    joueur2["chevalet"] = chevalet_restant
    joueur2["mise_initiale_faite"] = True
    joueurs2 = list(etat["joueurs"])
    joueurs2[idx] = joueur2
    return {
        "joueurs": joueurs2,
        "plateau": coup["nouveau_plateau"],
        "config": etat.get("config", {}),
    }


def _peut_finir_au_tour_suivant(etat, idx, coup, budget_temps):
    """Le même solveur (modèle exact) pourrait-il vider le chevalet restant,
    une fois ``coup`` joué, en supposant le tapis inchangé par l'adversaire ?

    Retourne ``True``/``False`` si déterminé, ou ``None`` si la question n'a
    pas pu être tranchée (budget épuisé, dépendances absentes, erreur) —
    l'appelant doit alors se replier sans toucher au coup d'origine.

    ``preferer_simple=False`` et pas d'``eval_config`` : seule la valeur de
    la PASSE 1 (nombre de tuiles posables) importe ici, jamais les critères
    de départage — les sauter accélère le calcul sans changer la réponse
    (la passe 1 reste strictement la même qu'avec ces options activées)."""
    if budget_temps is None or budget_temps <= 0:
        return None
    etat2 = _etat_apres_coup(etat, idx, coup)
    chevalet_restant = etat2["joueurs"][idx]["chevalet"]
    if not chevalet_restant:
        return True
    try:
        res = resoudre_exact(etat2, idx, budget_temps=budget_temps,
                             preferer_simple=False, eval_config=None)
    except (SolveurExactIndisponible, BudgetExactDepasse):
        return None
    except Exception:  # pragma: no cover - filet, ne doit jamais bloquer le jeu
        return None
    if not res.valide_globalement:
        return None
    return res.nb_tuiles == len(chevalet_restant)


def peut_poser_au_tour_suivant(etat, idx, coup, budget_temps):
    """Le même solveur (modèle exact) pourrait-il poser AU MOINS UNE tuile
    du chevalet restant, une fois ``coup`` joué, en supposant le tapis
    inchangé par l'adversaire (même hypothèse que
    ``_peut_finir_au_tour_suivant`` ci-dessus) ? Condition (c) de la
    stratégie ``reserve_tuile`` (#229) — moins stricte que « finir », qui
    exige de vider tout le chevalet.

    Retourne ``True``/``False`` si déterminé, ou ``None`` si la question n'a
    pas pu être tranchée (budget épuisé, dépendances absentes, erreur) —
    même convention que ``_peut_finir_au_tour_suivant``."""
    if budget_temps is None or budget_temps <= 0:
        return None
    etat2 = _etat_apres_coup(etat, idx, coup)
    chevalet_restant = etat2["joueurs"][idx]["chevalet"]
    if not chevalet_restant:
        return True
    try:
        res = resoudre_exact(etat2, idx, budget_temps=budget_temps,
                             preferer_simple=False, eval_config=None)
    except (SolveurExactIndisponible, BudgetExactDepasse):
        return None
    except Exception:  # pragma: no cover - filet, ne doit jamais bloquer le jeu
        return None
    if not res.valide_globalement:
        return None
    return res.nb_tuiles >= 1


def verifier(etat: dict, idx: int, candidats: list, deadline: float,
            idx_garde_joker: int | None = None):
    """Point d'entrée : décide, parmi ``candidats`` (coups ``{"action":
    "jouer", ...}``, ``candidats[0]`` étant TOUJOURS le meilleur coup du
    solveur), lequel jouer.

    Règle (issue #221, point 4 — ``candidats[0]`` qui vide déjà le chevalet
    n'est jamais passé ici, voir ``ia._verifier_finition_fin_de_partie``) :
    le premier candidat qui permet de finir au tour suivant est joué ;
    ``candidats[0]`` est vérifié EN PREMIER, donc toujours préféré en cas
    d'égalité (conforme au point 4). Si aucun ne permet de finir, ``candidats
    [0]`` est joué comme avant la vérification.

    ``idx_garde_joker`` (issue #225, point 2, ``None`` par défaut →
    comportement strictement inchangé) : index, dans ``candidats``, du
    candidat « garder un joker en main » (Champion du Monde seul), s'il
    existe — lorsque ce candidat précis est celui retenu, le statut rendu est
    ``APPLIQUEE_GARDE_JOKER`` plutôt que le générique ``APPLIQUEE_AUTRE_COUP``,
    pour les compteurs de campagne.

    ``deadline`` (``time.monotonic()``) est la limite de temps PARTAGÉE avec
    le calcul du coup normal (point 5 de l'issue) — chaque appel au solveur
    ci-dessous consomme le temps restant jusqu'à cette même échéance, sans
    budget supplémentaire propre.

    Retourne ``(coup_choisi, statut)`` — ``statut`` l'un des huit codes
    listés en tête de module, jamais ``None`` dans ce cas (l'appelant a déjà
    filtré les cas "non applicable"/"solveur non exact" avant d'appeler
    cette fonction). ``APPLIQUEE_MEILLEUR_SUFFIT`` (``candidats[0]`` finit
    déjà) et ``APPLIQUEE_AUCUN_CANDIDAT`` (aucun candidat ne finit) sont
    distingués depuis #223 : les deux aboutissaient au même code
    (``appliquee_sans_changement``), masquant deux situations très
    différentes dans les rapports de campagne."""
    if not candidats:
        return None, PAS_DE_COUP_A_COMPARER
    for i, coup in enumerate(candidats):
        restant = deadline - time.monotonic()
        verdict = _peut_finir_au_tour_suivant(etat, idx, coup, restant)
        if verdict is None:
            return candidats[0], BUDGET_EPUISE
        if verdict:
            if i == 0:
                return candidats[0], APPLIQUEE_MEILLEUR_SUFFIT
            if i == idx_garde_joker:
                return coup, APPLIQUEE_GARDE_JOKER
            return coup, APPLIQUEE_AUTRE_COUP
    return candidats[0], APPLIQUEE_AUCUN_CANDIDAT
