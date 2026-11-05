# Issue #236 — Retirer la vérification de finition d'Expert (elle n'a jamais changé un coup) et finir le nettoyage des stratégies

## Contexte
#235 a retiré le niveau Champion du Monde et le code des stratégies
multi-tours, mais a laissé en place la vérification de finition (#221)
d'Expert, pour respecter la consigne de ne pas toucher à Expert — alors que
c'est elle aussi une stratégie multi-tours du même lot, et la seule qui
restait. Elle n'a jamais changé un coup : sur la série de tests des
stratégies de #235 (12 configurations de 1 000 parties), elle a été
déclenchée 4 534 fois dans la configuration témoin sans changer le coup une
seule fois ; dans les campagnes précédentes (#221, #226), 5 180 tours de fin
de partie examinés, aucun coup changé, dont 881 tours sur 901 où aucun
candidat ne permettait de finir au tour suivant. Coût : un ou deux appels
supplémentaires au solveur exact sur environ un tour sur sept, pour aucun
effet. Décision d'Alain : retirer le code plutôt que de le laisser actif ou
désactivé — récupérable dans l'historique au même tag git
`archive-strategies-champion` (pointe sur le commit b7214b2, qui contient
encore le module avant ce retrait).

## Modifications
- **Module supprimé** : `src/rummikub/moteur/verification_finition.py`.
- **`moteur/ia.py`** : import du module retiré ; fonctions
  `_candidats_finition` et `_verifier_finition_fin_de_partie` supprimées ;
  branchement dans `jouer_niveau_bride` retiré (plus de calcul de
  `deadline`/`budget_total`, plus d'annotation `verif_finition` sur le coup
  ni sur le repli « pas de coup à comparer ») ; `import time` devenu inutile,
  retiré.
- **`moteur/niveaux.py`** : champ `Bridage.verif_finition` et constante
  `SEUIL_FIN_PARTIE_VERIF_FINITION` retirés ; l'entrée `BRIDAGES["Expert"]`
  perd son `verif_finition=True` (redevient strictement identique à
  `BRIDAGES["Avancé"]`) ; docstrings mises à jour (Expert et Avancé décrits
  comme strictement identiques).
- **`persistance/journal.py`** : paramètre `verif_finition` de
  `logger_action` et l'entrée correspondante du journal retirés.
- **`ui/api.py`** : l'appel à `logger_action` ne transmet plus
  `verif_finition=...`.
- **Tests** : suppression de `tests/test_verification_finition.py` (15
  tests) ; `tests/test_comparer_niveaux_ia_rapport.py` perd la mention de ce
  fichier dans son docstring ; `tests/test_echelle_niveaux.py` : commentaire
  « six niveaux » → « cinq niveaux » (reste du retrait de Champion du Monde
  par #235, non nettoyé à l'époque).
- **Scripts de mesure** : `scripts/comparer_campagnes_appariees.py` perd la
  mention de `verif_finition` dans son avertissement sur les divergences non
  liées au réglage testé ; `scripts/echelle_niveaux.py` : avertissement sur
  l'égalité Avancé/Expert mis à jour (ce n'est plus une approximation « Expert
  ajoute la vérification de finition », mais une stricte identité), et deux
  mentions résiduelles « SIX NIVEAUX »/« six niveaux » (restes non nettoyés de
  #235) corrigées en « CINQ NIVEAUX »/« cinq niveaux ».
- **CONTEXTE.md** : architecture (§ arborescence) — ligne du module supprimée,
  « 6 niveaux d'IA » → « 5 niveaux d'IA » (reste non nettoyé de #235). Archive
  « stratégies multi-tours de Champion du Monde » (§13) : le point `a`
  (vérification de finition) marqué comme retiré par #236 avec renvoi au
  nouveau point `g`, qui détaille les chiffres ci-dessus ; le point `f`
  (fichiers récupérables) mis à jour pour inclure
  `verification_finition.py` parmi les fichiers désormais supprimés, toujours
  récupérables au même tag. §16 (échelle) : nouveau paragraphe « Mise à jour
  #236 » actant qu'Expert et Avancé sont de nouveau strictement identiques.

## Restes d'autres stratégies retirées, recherchés
Recherche des noms cités dans l'issue (réserve, retenue, petits chiffres,
chances, placement du joker, garde joker, sorties, inconnues, stratégie) dans
tout le dépôt : aucun code mort trouvé.
- `réserve`/`rétention`/`joker gardé`/`chances` apparaissant dans
  `scripts/match_solveurs.py`, `scripts/comparer_campagnes_appariees.py` et
  CONTEXTE.md §13 (pistes 1/8/9) sont des pistes **documentées mais jamais
  implémentées** (idées pour une future révision des niveaux) — pas du code
  retiré, rien à nettoyer.
- `réserve` dans `persistance/coups_rates.py` et ses tests désigne une
  **technique de joueur humain** détectée par l'analyse des coups ratés
  (issue #193/#201/#202), sans rapport avec les stratégies IA retirées —
  code actif et utilisé, à conserver.
- `inconnues` dans `tests/test_coups_rates_parties_liees.py` désigne des
  décisions sans résultat connu dans l'analyse humaine, sans rapport avec la
  brique « Inconnues » (#219, déjà supprimée par #235).
- Deux restes textuels sans rapport avec la finition, mais relevant bien du
  nettoyage inachevé de #235, ont été trouvés et corrigés au passage (listés
  ci-dessus) : « 6/six niveaux » dans CONTEXTE.md et
  `scripts/echelle_niveaux.py` (×2), alors que l'échelle compte cinq niveaux
  depuis #235.

## Non-régression
Sur les 380 positions du corpus de l'issue #222, avec une graine (`42`) et un
budget de solveur fixes (1,5 s, le budget de production), les coups choisis
par les cinq niveaux ont été comparés avant (commit de départ de cette issue)
et après ce retrait : **1894 décisions identiques sur 1900** (380 positions ×
5 niveaux). Les 6 écarts restants (positions #70, #79 ×2, #85, #368 ×2 du
corpus, toutes marquées « chargées », 52 à 71 tuiles au plateau) sont des
artefacts du budget de temps du solveur exact (1,5 s) sur des plateaux
lourds, **indépendants du retrait** : rejouées isolément trois fois chacune
sur le code APRÈS ce retrait, 4 des 6 positions/niveaux donnent déjà des
réponses différentes d'un essai à l'autre (même code, même position, même
graine) — l'instabilité est celle du solveur sous charge/budget serré, pas un
effet du retrait. Les positions #79 et #368 font en outre diverger Avancé ET
Expert ENSEMBLE, dans le même sens : or `Avancé` n'appelait jamais la
vérification de finition (jamais concernée par ce retrait), ce qui confirme
que la cause est le temps de calcul réellement disponible au moment de la
résolution, pas le code retiré — exactement le phénomène déjà documenté par
#235 (positions #356/#372 de sa propre non-régression).

## Nombre de tests
447 tests avant ce retrait, 432 après (−15 : exactement les 15 tests de
`tests/test_verification_finition.py`, seul fichier de tests supprimé) —
baisse attendue, le code testé a disparu. Suite complète exécutée après
modification : 432 tests, tous passent (419 passés, 13 ignorés — dépendances
`rummikub_solver` absentes de l'environnement de mesure, sans rapport avec ce
retrait).

## Points d'attention
- Les réglages (`perturbation_max`, `taux_oubli`) des cinq niveaux n'ont pas
  été modifiés — seul le code devenu mort (vérification de finition) a été
  retiré, conformément à la consigne.
- Expert et Avancé sont désormais strictement identiques dans le code (même
  chemin `jouer_niveau_expert`, aucune étape additionnelle) : l'égalité
  statistique Avancé≈Expert déjà observée (#213, #221, #235) n'est plus une
  approximation provisoire mais le reflet exact du code.
- Plus aucun code de stratégie multi-tours ne subsiste dans le dépôt ; tout
  reste récupérable au tag git `archive-strategies-champion`.
