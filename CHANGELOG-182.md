# Issue #182 — Suite #181 : Tests de non-régression de la scission en bout de suite

Suite #181 : la scission en BOUT de suite (`_coup_scission`, cas le plus
fréquent en jeu) n'était couverte par aucun test unitaire — seuls des
scripts de simulation historiques (#134) la vérifiaient, et son
équivalence avec l'ancien comportement n'avait été validée que par
relecture du code lors de la généralisation à la scission en milieu de
suite (#181).

Dix tests ajoutés à `tests/test_ia.py` (Avancé et Expert), figeant le
comportement actuel sans aucun changement de code hors tests :

- **Scission en fin de suite** : suite rouge 4-5-6-7 + un 7 bleu et un 7
  jaune en main → détachement du 7 rouge, 4-5-6 reste valide, groupe de
  trois 7 posé.
- **Scission en début de suite** : même principe sur la première tuile
  (suite rouge 4-5-6-7 + un 4 bleu et un 4 jaune) → 5-6-7 reste valide,
  groupe de trois 4 posé.
- **Suite trop courte (3 tuiles)** : aucun détachement en bout n'est
  proposé, la partie restante (2 tuiles) étant invalide.
- **Tuile de bout qui est un joker** : non-régression — un joker en bout
  de suite n'est pas détaché par ce mécanisme (cf. `CONTEXTE.md` §8).
- **Mise initiale non faite** : aucune scission n'est proposée.

Tous les tests passent du premier coup sans aucune modification du code
de l'IA : le comportement actuel de la scission en bout de suite est
conforme à la description de l'issue, aucune divergence à signaler.

`tests/test_ia.py` : +192 lignes, 10 nouvelles fonctions de test + 5
fonctions d'état auxiliaires. Suite complète : 54 tests passés.
