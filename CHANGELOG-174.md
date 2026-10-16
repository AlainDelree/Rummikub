# Issue #174 — CONTEXTE.md : liste des tactiques de récupération de joker de l'IA

- Ajout d'une section **§8. Tactiques de récupération/libération de joker de
  l'IA** dans `CONTEXTE.md`, recensant :
  - les tactiques déjà implémentées, avec issue d'origine et fonction
    correspondante : échange direct (#148, `_jokers_recuperables`),
    détachement en bout de suite (#150, `_jokers_detachables_par_extension`),
    combinaison de plusieurs libérations dans le même coup (#169,
    `_liberations_possibles`/`_meilleur_coup_liberations`/`_coup_depuis_liberations`) ;
  - deux cas identifiés en discussion mais pas encore implémentés : la
    réduction d'un groupe de 4 à 3 (retrait du joker sans tuile de
    remplacement) et la scission en milieu de suite (extension de
    `_coup_scission`, qui ne traite aujourd'hui que le bout de suite et
    jamais un joker).
- But : disposer d'une base à jour pour une future révision des niveaux de
  difficulté de l'IA une fois l'ensemble des tactiques couvert.
- Pointeur ajouté dans la description de `moteur/ia.py` (§2) vers la
  nouvelle section §8.
- Aucun changement de code (`ia.py` inchangé) : tâche purement documentaire.
