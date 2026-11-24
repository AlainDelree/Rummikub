# Issue #262 — Suite #261 : trier les récits d'issue dans les fichiers de domaine

## Contexte

#261 avait classé, sans rien modifier, le contenu à trier dans quatre
fichiers de domaine (`docs/contexte/ia_anti_don_joker.md`,
`coups_rates_bilan.md`, `description_coup.md`, `pistes_amelioration_ia.md`)
et vérifié que les dix sous-sections de récit de coups ratés/pas-à-pas sont
intégralement couvertes par une entrée `CHANGELOG.md` dédiée. #262 applique
le tri : on garde l'état actuel et les règles (y compris les limites
connues), on retire le récit déjà couvert par un changelog en le
remplaçant par un pointeur.

## 1. Tailles avant/après (`wc -c`)

| Fichier | Avant | Après | Variation | Objectif indicatif |
|---|---:|---:|---:|---:|
| `ia_anti_don_joker.md` | 51 097 | 41 575 | −18,6 % | ≈ 40 000 |
| `coups_rates_bilan.md` | 36 157 | 10 399 | −71,2 % | ≈ 12 000 |
| `description_coup.md` | 30 097 | 12 585 | −58,2 % | ≈ 15 000 |
| `pistes_amelioration_ia.md` | 36 647 | 29 702 | −19,0 % | ≈ 27 000 |
| **Total** | **153 998** | **94 261** | **−38,8 %** | |

## 2. `ia_anti_don_joker.md`

