"""Tests du script de vérification de la simplicité des coups d'Expert
(``scripts/verifier_simplicite_expert.py``, issue #215, suite de #199).

On vérifie la LOGIQUE d'analyse du script sur un petit nombre de cas fabriqués,
sans dépendre d'une simulation complète :
  - la description française d'une combinaison (groupe, suite, suite avec joker) ;
  - un coup DÉJÀ minimal (extension directe d'un groupe) : écart nul, décomposition
    « nécessaire » ;
  - un coup artificiellement SUR-DÉCOMPOSÉ (une combinaison du plateau éclatée en
    deux) : l'écart de perturbation est bien détecté (« évitable ») ;
  - l'enchaînement complet (:func:`analyser_coup`) et le juge indépendant
    (:func:`juge_optimum`) sur un état jouable.

Le script n'a besoin d'aucune dépendance externe : le juge se replie sur la
recherche arborescente (``moteur/solveur``) si ``highspy``/``numpy`` manque, donc
ces tests tournent dans tous les environnements.
"""

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import verifier_simplicite_expert as V  # noqa: E402


# --------------------------------------------------------------------------- #
# Fabrication de tuiles / combinaisons (dicts JSON comme le reste du moteur).
# --------------------------------------------------------------------------- #

def _t(id_, valeur, couleur, joker=False):
    return {"id": id_, "valeur": valeur, "couleur": couleur, "est_joker": joker}


# --------------------------------------------------------------------------- #
# Description lisible.
# --------------------------------------------------------------------------- #

def test_decrire_combinaison_groupe():
    combo = [_t("a", 9, "bleu"), _t("b", 9, "jaune"), _t("c", 9, "noir")]
    assert V.decrire_combinaison(combo) == "groupe de 9 (bleu, jaune, noir)"


def test_decrire_combinaison_suite():
    combo = [_t("a", 5, "rouge"), _t("b", 6, "rouge"), _t("c", 7, "rouge")]
    assert V.decrire_combinaison(combo) == "suite rouge 5-6-7"


def test_decrire_combinaison_suite_avec_joker():
    combo = [_t("a", 4, "bleu"), _t("j", None, "bleu", joker=True),
             _t("c", 6, "bleu")]
    assert V.decrire_combinaison(combo) == "suite bleue 4-joker-6"


# --------------------------------------------------------------------------- #
# Coup déjà minimal : écart nul.
# --------------------------------------------------------------------------- #

def test_coup_deja_minimal_ecart_nul():
    # Plateau : un groupe de 9 à 3 couleurs. Expert pose le 9 rouge en ÉTENDANT
    # le groupe (aucune tuile du plateau déplacée).
    avant = [[_t("a", 9, "bleu"), _t("b", 9, "jaune"), _t("c", 9, "noir")]]
    apres = [[_t("a", 9, "bleu"), _t("b", 9, "jaune"), _t("c", 9, "noir"),
              _t("m", 9, "rouge")]]
    eva = V.evaluer_simplicite(avant, apres, nb_tuiles_reel=1,
                               plateau_apres_opt=apres, nb_tuiles_opt=1)
    assert eva["comparable"] is True
    assert eva["pert_reel"] == (0, 1)       # 0 déplacée, 1 combinaison modifiée
    assert eva["ecart_deplacees"] == 0
    assert eva["minimal"] is True
    assert eva["evitable"] is False


# --------------------------------------------------------------------------- #
# Coup artificiellement sur-décomposé : l'écart est bien détecté.
# --------------------------------------------------------------------------- #

def test_coup_sur_decompose_ecart_detecte():
    # Une suite rouge de 4 sur le plateau. Le coup « optimal » la reconduit
    # telle quelle (perturbation nulle) ; le coup « réel », artificiellement
    # sur-décomposé, l'éclate en deux morceaux — 2 tuiles déplacées.
    avant = [[_t("1", 1, "rouge"), _t("2", 2, "rouge"),
              _t("3", 3, "rouge"), _t("4", 4, "rouge")]]
    opt = [[_t("1", 1, "rouge"), _t("2", 2, "rouge"),
            _t("3", 3, "rouge"), _t("4", 4, "rouge")]]
    reel = [[_t("1", 1, "rouge"), _t("2", 2, "rouge")],
            [_t("3", 3, "rouge"), _t("4", 4, "rouge")]]

    eva = V.evaluer_simplicite(avant, reel, nb_tuiles_reel=0,
                               plateau_apres_opt=opt, nb_tuiles_opt=0)
    assert eva["comparable"] is True
    assert eva["pert_opt"] == (0, 0)        # optimum : rien déplacé
    assert eva["pert_reel"][0] == 2         # 2 tuiles du plateau déplacées
    assert eva["ecart_deplacees"] == 2
    assert eva["minimal"] is False
    assert eva["evitable"] is True


def test_moins_que_optimum_exclu():
    # Expert pose MOINS de tuiles que l'optimum : hors du sujet de la simplicité
    # (budget / coup raté), ni « minimal » ni « évitable », compté à part.
    avant = [[_t("a", 9, "bleu"), _t("b", 9, "jaune"), _t("c", 9, "noir")]]
    reel = avant
    opt = [[_t("a", 9, "bleu"), _t("b", 9, "jaune"), _t("c", 9, "noir"),
            _t("m", 9, "rouge")]]
    eva = V.evaluer_simplicite(avant, reel, nb_tuiles_reel=0,
                               plateau_apres_opt=opt, nb_tuiles_opt=1)
    assert eva["comparable"] is False
    assert eva["moins_que_optimum"] is True
    assert eva["minimal"] is False and eva["evitable"] is False


# --------------------------------------------------------------------------- #
# Juge indépendant et enchaînement complet sur un état jouable.
# --------------------------------------------------------------------------- #

def _etat_jouable():
    """Plateau = groupe de 9 (bleu, jaune, noir) ; main = 9 rouge (extensible)
    et quelques tuiles inutiles. Mise initiale faite."""
    avant = [[_t("a", 9, "bleu"), _t("b", 9, "jaune"), _t("c", 9, "noir")]]
    chevalet = [_t("m", 9, "rouge"), _t("x", 1, "bleu"), _t("y", 13, "noir")]
    etat = {
        "plateau": avant,
        "joueurs": [{"chevalet": chevalet, "mise_initiale_faite": True}],
        "config": {"mise_initiale_min": 30},
    }
    return avant, chevalet, etat


def test_juge_optimum_trouve_une_pose():
    _avant, _chevalet, etat = _etat_jouable()
    plateau_opt, nb = V.juge_optimum(etat, 0, budget_temps=3.0)
    assert plateau_opt is not None
    assert nb == 1  # le 9 rouge est posable (extension du groupe de 9)


def test_analyser_coup_minimal_integration():
    avant, chevalet, etat = _etat_jouable()
    # Coup réel = l'extension directe du groupe (le coup le plus simple).
    apres = [[_t("a", 9, "bleu"), _t("b", 9, "jaune"), _t("c", 9, "noir"),
              _t("m", 9, "rouge")]]
    enr = V.analyser_coup(avant, apres, chevalet, etat, 0, "Expert", tour=5,
                          budget_juge=3.0)
    assert enr["nb_tuiles_reel"] == 1
    assert enr["eval"]["comparable"] is True
    assert enr["eval"]["minimal"] is True
    assert enr["eval"]["evitable"] is False
    # La rédaction d'un exemple ne lève jamais et mentionne la conclusion.
    texte = V.rediger_exemple(1, enr)
    assert "décomposition NÉCESSAIRE" in texte
    assert "groupe de 9" in texte
