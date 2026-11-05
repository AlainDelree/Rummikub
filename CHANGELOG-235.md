# Issue #235 — Retirer le niveau Champion du Monde et le code des stratégies multi-tours

## Contexte
Douze configurations de 1 000 parties (Expert contre Champion du Monde, avec
et sans chacune des cinq stratégies multi-tours : `reserve_tuile`,
`retenue_debut`, `petits_chiffres`, `chances_prochain_tour`,
`placement_joker`) n'ont montré AUCUN effet mesurable : le taux de victoire de
Champion du Monde reste entre 49,8 % et 52,1 % pour toutes les configurations
(marge ±3,1 pt). Décision d'Alain : supprimer le niveau pour garder une
échelle cohérente, et retirer le code plutôt que de le laisser désactivé — il
reste récupérable dans l'historique au tag git
`archive-strategies-champion` (pointe sur le commit b7214b2).

## Modifications
- **Échelle des niveaux** : `config.NIVEAUX` passe de six à cinq niveaux
  (Débutant, Facile, Intermédiaire, Avancé, Expert). Compatibilité :
  `moteur/niveaux.niveau_compatible()` remplace un nom de niveau
  « Champion du Monde » (réglage, partie sauvegardée ou journal antérieur)
  par « Expert » avant toute résolution de bridage ou de fonction de jeu —
  jamais d'erreur. Mise à jour de l'écran d'accueil (bouton, badge, CSS) et
  de `moteur/ia.py` (`NIVEAUX_IA`, `jouer_ia`).
- **Retrait du code des stratégies multi-tours** (`moteur/niveaux.py`,
  `moteur/ia.py`, `moteur/solveur_exact.py`) : registre `Strategie`/
  `STRATEGIES`, champs de `Bridage` et constantes propres à chaque stratégie,
  fonctions `_appliquer_*`/`_coup_sans_joker_chevalet`/
  `_peut_tenter_garde_joker`, paramètres `max_tuiles_posees`/
  `valeur_max_petits` du solveur exact. `moteur/verification_finition.py`
  perd uniquement la variante « garder un joker » (`idx_garde_joker`,
  `APPLIQUEE_GARDE_JOKER`) — la vérification de finition elle-même reste
  active pour Expert, inchangée.
- **Modules et scripts supprimés** : `moteur/sorties.py`, `moteur/inconnues.py`
  (n'étaient utilisés que par les stratégies de Champion), `scripts/
  matrice_strategies.py`, `scripts/lancer_matrice_windows.ps1`.
- **Outils de mesure nettoyés, pas supprimés** : `scripts/
  comparer_niveaux_ia.py` perd ses options/compteurs de stratégies
  (`--sans-verif-finition`, `--sans-garde-joker`, `--strategies-champion`,
  `--sans-strategie` et les compteurs associés) mais garde ses exports, le
  budget du solveur réglable et le garde-fou solveur exact ;
  `scripts/echelle_niveaux.py`, `scripts/_verif_solveur_exact.py`,
  `scripts/comparer_campagnes_appariees.py`, `scripts/analyser_phases.py`,
  `scripts/profil_joueur.py`, `scripts/simulation_ia.py`,
  `scripts/generer_corpus_positions_222.py`, `scripts/analyser_coups_rates.py`
  perdent leurs mentions de Champion du Monde dans la documentation/les
  commentaires, sans changement de comportement.
- **Tests supprimés** (code testé disparu) : `test_sorties.py`,
  `test_inconnues.py`, `test_ia_reserve_tuile.py`, `test_ia_retenue_debut.py`,
  `test_ia_petits_chiffres.py`, `test_ia_chances_prochain_tour.py`,
  `test_ia_placement_joker.py`, `test_registre_strategies.py`,
  `test_matrice_strategies.py`, `test_option_strategies_champion.py`.
- **Tests adaptés** : `test_niveaux.py` (échelle à cinq niveaux, test de
  compatibilité « Champion du Monde » → Expert), `test_verification_finition.py`
  (retrait des tests « garder un joker », reste sur Expert),
  `test_comparer_niveaux_ia_rapport.py`, `test_garde_fou_scripts_tous.py`,
  `test_verif_solveur_exact.py`, `test_playwright_accueil_reglages.py`
  (bouton Champion retiré).
- **CONTEXTE.md** : la brique « Deux tours » (#221/#225), la brique
  « Inconnues » (#219) et les cinq stratégies (#228 à #232) sont condensées
  en une seule section d'archive (§13 « Archive : stratégies multi-tours de
  Champion du Monde (nov. 2026) ») qui garde les idées essayées, la méthode
  de mesure, les chiffres ci-dessus, la conclusion, l'intuition d'Alain et le
  moyen de retrouver le code (`git show`/`git checkout
  archive-strategies-champion:<chemin>`). §16 (échelle) et les sections
  générales sont mises à jour pour cinq niveaux.

## Non-régression
Sur les 380 positions du corpus de l'issue #222, avec une graine (`12345`)
et un budget de solveur fixes (1,5 s, le budget de production), les coups
choisis par les cinq niveaux restants sont identiques avant et après ce
retrait sur 1898 des 1900 décisions (380 positions × 5 niveaux). Les 2
écarts restants (positions #356 et #372 du corpus, toutes deux marquées
« chargées », 54 et 76 tuiles au plateau) sont des artefacts du budget de
temps du solveur exact pendant une longue campagne séquentielle : rejoués
isolément, chacun des deux codes (avant et après) donne le MÊME résultat,
stable sur plusieurs répétitions — l'écart ne vient donc ni du retrait du
niveau ni du retrait des stratégies, mais de la variation du temps machine
réellement disponible au moment précis où cette position a été résolue au
sein d'une longue campagne.

## Nombre de tests
556 tests avant ce retrait, 428 après (−128 ; essentiellement les 10 fichiers
de tests supprimés ci-dessus) — baisse attendue, le code testé a disparu.

## Points d'attention
- `moteur/verification_finition.py` reste dans le dépôt : seule la variante
  « garder un joker » (Champion seul) en a été retirée, pas le module
  lui-même (actif pour Expert depuis #221).
- Les définitions de Débutant, Facile, Intermédiaire, Avancé et Expert
  n'ont pas été modifiées — seul le code devenu mort (registre de
  stratégies, modules Champion-seul) a été retiré.
