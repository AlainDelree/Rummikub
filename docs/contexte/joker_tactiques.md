# Tactiques de récupération/libération de joker de l'IA (niveau Avancé)

## 8. Tactiques de récupération/libération de joker de l'IA (`moteur/ia.py`)

> Liste à tenir à jour par toute future issue qui ajoute ou modifie une
> tactique de joker (objectif : pouvoir un jour revoir les niveaux de
> difficulté de l'IA — jugés trop faibles actuellement — une fois
> l'ensemble des tactiques couvert).

> **Depuis #186, cette liste ne décrit plus que le niveau Avancé.** Expert
> ne les utilise plus comme chaîne de tactiques principale : il appelle le
> solveur de réarrangement global (§8bis), nettement plus fort, et ne se
> replie sur le comportement d'Avancé ci-dessous que si ce solveur dépasse
> son budget de temps par tour (ou échoue à trouver quoi que ce soit).

**Implémentées :**

- **Échange direct** (#148) — `_jokers_recuperables` : un joker posé dans
  une suite ou un groupe est remplacé par la tuile réelle identique déjà
  en main (même valeur/couleur pour une suite ; même valeur + couleur
  absente du groupe pour un groupe). Validité et points de la combinaison
  inchangés ; le joker est libéré pour un usage ailleurs sur le plateau.
- **Détachement en bout de suite** (#150) — `_jokers_detachables_par_extension` :
  un joker à une extrémité d'une suite est détaché *sans* tuile de
  remplacement, quand une tuile de la main jouée à l'extrémité OPPOSÉE
  allonge la portion de tuiles réelles restante à au moins 3 — celle-ci
  reste alors valide seule une fois le joker retiré.
- **Combinaison de plusieurs libérations dans le même coup** (#169) —
  `_liberations_possibles` / `_meilleur_coup_liberations` /
  `_coup_depuis_liberations` : les deux mécanismes ci-dessus sont
  recherchés simultanément sur des combinaisons distinctes du plateau,
  pour récupérer plusieurs jokers en un seul coup plutôt qu'un seul à la
  fois (corrige un bug où le second joker récupérable d'un même tour était
  systématiquement ignoré). Limite assumée : deux libérations sur la MÊME
  combinaison du plateau (ex. deux jokers dans une même suite) ne sont pas
  combinées — cas rare, laissé de côté pour borner la complexité.
- **Libération par réduction de groupe de 4 à 3** (#180) —
  `_jokers_liberables_par_reduction_groupe4` : un groupe de 4 tuiles de
  couleurs distinctes — déjà présent sur le plateau, ou complété à 4 par
  une tuile de la main de la 4e couleur manquante — perd une de ses
  tuiles RÉELLES (le groupe réduit à 3 reste valide) ; cette tuile libérée
  sert alors de remplacement pour un échange direct avec un joker
  récupérable ailleurs sur le plateau (même critère que
  `_jokers_recuperables`). Le joker ainsi libéré doit être rejoué dans le
  même tour. Intégré au même format unifié que #169
  (`_liberations_possibles`), qu'il a fallu généraliser pour supporter des
  libérations modifiant DEUX combinaisons du plateau à la fois (le groupe
  réduit et la combinaison du joker échangé), au lieu d'une seule pour les
  deux mécanismes précédents. À ne pas confondre avec la « réduction de
  groupe de 4 à 3 (joker retiré) » ci-dessous : ici on retire une tuile
  RÉELLE pour s'en servir comme remplaçante ailleurs, jamais le joker
  lui-même sans remplacement.
- **Scission en milieu de suite** (#181) — extension de `_coup_scission`
  (tuile réelle) et `_jokers_liberables_par_scission_milieu` (joker) :
  pour une suite d'au moins 7 tuiles, retirer une tuile intérieure (ni en
  tête ni en queue) peut laisser DEUX suites valides (chacune d'au moins 3
  tuiles, jokers éventuels compris) à la place de l'unique suite
  d'origine — une combinaison devient deux. Cas tuile réelle : la tuile
  libérée forme un nouveau groupe avec des tuiles de la main, comme pour
  le cas bout de suite déjà géré par `_coup_scission` (comportement
  inchangé pour ce cas bout). Cas joker : intégré au même format unifié
  que #169/#180 (`_liberations_possibles`), qu'il a fallu étendre pour
  qu'une libération puisse remplacer une combinaison du plateau par DEUX
  (au lieu de la modifier en place ou d'en modifier deux existantes) tout
  en gardant la détection de conflit (combinaisons touchées, tuiles de la
  main consommées) correcte ; le joker ainsi libéré doit être rejoué dans
  le même tour.
- **Réduction de groupe de 4 à 3 (joker retiré)** (#183) —
  `_jokers_liberables_par_groupe4_sans_remplacement` : un groupe de 4
  tuiles du plateau contenant un joker (3 tuiles réelles de couleurs
  distinctes + 1 joker) reste un groupe valide une fois le joker retiré —
  *sans* aucune tuile de remplacement, contrairement à l'échange direct
  (#148) qui exige une tuile identique en main, et à #180 qui retire une
  tuile RÉELLE (jamais le joker) pour l'utiliser ailleurs. Intégré au même
  format unifié que #169/#180/#181 (`_liberations_possibles`) ; le joker
  ainsi libéré doit être rejoué dans le même tour. Ne s'applique qu'aux
  groupes de 4 : un groupe de 3 avec joker (2 réelles + 1 joker) ne peut
  pas perdre son joker sans tomber sous le minimum de 3 tuiles.

**Identifiées mais pas encore implémentées pour Avancé :**

- **Démantèlement complet d'une courte suite contenant un joker** (#175) :
  retirer SES DEUX tuiles réelles (pas une seule comme dans les tactiques
  ci-dessus), chacune recombinée avec des tuiles de la main pour former
  deux NOUVELLES combinaisons (groupes ou suites) ailleurs sur le
  plateau — le joker est ainsi isolé et libéré sans qu'aucune tuile ne le
  remplace directement. Généralisable au cas sans joker. Nettement plus
  complexe que les tactiques ci-dessus — recherche de recombinaison
  globale sur plusieurs combinaisons du plateau, pas un simple motif
  local. Avancé ne le trouve toujours pas (tactiques locales inchangées,
  voir `test_avance_ne_demantele_pas_une_courte_suite_avec_joker`) ;
  **Expert le trouve désormais**, via le solveur de réarrangement global
  (§8bis) — voir `test_expert_demantele_completement_une_courte_suite_
  avec_joker` dans `tests/test_ia.py`.

Note : `_coup_scission` (`ia.py`) couvre le cas « tuile réelle » (bout ou
milieu de suite, #181) ; elle n'est plus limitée aux seuls bouts de suite,
mais reste étrangère aux jokers (dont la libération, bout ou milieu, passe
par `_liberations_possibles`).

**Règle de l'ouverture (#273)** : toutes les tactiques de ce paragraphe
(`_liberations_possibles`, `_coup_scission`) sont déjà gardées par
`mise_initiale_faite` (retournent `None`/rien tant que la mise initiale
n'est pas faite) — aucune ne pouvait déjà toucher le plateau avant
l'ouverture. Le seul chemin fautif identifié par #273 était `_coup_maximal`
(extensions du plateau après une ouverture réussie, via `_appliquer_
extensions`), désormais restreint aux seules combinaisons posées CE
tour-ci avant que la mise initiale ne soit faite — voir
`docs/contexte/moteur_regles.md`.

