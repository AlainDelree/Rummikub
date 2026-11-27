"""Tests de l'échéance commune pour tout le tour (issue #279, suite de #277).

Chaque appel au solveur est borné par un budget (``BUDGET_TEMPS_EXPERT``),
mais avant #279 rien ne bornait le TOUR entier : les étapes qui rappellent le
solveur au cours d'un même tour (``_appliquer_joker_utile``,
``_appliquer_echange_differe``, ``_appliquer_joker_libre``) recevaient
chacune une échéance neuve. Voir docs/contexte/joker_tactiques.md et
docs/contexte/solveur_expert.md pour le mécanisme, et
docs/contexte/niveaux_ia_calibrage.md (« Tours longs #277 ») pour la mesure
d'origine.

Horloge factice (``ia.time``, jamais ``time.monotonic`` global) : avance d'un
pas fixe à CHAQUE lecture, comme ``_HorlogeDeterministe`` de
``tests/conftest.py`` pour ``moteur.solveur`` — ne ralentit jamais les tests
(aucun ``sleep``), et ne modifie pas la mesure de temps RÉELLE utilisée par
``moteur.solveur``/``moteur.solveur_exact`` (chacun garde son propre nom de
module ``time``, non affecté)."""

import rummikub.moteur.ia as ia
from rummikub.moteur.ia import (
    jouer_niveau_bride, jokers_rendus_libres_par_coup,
    _appliquer_joker_utile, _appliquer_joker_libre,
    _plafond_tour, _budget_selon_echeance, FACTEUR_PLAFOND_TOUR,
    BUDGET_TEMPS_EXPERT,
)
from rummikub.moteur.partie import creer_partie


def _partie_2j(niveau):
    return creer_partie(
        [{"nom": "Humain", "est_ia": False, "niveau": None},
         {"nom": "Bot", "est_ia": True, "niveau": niveau}],
        {"nb_manches": 1, "valeur_joker_penalite": 30, "mise_initiale_min": 30})


def _t(id_, valeur=None, couleur=None, est_joker=False):
    return {"id": id_, "valeur": valeur, "couleur": couleur, "est_joker": est_joker}


def _bot(niveau, plateau, chevalet, mise_initiale_faite=True):
    etat = _partie_2j(niveau)
    etat["index_joueur_actuel"] = 1
    bot = etat["joueurs"][1]
    bot["mise_initiale_faite"] = mise_initiale_faite
    etat["plateau"] = plateau
    bot["chevalet"] = chevalet
    return etat


class _HorlogeIA:
    """Remplace ``ia.time`` : avance d'un pas fixe à CHAQUE lecture — simule
    un tour « lent » sans dormir ni dépendre de la vitesse de la machine.
    N'affecte PAS ``moteur.solveur``/``moteur.solveur_exact`` (chacun importe
    ``time`` dans son propre espace de noms, jamais touché ici)."""

    def __init__(self, pas):
        self._valeur = 0.0
        self._pas = pas

    def monotonic(self):
        self._valeur += self._pas
        return self._valeur


def _etat_joker_libre_evitable():
    """Plateau : suite rouge 7-8-(joker_1=9) — PAS libre (3 tuiles). Main :
    rouge_6 (étendrait la suite en 4 tuiles, joker_1 deviendrait libre en
    bout), bleu_5-6-7 (alternative sûre, sans toucher au plateau), noir_2
    isolée (empêche de vider la main). Repris de
    ``test_evite_le_coup_qui_rend_un_joker_libre_en_posant_moins_de_tuiles``
    (tests/test_ia_anti_don_joker.py, docs/contexte/joker_tactiques.md) :
    déclenche la règle du joker LIBRE évité (#253 point 4), l'étape de la
    chaîne la plus coûteuse en appels au solveur (une recherche
    d'alternative par tuile jouée)."""
    return _bot("Expert",
               plateau=[[
                   _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
                   _t("joker_1", est_joker=True),
               ]],
               chevalet=[
                   _t("rouge_6_a", 6, "rouge"),
                   _t("bleu_5_a", 5, "bleu"), _t("bleu_6_a", 6, "bleu"),
                   _t("bleu_7_a", 7, "bleu"), _t("noir_2_a", 2, "noir"),
               ])


