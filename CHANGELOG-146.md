# Issue #146 — Pioche hors-tour qui bloque la partie + échange tuile/joker toujours cassé pour un groupe

## Point 1 — Cliquer « Piocher » pendant le tour de l'IA bloque la partie définitivement

### Investigation
Côté client (`jeu.js`), `rafraichirBoutons()` désactive déjà correctement le bouton Piocher
(`btnPiocher.disabled = aPose || !monTour`) dès que ce n'est plus le tour du joueur humain, y
compris pendant la latence de ~1 s avant le coup automatique de l'IA (#126, `verifierAutoIA`).
Mais rien n'empêchait un clic arrivé malgré tout (course entre le rendu du bouton désactivé et
un clic déjà en vol, ou tout autre décalage client/serveur) d'atteindre le serveur : `api.py`
(`jeu_piocher`, `jeu_jouer_coup`, `jeu_passer`) agissait alors sur `etat["index_joueur_actuel"]`
sans jamais vérifier qui appelait, contrairement à `jeu_ia_jouer` qui, lui, vérifie bien
`etat["joueurs"][idx]["est_ia"]`.

**Mécanisme de blocage reconstitué :** un `jeu_piocher()` illégitime pendant le tour de l'IA
pioche (silencieusement) pour l'IA et fait avancer `index_joueur_actuel` vers le joueur humain
via `_terminer_tour`. Le timer JS `verifierAutoIA`, programmé *avant* cette pioche illégitime,
se déclenche ensuite et appelle `jeu_ia_jouer()` : celui-ci constate que ce n'est plus le tour
d'une IA et renvoie `{"ok": false}`. Côté client, `jouerIA()` traite cet échec en ré-affichant
l'état *local* (déjà périmé, toujours sur l'ancien tour IA) sans jamais le resynchroniser depuis
le serveur (`etat = nouvelEtat` n'est atteint que dans la branche de succès). Le client reste
alors persuadé que c'est encore le tour de l'IA (boutons humains désactivés) alors que le
serveur, lui, est déjà passé au joueur humain — et `verifierAutoIA` ne reprogramme pas de
nouvelle tentative car son garde anti-doublon (`indexAutoIAProgramme === etat.index_joueur_actuel`)
matche toujours sur l'ancien index. Aucune action ne peut plus faire avancer la partie :
blocage définitif, exactement le symptôme rapporté.

### Correctif
- **`src/rummikub/ui/api.py`** : nouvelle méthode privée `_tour_est_humain(etat)`, et garde en
  tête de `jeu_jouer_coup`, `jeu_piocher`, `jeu_passer`, `jeu_annuler` — ces quatre actions de
  jeu renvoient désormais `{"ok": false, "erreur": "Pas votre tour"}` sans toucher à l'état si
  ce n'est pas le tour du joueur humain. C'est la protection essentielle demandée par l'issue :
  même si un clic hors-tour atteint malgré tout le serveur, il n'a plus aucun effet et ne peut
  plus faire avancer `index_joueur_actuel` deux fois.
- **`src/rummikub/ui/web/jeu.html`** : `btn-piocher` a désormais `disabled` par défaut dans le
  HTML (comme `btn-annuler`/`btn-jouer`), pour couvrir la courte fenêtre entre le chargement de
  la page et le premier `rafraichirTout()` de `init()`.
- **`src/rummikub/ui/web/jeu.js`** : garde `estMonTour()` ajoutée en tête de `onPiocher`,
  `onPasser`, `onJouer` et `onAnnuler`, en plus de la désactivation déjà correcte du bouton —
  défense en profondeur cohérente avec le motif déjà utilisé ailleurs dans le fichier
  (`etendreTapis`, `insererTuileTapis`, `tenterRecupererJoker`).

### Vérification
- `python3 -m pytest` : 25 passés, aucune régression.
- `py_compile` sur `api.py`/`partie.py` : OK. `node --check` sur `jeu.js` : OK.
- Lecture pas à pas de `_terminer_tour`/`verifierAutoIA`/`jouerIA` confirmant le mécanisme de
  désynchronisation ci-dessus et sa fermeture par la garde serveur.

## Point 2 — Échange tuile/joker toujours cassé pour un GROUPE (suite #137/#142/#143)

### Investigation
`valeurJokerDansCombo`/`peutRemplacerJoker` (`jeu.js`) gèrent déjà correctement le cas groupe
(valeur commune, couleur manquante parmi celles non utilisées, anti-doublon #142) — vérifié par
rejeu réel (Playwright) du scénario exact de l'issue (groupe 11-bleu/11-jaune/joker, 11-rouge en
main) : `peutRemplacerJoker` renvoie bien `true`. La détection n'est donc pas en cause.

**Cause réelle, confirmée par clic réel dans la page (chose que #143 n'avait pas pu faire,
faute de navigateur disponible dans son worktree) :** le dispatcheur de clic de
`rafraichirPlateau` exige deux clics successifs sur une combinaison pas encore active — un
premier clic qui l'« active » (affiche ses zones d'insertion), un second qui agit vraiment.
Mais activer une combinaison insère pour la première fois les zones d'extension internes
(`zone-ext-interne`, une par espace entre deux tuiles), ce qui **décale horizontalement vers la
droite toutes les tuiles situées après la première** de la combinaison. Si le joueur clique une
première fois sur le joker (geste naturel), puis une seconde fois au même endroit en s'attendant
à ce que l'échange se déclenche, ce second clic — désormais décalé — ne retombe plus sur le
joker mais sur la zone d'insertion ou la tuile juste avant lui, d'où un ajout normal « à côté »
au lieu de l'échange. Reproduit et confirmé pas à pas avec Playwright (mesure des coordonnées
du joker avant/après activation : décalage mesuré de ~49 px pour un joker en 3ᵉ position d'un
groupe de 3). Un joker en tout premier élément d'une combinaison (position 0) n'est précédé
d'aucune zone interne et n'est donc jamais décalé — ce qui explique que le scénario « suite »
testé lors de #143 (joker visiblement en position non-initiale mais jamais vérifié par clic réel)
ait été présumé fonctionnel sans que cette régression de position ne soit détectée.