- §1 réduit à un pointeur de quelques lignes (récit de #252/#253/#254) →
  CHANGELOG.md, issues #252/#253/#254.
- §2 : paragraphe de récit « Changements par rapport à #252 » réduit à une
  phrase.
- §9 : chiffres de mesure figés retirés (dupliqués avec le récit de #254),
  commandes « Campagnes appariées à lancer par Alain » conservées telles
  quelles → CHANGELOG.md, issues #253/#254.
- §10 : description de l'option de test conservée, sous-paragraphe
  « Mesure » retiré → CHANGELOG.md, issue #256.
- §11 (diagnostic de lenteur #257) réduit à une note de 5 lignes, renvoyant
  à `solveur_expert.md` §8ter (modèle lexicographique, déjà documenté),
  `solveur_verification_exacte.md` §18 (limites de volume de calcul) et
  CHANGELOG.md, issue #257.

## 3. Dix sous-sections de récit → règle + pointeur changelog

Chacune des dix sous-sections (`coups_rates_bilan.md` 11bis→11sexies,
`description_coup.md` 12bis→12sexies) est conservée comme sous-section
séparée, réduite à sa règle actuelle (formulations reprises du rapport de
#261) plus un pointeur `CHANGELOG.md` :

| Sous-section | Issue | Règle conservée (résumé) |
|---|---|---|
| 11bis | #193 | Poses sous-optimales, budget nécessaire, vérification croisée exhaustive, réserve vs coup raté, cas de référence non écrasés. |
| 11ter | #196 | Description française + mesure simple/complexe du coup proposé, relabellisation anti-artefact. |
| 11quater | #198 | Classement par taille (petit/moyen/grand) + filtre `--depuis`. |
| 11quinquies | #201 | `nb_tuiles_jouees` par différence de main réelle ; **limite connue du bug de la règle de mise initiale conservée** (voir point 5 ci-dessous). |
| 11sexies | #202 | Regroupement des journaux d'une partie reprise par `partie_id` ; mise initiale lue dans le journal, jamais supposée. |
| 12bis | #197 | Tuiles identiques interchangeables, cycles traités en bloc, repli d'urgence. |
| 12ter | #198 | Accord féminin de « suite », suppression des pronoms genrés. |
| 12quater | #207 | Pas-à-pas condensé (réservé à `coups_rates.py` depuis #214), mesure de taille, bascule Avant/Après — **affirmation « condensé = défaut » corrigée** (voir point 6). |
| 12quinquies | #209 | Surbrillance forte `.tuile-pas-active`. |
| 12sexies | #214 | Mode « modification » devenu le défaut affiché, repères Départ/Arrivée, bascule Avant/Après corrigée. |

## 4. `coups_rates_bilan.md` — options CLI consolidées

La liste complète des options de `scripts/analyser_coups_rates.py`
(auparavant répartie entre §11 et ses sous-sections) est désormais
rassemblée en un seul endroit, dans le bullet « Script CLI, options
complètes » de §11, avec un renvoi vers la sous-section qui introduit
chaque option.

## 5. Bug de la règle de mise initiale (11quinquies) — vérifié par lecture du code, NON corrigé

Lecture de `src/rummikub/moteur/partie.py::jouer_tour`/`_points_tuiles_posees` :
le bug signalé par #201 est **toujours présent**. `_points_tuiles_posees`
additionne la valeur de CHAQUE id de `ids_tuiles_posees` trouvé dans une
combinaison valide du nouveau plateau, sans distinguer une tuile venue de
la main d'une tuile simplement déplacée sur le plateau — un joueur qui
réarrange le tapis avant sa propre mise initiale peut donc voir ces points
compter à tort vers le minimum requis. Non corrigé dans cette issue
(demande explicite : « sans le corriger »).

## 6. `description_coup.md` 12quater — correction de l'affirmation fausse

Le texte affirmait que le mode condensé (#207) serait le mode par défaut.
C'est faux depuis #214 (12sexies) : le mode affiché par défaut est
`"modification"`. 12quater corrigé en conséquence (le condensé n'est plus
décrit que comme le mode réservé à `coups_rates.py`), 12sexies relu en
regard et sa formulation alignée.

## 7. `pistes_amelioration_ia.md`

- Tableau des hypothèses H1-H8 conservé, reformaté en tableau avec une
  colonne Statut (« testée et retirée », « jamais testée », « comportement
  par défaut ») — correspondance stratégie/issue tirée du code et de
  l'archive.
- « Protocole d'expérience prévu » (périmé : déjà exécuté et conclu, voir
  l'archive) retiré.
- Archive des stratégies multi-tours de Champion du Monde réduite à une
  synthèse (conclusion, chiffres clés, tag git `archive-strategies-champion`)
  → CHANGELOG.md, issues #235/#236.
- Liste des sources conservée intégralement (non dupliquée ailleurs),
  reformatée à une ligne par source (certaines lignes regroupaient
  auparavant plusieurs sources).

## 8. Renvois « §X de CONTEXTE.md » devenus caducs — réparés

Les 7 renvois signalés par #261 (6 dans `ia_anti_don_joker.md`, 1 dans
`pistes_amelioration_ia.md`) ont été corrigés vers le bon fichier de
domaine :

- §8bis → `solveur_expert.md` §8bis (économie de jokers, critère de
  départage).
- §8 → `joker_tactiques.md` §8 (détection des jokers libérables).
- §3bis (×3 occurrences) → `moteur_regles.md` §3bis (manches multiples,
  blocage).
- §9/§16 → `scripts_simulation.md` §9 / `niveaux_ia_calibrage.md` §16
  (option de calibration).
- `pistes_amelioration_ia.md`, « CONTEXTE.md §7 » : ce renvoi (vers la
  règle front-end de #260, sans rapport avec le sujet de la phrase — pas
  de campagne longue rejouée par l'agent) a été reformulé sans numéro de
  section précis, faute d'équivalent exact parmi les cinq fichiers listés
  par l'issue ; signalé ci-dessous comme point laissé à la décision
  d'Alain.

Vérification : plus aucun renvoi `CONTEXTE.md` (numéroté ou non) ne
subsiste dans aucun fichier de `docs/contexte/` après le tri — voir le
rapport de clôture pour le détail de la vérification et des quelques
renvois `(§N)` bruts restants dans d'AUTRES fichiers de domaine (hors
périmètre de cette issue).

## 9. Renvois croisés coups_rates_bilan.md ↔ description_coup.md

Vérifiés après raccourcissement : 11ter → `description_coup.md` §12 ;
11quater → `description_coup.md` §12ter ; 12ter/12quater →
`coups_rates_bilan.md` §11quater. Tous valides.

## Fichiers touchés

`docs/contexte/ia_anti_don_joker.md`, `docs/contexte/coups_rates_bilan.md`,
`docs/contexte/description_coup.md`, `docs/contexte/pistes_amelioration_ia.md`.
Aucun autre fichier modifié (ni `CONTEXTE.md`, ni code Python, ni test, ni
`README.md`).

## Points laissés à la décision d'Alain

1. Le renvoi « CONTEXTE.md §7 » de `pistes_amelioration_ia.md` ne
   correspondait déjà à aucune section pertinente au moment de sa
   rédaction (#226) — reformulé sans pointeur précis ; à corriger
   vous-même si vous identifiez la règle visée.
2. D'autres renvois bruts `(§N)` (sans mention explicite de
   `CONTEXTE.md`) subsistent dans des fichiers de domaine HORS périmètre
   de cette issue : `scripts_simulation.md:19` (« §7 »),
   `architecture.md:41,52` (« §9 », « §16 »), `solveur_expert.md:67`
   (« §8 »), `niveaux_ia_calibrage.md:190` (« §8 ») — pointent eux aussi
   vers des sections qui ont changé de fichier depuis #260. Non corrigés
   ici (hors des 4 fichiers listés par l'issue).
3. Le bug de la règle de mise initiale (11quinquies, §5 ci-dessus) reste
   non corrigé, comme demandé — à traiter dans une future issue dédiée si
   vous le confirmez.
