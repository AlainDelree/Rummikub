"""Échelle des six niveaux d'IA et paramètres d'affaiblissement (issue #213).

**Un seul moteur exact pour tous les niveaux.** Depuis #213, les six niveaux
d'IA sont bâtis sur le même modèle exact d'un tour (``moteur/solveur_exact.py``,
le joueur d'Expert depuis #206). Leur force n'est plus réglée par six
algorithmes différents mais par **deux paramètres réunis ICI**, appliqués au
même moteur (voir ``moteur/ia.jouer_niveau_bride``) :

* ``perturbation_max`` — nombre maximal de tuiles **du plateau** que le coup
  peut DÉPLACER. Ajouter des tuiles de la main à une combinaison existante, ou
  créer de nouvelles combinaisons depuis la main, **ne compte pas** comme un
  déplacement (mesure #199, ``solveur.mesurer_perturbation``). Ce paramètre
  exprime ce qu'un joueur « voit » : ``0`` = ne touche jamais à la structure du
  plateau (il pose depuis la main et prolonge les combinaisons existantes, sans
  jamais recomposer le plateau) ; ``None`` = aucune limite (le solveur complet,
  qui recompose librement tout le plateau).
* ``taux_oubli`` — probabilité, à chaque tour, que le joueur ne « voie » pas le
  meilleur coup et **pioche** à la place (il se contente d'un tour « raté »).
  Le tirage est reproductible quand ``config.graine_ia`` est fixée (simulations).

**Garde-fous d'incohérence** (voir CONTEXTE.md §13) :

* un coup qui **vide le chevalet gagne la partie** : il n'est JAMAIS oublié ni
  dégradé (aucun critère « pour plus tard » ne s'applique à un coup gagnant) ;
* le taux d'oubli **décroît quand la main est petite** (``taux_oubli_effectif``)
  pour qu'un joueur ne « pioche » pas bêtement en toute fin de partie, quand il
  est sur le point de sortir.

**Structure cible de l'échelle** (issue #213 §2) :

* **Débutant, Facile, Intermédiaire** : le solveur un-tour AFFAIBLI (de plus en
  plus bridé vers le bas) ;
* **Avancé** : le solveur un-tour COMPLET, tel quel ;
* **Expert, Champion du Monde** : le solveur un-tour complet PLUS des stratégies
  multi-tours (réserve d'un coup, non-don de joker, rétention défensive — pistes
  de CONTEXTE.md §13). Ces stratégies ne sont **pas** implémentées par #213 :
  Expert et Champion du Monde sont donc **provisoirement identiques à Avancé**
  (solveur un-tour complet), jusqu'à ce que des issues ultérieures développent
  les stratégies multi-tours. Signalé clairement ici et dans CONTEXTE.md.

Les valeurs ci-dessous sont les valeurs de départ INDICATIVES de l'issue, à
resserrer par les mesures (``scripts/echelle_niveaux.py``,
``scripts/profil_joueur.py``).
"""

from __future__ import annotations

from dataclasses import dataclass

from rummikub.config import NIVEAUX


# Ordre de l'échelle (du plus faible au plus fort) : la seule source de vérité
# est ``config.NIVEAUX``, repris tel quel pour rester cohérent partout.
ECHELLE = list(NIVEAUX)