### Correctif (`src/rummikub/ui/web/jeu.js`, `rafraichirPlateau`)
La détection d'échange (`estEchangeJoker`) est désormais évaluée et son écouteur de clic attaché
**dès le premier clic**, que la combinaison soit déjà active ou non — plus besoin d'activer la
combinaison au préalable pour échanger un joker qui correspond exactement à la tuile de la main
sélectionnée. Cliquer directement sur un tel joker déclenche l'échange immédiatement, sans
rendu intermédiaire ni décalage. Le classement visuel « joker-recuperable » (surlignage orange)
est lui aussi appliqué dès le premier rendu, avant toute activation. Le comportement existant
est conservé dans tous les autres cas : une tuile non-joker, ou un joker que la tuile
sélectionnée ne peut pas remplacer (valeur différente, couleur déjà présente dans le groupe,
#142), nécessite toujours d'abord d'activer la combinaison avant de pouvoir y insérer une tuile
à un point précis.

### Vérification
- `node --check` sur `jeu.js` : OK.
- Rejeu réel via Playwright (Chromium headless, `jeu.html` chargé avec un état de partie simulé
  et `window.pywebview.api` simulé) :
  - Groupe 11-bleu/11-jaune/joker, 11-rouge en main → clic UNIQUE direct sur le joker : échange
    confirmé (`plateauLocal` contient désormais le 11-rouge à la place du joker, le joker atterrit
    dans la zone de travail, `tuileSelectionnee` vaut l'id du joker — attaché au curseur).
  - Suite 5-6-[joker]-8 rouge, 7-rouge en main → clic unique sur le joker : échange confirmé
    (non-régression, et amélioration : plus besoin des deux clics qu'imposait #143).
  - Groupe 11-bleu/11-jaune/joker, second 11-bleu en main (couleur déjà présente, #142) → clic
    (avec un délai > 350 ms entre les deux clics pour ne pas déclencher le détecteur de
    double-clic existant, sans rapport avec ce correctif) : échange bien refusé, ajout normal à
    côté du joker — comportement de #142 intact.
  - Suite 5-6-7 rouge (sans joker), 9-rouge en main, insertion en fin via la zone d'extension :
    insertion normale intacte (non-régression).
- `python3 -m pytest` : 25 passés, aucune régression.
