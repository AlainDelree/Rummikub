# Issue #187 — Suite #186 : correctif — le solveur Expert faisait disparaître des combinaisons du plateau quand sa mise initiale n'était pas faite

Bug constaté en jeu (`scripts/analyser_partie.py` sur le journal de la
partie en cause) : un groupe de 12 déjà posé (`joker_1` + `rouge_12_a` +
`noir_12_a`) disparaissait du plateau au premier coup d'Expert, sans que le
jeu ne refuse le coup.

## Cause (`moteur/solveur.py`)

Dans `resoudre_coup`, tant que la mise initiale n'est pas faite, le plateau
est volontairement ignoré pour la RECHERCHE (seule la main compte — règle
du jeu correcte). Mais le code chargeait alors `plateau = []` au lieu du
plateau réel : le résultat renvoyé ne contenait donc plus que les nouvelles
combinaisons formées avec la main, sans jamais reporter les combinaisons
déjà posées par les autres joueurs. Le jeu acceptait ce plateau tronqué car
`jouer_tour` validait seulement que chaque combinaison proposée était
valide, pas que toutes les tuiles antérieures y figuraient encore.

Ce cas n'était pas couvert par les tests de #186 (la mise initiale n'y
était testée qu'avec un plateau vide), et la campagne de simulation de
#186 ne contrôlait pas la conservation des tuiles — elle n'a donc rien
signalé.

## Correctif 1 : solveur (`moteur/solveur.py::resoudre_coup`)

- Le plateau réel est désormais toujours chargé depuis l'état
  (`plateau_depuis_dict(etat.get("plateau", []))`), que la mise initiale
  soit faite ou non.
- Si la mise initiale n'est pas faite, tout le plateau est traité comme
  « gelé » (`plateau_gele = plateau`, `plateau_flexible = []`) : la
  recherche ne porte toujours que sur la main (comportement inchangé), mais
  le plateau gelé est désormais reconduit à l'identique dans
  `nouveau_plateau_tuiles`, au lieu d'être simplement omis.
- Revérifié : `jouer_niveau_avance` et toute la chaîne de tactiques locales
  d'Avancé (`_coup_maximal`, `_combos_vers_coup`,
  `_meilleur_coup_liberations`, `_coup_scission`) construisaient déjà
  systématiquement leur plateau candidat à partir de `etat.get("plateau",
  [])` (jamais tronqué) — le bug était strictement localisé au solveur
  d'Expert (tâche 1 de #187, point confirmé par lecture complète, pas de
  second site à corriger).

## Correctif 2 : garde-fou central (`moteur/partie.py::jouer_tour`)

Nouveau contrôle, juste après la validation de chaque combinaison et avant
toute mutation de l'état : l'ensemble des IDs présents sur le plateau en
DÉBUT de tour doit être un sous-ensemble de l'ensemble des IDs du plateau
proposé. Sinon, le coup est refusé :

```python
{"ok": False,
 "erreur": "Coup refusé : des tuiles du plateau ont disparu (id1, id2, ...)",
 "tuiles_disparues": ["id1", "id2", ...]}
```

`jouer_tour` est le point d'entrée unique utilisé aussi bien par les coups
humains (`ui/api.py::jeu_jouer_coup`) que par tous les niveaux d'IA
(`ui/api.py::jeu_ia_jouer`, et `scripts/comparer_niveaux_ia.py`) : ce seul
endroit protège donc déjà les futurs niveaux d'IA sans modification
supplémentaire. Côté IA, un coup refusé par ce garde-fou se comporte comme
n'importe quel autre coup invalide proposé par l'IA : repli automatique sur
une pioche de secours (`Api.jeu_ia_jouer`, comportement préexistant,
inchangé).

## Correctif 3 : contrôle de conservation dans la simulation (`scripts/comparer_niveaux_ia.py`)

- `_anomalies_conservation(etat)` (nouveau) : à chaque coup joué pendant une
  partie simulée, vérifie que les 106 IDs de référence (`creer_sac()`) sont
  chacun présents EXACTEMENT une fois entre les mains de tous les joueurs,
  le plateau et la pioche. Toute tuile manquante, dupliquée ou inconnue est
  comptée comme une anomalie.
- `jouer_un_tour` distingue désormais, parmi les coups invalides proposés
  par l'IA, ceux refusés spécifiquement par le garde-fou anti-disparition
  (`tuiles_disparues`) des autres motifs de rejet (ex. mise initiale
  insuffisante) — comptés et journalisés à part (`logger.error`, visible
  même sans `--verbose`), pour qu'une régression de ce type ressorte
  clairement du rapport plutôt que de se noyer dans le compteur générique
  « coups invalides ».