@dataclass(frozen=True)
class Bridage:
    """Réglage de force d'un niveau. ``perturbation_max=None`` → illimité
    (solveur complet) ; ``taux_oubli`` ∈ [0, 1] ; ``verif_finition`` (issue
    #221, étape 1 de la brique « Deux tours ») active la vérification de
    finition en fin de partie pour ce niveau — ``False`` par défaut, pour que
    Débutant à Avancé restent strictement inchangés. ``garder_joker_fin_partie``
    (issue #225, deuxième stratégie multi-tours de la brique « Deux tours »,
    SEULEMENT pour Champion du Monde) : en fin de partie, si le chevalet
    contient un joker et qu'aucun adversaire n'est trop proche de finir (voir
    ``SEUIL_PRUDENCE_ADVERSAIRE_GARDE_JOKER`` ci-dessous), ajoute comme
    candidat de la vérification de finition le meilleur coup qui NE JOUE PAS
    le joker du chevalet — ``False`` par défaut, y compris pour Expert, qui
    reste le niveau de référence inchangé. ``reserve_tuile`` (issue #229,
    hypothèse H2, Champion du Monde SEUL) : après le coup du solveur,
    essaie de jouer un coup qui GARDE une tuile que ce même coup aurait
    posée, pour disposer d'un coup au tour suivant plutôt que de piocher —
    ``False`` par défaut. ``retenue_debut`` (issue #229, hypothèse H1,
    Champion du Monde SEUL) : pendant les premiers tours qui suivent SA
    PROPRE ouverture, plafonne le nombre de tuiles posées par tour —
    ``False`` par défaut."""
    perturbation_max: int | None
    taux_oubli: float
    verif_finition: bool = False
    garder_joker_fin_partie: bool = False
    reserve_tuile: bool = False
    retenue_debut: bool = False

    @property
    def complet(self) -> bool:
        """Vrai si le niveau joue le solveur un-tour complet, sans bridage."""
        return self.perturbation_max is None and self.taux_oubli <= 0.0


# Seuil de taille de main au-delà duquel le taux d'oubli s'applique en plein ;
# en dessous, il décroît linéairement jusqu'à 0 à une seule tuile en main, pour
# qu'un joueur n'« oublie » pas (= ne pioche pas) alors qu'il est près de sortir.
SEUIL_OUBLI = 7


def taux_oubli_effectif(taux: float, taille_main: int) -> float:
    """Taux d'oubli réel pour une main de ``taille_main`` tuiles.

    Égal à ``taux`` tant que la main compte au moins :data:`SEUIL_OUBLI`
    tuiles ; décroît linéairement en dessous et vaut 0 à une seule tuile
    (jamais d'oubli incohérent en fin de partie — voir CONTEXTE.md §13). Un
    coup qui vide la main est de toute façon traité à part (jamais oublié)."""
    if taux <= 0.0:
        return 0.0
    if taille_main >= SEUIL_OUBLI:
        return taux
    if taille_main <= 1:
        return 0.0
    return taux * (taille_main - 1) / (SEUIL_OUBLI - 1)


