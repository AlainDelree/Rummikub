# Issue #221 — Expert et Champion du Monde : vérification de finition en fin de partie (étape 1 de la brique « Deux tours »)

Le solveur exact d'Expert/Champion du Monde pose toujours le maximum de
tuiles à chaque tour, sans se demander si ce coup aide ou gêne le tour
suivant. Cette issue ajoute une vérification **bornée à la fin de partie**
qui compare le meilleur coup du solveur à une alternative qui ne reprend
aucun joker du tapis, et préfère celle des deux qui permet de vider
entièrement le chevalet au tour suivant — en supposant que l'adversaire ne
touche pas au tapis entre les deux tours (hypothèse optimiste assumée).

## 1. Mécanisme (`moteur/verification_finition.py`, nouveau module)

- S'applique **seulement** à Expert et Champion du Monde, et **seulement**
  quand le chevalet compte au plus `niveaux.SEUIL_FIN_PARTIE_VERIF_FINITION`
  tuiles (**5** par défaut). Interrupteur par niveau : `Bridage.verif_finition`
  (`moteur/niveaux.py`, `False` pour Débutant à Avancé — inchangés).
- Candidats : toujours le meilleur coup du solveur exact ; s'il existe et
  diffère, le meilleur coup **sans réarrangement du plateau**
  (`ia._coup_sans_rearrangement`, qui ne reprend jamais un joker déjà posé —
  approximation documentée, plus restrictive que « ne pas reprendre un
  joker » au sens strict, mais jamais l'inverse). Troisième candidat
  (« éventuellement ») délibérément omis : la recherche arborescente de
  repli aurait consommé le budget partagé pour un gain non démontré.
- Pour chaque candidat non gagnant, on demande au MÊME solveur exact s'il
  pourrait vider entièrement le chevalet restant au tour suivant (tapis
  inchangé). Le meilleur coup du solveur est vérifié EN PREMIER : s'il
  convient, il est joué (préféré à égalité) ; sinon, le premier candidat
  suivant qui convient est joué à sa place ; si aucun ne convient, le
  meilleur coup du solveur est joué comme avant cette issue.
- **Priorité absolue** (inchangée depuis #213) : un coup qui vide déjà le
  chevalet CE tour-ci n'est jamais soumis à la vérification.
- **Budget partagé** : les appels supplémentaires au solveur consomment la
  MÊME échéance de temps que le coup normal du tour (pas de budget séparé,
  pas de duplication du mécanisme de limite). Si cette limite est épuisée, si
  `highspy`/`numpy` manquent, ou en cas d'erreur, l'IA joue comme avant cette
  issue, sans erreur visible.
- Journal de partie (`persistance/journal.py`, `ui/api.py`) : nouvelle clé
  optionnelle `verif_finition` sur l'action, avec l'un des quatre statuts
  `appliquee_autre_coup` / `appliquee_sans_changement` / `non_applicable` /
  `budget_epuise` — même esprit que la clé `solveur` ajoutée par #211.

## 2. Constat mathématique découvert pendant cette issue

Ce moteur autorise une recomposition totale du plateau en un seul tour
(seule contrainte : aucune tuile déjà posée ne disparaît). Il en découle
qu'un coup **prouvé optimal** (modèle exact, budget suffisant) qui ne vide
pas le chevalet ne peut JAMAIS avoir de candidat qui permette de finir au
tour suivant — sinon ce coup aurait déjà pu lui-même finir CE tour en
combinant les deux coups en un (même conservation, même validité, que le
solveur — cherchant le MAXIMUM — aurait alors trouvé). Vérifié par
construction sur plus d'une dizaine de scénarios pendant cette issue.

**Conséquence** : le mécanisme ne peut réellement changer le coup joué que
lorsque le coup marqué comme venant du modèle exact n'a PAS été prouvé
optimal (budget de temps serré) — cas rare mais réel (seul cas couvert par
`--sans-verif-finition` dans la mesure ci-dessous, et par les tests qui
contrôlent directement la réponse du solveur plutôt que de chercher une
position réelle introuvable). Documenté dans le module et dans
`CONTEXTE.md` §13.

## 3. Tests (`tests/test_verification_finition.py`, 12 positions fixes)

Hors fin de partie (décision inchangée) ; coup gagnant jamais vérifié ;
aucun candidat naturel ne permet de finir ; cas sans joker ; décision de
`verifier()` avec l'oracle « peut finir » contrôlé directement (candidat B
choisi, meilleur coup conservé, égalité → premier candidat préféré) ;
intégration complète via `jouer_niveau_bride` (coup forcé « exact » +
candidat sans réarrangement réel) ; budget déjà épuisé ; repli sans
highspy/numpy ; Avancé non affecté ; interrupteur par niveau. Tests existants
inchangés et au vert (385 passed, 14 skipped avec les 12 nouveaux).

## 4. Mesure par simulation

`scripts/comparer_niveaux_ia.py` : nouveau drapeau `--sans-verif-finition`
(même esprit que `--sans-exact`/`--sans-preferer-simple`) + nouvelles
statistiques (fréquence d'activation, appels supplémentaires au solveur par
tour concerné). Expert étant appelé directement par ce script pour ses
propres statistiques (`on_repli`, perturbation), la vérification y est
appliquée manuellement via le MÊME appel de production
(`ia._verifier_finition_fin_de_partie`) ; Champion du Monde l'obtient
nativement via `jouer_ia`.

Campagne (Avancé vs Expert, 100 donnes = 200 matchs en miroir, seed 42,
1 manche, max-tours 300) :

<!-- RESULTATS_CAMPAGNE -->

Le moteur détecte déjà un blocage par pioche épuisée (`pioche_vide`, compté
dans le rapport) — **rien n'y est changé** par cette issue, conformément à
son périmètre.

## 5. Documentation (`CONTEXTE.md` §13, §2, §16)

Arbre des stratégies multi-tours et dépendances (Inconnues → Indices, Deux
tours [étape 1 faite], Main restante, puis Course, Rétention, Ouverture,
Joker et réserve) ; nouveau module listé en §2 ; §16 signale que Expert et
Champion du Monde ne sont plus strictement identiques à Avancé en toute fin
de partie. Deux idées d'Alain consignées (calcul pendant le tour de
l'humain — distinction pioche/pose ; pioche vide — signalée seulement, pas
de stratégie dédiée).

## Contraintes respectées

Solveur, interface, niveaux Débutant à Avancé non modifiés. `N` et
l'interrupteur par niveau vivent dans `moteur/niveaux.py` (seul endroit à
régler). Tests existants inchangés et au vert.