def _compter_appels_solveur(monkeypatch):
    """Monkeypatch ``ia._coup_exact``/``ia._coup_recherche`` (les deux seuls
    points d'entrée réels du solveur, voir ``jouer_niveau_expert``) pour
    compter les appels SANS changer leur comportement. Retourne la liste
    (mutée en place)."""
    appels = []
    original_exact = ia._coup_exact
    original_recherche = ia._coup_recherche

    def _exact_compte(*args, **kwargs):
        appels.append("exact")
        return original_exact(*args, **kwargs)

    def _recherche_compte(*args, **kwargs):
        appels.append("recherche")
        return original_recherche(*args, **kwargs)

    monkeypatch.setattr(ia, "_coup_exact", _exact_compte)
    monkeypatch.setattr(ia, "_coup_recherche", _recherche_compte)
    return appels


# --------------------------------------------------------------------------- #
# (d) Le plafond du tour ne descend jamais sous le budget d'un appel
# --------------------------------------------------------------------------- #

def test_plafond_tour_toujours_au_moins_le_budget_dun_appel():
    for budget in (0.001, 0.05, 1.5, 3.0, 10.0):
        plafond = _plafond_tour(budget)
        assert plafond >= budget
        assert plafond == FACTEUR_PLAFOND_TOUR * budget

    assert _plafond_tour(None) == FACTEUR_PLAFOND_TOUR * BUDGET_TEMPS_EXPERT
    assert _plafond_tour(None) >= BUDGET_TEMPS_EXPERT


def test_budget_selon_echeance_sans_echeance_renvoie_le_budget_habituel():
    # ``deadline_tour is None`` (hors ``jouer_niveau_bride``) : comportement
    # inchangé, pas de borne supplémentaire.
    assert _budget_selon_echeance(1.5, None) == 1.5
    assert _budget_selon_echeance(0.0, None) == 0.0


def test_budget_selon_echeance_echeance_depassee_renvoie_none(monkeypatch):
    monkeypatch.setattr(ia, "time", _HorlogeIA(pas=1.0))
    # Premier appel (dans le test) : horloge à 1.0. Échéance déjà au passé.
    assert _budget_selon_echeance(1.5, deadline_tour=0.5) is None


def test_budget_selon_echeance_borne_par_le_temps_restant(monkeypatch):
    monkeypatch.setattr(ia, "time", _HorlogeIA(pas=0.2))
    # Horloge à 0.2 au premier appel : échéance à 1.0 -> il reste 0.8s, plus
    # petit que le budget habituel (1.5s) -> le minimum est pris.
    assert _budget_selon_echeance(1.5, deadline_tour=1.0) == 0.8


# --------------------------------------------------------------------------- #
# (b) Budget confortable : le coup choisi est inchangé par #279
# --------------------------------------------------------------------------- #

def test_coup_inchange_avec_budget_confortable_debutant():
    etat = _bot("Débutant", plateau=[], chevalet=[
        _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
        _t("rouge_9_a", 9, "rouge"), _t("bleu_2_a", 2, "bleu"),
    ])
    coup = jouer_niveau_bride(etat, 1, "Débutant", budget_temps=5.0)
    # Débutant n'a pas la chaîne du joker (#277) : le résultat ne dépend
    # jamais de l'échéance commune introduite par #279 avec un budget large.
    assert coup["action"] in ("jouer", "piocher")


def test_coup_inchange_avec_budget_confortable_intermediaire():
    etat = _bot("Intermédiaire", plateau=[], chevalet=[
        _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
        _t("rouge_9_a", 9, "rouge"), _t("bleu_2_a", 2, "bleu"),
    ])
    coup = jouer_niveau_bride(etat, 1, "Intermédiaire", budget_temps=5.0)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_7_a", "rouge_8_a", "rouge_9_a"}


def test_coup_inchange_avec_budget_confortable_avance():
    etat = _bot("Avancé", plateau=[], chevalet=[
        _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
        _t("rouge_9_a", 9, "rouge"), _t("bleu_2_a", 2, "bleu"),
    ])
    coup = jouer_niveau_bride(etat, 1, "Avancé", budget_temps=5.0)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"rouge_7_a", "rouge_8_a", "rouge_9_a"}