# ---- Table des bridages par niveau (le SEUL endroit à régler) -------------- #
# Valeurs RECALIBRÉES par #216 (suite #213) pour une échelle à écarts RÉGULIERS,
# mesurées sur le BON critère de force : les « tuiles restantes en main quand le
# niveau PERD » (plus bas = plus fort), par ``scripts/calibrer_niveaux.py`` en
# miroir. Objectif : Alain (≈ 3,5 tuiles, profil provisoire) situé ENTRE
# Intermédiaire et Avancé. Mesure retenue (miroir, graine 0) :
#   Débutant 0/0.42 ≈ 8 ; Intermédiaire 4/0.08 ≈ 4,5 ;
#   Avancé ∞/0 ≈ 2,7 (NON modifié, solveur complet).
# Cible Débutant ≈ 9 NON atteignable : avec perturbation=0 la mesure sature
# vers 7–8 quel que soit le taux d'oubli (celui-ci ne pèse quasiment plus sur
# les tuiles restantes, seulement sur le taux de victoire) ; on retient le
# réglage le PLUS FAIBLE utile (oubli 0.42) et on le signale (issue #216 §2).
#
# FACILE REMONTÉ par #217 (suite #216) : perturbation 0 → 1, oubli 0.15 → 0.30.
# À #216, Facile (0/0.15) était quasi indistinct de Débutant (Débutant lui
# gardait même marginalement MOINS de tuiles → ordre inversé) et perdait contre
# Intermédiaire à 85 % (trop écrasant). À perturbation=0 le taux d'oubli ne pèse
# presque plus sur l'issue : le seul levier qui sépare réellement les niveaux du
# bas est la PERTURBATION (#216). On donne donc à Facile une perturbation de 1
# (petits coups de récupération : déplacer au plus 1 tuile du plateau, ce que
# l'oubli seul ne permettait pas) et on règle son oubli à 0.30. Ce couple place
# Facile STRICTEMENT entre Débutant et Intermédiaire sur LES DEUX leviers :
#   * oubli 0.30 < Débutant 0.42 ET perturbation 1 > Débutant 0 → Facile est
#     plus fort que Débutant par construction (l'inversion d'ordre ne peut plus
#     se produire, garantie structurelle et non seulement statistique) ;
#   * oubli 0.30 > Intermédiaire 0.08 ET perturbation 1 < Intermédiaire 4 →
#     Facile reste clairement plus faible qu'Intermédiaire (pas de dépassement).
# Cible tuiles restantes ~6,0–6,3 (entre Débutant ≈ 7 et Intermédiaire ≈ 5,4) :
# le smoke pert1/oubli0.15 donnait ≈ 4,0 (TROP fort, sous Intermédiaire), d'où
# l'oubli relevé à 0.30 pour rapprocher Facile de la cible. La mesure fine
# n'est PAS fiable au calibrage : en MIROIR, deux joueurs pert=1 égaux recyclent
# le plateau et quasiment TOUTES les donnes atteignent le garde-fou de tours
# (comme la précaution déjà notée pour Intermédiaire pert=4, #216) ; le tournoi
# de validation au budget de production, trop coûteux pour aboutir dans le temps
# imparti de #217, est laissé à relancer par Alain (voir CONTEXTE.md §16,
# ``scripts/valider_bas_echelle.py``). Le réglage s'appuie donc sur la garantie
# structurelle ci-dessus plutôt que sur une mesure non significative.
BRIDAGES: dict[str, Bridage] = {
    "Débutant":          Bridage(perturbation_max=0,    taux_oubli=0.42),
    "Facile":            Bridage(perturbation_max=1,    taux_oubli=0.30),
    "Intermédiaire":     Bridage(perturbation_max=4,    taux_oubli=0.08),
    "Avancé":            Bridage(perturbation_max=None, taux_oubli=0.0),
    # Expert et Champion du Monde : solveur un-tour complet PLUS, depuis
    # #221 (étape 1 de la brique « Deux tours »), la vérification de
    # finition en fin de partie (voir moteur/verification_finition.py et
    # SEUIL_FIN_PARTIE_VERIF_FINITION ci-dessous).
    #
    # Champion du Monde SEUL reçoit en plus, depuis #225, « garder un joker
    # en main » (deuxième stratégie multi-tours de la brique « Deux tours »,
    # §13) : Expert reste le niveau de RÉFÉRENCE, strictement inchangé — le
    # duel Expert contre Champion du Monde mesure l'effet de cette seule
    # stratégie. D'autres stratégies multi-tours de #213/§13 restent À FAIRE.
    "Expert":            Bridage(perturbation_max=None, taux_oubli=0.0,
                                  verif_finition=True),
    "Champion du Monde": Bridage(perturbation_max=None, taux_oubli=0.0,
                                  verif_finition=True,
                                  garder_joker_fin_partie=True),
}


# Taille maximale du chevalet (nombre de tuiles, AVANT de jouer) au-delà de
# laquelle la vérification de finition (#221) ne s'applique pas — hors de
# cette borne, on est trop loin de la fin de partie pour que le coût d'un
# appel supplémentaire au solveur soit justifié par la rareté du bénéfice.
# Valeur de départ INDICATIVE de l'issue (5), réglable ICI uniquement (même
# emplacement que les autres paramètres de force de ce fichier).
SEUIL_FIN_PARTIE_VERIF_FINITION = 5


# Seuil de prudence sur l'adversaire pour « garder un joker en main » (#225) :
# en dessous de ce nombre de tuiles dans la main d'un adversaire, Champion du
# Monde ne tente PAS de garder son joker (l'adversaire pourrait finir avant
# que le tour de garder le joker ne paie). Information PUBLIQUE (le nombre de
# tuiles restantes de chaque joueur est visible de tous, voir CONTEXTE.md §13)
# — jamais le contenu de sa main, jamais lu dans sa main. Valeur de départ
# INDICATIVE de l'issue (3), réglable ICI uniquement.
SEUIL_PRUDENCE_ADVERSAIRE_GARDE_JOKER = 3


# Paramètres de « réserve d'une tuile » (#229, hypothèse H2) : écart maximal
# ACCEPTÉ, en nombre de tuiles, entre le meilleur coup du solveur et le coup
# qui en garde une (condition (b) de l'issue) — au-delà, la perte immédiate
# de tuiles posées n'est plus jugée compensée par le coup gardé pour le tour
# suivant. Valeur de départ INDICATIVE de l'issue (1), réglable ICI
# uniquement (même emplacement que les autres paramètres de ce fichier).
ECART_MAX_RESERVE = 1

