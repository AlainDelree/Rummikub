# Issue #183 — Suite #181 : IA : retirer un joker d'un groupe de 4 sans tuile de remplacement

Dernière tactique simple identifiée dans `CONTEXTE.md` §8 (« Réduction de
groupe de 4 à 3 (joker retiré) »). Un groupe de 4 tuiles du plateau
contenant un joker (3 tuiles réelles de couleurs distinctes + 1 joker)
reste un groupe valide une fois le joker retiré : les 3 tuiles réelles
suffisent seules. Contrairement à l'échange direct (#148, qui exige une
tuile identique en main) et à #180 (qui retire une tuile RÉELLE, jamais le
joker, pour l'échanger ailleurs), ici le joker est retiré sans qu'aucune
tuile ne le remplace.

## Ajout

`src/rummikub/moteur/ia.py` :

- `_jokers_liberables_par_groupe4_sans_remplacement(plateau)` (nouvelle
  fonction) : détecte, pour tout groupe de 4 tuiles du plateau, un joker
  dont le retrait laisse un groupe de 3 valide. Ne consomme aucune tuile
  du chevalet.
- `_liberations_possibles` : intègre cette nouvelle tactique au même
  format unifié que #169/#180/#181 (`combis`, `joker`, `tuiles_consommees`
  vide, `appliquer`), pour qu'elle puisse se combiner avec les autres
  libérations dans la même recherche combinatoire (`_meilleur_coup_liberations`).

Comme pour les autres tactiques de joker, limité aux niveaux Avancé et
Expert (`_meilleur_coup_avec_joker`, déjà réservé à ces niveaux) ; le
joker libéré doit être rejoué dans le même tour avec des tuiles de la main,
sinon le coup n'est pas retenu. S'applique uniquement aux groupes de 4 :
un groupe de 3 avec joker (2 réelles + 1 joker) ne peut pas perdre son
joker sans tomber sous le minimum de 3 tuiles.

## Tests

`tests/test_ia.py` :

- `test_avance_libere_un_joker_de_groupe4_sans_remplacement` /
  `test_expert_libere_un_joker_de_groupe4_sans_remplacement` : groupe
  plateau de trois 9 (rouge, bleu, jaune) + joker, chevalet avec 12 rouge
  et 12 jaune — le joker est retiré du groupe (réduit à 3, toujours
  valide) et rejoué dans un nouveau groupe de 12.
- `test_facile_ne_libere_pas_le_joker_de_groupe4` : non-régression, Facile
  ne tente pas cette tactique (aucun coup jouable avec les mêmes données).
- `test_avance_ne_reduit_pas_un_groupe_de_3_avec_joker` : un groupe de
  SEULEMENT 3 tuiles avec joker (2 réelles + 1 joker) ne peut pas perdre
  son joker — la réduction est impossible, le coup n'est pas proposé.

Tous les tests existants (48 au total sur le dépôt) passent sans
modification de leurs assertions.

## Documentation

`CONTEXTE.md` §8 : la tactique « Réduction de groupe de 4 à 3 (joker
retiré) » est déplacée des tactiques identifiées mais non implémentées
vers les tactiques implémentées, avec le numéro #183 et une description
courte. Il ne reste plus que le démantèlement complet d'une courte suite
(#175) dans les tactiques identifiées mais non implémentées.