def test_coup_inchange_avec_budget_confortable_expert_joker_libre():
    """Même scénario que la règle du joker libre évité
    (:func:`_etat_joker_libre_evitable`) : avec un budget confortable
    (horloge réelle, aucune échéance atteinte), le résultat est EXACTEMENT
    celui attendu sans la contrainte de temps (voir ``test_evite_le_coup_
    qui_rend_un_joker_libre_en_posant_moins_de_tuiles``,
    tests/test_ia_anti_don_joker.py) : bleu_5-6-7 joué, rouge_6 PAS joué."""
    etat = _etat_joker_libre_evitable()
    coup = jouer_niveau_bride(etat, 1, "Expert", budget_temps=5.0)
    assert coup["action"] == "jouer"
    assert set(coup["ids_tuiles"]) == {"bleu_5_a", "bleu_6_a", "bleu_7_a"}
    assert coup["joker"]["joker_libre_declenche"] is True
    assert coup["joker"]["joker_libre_evite"] is True


# --------------------------------------------------------------------------- #
# (a) La chaîne complète du joker reste bornée par l'échéance du tour
# --------------------------------------------------------------------------- #

def test_chaine_joker_bornee_par_echeance_commune(monkeypatch):
    """Sans contrainte de temps, la règle du joker libre évité
    (:func:`_etat_joker_libre_evitable`) appelle le solveur deux fois
    (l'étape principale, puis la recherche d'alternative sans joker libre —
    mesuré ci-dessous, ``appels_libres``). Avec une horloge factice qui
    avance à CHAQUE lecture et un budget de tour très court, le nombre
    d'appels ET le temps simulé du tour restent bornés par le plafond
    (#279) au lieu de croître avec le nombre de tuiles jouées (autant de
    candidats que de tuiles dans ``_chercher_coup_sans_joker_libre``)."""
    appels_libres = _compter_appels_solveur(monkeypatch)
    etat_libre = _etat_joker_libre_evitable()
    jouer_niveau_bride(etat_libre, 1, "Expert", budget_temps=5.0)
    nb_appels_libres = len(appels_libres)
    assert nb_appels_libres >= 2

    monkeypatch.undo()  # retire le compteur + toute horloge précédente

    appels_bornes = _compter_appels_solveur(monkeypatch)
    budget = 0.5
    pas = 0.6  # > budget : la recherche d'alternative n'a plus aucun temps.
    horloge = _HorlogeIA(pas)
    monkeypatch.setattr(ia, "time", horloge)
    etat_borne = _etat_joker_libre_evitable()
    coup = jouer_niveau_bride(etat_borne, 1, "Expert", budget_temps=budget)

    plafond = _plafond_tour(budget)
    # Nombre d'appels strictement borné (beaucoup moins que sans contrainte).
    assert len(appels_bornes) < nb_appels_libres
    # Temps simulé du tour resté proche du plafond, jamais laissé croître
    # librement avec le nombre de tuiles jouées (marge large pour la
    # dernière lecture qui détecte le dépassement, jamais un nouvel appel
    # solveur).
    assert horloge._valeur <= plafond + 4 * pas
    # Le coup renvoyé reste une action légale (jouer/piocher/passer), et
    # jamais le coup qui laisserait joker_1 libre (voir le test suivant).
    assert coup["action"] in ("jouer", "piocher", "passer")


# --------------------------------------------------------------------------- #
# (c) Un repli par échéance ne joue jamais un coup interdit par l'anti-don
# de joker — il pioche
# --------------------------------------------------------------------------- #

def test_repli_par_echeance_pioche_plutot_que_de_laisser_un_joker_libre(
        monkeypatch):
    """Même état que :func:`_etat_joker_libre_evitable` (bleu-5-6-7 est
    l'alternative sûre à rouge_6), mais l'échéance du TOUR est déjà sur le
    point d'être dépassée dès la recherche d'alternative (point 4, joker
    libre) : impossible de la chercher. L'IA doit piocher plutôt que de
    jouer rouge_6 (qui rendrait joker_1 libre) — jamais un coup que la
    règle anti-don de joker refuserait en temps normal."""
    etat = _etat_joker_libre_evitable()
    # Budget de tour modeste pour l'étape PRINCIPALE (qui doit réussir
    # normalement), mais un pas d'horloge PLUS GRAND que ce budget : la
    # recherche d'alternative du point 4 n'a alors matériellement plus
    # aucun temps disponible dès sa première vérification.
    budget = 0.5
    horloge = _HorlogeIA(pas=0.6)
    monkeypatch.setattr(ia, "time", horloge)

    coup = jouer_niveau_bride(etat, 1, "Expert", budget_temps=budget)

    # Sans la contrainte de temps, ce même état joue bleu_5-6-7 (voir
    # test_evite_le_coup_qui_rend_un_joker_libre_en_posant_moins_de_tuiles,
    # tests/test_ia_anti_don_joker.py) : ici, faute de temps pour chercher
    # cette alternative, l'IA pioche plutôt que de jouer rouge_6.
    assert coup["action"] == "piocher"