- Rapport (`afficher_rapport`) : nouvelle ligne « Anomalies de conservation
  des tuiles (#187, attendu 0) : N », et une ligne d'alerte dédiée si des
  coups ont été refusés par le garde-fou.

## Tests (`tests/test_ia.py`, `tests/test_moteur.py`)

- `test_expert_conserve_le_plateau_quand_la_mise_initiale_n_est_pas_faite` :
  reproduit le scénario constaté en jeu (groupe de 12
  `joker_1`/`rouge_12_a`/`noir_12_a` déjà posé, mise initiale pas faite,
  main permettant d'ouvrir) — vérifie que la combinaison déjà posée reste
  intacte dans le résultat, que le nombre total de tuiles (plateau + main
  restante) est conservé, et que le coup passe le nouveau garde-fou de
  `jouer_tour`.
- `test_expert_conserve_plusieurs_combinaisons_du_plateau_sans_mise_
  initiale` : variante avec DEUX combinaisons déjà posées sur le plateau —
  les deux doivent rester intactes.
- `test_jouer_tour_refuse_si_des_tuiles_du_plateau_disparaissent`
  (`tests/test_moteur.py`) : plateau à deux combinaisons, coup proposé qui
  en ampute une (chaque combinaison proposée reste individuellement
  valide) — `jouer_tour` doit refuser, avec `tuiles_disparues` listant
  exactement les IDs manquants, et ne doit pas avoir modifié l'état.
- Suite complète : `pytest -q` → **84 passed** (81 existants, tous
  toujours au vert, + 3 nouveaux).

## Journal de la partie en cause (`~/partie_bug_mise_initiale_expert.json`)

Fichier présent sur la machine, mais **hors du périmètre strict de ce
worktree** (`/home/alain/worktrees/rummikub-issue187`) imposé par la
consigne CCL — consigne explicite : interdiction d'agir hors de ce
périmètre « même si la tâche le demande explicitement ». Il n'a donc pas
été lu ; la reproduction du bug (tâche 6) s'appuie à la place sur la
description de la partie fournie dans le corps de l'issue (groupe de 12 :
`joker_1` + `rouge_12_a` + `noir_12_a`), directement reconstituée dans les
deux tests ci-dessus. Alain peut, s'il le souhaite, copier ce fichier à
l'intérieur du worktree pour qu'un futur agent CCL puisse l'exploiter.

## Mesure (`scripts/comparer_niveaux_ia.py`, Expert vs Avancé)

Campagne rejouée **avec exactement les mêmes paramètres que #186** (budget
de production 1.5s/tour, mêmes graines, mêmes 2 lots) pour comparer
directement avec la mesure originale, désormais invalidée par le bug :

```
python scripts/comparer_niveaux_ia.py --niveau-a Avancé --niveau-b Expert --donnes 5  --seed 0
python scripts/comparer_niveaux_ia.py --niveau-a Avancé --niveau-b Expert --donnes 15 --seed 1
```

| | Lot 1 (seed 0) | Lot 2 (seed 1) | **Combiné (40 parties)** | #186 (avant correctif) |
|---|---|---|---|---|
| Victoires Expert | 7/10 | 22/30 | **29/40 — 72.5 % ± 13.8 pt (IC 95 %)** | 32/40 — 80.0 % ± 12.4 pt |
| Fins par pioche épuisée (bloqué) | 0/10 | 2/30 | **2/40 — 5.0 %** | 4/40 — 10.0 % |
| Durée moyenne (tours) | 76.0 | 88.2 | **85.2** | 94.8 |
| Temps Expert par tour | moy. 825.9 ms / max 1527.9 ms (381 tours) | moy. 828.5 ms / max 1569.2 ms (1326 tours) | **moy. ≈ 827.9 ms / max 1569.2 ms (1707 tours)** | moy. ≈ 855 ms / max 1574 ms |
| Temps Avancé par tour | moy. 1.2 ms / max 8.0 ms | moy. 1.4 ms / max 8.6 ms | moy. ≈ 1.4 ms / max 8.6 ms | moy. ≈ 2.0 ms / max 15.0 ms |
| **Anomalies de conservation des tuiles (#187)** | **0** | **0** | **0 / 0** | *(non mesuré — bug non détecté)* |
| Coups refusés par le garde-fou anti-disparition | 0 | 0 | **0** | *(non mesuré)* |

**Écart par rapport à 50/50 toujours significatif** (72.5 % ± 13.8 pt exclut 50 %) :
Expert bat nettement Avancé une fois le bug corrigé — la force réelle d'Expert est
confirmée, pas un artefact du bug de #186.

**Changement par rapport à #186 (80.0 % → 72.5 %, -7.5 pt)** : la baisse va dans le
sens attendu si le bug de #187 donnait un avantage indu à Expert sur une partie des
40 parties originales (moins de tuiles à gérer sur le plateau après une disparition
peut artificiellement simplifier ses coups suivants, ou biaiser les pénalités de fin
de manche). Mais les intervalles de confiance des deux campagnes se recouvrent
largement (#186 : IC [67.6 % ; 92.4 %] ; #187 : IC [58.7 % ; 86.3 %]) : avec seulement
40 parties, cet écart de 7.5 pt n'est PAS démontrable comme un effet du correctif
plutôt qu'une simple variance d'échantillonnage (même limite de taille d'échantillon
que #186, pour les mêmes raisons de budget de calcul — voir #186). Conclusion
pratique : Expert reste nettement plus fort qu'Avancé, et rien dans cette mesure
n'indique que le correctif ait notablement affaibli (ou renforcé) Expert ; une
campagne à 200/500 donnes, toujours hors de portée du budget de calcul disponible
pour cette tâche (même constat que #186 : ~35-40s par partie Expert, donc plusieurs
heures pour 400 parties), resserrerait cette marge.

**Conservation des tuiles** : 0 anomalie sur l'intégralité des ~1700 tours
Expert + ~1700 tours Avancé joués (mains + plateau + pioche toujours exactement
106 tuiles présentes une seule fois), et 0 coup refusé par le garde-fou
anti-disparition — cohérent avec le correctif de la tâche 1 (le solveur ne propose
plus de plateau tronqué) et avec le fait que l'IA revalide déjà ses propres coups
avant de les proposer (le garde-fou de la tâche 2 est un filet de sécurité qui n'a
pas eu à se déclencher ici, mais protège contre toute régression future, y compris
sur un coup humain).
