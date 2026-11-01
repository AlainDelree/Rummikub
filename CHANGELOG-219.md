# Issue #219 — Brique « Inconnues » : tuiles inconnues et probabilités, sans changer le jeu

Nouveau module de calcul pur `src/rummikub/moteur/inconnues.py`, indépendant
du solveur, des niveaux et de l'interface. Aucun comportement de jeu n'est
modifié : brique de base pour les futures stratégies multi-tours décrites en
CONTEXTE.md §13 (Indices, Tuiles vivantes, Joker et réserve, Course,
Rétention, Ouverture), qui restent à implémenter dans des issues séparées.

## 1. Calcul des tuiles inconnues

`calculer_inconnues(plateau, main, tailles_mains_adversaires, taille_pioche)`
calcule, à partir de ce qu'un joueur voit (tapis, sa main, tailles des mains
adverses, taille de la pioche), l'ensemble des tuiles qui lui sont inconnues
avec leur nombre d'exemplaires encore possibles (0, 1 ou 2 ; 2 pour les
jokers — traités comme un seul type, leur couleur étant purement visuelle).
`calculer_inconnues_depuis_etat(etat, index_joueur)` est un raccourci depuis
l'état de partie complet.

## 2. Probabilités uniformes

`proba_instance_chez_adversaire`/`proba_instance_dans_pioche` (une tuile
inconnue prise au hasard), `proba_tuile_chez_adversaire`/
`proba_tuile_chez_un_adversaire_quelconque`/`proba_tuile_dans_pioche` (au
moins un exemplaire d'une tuile donnée, formule hypergéométrique exacte qui
se réduit à la formule uniforme simple demandée par l'issue quand il ne
reste qu'un seul exemplaire), `proba_joker_chez_adversaire`/
`proba_joker_chez_un_adversaire_quelconque`. `Inconnues.exemplaires_restants`
sert à détecter qu'une tuile n'a plus de voisines utilisables.

## 3. Pas de triche

`calculer_inconnues_depuis_etat` n'appelle jamais que `len(...)` sur les
chevalets adverses, jamais leur contenu. Testé explicitement
(`test_equite_pas_de_triche_contenu_main_adverse`,
`test_wrapper_etat_nutilise_que_len_sur_main_adverse`) : remplacer le contenu
de la main d'un adversaire sans changer sa taille ne change aucun résultat.

## 4. Vérification sur des parties réelles/simulées

`diagnostiquer_coherence(...)` liste les anomalies (tuile vue en trop, total
incohérent) sans jamais lever d'exception, pour analyser des journaux
potentiellement corrompus. `data/logs_parties` étant vide dans ce worktree
isolé (journaux présents uniquement sur la machine d'Alain), le test dédié
(`test_verification_sur_journaux_reels_si_disponibles`) s'ignore proprement ;
à la place, `test_verification_sur_parties_simulees` vérifie les mêmes
invariants à chaque tour de 5 parties simulées (2 à 4 IA, niveaux variés) :
254 tours, 686 vérifications par-joueur, 0 anomalie.

## 5. Performance

Indicatif, sans seuil bloquant : ≈ 0,12 ms par appel sur la machine de
développement (2000 appels mesurés) — négligeable devant le temps du
solveur (≈ 180–215 ms par tour, voir CONTEXTE.md §16).

## 6. Tests

`tests/test_inconnues.py` (20 tests) : cas fabriqués à la main (début/fin de
partie, tapis chargé, 0/1/2 exemplaires restants, 1 à 3 adversaires, jokers
sur le tapis/en main/inconnus), équité anti-triche, probabilités (uniformité,
bornes, cas limite k=1), diagnostic de cohérence, vérification sur parties
simulées et sur journaux réels (si disponibles), ordre de grandeur de
performance.

## 7. Documentation

CONTEXTE.md §13 mis à jour : la brique « Inconnues » est marquée réalisée,
avec le détail de ce que le module fournit et le rappel des stratégies qui
s'en serviront (Indices, Tuiles vivantes, Joker et réserve, Course,
Rétention, Ouverture), sans les implémenter.
