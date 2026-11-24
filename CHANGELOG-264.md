# Issue #264 — Suite #263 : corriger les derniers renvois « CONTEXTE.md §N » dans les messages affichés

## Contexte

#263 avait traité les commentaires/docstrings mais laissé volontairement de
côté les renvois situés dans le texte de messages réellement affichés
(aide CLI, messages imprimés, message d'erreur), ainsi qu'un commentaire de
test dont la cible s'est avérée mal identifiée.

## 1. Cinq renvois dans des messages affichés, réécrits avec le préfixe `docs/contexte/<fichier>.md`

- `scripts/solveur_exact.py` (`MESSAGE_INSTALLATION`) : « Voir CONTEXTE.md
  §14. » → « Voir docs/contexte/solveur_verification_exacte.md §14. »
- `scripts/match_solveurs.py` (rapport texte, deux occurrences) :
  « (réserve, joker gardé, rétention — CONTEXTE.md §13) » et « le progrès
  est à chercher dans le jeu sur plusieurs tours (CONTEXTE.md §13). » →
  `docs/contexte/pistes_amelioration_ia.md §13`.
- `scripts/analyser_coups_rates.py` (aide `--juge-exact` et message
  stderr de repli) : « CONTEXTE.md §14 » → `docs/contexte/
  solveur_verification_exacte.md §14` (deux occurrences).

Aucun test ne vérifiait le texte exact de ces cinq messages — rien à
adapter.

## 2. Commentaire de test mal ciblé (`tests/test_ia_anti_don_joker.py` ~L491)

Le renvoi « §13 » (ancienne numérotation de CONTEXTE.md, section qui a
depuis migré) correspondait en réalité à `ia_anti_don_joker.md §3`
(exception absolue du coup gagnant), pas à `pistes_amelioration_ia.md`
§13 (correspondance générale de #263) : corrigé en conséquence.

## 3. Autres renvois bruts « (§N) » trouvés et corrigés (hors périmètre strict de la demande, mais cible certaine)

Recherche de renvois « (§N) » sans préfixe `CONTEXTE.md`/`docs/contexte/`
reprenant l'ancienne numérotation globale de CONTEXTE.md ou la numérotation
interne d'un fichier de domaine déjà scindé :

- `src/rummikub/moteur/ia.py` L1146 : « (§8) » → `docs/contexte/
  joker_tactiques.md §8` (contenu : récupération de joker lors du propre
  coup de l'IA, correspond exactement à ce fichier).
- `src/rummikub/moteur/ia.py` L1697 et L1748 : « (§13) » (même ancienne
  numérotation mal reconduite que le cas 2 ci-dessus — texte identique sur
  l'exception absolue du coup gagnant) → `docs/contexte/
  ia_anti_don_joker.md §3`.
- `src/rummikub/moteur/ia.py` L1470 : « voir §5 » → `docs/contexte/
  ia_anti_don_joker.md §5` (pioche sans compteur ni limite, §5 du fichier).
- `src/rummikub/moteur/niveaux.py` L196 : « voir §4 » → `docs/contexte/
  ia_anti_don_joker.md §4` (joker non utile gardé en main).
- `tests/test_analyser_phases.py` L29 : « §13/#226 » → `docs/contexte/
  pistes_amelioration_ia.md §13/#226`.

Les occurrences restantes de « §N » sans préfixe (`niveaux.py` L29/L119,
`calibrer_niveaux.py` L237, `echelle_niveaux.py` L20/L126/L397,
`_rapport_duels.py` L38/L40) sont de la forme « issue #NNN §M » : elles
renvoient à une section numérotée de l'issue GitHub elle-même, pas à
CONTEXTE.md — laissées inchangées.

## Vérifications

`py_compile` OK sur les 7 fichiers modifiés. `pytest -m "not lent"` :
513 passés, 13 sautés, 7 échecs — tous dans
`test_playwright_accueil_reglages.py`/`test_playwright_tri_automatique.py`,
`net::ERR_NAME_NOT_RESOLVED` (réseau indisponible dans cet environnement
sandboxé), sans rapport avec les fichiers modifiés par cette issue.
Recherche finale : plus aucun « CONTEXTE.md §N » dans les fichiers Python.