def test_appliquer_joker_libre_sans_temps_restant_pioche(monkeypatch):
    """Test unitaire direct (complément du précédent) : ``deadline_tour``
    déjà entièrement consommée AVANT même le premier appel de
    :func:`_appliquer_joker_libre` — aucun nouvel appel au solveur ne doit
    être lancé, et le repli doit piocher (jamais jouer ``coup`` tel quel,
    qui laisserait joker_1 libre)."""
    etat = _bot("Expert",
               plateau=[[
                   _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
                   _t("joker_1", est_joker=True),
               ]],
               chevalet=[_t("rouge_6_a", 6, "rouge"), _t("noir_2_a", 2, "noir")])
    bridage = ia._niveaux.bridage_pour("Expert")
    coup = {"action": "jouer", "ids_tuiles": ["rouge_6_a"],
           "nouveau_plateau": [[
               _t("rouge_6_a", 6, "rouge"), _t("rouge_7_a", 7, "rouge"),
               _t("rouge_8_a", 8, "rouge"), _t("joker_1", est_joker=True),
           ]]}
    assert jokers_rendus_libres_par_coup(etat, 1, coup) == {"joker_1"}

    appels = _compter_appels_solveur(monkeypatch)
    monkeypatch.setattr(ia, "time", _HorlogeIA(pas=1.0))
    deadline_deja_passee = -1.0  # horloge >= 0 à la première lecture : dépassée.

    resultat, info = _appliquer_joker_libre(
        etat, 1, coup, bridage, budget_temps=1.5, preferer_simple=None,
        eval_config=None, deadline_tour=deadline_deja_passee)

    assert appels == []  # aucun nouvel appel au solveur
    assert resultat["action"] == "piocher"
    assert info["declenchee"] is True
    assert info["evite"] is False


def test_appliquer_joker_utile_sans_temps_restant_garde_le_coup(monkeypatch):
    """Même principe sur ``_appliquer_joker_utile`` : échéance déjà
    dépassée -> aucun nouvel appel au solveur, et le joker non encore jugé
    reste par défaut considéré UTILE (comportement prudent : ``coup`` est
    renvoyé inchangé, jamais un coup qui retirerait à tort un joker sans
    l'avoir vérifié)."""
    etat = _bot("Expert", plateau=[], chevalet=[
        _t("joker_1", est_joker=True), _t("joker_2", est_joker=True),
        _t("rouge_7_a", 7, "rouge"), _t("rouge_8_a", 8, "rouge"),
        _t("noir_5_a", 5, "noir"), _t("noir_6_a", 6, "noir"),
        _t("noir_7_a", 7, "noir"), _t("bleu_2_a", 2, "bleu"),
    ])
    bridage = ia._niveaux.bridage_pour("Expert")
    coup = {"action": "jouer",
           "ids_tuiles": ["joker_1", "joker_2", "rouge_7_a", "rouge_8_a",
                          "noir_5_a", "noir_6_a", "noir_7_a"],
           "nouveau_plateau": []}

    appels = _compter_appels_solveur(monkeypatch)
    monkeypatch.setattr(ia, "time", _HorlogeIA(pas=1.0))
    deadline_deja_passee = -1.0

    resultat, info = _appliquer_joker_utile(
        etat, 1, coup, bridage, budget_temps=1.5, preferer_simple=None,
        eval_config=None, deadline_tour=deadline_deja_passee)

    assert appels == []  # aucun nouvel appel au solveur
    assert resultat is coup  # coup déjà trouvé, renvoyé inchangé
    assert info["evalue"] is True
