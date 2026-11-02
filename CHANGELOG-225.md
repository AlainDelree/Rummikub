# Issue #225 — Champion du Monde : garder un joker en main en fin de partie pour finir d'un coup

Troisième candidat de la vérification de finition (#221, statuts affinés par
#223) : étape 2 de la brique « Deux tours » (CONTEXTE.md §13), réservée à
**Champion du Monde SEUL** — Expert reste le niveau de référence, strictement
inchangé.

## 1. Réglages (`moteur/niveaux.py`)

- `Bridage.garder_joker_fin_partie` (nouveau champ, défaut `False`) : actif
  uniquement pour `"Champion du Monde"`. Expert et les niveaux inférieurs
  n'y ont jamais droit.
- `SEUIL_PRUDENCE_ADVERSAIRE_GARDE_JOKER = 3` : seuil de prudence sur le
  nombre de tuiles d'un adversaire (information PUBLIQUE, jamais le contenu
  de sa main) en dessous duquel la stratégie n'est pas tentée.

## 2. Troisième candidat (`moteur/ia.py`, `moteur/verification_finition.py`)

- `ia._peut_tenter_garde_joker` : portes d'activation (joker en main ET
  aucun adversaire sous le seuil de prudence).
- `ia._coup_sans_joker_chevalet` : résout la position avec un joker du
  chevalet retiré pour ce seul calcul (modèle exact), marqué
  `SOLVEUR_SANS_JOKER`.
- `ia._candidats_finition` étendu : ajoute ce troisième candidat quand le
  réglage est actif et les portes s'y prêtent ; ne vaut que s'il pose au
  moins une tuile et diffère du meilleur coup du solveur.
- `verification_finition.verifier` : nouveau paramètre optionnel
  `idx_garde_joker` (défaut `None`, compatible avec tous les appels
  existants) et nouveau statut `APPLIQUEE_GARDE_JOKER` (« appliquée : un
  coup qui garde le joker a été choisi »), cas particulier distingué
  d'`APPLIQUEE_AUTRE_COUP`. La vérification utilise le chevalet restant
  AVEC le joker pour juger si le tour suivant finit.
- Règle de décision inchangée (coup gagnant jamais vérifié ; premier
  candidat qui finit joué ; meilleur coup du solveur préféré à égalité).

## 3. Statuts et compteurs

- `coup["garde_joker_info"]` (posé uniquement quand `garder_joker` est actif
  ET qu'un joker est en main) : `joker_en_main`, `candidat_existe`,
  `permet_de_finir` (`True`/`False`/`None` si la question n'a pas été
  tranchée par court-circuit), `choisi`.
- `persistance/journal.py` : `logger_action(..., garde_joker=...)`, clé
  optionnelle `garde_joker` du journal (même esprit que `verif_finition`).
  `ui/api.py` transmet `res_ia.get("garde_joker_info")`.
- `scripts/comparer_niveaux_ia.py` : compteurs agrégés
  (`tours_joker_en_main`, `candidat_existe`, `permet_de_finir`, `choisi`) et
  liste des parties où la stratégie a été choisie au moins une fois, avec
  leur vainqueur — affichés dans le rapport, avec le coût d'un joker resté
  en main (`reglages.DEFAUTS["valeur_joker_penalite"]`, 30 points par
  défaut).

## 4. Nombre de manches

Première version : la règle s'applique à l'identique quel que soit
`--manches`, avec le seul seuil de prudence sur l'adversaire. Piste non
implémentée, documentée dans CONTEXTE.md §13 : relever ce seuil quand une
manche perdue coûte cher (plusieurs manches, score déjà serré) — à trancher
par Alain une fois les compteurs mesurés sur de vraies campagnes.

## 5. Option de campagne et comparaison appariée

- `scripts/comparer_niveaux_ia.py --sans-garde-joker` : désactive la
  stratégie pour Champion du Monde seul (même esprit que
  `--sans-verif-finition`).
- `scripts/comparer_niveaux_ia.py --export-resultats FICHIER` : écrit un
  fichier JSON Lines (un match par ligne : donne, ordre, vainqueur, scores).
- `scripts/comparer_campagnes_appariees.py` (nouveau) : compare deux
  fichiers exportés à la même graine, rapporte parties identiques,
  divergences par sens, et un test des signes (implémentation directe, sans
  dépendance externe) sur les parties divergentes à direction nette — avec
  l'avertissement qu'une divergence peut aussi venir d'une simple variation
  du budget de temps du solveur, sans lien avec la stratégie.

## 6. Tests

`tests/test_verification_finition.py` (8 tests ajoutés) : décision pure de
`verifier` avec `idx_garde_joker`, choix du candidat garde-joker quand il
permet de finir, non-activation si un adversaire est à 1 ou 2 tuiles, aucun
effet sans joker en main, coup gagnant jamais vérifié même avec un joker,
Expert et niveaux inférieurs non affectés (chevalet avec joker compris,
`_coup_sans_joker_chevalet` jamais appelé).

`tests/test_comparer_niveaux_ia_rapport.py` (4 tests ajoutés) : le drapeau
`--sans-garde-joker` désactive et restaure bien le réglage (sans affecter
Expert), affichage des compteurs du rapport, absence de la section quand
aucun tour concerné.

Tous les tests existants (446 passés, 4 ignorés faute de `highspy`/`numpy`
sur certains tests déjà marqués `@besoin_exact` avant cette issue) restent
verts.

## 7. Documentation

CONTEXTE.md §13 : nouvelle entrée « Réalisée (#225) » (arbre des stratégies
multi-tours mis à jour, réglages, troisième candidat, statuts, compteurs,
coût d'un joker en points, piste non implémentée pour plusieurs manches,
commandes de campagne prêtes à copier, rappel que les compteurs — plus que
le taux de victoire — diront si la stratégie change quelque chose).

## Aucune modification

Du solveur lui-même, de l'interface, des règles du jeu, ni du comportement
d'Expert, Avancé ou des niveaux inférieurs.