# Paramètres de « retenue au début » (#229, hypothèse H1) : nombre de tours
# du JOUEUR LUI-MÊME (pas le tour global de la partie), comptés à partir de
# SA PROPRE ouverture (mise initiale), pendant lesquels le plafond
# ``POSE_MAX_DEBUT`` s'applique ; désactivé au-delà de
# ``TUILES_TAPIS_MAX_RETENUE`` tuiles sur le tapis (le tapis est déjà assez
# fourni pour que la retenue n'ait plus de sens) ou en dessous de 9 tuiles en
# main (on se rapproche de la fin, la retenue devient contre-productive).
# Valeurs de départ INDICATIVES de l'issue, réglables ICI uniquement.
TOURS_RETENUE_DEBUT = 4
TUILES_TAPIS_MAX_RETENUE = 20
POSE_MAX_DEBUT = 2


def bridage_pour(nom_niveau: str | None) -> Bridage:
    """Bridage d'un niveau. Un niveau inconnu (ou ``None``) — p. ex. une partie
    sauvegardée avec un libellé disparu — retombe sur « Débutant », jamais
    d'erreur (parties anciennes toujours valides)."""
    return BRIDAGES.get(nom_niveau, BRIDAGES["Débutant"])


# --------------------------------------------------------------------------- #
# Registre unique des stratégies multi-tours (issue #228).
#
# Avant #228, chaque stratégie avait son propre drapeau de script
# (``--sans-verif-finition``, ``--sans-garde-joker``) et aucune liste ne les
# réunissait : ajouter des stratégies une à une aurait multiplié les
# drapeaux et les commandes à retenir. Ce registre est désormais LA seule
# source de vérité sur « quelles stratégies multi-tours existent » — y
# ajouter une entrée (plus son branchement dans ``_bridage_champion``
# ci-dessous si la stratégie a un effet sur le bridage) suffit pour qu'elle
# apparaisse dans les options de campagne et les rapports (voir
# ``scripts/comparer_niveaux_ia.py``, CONTEXTE.md §13).
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Strategie:
    """Une entrée du registre. ``niveaux`` : les niveaux auxquels la
    stratégie s'applique (p. ex. ``verif_finition`` s'applique à Expert ET
    Champion du Monde, ``garde_joker`` à Champion du Monde seul — Expert
    reste le témoin, jamais concerné). ``active_par_defaut`` : vrai si la
    stratégie est active par défaut, DANS LE JEU, pour les niveaux où elle
    s'applique (reflet de ce qui est câblé dans ``BRIDAGES`` — ne détermine
    PAS, à lui seul, ce que Champion du Monde utilise : voir
    :data:`STRATEGIES_CHAMPION_PAR_DEFAUT`, la liste qui fait foi pour le
    jeu). ``compteurs`` : noms des compteurs génériques que la stratégie
    déclare (voir ``scripts/comparer_niveaux_ia.py``, qui les affiche sans
    code spécifique par stratégie dans la boucle de rapport)."""
    id: str
    description: str
    niveaux: tuple[str, ...]
    active_par_defaut: bool
    compteurs: tuple[str, ...] = ("declenchee", "a_change_le_coup")


STRATEGIES: dict[str, Strategie] = {
    "verif_finition": Strategie(
        id="verif_finition",
        description=("Vérification de finition en fin de partie (#221) : "
                     "préfère, parmi quelques coups candidats, celui qui "
                     "permet de vider le chevalet au tour suivant."),
        niveaux=("Expert", "Champion du Monde"),
        active_par_defaut=True,
    ),
    "garde_joker": Strategie(
        id="garde_joker",
        description=("Garder un joker en main en fin de partie si aucun "
                     "adversaire n'est trop proche de finir (#225)."),
        niveaux=("Champion du Monde",),
        active_par_defaut=True,
    ),
    "reserve_tuile": Strategie(
        id="reserve_tuile",
        description=("Garder une tuile du chevalet que le meilleur coup "
                     "aurait posée, pour avoir un coup au tour suivant "
                     "plutôt que de piocher (#229, hypothèse H2)."),
        niveaux=("Champion du Monde",),
        active_par_defaut=False,
        compteurs=("declenchee", "a_change_le_coup", "nb_tuiles_gardees",
                  "pioche_evitee", "tuile_gardee_posee"),
    ),
    "retenue_debut": Strategie(
        id="retenue_debut",
        description=("Se retenir en début de partie : plafonner le nombre "
                     "de tuiles posées par tour pendant les premiers tours "
                     "qui suivent sa propre ouverture (#229, hypothèse H1)."),
        niveaux=("Champion du Monde",),
        active_par_defaut=False,
    ),
}


