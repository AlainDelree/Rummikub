# Issue #185 — Bilan des parties jouées : synthèse par niveau d'IA à partir des journaux de parties

Alain voulait pouvoir rejouer quelques parties contre les niveaux d'IA les
plus forts et retrouver ensuite, sans tenir de comptes à la main, ce que ces
parties ont donné (victoires, marge, comportement de l'IA) afin de recaler
les niveaux par rapport à un joueur humain.

## État des lieux

Le jeu dispose déjà d'un journal de parties optionnel
(`persistance/journal.py`, issues #97/#99), activable via la clé
`log_parties` de `config.json` (défaut `False`, aucun overhead). Il
enregistre chaque coup (mains, plateau, pioche) mais ne portait ni le niveau
des joueurs, ni l'auteur réel d'une décision IA (le champ générique
`"tour_ia"` ne distinguait pas pose/pioche/passe), ni aucune marque de fin de
partie — impossible donc d'en tirer un bilan sans tout rejouer à la main.
Décision : compléter ce journal existant plutôt que d'en créer un second.

## Journal complété (`persistance/journal.py`, `ui/api.py`)

- En-tête `joueurs` : désormais `{"nom", "est_ia", "niveau"}` par joueur
  (au lieu du seul nom).
- Chaque action porte maintenant `auteur_index` (qui a décidé — distinct de
  `joueur_actuel`, déjà avancé au joueur suivant au moment de l'écriture),
  `nb_tuiles_posees`, `termine` et `gagnant_index`.
- Libellés d'action canonisés côté `api.py` : le tour IA journalisait jusqu'ici
  un `"tour_ia"` générique ; il journalise maintenant la décision réelle
  (`"pose"|"pioche"|"passe"`), alignée sur celle des coups humains (le coup
  humain `"fin_de_tour"` est renommé `"passe"` pour la même raison). Une
  partie dont la dernière action n'a pas `termine: True` est reconnue comme
  abandonnée en cours (ou toujours en cours) et exclue du bilan — sans
  mécanisme de détection séparé à maintenir.
- Rétro-compatibilité : les journaux écrits avant #185 (joueurs = liste de
  noms, pas de `termine`) restent lisibles ; `bilan.py` les exclut proprement
  du bilan (faute de ces champs) plutôt que de planter.
- **`moteur/ia.py` non modifié**, conformément à la consigne.

## Bilan (`persistance/bilan.py` + `scripts/bilan_parties.py`)

- `persistance/bilan.py` : module pur (aucune dépendance pywebview) —
  lecture tolérante des journaux (`charger_journal`, `extraire_partie`,
  dédoublonnage des décisions annulées/rejouées sur un même tour) et calcul
  du bilan par niveau d'IA (`calculer_bilan`) : parties, victoires/défaites
  humain, taux de victoire, marge moyenne (tuiles restantes de l'IA à la
  victoire humaine / de l'humain à sa défaite), tours moyens par partie, part
  des tours IA en pioche/passe plutôt qu'en pose et répartition
  début/milieu/fin de partie. Filtres `nom_joueur`, `depuis`, `jusqu`.
- `scripts/bilan_parties.py` : script CLI (`python scripts/bilan_parties.py
  [--joueur NOM] [--depuis AAAA-MM-JJ] [--jusqu AAAA-MM-JJ] [--dossier
  CHEMIN]`), sur le même modèle que `scripts/analyser_partie.py` existant.
  Affiche le bilan par niveau d'IA, triés selon `config.NIVEAUX`.

## Vérifications

- `scripts/analyser_partie.py` adapté pour afficher proprement le nouveau
  format `joueurs` (liste de dicts) comme l'ancien (liste de noms).
- Performance : avec `log_parties` désactivé (réglage par défaut), aucun
  changement — `logger_action` retourne toujours immédiatement (mesuré :
  0,12 ms pour 78 coups, contre ~2,4 s si activé, un coût déjà présent avant
  #185 et indépendant de cette issue). Avec `log_parties` activé, le delta dû
  aux 4 champs ajoutés par #185 est non mesurable : 2182 ms (après #185) vs
  2399 ms (avant #185) pour les mêmes 78 coups — la sérialisation complète de
  l'état à chaque coup, déjà existante, domine entièrement.
- `tests/test_bilan.py` (17 tests nouveaux) : lecture de journaux valides/
  abandonnés/anciens/corrompus, dédoublonnage après annulation, calcul du
  bilan (victoire/défaite, marges, tours moyens, part pioche/passe et son
  répartition, filtres nom/période), et un test d'intégration qui fait
  vraiment jouer une partie via le moteur (`creer_partie`/`piocher` jusqu'à
  épuisement de la pioche) et vérifie que `journal.logger_action` et
  `bilan.py` restent d'accord sur le format.
- `CONTEXTE.md` : nouvelle section §9 (journal + bilan), arborescence et
  compteur de tests mis à jour (75 tests passent).
- Suite complète : `pytest -q` → **75 passed**.
