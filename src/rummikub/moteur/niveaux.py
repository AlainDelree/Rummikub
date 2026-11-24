"""Échelle des cinq niveaux d'IA et paramètres d'affaiblissement (issue #213).

**Un seul moteur exact pour tous les niveaux.** Depuis #213, les cinq niveaux
d'IA sont bâtis sur le même modèle exact d'un tour (``moteur/solveur_exact.py``,
le joueur d'Expert depuis #206). Leur force n'est plus réglée par des
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

**Garde-fous d'incohérence** (voir docs/contexte/pistes_amelioration_ia.md §13) :

* un coup qui **vide le chevalet gagne la partie** : il n'est JAMAIS oublié ni
  dégradé (aucun critère « pour plus tard » ne s'applique à un coup gagnant) ;
* le taux d'oubli **décroît quand la main est petite** (``taux_oubli_effectif``)
  pour qu'un joueur ne « pioche » pas bêtement en toute fin de partie, quand il
  est sur le point de sortir.

**Structure de l'échelle** (issue #213 §2) :

* **Débutant, Facile, Intermédiaire** : le solveur un-tour AFFAIBLI (de plus en
  plus bridé vers le bas) ;
* **Avancé, Expert** : le solveur un-tour COMPLET, tel quel — STRICTEMENT
  IDENTIQUES. Expert avait porté une vérification de finition en fin de
  partie (#221) puis un sixième niveau, « Champion du Monde », d'autres
  stratégies multi-tours ; tout ce code a été retiré (#235, #236, voir
  CONTEXTE.md — archive : aucun effet mesurable sur le taux de victoire,
  code récupérable au tag git ``archive-strategies-champion``).

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
    (solveur complet) ; ``taux_oubli`` ∈ [0, 1].

    ``eviter_don_joker`` (issue #252, RÉÉCRIT par #253 — nom du champ
    conservé pour éviter de propager un renommage dans tout le code et les
    campagnes existantes) : si vrai, le niveau applique l'ensemble des
    règles de gestion du joker de l'issue #253 (voir ``moteur/ia.py``,
    ``jouer_niveau_bride`` — arbre de décision complet et définitions dans
    ``docs/contexte/ia_anti_don_joker.md``) : un joker de la main n'est joué
    que s'il est UTILE, aucun joker n'est laissé LIBRE sur le plateau quand
    un autre coup l'évite (pioche sinon, sans compteur ni limite — la
    pioche bornée de #252 est SUPPRIMÉE par #253), un joker repris du
    plateau que l'IA ne peut pas utiliser avec sa main est camouflé en
    position non libre quand c'est possible, et un échange facultatif
    « en réserve » peut être différé quelques tours. ``False`` (Débutant,
    Facile) laisse le comportement d'avant #252/#253."""
    perturbation_max: int | None
    taux_oubli: float
    eviter_don_joker: bool = False

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
    (jamais d'oubli incohérent en fin de partie — voir
    docs/contexte/pistes_amelioration_ia.md §13). Un
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
# imparti de #217, est laissé à relancer par Alain (voir
# docs/contexte/niveaux_ia_calibrage.md §16,
# ``scripts/calibrer_echelle.py`` depuis #240, qui remplace l'ancien
# ``scripts/valider_bas_echelle.py``). Le réglage s'appuie donc sur la
# garantie structurelle ci-dessus plutôt que sur une mesure non significative.
# ``eviter_don_joker`` (issue #252) : activé pour Intermédiaire, Avancé et
# Expert — un joueur de ce niveau ne doit plus offrir gratuitement un joker
# à l'adversaire (voir docs/contexte/ia_anti_don_joker.md). Débutant et
# Facile restent à ``False`` (comportement d'avant #252, inchangé) : un
# joueur de ce niveau peut encore offrir un joker, considéré comme une
# erreur plausible pour ce niveau de jeu.
BRIDAGES: dict[str, Bridage] = {
    "Débutant":          Bridage(perturbation_max=0,    taux_oubli=0.42),
    "Facile":            Bridage(perturbation_max=1,    taux_oubli=0.30),
    "Intermédiaire":     Bridage(perturbation_max=4,    taux_oubli=0.08,
                                 eviter_don_joker=True),
    "Avancé":            Bridage(perturbation_max=None, taux_oubli=0.0,
                                 eviter_don_joker=True),
    # Expert : solveur un-tour complet, STRICTEMENT IDENTIQUE à Avancé.
    # Avait porté une vérification de finition en fin de partie (#221), puis
    # un sixième niveau, « Champion du Monde », d'autres stratégies
    # multi-tours (#225/#229/#230/#231/#232) ; tout ce code a été retiré
    # (#235, #236 — aucun des deux n'a jamais changé un coup mesurablement,
    # voir CONTEXTE.md). Expert n'est pas modifié par ces retraits.
    "Expert":            Bridage(perturbation_max=None, taux_oubli=0.0,
                                 eviter_don_joker=True),
}

