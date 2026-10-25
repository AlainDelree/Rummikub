# Issue #180 — Suite #169 : IA : libérer une tuile d'un groupe de 4 (réduit à 3) pour l'échanger contre un joker ailleurs sur le plateau

Suite de #148 (échange direct), #150 (détachement en bout de suite) et
#169 (combinaison de plusieurs libérations dans un même coup) : un
quatrième cas, constaté en jeu par Alain, n'était couvert par aucun des
trois. Exemple observé : un groupe de trois 11 (bleu, jaune, noir) devient
un groupe de quatre en y ajoutant le 11 rouge de la main ; le 11 noir
libéré (groupe restant bleu/jaune/rouge, valide) correspond exactement au
joker d'une suite noire (10, joker, 12, 13) ailleurs sur le plateau. L'IA
posait le 11 rouge et s'arrêtait là, sans aller chercher ce joker.

À ne pas confondre avec la « réduction de groupe de 4 à 3 (joker retiré) »
listée comme non implémentée dans `CONTEXTE.md` §8 : celle-là retire un
JOKER d'un groupe de 4 sans tuile de remplacement. Ici, on retire une
tuile RÉELLE pour s'en servir comme remplaçante ailleurs — la première
reste hors périmètre de cette issue.

## Ajout

`src/rummikub/moteur/ia.py` :

- `_jokers_liberables_par_reduction_groupe4(plateau, chevalet)` : pour
  tout groupe de 4 tuiles du plateau — existant, ou complété à 4 par une
  tuile de la main de la 4e couleur manquante — détecte si retirer l'une
  de ses tuiles réelles laisse un groupe de 3 valide, et si cette tuile
  correspond exactement à un joker récupérable par échange direct ailleurs
  sur le plateau (même critère que `_jokers_recuperables`, désormais
  factorisé dans un helper commun `_tuile_correspond_au_joker`).
- `_liberations_possibles` intègre cette troisième tactique à côté des
  deux précédentes, dans la même recherche combinatoire (#169) : plusieurs
  libérations — de n'importe quelle combinaison des trois mécanismes —
  restent possibles dans le même tour.
- Généralisation nécessaire du format unifié de #169 : une libération ne
  modifiait jusqu'ici qu'UNE combinaison du plateau (`combi_index` /
  `tuile_consommee` / `appliquer(combo)`). La réduction de groupe en
  modifie DEUX à la fois (le groupe réduit et la combinaison du joker
  échangé) ; le format passe donc à `combis` (liste), `tuiles_consommees`
  (liste, éventuellement vide quand le groupe était déjà à 4 et qu'aucune
  tuile de main n'est nécessaire) et `appliquer(plateau)` qui modifie en
  place les combinaisons concernées. `_coup_depuis_liberations` et
  `_meilleur_coup_liberations` adaptés en conséquence ; les deux tactiques
  précédentes (#148, #150) sont inchangées fonctionnellement, seul leur
  format d'enveloppe change.
- Limité à Avancé/Expert via `_meilleur_coup_avec_joker` (déjà le point
  d'entrée commun), comme pour #148/#150/#169 — aucun changement requis
  dans `jouer_niveau_avance`/`jouer_niveau_expert`.

`CONTEXTE.md` §8 mis à jour : nouvelle tactique ajoutée aux
« Implémentées » (#180), et « Réduction de groupe de 4 à 3 » renommée
« (joker retiré) » dans les « Identifiées mais pas encore implémentées »
pour lever toute ambiguïté avec le nouveau mécanisme.

## Tests

`tests/test_ia.py` : trois nouveaux tests reprenant l'exemple de l'issue
(groupe plateau 11 bleu/jaune/noir, suite plateau noire
10-joker-12-13, chevalet 11 rouge + 1 noir + 2 noir) :

- `test_avance_libere_une_tuile_de_groupe4_pour_echanger_un_joker` et
  `test_expert_libere_une_tuile_de_groupe4_pour_echanger_un_joker` :
  l'IA Avancé/Expert complète le groupe à 4 avec le 11 rouge, échange le
  11 noir libéré contre le joker noir, et rejoue ce dernier dans une
  nouvelle suite 1-2-3(joker) noire — seule façon de poser les 3 tuiles de
  la main dans ce scénario.
- `test_facile_ne_libere_pas_de_tuile_de_groupe4` : Facile reste inchangé
  (pose seulement le 11 rouge, sans toucher au joker).

Tous les tests existants (#148, #150, #169) passent sans modification.
Suite complète : 38 tests, tous au vert (`pytest -q`).