# Ce que Champion du Monde utilise AUJOURD'HUI dans le JEU (inchangé par
# #228) : reproduit à l'identique l'état actuel (``verif_finition`` +
# ``garde_joker``, voir ``BRIDAGES`` ci-dessus). Une stratégie du registre
# n'est ajoutée à cette liste qu'après validation par les tests/campagnes —
# être dans ``STRATEGIES`` ne suffit pas à être jouée dans le jeu (une
# stratégie peut exister dans le registre, à l'étude via les options de
# campagne, SANS être encore active en production).
STRATEGIES_CHAMPION_PAR_DEFAUT: tuple[str, ...] = ("verif_finition", "garde_joker")


def strategies_champion_valides() -> tuple[str, ...]:
    """Identifiants du registre applicables à Champion du Monde (ordre du
    registre) — utilisé pour valider les options de campagne et lister les
    noms valides en cas d'erreur."""
    return tuple(s.id for s in STRATEGIES.values() if "Champion du Monde" in s.niveaux)


def valider_noms_strategies(noms) -> None:
    """Lève ``ValueError`` (message listant les noms valides) si ``noms``
    contient un identifiant de stratégie inconnu pour Champion du Monde."""
    valides = set(strategies_champion_valides())
    inconnus = [n for n in noms if n not in valides]
    if inconnus:
        raise ValueError(
            f"stratégie(s) inconnue(s) : {', '.join(sorted(set(inconnus)))} — "
            f"noms valides : {', '.join(sorted(valides))}")


def bridage_champion_personnalise(strategies_actives) -> "Bridage":
    """Construit le ``Bridage`` de Champion du Monde pour un jeu de
    stratégies actives donné (ids du registre, p. ex. ``{"garde_joker"}``) —
    utilisé par les campagnes de mesure (``--strategies-champion``,
    ``scripts/matrice_strategies.py``) pour substituer, DURANT la campagne
    seulement, la liste de stratégies de Champion du Monde sans jamais
    toucher au jeu (``BRIDAGES`` n'est modifié que temporairement par
    l'appelant, voir ``comparer_niveaux_ia._strategies_champion_forcees``).
    La perturbation et le taux d'oubli restent ceux du solveur complet
    (Champion du Monde n'est jamais bridé sur ces deux paramètres)."""
    actives = frozenset(strategies_actives)
    valider_noms_strategies(actives)
    return Bridage(
        perturbation_max=None, taux_oubli=0.0,
        verif_finition="verif_finition" in actives,
        garder_joker_fin_partie="garde_joker" in actives,
        reserve_tuile="reserve_tuile" in actives,
        retenue_debut="retenue_debut" in actives,
    )


# Garde-fou de cohérence (vérifié à l'import) : ``STRATEGIES_CHAMPION_PAR_
# DEFAUT`` doit reproduire EXACTEMENT le ``Bridage`` câblé en dur pour
# Champion du Monde ci-dessus — sinon le registre mentirait sur ce que le
# jeu joue réellement. Si ce test échoue, c'est que l'un des deux a été
# modifié sans l'autre : ne JAMAIS faire taire cette assertion, corriger le
# registre ou ``BRIDAGES`` pour qu'ils concordent à nouveau.
assert bridage_champion_personnalise(STRATEGIES_CHAMPION_PAR_DEFAUT) == \
    BRIDAGES["Champion du Monde"], (
    "STRATEGIES_CHAMPION_PAR_DEFAUT ne reproduit plus BRIDAGES['Champion du "
    "Monde'] — voir moteur/niveaux.py (issue #228).")