# Échange différé (issue #253, point 6, REMPLACE la pioche bornée de #252 —
# supprimée : plus de compteur ni de limite de tours pour la règle du joker
# LIBRE elle-même, voir ``moteur/ia._appliquer_joker_libre``). Un échange
# FACULTATIF (l'IA détient la tuile exacte de remplacement, ``_jokers_
# recuperables``) dont le joker récupéré est « en réserve » (``_joker_en_
# reserve`` : l'autre exemplaire de la tuile est visible sur le plateau, et
# aucune recombinaison du plateau seul ne le libère) et que l'IA ne peut pas
# utiliser avec le reste de sa main peut être DIFFÉRÉ au plus ce nombre de
# tours CONSÉCUTIFS (propre à CE joker, pas un compteur global) :
LIMITE_ECHANGE_DIFFERE = 3
# ... ou ce nombre, réduit, si au moins un AUTRE joueur a STRICTEMENT moins
# de ``SEUIL_TUILES_ADVERSAIRE_FAIBLE`` tuiles en main (nombre de tuiles,
# visible de tous — jamais le contenu d'une main) :
LIMITE_ECHANGE_DIFFERE_ADVERSAIRE_FAIBLE = 2
SEUIL_TUILES_ADVERSAIRE_FAIBLE = 5

# Clé du compteur d'attente de l'échange différé, persisté sur
# ``etat["joueurs"][idx]`` (issue #253) — ``dict`` ``{id_joker: n}`` (un
# compteur PROPRE À CHAQUE JOKER, pas un compteur unique du joueur). Un
# joker est retiré de ce dict dès que son échange est effectivement fait
# (différé épuisé ou déclenchement immédiat) ou dès que sa réserve cesse
# (voir ``moteur/ia._appliquer_echange_differe``).
CLE_ATTENTE_ECHANGE_DIFFERE = "tours_attente_echange_differe"

# Débarras du joker inutile en fin de MATCH multi-manches (#254, point 7).
# Un joker de main jugé NON utile (``moteur/ia._appliquer_joker_utile``) est
# normalement gardé en main (voir docs/contexte/ia_anti_don_joker.md §4) —
# SAUF en fin de match à plusieurs
# manches (``etat["config"]["nb_manches"] > 1``), où le conserver jusqu'à la
# fin de la DERNIÈRE manche perdue coûterait sa pénalité
# (``valeur_joker_penalite``, défaut 30, voir ``moteur/score.
# calculer_scores_manche``) dans le score CUMULÉ du match — alors qu'à une
# seule manche, perdre avec ou sans joker en main ne change rien (aucun
# score cumulé au-delà de cette manche). Activé seulement si TOUTES les
# conditions suivantes tiennent (nombres visibles de tous, jamais le
# contenu d'une main) :
#   * ``nb_manches > 1`` (match à plusieurs manches) ;
#   * au moins un AUTRE joueur a AU PLUS ``SEUIL_TUILES_ADVERSAIRE_FIN_MATCH``
#     tuiles en main (fin de manche proche) ;
#   * la pioche contient STRICTEMENT MOINS de ``SEUIL_PIOCHE_FIN_MATCH``
#     tuiles (fin de manche proche par épuisement de la pioche).
# Le joker n'est alors posé que SI une pose existe déjà (même sans gain de
# tuile réelle) pour lui dans le coup de base — jamais forcé par une
# recherche supplémentaire. ``DEBARRAS_JOKER_FIN_MATCH_ACTIF=False`` (lu à
# l'appel, comme ``ia.UTILISER_SOLVEUR_EXACT``) désactive entièrement cette
# règle en simulation, sans toucher aux deux seuils.
DEBARRAS_JOKER_FIN_MATCH_ACTIF = True
SEUIL_TUILES_ADVERSAIRE_FIN_MATCH = 2
SEUIL_PIOCHE_FIN_MATCH = 30


# Compatibilité (issue #235) : « Champion du Monde », niveau retiré (aucun
# effet mesurable de ses stratégies multi-tours sur le taux de victoire face
# à Expert — voir CONTEXTE.md, code récupérable au tag git
# ``archive-strategies-champion``). Un réglage, une partie sauvegardée ou un
# journal antérieur qui nomme encore ce niveau ne doit jamais planter : il
# est remplacé par « Expert », le niveau le plus proche restant — jamais par
# le repli générique « Débutant » (ci-dessous) réservé aux noms vraiment
# inconnus.
NIVEAU_RETIRE = "Champion du Monde"
NIVEAU_RETIRE_REMPLACEMENT = "Expert"


def niveau_compatible(nom_niveau: str | None) -> str | None:
    """Remplace :data:`NIVEAU_RETIRE` par :data:`NIVEAU_RETIRE_REMPLACEMENT` ;
    retourne ``nom_niveau`` inchangé sinon (y compris ``None`` ou un nom
    inconnu pour une autre raison, laissés à ``bridage_pour``/``ia.jouer_ia``)."""
    if nom_niveau == NIVEAU_RETIRE:
        return NIVEAU_RETIRE_REMPLACEMENT
    return nom_niveau


def bridage_pour(nom_niveau: str | None) -> Bridage:
    """Bridage d'un niveau. Un niveau inconnu (ou ``None``) — p. ex. une partie
    sauvegardée avec un libellé disparu — retombe sur « Débutant », jamais
    d'erreur (parties anciennes toujours valides). ``NIVEAU_RETIRE``
    (« Champion du Monde ») est d'abord traduit par ``niveau_compatible``."""
    nom_niveau = niveau_compatible(nom_niveau)
    return BRIDAGES.get(nom_niveau, BRIDAGES["Débutant"])
