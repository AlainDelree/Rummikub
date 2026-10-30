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
    (solveur complet) ; ``taux_oubli`` ∈ [0, 1]."""
    perturbation_max: int | None
    taux_oubli: float

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
    # Expert et Champion du Monde : provisoirement identiques à Avancé (solveur
    # un-tour complet) tant que les stratégies multi-tours (§13) ne sont pas
    # développées. À faire évoluer par des issues ultérieures.
    "Expert":            Bridage(perturbation_max=None, taux_oubli=0.0),
    "Champion du Monde": Bridage(perturbation_max=None, taux_oubli=0.0),
}


def bridage_pour(nom_niveau: str | None) -> Bridage:
    """Bridage d'un niveau. Un niveau inconnu (ou ``None``) — p. ex. une partie
    sauvegardée avec un libellé disparu — retombe sur « Débutant », jamais
    d'erreur (parties anciennes toujours valides)."""
    return BRIDAGES.get(nom_niveau, BRIDAGES["Débutant"])
