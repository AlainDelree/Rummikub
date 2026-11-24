# Issue #260 — Suite #259 : restructurer CONTEXTE.md en fichiers de domaine avec index

## Contexte

#259 avait montré que `CONTEXTE.md` (232 618 caractères) était presque
entièrement invisible pour CCL, qui n'en reçoit que les 4 000 premiers
caractères. #260 applique le découpage validé par #259 : extraction
mécanique des sections vers `docs/contexte/<domaine>.md`, puis réécriture
de `CONTEXTE.md` en un index tenant dans la limite de 4 000 caractères.

## 1. Onze nouveaux fichiers de domaine créés

Chaque section a été déplacée par extraction mécanique des lignes (`sed`),
sans réécriture ni retranscription, puis vérifiée section par section
(taille avant/après, voir le rapport de clôture) :

- `docs/contexte/architecture.md` ← §1, §2
- `docs/contexte/moteur_regles.md` ← §3, §3bis, §4
- `docs/contexte/tests_frontend.md` ← §6, §7
- `docs/contexte/joker_tactiques.md` ← §8
- `docs/contexte/solveur_expert.md` ← §8bis, §8ter, §8quater, §8bis-bis, §17
- `docs/contexte/solveur_verification_exacte.md` ← §14, §15, §18
- `docs/contexte/coups_rates_bilan.md` ← §10, §11 (avec ses sous-sections)
- `docs/contexte/description_coup.md` ← §12 (avec ses sous-sections)
- `docs/contexte/scripts_simulation.md` ← §9
- `docs/contexte/niveaux_ia_calibrage.md` ← §16
- `docs/contexte/pistes_amelioration_ia.md` ← §13 en entier

Chaque nouveau fichier a reçu un titre `#` minimal (seul ajout hors
extraction mécanique) et a été référencé dans l'index de `CONTEXTE.md`.

## 2. §19 fusionné dans `docs/contexte/ia_anti_don_joker.md`, sans duplication

Le paragraphe principal de §19 était déjà intégralement couvert par les
sections 1 à 8bis du fichier de domaine (définitions, arbre de décision,
paramètres) : il n'a donc pas été recopié. Seul le contenu non dupliqué —
le bloc « Campagnes appariées à lancer par Alain » (commandes
`comparer_niveaux_ia.py` complètes) — a été déplacé dans le fichier de
domaine, remplaçant le renvoi circulaire « voir CONTEXTE.md §19 » sous son
§9. Un second renvoi interne dangling (« voir CONTEXTE.md §19 ») a été
corrigé en renvoi local.

## 3. Corrections de contenu (limitées à celles demandées par l'issue)

- §5 « État des issues » supprimé en entier, sans fichier de remplacement
  (contenu périmé : liste de statuts figée au 2026-07-28).
- Dans `niveaux_ia_calibrage.md` (ex-§16) : la mention du tableau
  « Expert : exact complet + multi-tours PARTIELLES (à venir) » corrigée
  — ce code a été écrit puis retiré sans effet mesurable (issues #235 et
  #236).
- Dans `niveaux_ia_calibrage.md` : les sous-sections « Recalibrage #216 »
  et « Recalibrage #217 » condensées en un seul état final (réglages
  retenus dans `moteur/niveaux.py`), le récit complet (mesures
  intermédiaires, anomalies, outils) étant déjà couvert par `CHANGELOG.md`
  (issues #216 et #217).

Rien d'autre n'a été modifié dans le contenu déplacé.

## 4. `CONTEXTE.md` réécrit (3 699 caractères, mesuré `wc -m`)

Nouveau squelette : règles impératives (jamais de `git push`, commit de
sauvegarde `--allow-empty` avant modification, règle de vérification
front-end de l'ex-§7 — jamais l'application pywebview réelle, toujours
Playwright sur le fichier HTML avec mock de l'API), architecture résumée,
conventions clés, puis index de tous les fichiers de domaine (nouveaux et
existants) avec le moment où lire chacun.

## 5. Hors périmètre de cette issue (comme demandé)

- Aucun code Python, aucun test, aucun `README.md` modifié : les renvois
  `CONTEXTE.md §N` dans `src/` et `tests/` restent à mettre à jour dans une
  issue séparée après fusion.
- Aucun fichier `configs/*.conf` modifié.
