# Issue #67 — Réglages : « Vitesse de l'ordinateur » déplacée vers l'onglet Général

# Issue #149 — Ralentir le rejeu à plusieurs tuiles + représenter le réarrangement du tapis par l'IA

## Contexte
Suite à l'usage réel du rejeu animé (#144/#145), deux remarques d'Alain :
1. Quand l'IA pose plusieurs tuiles en un seul tour, l'animation défile trop vite.
2. Sur 3 parties (2× Avancé, 1× Expert), Alain n'a jamais vu l'IA réarranger des tuiles déjà
   posées (mécanisme `_coup_scission`), alors qu'une investigation précédente (#134) mesurait
   un déclenchement dans 90,8 % des parties simulées 4 IA dès qu'un niveau Avancé/Expert est
   présent.

## 1. Rythme du rejeu ralenti
`animerPoseTuiles()` (jeu.js) calcule désormais un délai effectif entre tuiles ralenti de 40 %
(`delaiEntreTuiles * 1.4`) dès qu'un coup anime plus de 3 tuiles, pour rester lisible sur les
coups à plusieurs tuiles (extension multiple, scission) sans ralentir les coups simples (1-3
tuiles) qui restaient déjà confortables.

## 2. Fréquence réelle de `_coup_scission` — investigation
Reproduit la méthode de l'investigation #134 (monkeypatch temporaire et non committé de
`rummikub.moteur.ia._coup_scission` pour compter ses déclenchements effectifs, via
`scripts/simulation_ia.simuler`), mais sur des parties à **2 joueurs** — configuration plus
proche du cas réel d'Alain (1 humain + 1 IA) que les parties à 4 IA testées en #134 :

- 150 parties « 4× Avancé » (reproduction #134, contrôle) : 626 déclenchements, 98,0 % des
  parties, 84,1 tours/partie en moyenne — chiffres identiques à #134, méthode validée.
- 150 parties « 2× Avancé » : 976 déclenchements, **100 %** des parties, 128,0 tours/partie.
- 150 parties « Débutant + Avancé » : 291 déclenchements, 86,0 % des parties, 112,2 tours/partie.
- 150 parties « Débutant + Expert » : 280 déclenchements, 86,0 % des parties, 111,8 tours/partie.

**Conclusion : `_coup_scission` se déclenche en réalité AU MOINS aussi souvent, voire plus
souvent, en partie à 2 joueurs qu'en partie à 4 IA** (moins de joueurs ne réduit pas les tours
totaux d'une manche — au contraire, 112-128 tours/partie contre 84 à 4 joueurs, car chaque
pioche de secours allonge la manche). L'hypothèse « moins de joueurs → moins d'opportunités »
est donc infirmée par les données : le nombre réel de tours disponibles pour qu'une suite de 4+
tuiles se forme sur le tapis est au moins aussi grand, pas plus petit.

**L'écart entre le 0/3 observé par Alain et ces 86-100 % mesurés ne s'explique donc pas par la
configuration de jeu (nombre de joueurs), mais par l'absence, jusqu'à ce correctif, de tout
signal visuel distinguant une tuile déplacée d'une tuile simplement déjà présente.** Avant le
correctif du point 3 ci-dessous, `trouverTuilesAjoutees()` ne repérait que les tuiles dont l'id
n'existait pas dans l'ancien plateau (donc venues de la main) ; une tuile déjà posée qui change
de combinaison (comme le 7 détaché par `_coup_scission`) n'était comptée nulle part : elle
apparaissait directement dans sa position finale dès la première image du rejeu, sans aucune
animation ni surbrillance la distinguant d'une tuile qui n'a pas bougé. Il est donc très
probable que `_coup_scission` se soit déjà produit dans les parties d'Alain sans qu'il puisse le
remarquer dans un plateau ré-affiché intégralement à chaque tour — pas une anomalie du moteur IA,
mais un angle mort de l'ancien rendu. Script d'investigation temporaire, non committé
(conformément à la consigne #134).

## 3. Représentation du réarrangement dans le rejeu
- `trouverTuilesDeplacees(ancienPlateau, nouveauPlateau)` (nouvelle fonction, jeu.js) : pour
  chaque combinaison de l'ancien plateau, regroupe ses tuiles selon la combinaison du nouveau
  plateau où elles se retrouvent ; le groupe d'arrivée majoritaire est considéré comme la
  « continuation » de la combinaison (couvre aussi bien une extension qu'une scission qui la
  raccourcit sans la vider), les tuiles parties dans un autre groupe d'arrivée sont comptées
  comme déplacées.
  ⚠️ Une première version de cette fonction (de la tentative précédente sur ce même worktree)
  comparait l'ensemble des voisines déjà posées de chaque tuile avant/après — ce qui marquait à
  tort **toutes** les tuiles d'une suite scindée comme « déplacées » dès qu'une seule tuile la
  quittait (ex. scission 4-5-6-7 → 4-5-6 + groupe(7) marquait 4, 5, 6 **et** 7 comme déplacées,
  alors que 4/5/6 restent groupées entre elles, seul le 7 change réellement de combinaison).
  Conséquence concrète : les tuiles restées en place auraient disparu puis réapparu pendant le
  rejeu (`animerPoseTuiles` les traite comme à révéler) et reçu à tort le flash bleu
  « réarrangement ». Vérifié par trace manuelle (Node) sur l'exemple canonique de
  `_coup_scission`, l'extension simple et le cas sans rapport ; la nouvelle version ne marque
  plus que la tuile réellement déplacée dans les trois cas.
- `animerPoseTuiles()` anime désormais, dans l'ordre, les tuiles déplacées (surbrillance bleue,
  classe CSS `tuile-ia-deplacee`) puis les tuiles neuves venues de la main (surbrillance dorée
  existante) — part de `plateauAvant` et converge vers `plateauApres`.
  `jeu.css` : nouvelle animation `tuile-deplacee` (bleu, `rgba(90,170,255,…)`) distincte du
  doré existant pour les tuiles neuves.
- `jouerIA()` et `rejouerDernierCoupIA()` calculent désormais `tuilesDeplacees` en plus de
  `tuiAjoutees` et les passent à `animerPoseTuiles()` ; le cas « aucune tuile ajoutée »
  (pioche/passe) tient compte des deux listes.

## Test
- `python -m pytest` : 25 passés (aucun fichier Python modifié — point 2 est une investigation
  en lecture seule via script temporaire non committé, le front-end JS n'a pas de suite de
  tests dédiée dans ce projet).
- `node --check jeu.js` : syntaxe valide.
- Logique de `trouverTuilesDeplacees()` vérifiée par trace manuelle (Node, hors dépôt) sur
  3 cas : scission (seule la tuile détachée est marquée), extension simple (rien marqué),
  combinaison sans rapport avec le coup (rien marqué).

## Résultat
Le rejeu d'un coup à plusieurs tuiles est 40 % plus lent à partir de 4 tuiles animées, restant
confortable à suivre. La fréquence réelle de `_coup_scission` est confirmée au moins aussi
élevée en configuration 2 joueurs qu'en 4 IA (86-100 % des parties) ; l'écart avec le 0/3 observé
par Alain s'explique par l'absence passée de signal visuel distinguant une tuile réarrangée,
pas par une rareté réelle du mécanisme. Le rejeu représente maintenant clairement ce cas
(surbrillance bleue sur la tuile qui change de combinaison), sans faux positifs sur les tuiles
qui restent groupées.

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

# Issue #148 — IA : récupération d'un joker libérable lors d'une extension (Avancé/Expert)

## Contexte
Niveau "Expert" jugé trop faible : l'IA se contentait du premier coup simple trouvé
(`_coup_maximal`) même quand un joker du tapis était récupérable (échangeable contre une
tuile identique de la main) et aurait permis, une fois replacé ailleurs, un coup nettement
meilleur (plus de tuiles posées, plus de points). `_coup_scission` existait déjà mais
seulement en dernier recours, selon un seul patron.

## Modification (`src/rummikub/moteur/ia.py`)
- `_jokers_recuperables(plateau, chevalet)` : détecte les jokers du plateau échangeables
  contre une tuile identique de la main (même valeur/couleur pour une suite ; même valeur
  et une couleur absente du groupe pour un groupe).
- `_coup_avec_joker_recupere(etat, idx, ordre_points)` : pour chaque joker récupérable,
  simule l'échange puis tente de replacer le joker libéré ailleurs sur le plateau (nouvelle
  combinaison ou extension), et retourne le meilleur coup obtenu.
- `_valeur_coup(etat, idx, coup)` : valeur comparative d'un coup `(nb tuiles jouées, points
  posés)`, utilisée pour départager les coups candidats.
- `_meilleur_coup_avec_joker(etat, idx, ordre_points)` : compare le coup évident
  (`_coup_maximal`) et le coup de récupération de joker, retourne le meilleur des deux.
- `jouer_niveau_avance` et `jouer_niveau_expert` utilisent désormais
  `_meilleur_coup_avec_joker` à la place de `_coup_maximal`. Facile/Intermédiaire/Débutant
  ne sont pas modifiés — l'amélioration vise uniquement Avancé/Expert comme demandé.

## Tests (`tests/test_ia.py`)
Scénario dédié (`_etat_avec_joker_recuperable`) : suite rouge 4-5-(joker=6) au tapis ;
chevalet du bot avec un rouge 6 (reprise du joker), un noir 9 + un bleu 9 (groupe complet
uniquement avec le joker libéré), et un rouge 7 (extension évidente sans toucher au joker).
- Avancé/Expert choisissent le coup de récupération (4 tuiles posées, 31 pts) plutôt que
  l'extension évidente (1 tuile, 7 pts).
- Facile/Intermédiaire jouent toujours l'extension évidente (rouge 7 seul) — comportement
  inchangé.

# Issue #147 — Suite #144 : reformuler et habiller la modale de confirmation du rejeu du dernier coup IA

## Contexte
La confirmation avant rejeu du dernier coup IA (#144) utilisait le mot « annulé », qui pouvait
faire craindre à Alain de perdre un tour de jeu complet, alors qu'il s'agit seulement de remettre
en main les tuiles pas encore validées du tour en cours. C'était par ailleurs une `confirm()`
JavaScript native, sans style ni titre spécifique.

## Modification
- `jeu.html` : nouvel overlay `#overlay-confirm-rejeu` (`.carte.carte-confirm`), avec titre
  `#titre-confirm-rejeu` rempli dynamiquement et deux boutons (`btn-confirm-rejeu-non` /
  `btn-confirm-rejeu-oui`).
- `jeu.css` : styles `.carte-confirm` (carte compacte, titre coloré comme les fiches IA via
  `--couleur-ordinateur`) et `.btn-secondaire` (nouveau bouton générique pour les annulations).
- `jeu.js` :
  - Nouvelle fonction `confirmerRejeuIA(nomIA)`, qui affiche l'overlay stylé avec pour titre
    « Dernier coup de `<nomIA>` » et résout une Promise `true`/`false` selon le bouton cliqué.
  - `rejouerDernierCoupIA()` utilise désormais cette modale (au lieu de `confirm()` natif), avec
    pour titre le prénom de l'IA dont on rejoue le coup (`coup.nom`, déjà présent dans
    `dernier_coup_ia`).
  - Texte reformulé : « Vos tuiles pas encore validées pour ce tour seront remises en main pour
    laisser la place au rejeu — continuer ? » (plus de mention d'annulation de tour).

## Tests
- `python3 -m pytest` : 25 passed (aucune régression, modification purement front-end).
- `node --check jeu.js` : syntaxe JS valide.

# Issue #145 — Animation quand l'ordinateur pioche une tuile

## Contexte
Le joueur humain disposait déjà d'une animation à la pioche (`animerPiochee` dans jeu.js :
tuile montrée en grand au centre de l'écran, puis glissée/rétrécie vers le chevalet). Rien
d'équivalent n'existait côté IA : quand un joueur IA pioche, le tour se terminait directement
par un simple toast ("X pioche"), sans aucun geste visuel.

## Modification
- `commun.js` : nouvelle fonction `creerTuileDos()`, qui construit une tuile au même gabarit
  que `creerTuileJeu()` mais avec un disque central vide — aucune couleur ni valeur n'est donc
  révélée.
- `jeu.js` : nouvelle fonction `animerPiocheeIA(idxIA, apres)`, variante de `animerPiochee()`.
  La tuile dos visible part du centre de l'écran (comme pour l'humain) puis glisse vers la
  fiche du joueur IA concerné — position calculée dynamiquement via `getBoundingClientRect()`
  sur `.fiche-joueur` (nécessaire car la disposition des fiches varie selon le nombre de
  joueurs). Repli vers le haut de l'écran si la fiche n'est pas trouvée.
  Dans `jouerIA()`, la branche « aucune tuile ajoutée » distingue désormais pioche et passe :
  en cas de pioche, `animerPiocheeIA()` est jouée avant de rafraîchir l'affichage ; en cas de
  passe, le délai fixe de 800 ms est conservé inchangé.
- `jeu.css` : nouvelle règle `.vers-ia` (variables `--dx`/`--dy` posées en JS) qui réutilise la
  transition déjà définie sur `.tuile-piochee-grande`, en parallèle de `.vers-chevalet`
  (animation existante côté humain, inchangée).

## Test
`python -m pytest` : 25 passés (aucun fichier Python modifié, animation purement front-end).

# Issue #144 — Remplace « Derniers coups » par un rejeu animé du dernier coup de l'ordinateur

## Contexte
La liste textuelle « Derniers coups » (panneau gauche) était jugée peu utile par Alain : il
préfère pouvoir revoir l'animation du dernier coup de l'IA plutôt que lire une description
textuelle. Comme le rejeu réutilise la zone du tapis, les tuiles du tour en cours d'Alain
(posées mais pas encore validées) doivent d'abord repartir en main — ce qui annule sa
progression du tour, donc exige une confirmation explicite au préalable.

## Modifications

**`src/rummikub/ui/web/jeu.html`** : la section `#details-historique` (liste + compteur) est
remplacée par un bouton `#btn-rejouer-coup-ia` (« ▶ Dernier coup joué par l'ordinateur »),
désactivé par défaut tant qu'aucun coup IA n'a encore été joué.

**`src/rummikub/ui/web/jeu.css`** : styles `#details-historique`/`#liste-historique`/
`.entree-historique` remplacés par `.btn-rejouer-coup-ia` (même famille visuelle que
`.btn-jouer-ia`).

**`src/rummikub/moteur/partie.py`** : nouveau champ d'état `dernier_coup_ia` (initialisé à
`None` dans `creer_partie` et réinitialisé dans `nouvelle_manche`). Simple valeur de données,
alimentée côté API — la logique de pose (`jouer_tour`) n'a pas besoin de savoir qui joue.

**`src/rummikub/ui/api.py`** (`jeu_ia_jouer`) : capture une copie profonde du plateau avant
et après le coup de l'IA ; si l'action était bien une pose réussie (pas une pioche/un passage,
qui n'ont rien à rejouer), mémorise `{joueur_index, nom, plateau_avant, plateau_apres}` dans
`etat["dernier_coup_ia"]`. Ce champ est un sous-ensemble de l'état déjà sérialisé tel quel vers
JS (`jeu_get_etat`) et persisté en SQLite (`sauvegarder_partie` sérialise l'état entier) — aucune
nouvelle route API de lecture n'était nécessaire. Les parties sauvegardées avant cette issue
n'ont simplement pas ce champ (`undefined` côté JS → bouton désactivé, pas d'erreur).

**`src/rummikub/ui/web/jeu.js`** :
- `rafraichirHistorique()` → renommée `rafraichirBoutonRejouerIA()` : active/désactive le
  bouton selon la présence de `etat.dernier_coup_ia` et affiche le nom de l'IA dans son libellé.
- Extraction de `animerPoseTuiles(tuiAjoutees, plateauComplet, delaiEntreTuiles)` et
  `effacerSurbrillanceIA()` depuis le corps de `jouerIA()` (pose des tuiles IA une par une avec
  surbrillance dorée) : logique désormais partagée entre le coup IA en direct et son rejeu, pour
  éviter de dupliquer ~45 lignes d'animation. `vitesseIA()` centralise la lecture du réglage
  « Vitesse de l'ordinateur » (`VITESSES_IA`), utilisée par les deux appelants.
- Nouvelle fonction `rejouerDernierCoupIA()` (déclenchée par le clic sur le nouveau bouton) :
  si `tuilesCeTour` contient des tuiles (tour en cours non validé), affiche une confirmation
  (« Votre tour en cours sera annulé pour rejouer ce coup — continuer ? ») ; si l'utilisateur
  annule, rien ne se passe. Sinon, appelle `onAnnuler()` (même chemin que le bouton « Annuler »
  existant : remet les tuiles en main via l'API `jeu_annuler`, resynchronise le chevalet et
  réaffiche le tapis) avant de lancer l'animation à partir des plateaux mémorisés
  (`trouverTuilesAjoutees(plateau_avant, plateau_apres)` + `animerPoseTuiles`), sans appel
  serveur ni changement d'état — c'est un simple rejeu visuel.

## Points d'attention
- Le rejeu anime les tuiles identifiées par id entre `plateau_avant`/`plateau_apres` du dernier
  coup IA, mais les révèle sur le plateau *actuel* (`etat.plateau`) : si le plateau a depuis été
  réorganisé (tours suivants), l'emplacement visuel peut différer de celui d'origine — seules les
  tuiles elles-mêmes et leur ordre d'apparition sont fidèles au coup réellement joué.
- Le tableau `etat["historique"]` (texte) est conservé tel quel côté moteur : il reste utilisé en
  interne pour le message toast « X pioche »/« X passe son tour » après un tour IA ; seule la
  section visuelle qui en affichait la liste a été retirée.

# Issue #143 — Suite #137 : l'échange tuile/joker ne se produisait pas — la tuile se posait à côté du joker qui restait en place

## Contexte
#137 avait modifié `tenterRecupererJoker` pour que le joker libéré par un échange devienne la
tuile sélectionnée (attachée au curseur) plutôt que simplement désélectionné. Mais le test réel
d'Alain montrait que l'échange ne se déclenchait jamais : la tuile posée sur le joker s'insérait
À CÔTÉ de lui (insertion normale), et le joker restait en place. L'issue soupçonnait un défaut
de détection de correspondance pour les jokers ambigus entre plusieurs couleurs restantes (même
défaut que #142 avait corrigé côté blocage d'un remplacement invalide).

## Investigation
La fonction `peutRemplacerJoker`/`valeurJokerDansCombo` (jeu.js) s'est révélée correcte même pour
le cas à deux couleurs manquantes : vérifié par un test Node isolant ces deux fonctions pures sur
le scénario exact de l'issue (groupe 8-noir/8-jaune/joker, tuile 8-bleu ou 8-rouge en main) — les
deux couleurs sont acceptées, un doublon (8-noir) est refusé (#142). La piste de l'issue n'était
donc pas la cause réelle.

**Cause réelle : branche morte dans le dispatcheur de clic de `rafraichirPlateau`.** La
récupération de joker (issue #12, bien avant #137) est déclenchée par une branche
`else if (d.est_joker && tuileSelectionnee !== null && ...)` tout en bas d'une chaîne
`if/else if`. L'issue #47 (« insertion ciblée ») a depuis inséré AVANT cette branche un cas
`else if (modeCible)` qui, sur la combinaison active, attache systématiquement un clic vers
`insererTuileTapis` (insertion à côté) à CHAQUE tuile — y compris un joker — sans jamais vérifier
si la tuile sélectionnée pourrait l'échanger. Or `modeCible` est vrai exactement quand
`tapisManipulable() && une tuile est sélectionnée` — c'est-à-dire précisément la condition
requise pour atteindre la branche de récupération de joker plus bas. Résultat : cette dernière
branche ne pouvait plus jamais s'exécuter pendant le tour du joueur (elle ne devenait accessible
que si `tapisManipulable()` était faux, ce qui exige de ne PAS être son tour — un état où aucun
clic ne devrait de toute façon produire d'effet). Le correctif de #137 avait donc modifié une
fonction (`tenterRecupererJoker`) que le dispatcheur de clic n'appelait plus jamais en pratique
depuis l'ajout de #47 — bug resté invisible car vérifié uniquement par relecture de code et
`node -e`, sans clic réel dans la page.

## Correctif (src/rummikub/ui/web/jeu.js)
Dans la branche `modeCible` / `estActive` de `rafraichirPlateau` : avant d'attacher le clic de
chaque tuile de la combinaison ciblée, on calcule si la tuile cliquée est un joker que la tuile
actuellement sélectionnée (si elle vient bien de la main, via `chevaletLocal`) peut remplacer
(`peutRemplacerJoker(tuileSelDict, valeurJokerDansCombo(combo, idxTuile))`). Si oui, le clic
appelle `tenterRecupererJoker` (échange réel : retrait du joker, insertion de la tuile à sa
place, joker libéré attaché au curseur) au lieu de `insererTuileTapis` (insertion à côté). La
classe CSS `joker-recuperable` (surlignage orange pulsé, déjà définie dans jeu.css depuis #12)
est réutilisée pour signaler visuellement ce joker échangeable.

L'ancienne branche `else if (d.est_joker && ...)`, désormais prouvée inatteignable pendant le
tour du joueur, a été supprimée — elle induisait en erreur sur l'endroit où la logique
s'exécutait réellement (cause de la confusion ayant mené à la clôture erronée de #137).

## Vérification
- `node --check` sur jeu.js : syntaxe OK.
- Script Node isolant `valeurJokerDansCombo`/`peutRemplacerJoker` sur le scénario exact de
  l'issue (groupe de 3 avec joker ambigu entre 2 couleurs) : comportement correct confirmé,
  ce n'était pas la cause.
- `pytest` (suite existante, côté Python, non concernée par ce changement JS) : 25 passés,
  aucune régression.
- Pas de test Playwright/navigateur disponible dans ce worktree pour rejouer le clic réel ;
  la correction a été tracée pas à pas dans le dispatcheur de clic (ordre des branches
  `if/else if`, conditions exactes de `modeCible` vs `tapisManipulable()`) jusqu'à confirmer
  que la nouvelle branche est bien atteinte et appelle `tenterRecupererJoker` dans le scénario
  décrit par Alain.

# Issue #140 — Suite #135 : seuil de dé-zoom revérifié dans la page réelle complète

## Contexte
#135 avait mesuré le seuil de débordement du tapis (`#zone-plateau-scroll`) en chargeant
`jeu.html` isolément dans Playwright, et conclu qu'il n'y avait pas de régression. En jeu réel
(fenêtre pywebview maximisée, page complète avec en-tête, chevalet, zones de pose), Alain
observait un dé-zoom (100%→75%) toujours trop précoce, alors qu'il restait visiblement de la
place à l'écran.

## Investigation (Playwright, page réelle complète via un état de partie généré par le vrai
moteur — joueurs, chevalet, historique peuplés comme dans l'appli, pas un harnais minimal)

**Deux causes distinctes trouvées, indépendantes de la CSS mesurée par #135 :**

1. **`#zone-plateau-scroll` avait une hauteur figée (`max-height: 330px`, #128) au lieu d'utiliser
   l'espace réellement disponible.** Sur une fenêtre pywebview maximisée (ex. laptop 1366×768),
   la bande sous le tapis (zone de pose + résultat) ne prend qu'environ 120px, laissant ~400px
   disponibles à `#zone-plateau-wrap` — mais la hauteur figée à 330px plafonnait artificiellement
   le tapis bien en-dessous, gaspillant ~90-115px d'espace pourtant visible et vide à l'écran
   (exactement ce qu'Alain rapportait). À l'inverse, sur une petite fenêtre (ex. 900×600), le
   budget réellement disponible pouvait descendre sous 330px : comme `#zone-plateau-wrap` est
   compressible (`flex-shrink`) mais que `#zone-plateau-scroll` gardait son `max-height` fixe
   indépendant de son parent compressé, le tapis pouvait effectivement s'afficher sur 330px alors
   que son conteneur n'en avait que ~255 de libres — chevauchant visuellement la zone de pose
   juste en-dessous (vérifié par capture d'écran, voir rapport).

2. **Le niveau de zoom déclenché AUTOMATIQUEMENT par débordement était mémorisé dans le même
   `localStorage` que le choix manuel de l'utilisateur**, et relu comme point de départ à chaque
   chargement de `jeu.html`. Comme ce stockage persiste réellement entre les parties dans l'appli
   pywebview (contrairement à un test Playwright isolé, qui repart toujours d'un stockage vide à
   chaque exécution), un dé-zoom automatique survenu une seule fois dans une partie passée restait
   collé indéfiniment : **toute nouvelle partie démarrait déjà zoomée à 75%, dès la toute première
   tuile posée**, donnant l'impression d'un dé-zoom systématiquement prématuré — un effet que la
   méthodologie de #135 (page isolée, stockage toujours vierge) ne pouvait structurellement pas
   révéler.

Mesure du seuil (nombre de combinaisons de 3 tuiles posées avant le premier dé-zoom 100%→75%),
avec un état de partie réaliste (3 joueurs, chevalet de 14 tuiles, historique) sur les tailles de
fenêtre couvertes par l'appli :

| Fenêtre                    | Seuil AVANT (page réelle) | Seuil APRÈS |
|-----------------------------|:---:|:---:|
| 900×600 (taille mini)       | 7  | 5\* |
| 1024×600                    | 10 | 7\* |
| 1100×650                    | 10 | 10  |
| 1100×750 (défaut)           | 10 | 13  |
| 1366×768 (laptop courant)   | 13 | 17  |

\* Sur les deux plus petites tailles, le seuil mesuré baisse légèrement — mais le seuil « avant »
était artificiellement gonflé par le chevauchement décrit au point 1 (le tapis débordait déjà
visuellement sur la zone de pose avant même que `scrollHeight > clientHeight` ne soit détecté).
Le nouveau seuil, plus bas mais honnête, correspond à l'espace réellement disponible sans
chevauchement. Sur les tailles réalistes (1100×750 et plus, dont le format laptop 1366×768 visé
par la tâche), le seuil progresse de +30 à +45 %.

## Correctifs

- `jeu.css` (`#zone-plateau-wrap`, `#zone-plateau-scroll`) : remplace la hauteur figée
  (`max-height: 330px`) par `flex: 1 1 auto` + `height: 100%`, pour que le tapis occupe tout
  l'espace vertical réellement laissé libre par le reste de la mise en page, quelle que soit la
  taille de fenêtre — au lieu d'une constante choisie sans rapport avec la fenêtre réelle de
  l'appli. Supprime au passage le chevauchement visuel avec la zone de pose sur petite fenêtre.
- `jeu.js` (`autoZoomSiTapisDeborde`) : le dé-zoom déclenché automatiquement n'est plus écrit dans
  `localStorage` (seul un clic manuel sur un bouton de zoom reste mémorisé comme préférence
  durable). Le niveau automatique continue de s'appliquer visuellement pour la partie en cours,
  mais ne contamine plus le point de départ des parties futures.
- `jeu.js` (`init`) : à chaque chargement de `jeu.html`, si le tapis est vide (nouvelle partie, ou
  reprise avant la première pose), le zoom est explicitement remis à 100% (et la mémoire nettoyée),
  même si une ancienne valeur dézoomée traînait en `localStorage` — ce qui corrige aussi
  immédiatement les parties déjà affectées par le problème, sans attendre un clic manuel de
  l'utilisateur. Dans tous les autres cas (reprise d'une partie avec un tapis déjà rempli), le
  débordement réel est réévalué immédiatement après le premier rendu (`autoZoomSiTapisDeborde()`
  appelé en fin d'`init()`), pour retrouver le bon niveau de zoom dès l'affichage plutôt que
  d'attendre la pose suivante.

## Vérification
Suite pytest existante (25 tests, logique moteur non touchée) : OK. `node --check jeu.js` : OK.
Revérification par Playwright sur la page réelle complète (état de partie généré par le vrai
moteur, pas un harnais minimal) : seuils mesurés ci-dessus, chevauchement visuel disparu (capture
avant/après), et confirmation qu'une nouvelle partie démarre bien à 100% même avec un ancien
`localStorage` pollué à 0.75 par une exécution précédente.

## Issue #142 — Remplacement d'un joker dans un groupe : vérifier la couleur de la tuile de remplacement

- `jeu.js` (`valeurJokerDansCombo`, `peutRemplacerJoker`) : pour un groupe, refuse désormais le remplacement d'un joker par une tuile dont la couleur est déjà présente parmi les autres tuiles du groupe (même garde-fou que pour une suite, qui vérifiait déjà la couleur). Avant ce correctif, un groupe 7-rouge / 7-bleu / joker pouvait voir son joker remplacé par un 7-rouge pris en main, créant un groupe invalide (couleur dupliquée).

# Issue #141 — Fin de partie : message de fin de manche redondant supprimé + animation de victoire

## Contexte
À la fin d'une partie, deux fenêtres s'affichaient l'une après l'autre : l'overlay de fin de
manche (« Dernière manche — X remporte la manche », tableau manche/total) suivi immédiatement
de l'overlay de classement final (« X remporte la partie ! », tableau de classement). Les deux
montraient la même information quand la partie ne comptait qu'une seule manche.

## Correctif (`jeu.js`, `jeu.html`, `jeu.css`)
- `afficherFinDeManche()` (nouveau dispatcher) remplace les deux appels directs à
  `afficherFinManche()` : si `etat.terminee` (la manche qui se termine est la dernière de la
  partie), on affiche directement le classement final (`afficherClassementFinal()`) sans
  passer par l'overlay de fin de manche intermédiaire. Sinon, comportement inchangé.
- `afficherFinManche()` simplifiée : elle n'est plus jamais appelée avec `etat.terminee` vrai,
  donc la logique de titre/boutons conditionnelle à la fin de partie (bouton « Fin de partie »,
  titre « Dernière manche — ») a été retirée, ainsi que `onFinPartie()` et son écouteur,
  devenus inatteignables.
- Ajout d'une animation de feu d'artifice (CSS, particules générées par
  `lancerFeuArtifice()`) affichée derrière la carte du classement final lors de l'annonce du
  gagnant de la partie. Plusieurs bouquets de particules colorées jaillissent en cercle puis
  s'évanouissent (`@keyframes eclat-feu`), positions/couleurs/délais randomisés en JS, le
  mouvement restant purement CSS (`transform: rotate() translateX()`).

## Non régression
Le comportement pour une manche intermédiaire (partie à plusieurs manches) est inchangé :
l'overlay de fin de manche avec bouton « Manche suivante » / « Retour au menu » continue de
s'afficher normalement quand `etat.terminee` est faux.

# Issue #138 — Reprendre individuellement une tuile du tour en cours (sans tout « Annuler »)

## Contexte

Le mécanisme pour reprendre une tuile posée ce tour (clic/double-clic sur le
tapis → `prendreTuileTapis`/`reprendreTuile`/`reprendreTuileRangee`) existait
déjà depuis les issues #128/#133/#136, mais contenait un bug qui en annulait
l'intérêt dans le cas précis visé par cette issue : une tuile venant de la
main, posée ce tour-ci, puis redéplacée au sein du tapis (ex. sortie d'une
combinaison pour la recombiner ailleurs), était marquée à tort comme
« origine tapis ». Une fois cette étiquette posée à tort, `reprendreTuileRangee`
refusait de la renvoyer à la main (règle légitime pour une VRAIE tuile du
tapis — elle n'appartient pas au joueur) — le seul recours redevenait alors
« Annuler », qui réinitialise tout le tour. C'est exactement le problème
décrit par l'issue.

## Correctif (`jeu.js`)

- `prendreTuileTapis(idxCombo, idxTuile)` : calcule désormais `venaitDeLaMain`
  (la tuile est déjà dans `tuilesCeTour` et n'est PAS encore taguée
  `tuilesOrigineTapis`) **avant** de muter l'état, puis n'ajoute la tuile à
  `tuilesOrigineTapis` que si elle ne vient pas de la main. Une tuile de main
  redéplacée au sein du tapis garde ainsi son identité « main » et peut
  toujours repartir au chevalet individuellement.
- `reprendreTuileRangee(id, indexRangee)` : ajout de l'appel symétrique
  `rendreAuChevaletServeur(d)` dans la branche « retour au chevalet », comme
  le fait déjà `reprendreTuile` pour le chemin direct `etendreTapis`/
  `insererTuileTapis`. Sans cet appel, une tuile de main posée directement sur
  une combinaison existante (chemin qui retire la tuile du chevalet serveur),
  puis reprise via le mécanisme de manipulation du tapis et renvoyée à la
  main, restait durablement absente du chevalet serveur — désynchronisant le
  compteur de tuiles affiché sur la fiche du joueur jusqu'à la fin du tour.
  Ce chemin n'était tout simplement pas atteignable avant la correction
  ci-dessus (la tuile y était toujours mal étiquetée « origine tapis »),
  donc le bug n'avait pas d'effet observable jusqu'ici.

## Résultat

Une tuile posée par erreur ce tour (qu'elle vienne de la main ou qu'elle ait
été déplacée depuis une combinaison déjà sur le tapis) peut désormais être
reprise individuellement et repositionnée ou rendue à la main, sans affecter
le reste des tuiles déjà placées ce tour — plus besoin de passer par
« Annuler » pour corriger une seule tuile mal placée.

## Vérifications

- `node --check src/rummikub/ui/web/jeu.js` : syntaxe valide.
- `pytest` (suite existante, moteur non touché) : 25 passés.
- Lecture manuelle de tous les chemins touchant `tuilesCeTour`/
  `tuilesOrigineTapis`/chevalet serveur (`placerTuileDansRangee`,
  `insererTuileRangee`, `placerRangee`, `viderRangee`, `etendreTapis`,
  `insererTuileTapis`, `reprendreTuile`, `prendreTuileTapis`,
  `reprendreTuileRangee`, `reinitTour`) pour confirmer l'absence de
  régression sur les tuiles réellement issues d'un tour précédent (elles
  restent non renvoyables à la main, comme attendu).

# Issue #137 — Échanger une tuile de la main contre un joker équivalent du tapis

## Contexte
Un joker posé dans une combinaison du tapis représente une tuile précise (même valeur, et
même couleur dans le cas d'une suite). Quand le joueur a en main cette tuile exacte, il
pouvait déjà la sélectionner puis cliquer sur le joker pour l'échanger (`tenterRecupererJoker`,
issue #12) — mais le joker libéré était simplement désélectionné et renvoyé en zone de
travail, sans pouvoir être immédiatement replacé ailleurs d'un seul geste.

## Correctif (`jeu.js`)
- `tenterRecupererJoker` : le joker libéré par l'échange devient désormais la tuile
  sélectionnée (`tuileSelectionnee = dictJoker.id`) au lieu d'être désélectionné, et
  `majFantome()` remplace `detruireFantome()` pour qu'il suive le curseur — exactement le
  même traitement qu'une tuile fraîchement prise sur le tapis (`prendreTuileTapis`).
- Le joker libéré est ajouté à `tuilesOrigineTapis` (comme toute tuile provenant du tapis),
  afin que les mécanismes existants de replacement (`etendreTapis`, `insererTuileTapis`,
  `reprendreTuileRangee`, …) le traitent correctement.

## Résultat
Un joueur peut déposer une tuile de sa main sur un joker du tapis qu'elle remplace
exactement ; le joker libéré reste attaché au curseur, prêt à être reposé ailleurs dans le
même tour, sans étape intermédiaire.

# Issue #139 — Suite #136 : pourtour des tuiles déplacées depuis le tapis indiscernable

## Contexte
#136 avait introduit `.deplacee-tapis` (pourtour bleu `#3b82f6`) pour distinguer les tuiles déjà
sur le tapis mais déplacées ce tour-ci, des tuiles neuves de la main (`.ce-tour`, vert). En test
réel, ce bleu se fondait avec le contour pointillé bleu que `.tapis-manipulable` (jeu.css) applique
à toutes les tuiles manipulables du tapis une fois la mise initiale faite — la même collision
visuelle déjà corrigée pour le vert en #129.

## Correctif (`commun.css`, `jeu.css`)
- `.deplacee-tapis` passe du bleu `#3b82f6` à l'orange `#f59e0b` (border-color + box-shadow),
  désormais distinct à la fois du vert de `.ce-tour` et du bleu de `.tapis-manipulable`.
- Ajout de `.tuile-jeu.deplacee-tapis.tapis-manipulable` (et son `:hover`) sur le même modèle que
  `.tuile-jeu.ce-tour.tapis-manipulable` déjà présent : le contour pointillé de
  `.tapis-manipulable` reprend la couleur orange plutôt que de l'écraser.
- `.ce-tour` et `.deplacee-tapis` restent mutuellement exclusifs côté JS (`jeu.js`, `else if`),
  aucune règle de combinaison des deux classes n'était donc nécessaire.

# Issue #136 — Distinguer tuiles main/tapis + messages d'erreur précis sur une combinaison invalide

## Contexte
En formant un groupe de trois 7 mêlant une tuile de la main et deux tuiles déjà posées ailleurs
sur le tapis, les 3 tuiles recevaient le même pourtour vert (`.ce-tour`, issue #128), sans
distinguer l'origine réelle de chacune. Par ailleurs, un plateau invalide affichait un message
générique ("Combinaison 9 : ni suite ni groupe valide") sans indiquer la raison précise, et la
combinaison fautive n'était pas repérable visuellement sur le tapis.

## Correctif

### 1. Distinction visuelle main vs tapis déplacé (`jeu.js`, `commun.css`)
- Nouvelle classe CSS `.deplacee-tapis` (pourtour bleu `#3b82f6`), appliquée à la place de
  `.ce-tour` (vert) sur les tuiles déjà présentes sur le tapis avant ce tour mais
  déplacées/réorganisées pendant celui-ci — déduit de `tuilesOrigineTapis`, déjà suivi par le
  code existant (issue #103/#133) mais jusqu'ici non reflété visuellement.
- Appliqué à la fois sur le tapis (`rafraichirPlateau`) et dans les zones de pose
  (`rafraichirZoneTravail`).
- Aucune nouvelle règle n'était nécessaire pour l'état « tapis-manipulable » : son contour par
  défaut est déjà bleu, cohérent avec la nouvelle couleur.

### 2. Messages d'erreur précis (`validation.py`)
- `valider_suite`/`valider_groupe` retournent désormais un champ `"raison"` (texte explicite :
  couleurs différentes, jokers adjacents, valeurs hors limites, tuiles non consécutives, couleurs
  en double, plus d'un joker, etc.) en plus de `"valide"`/`"points"`.
- `valider_combinaison` déduit, via `_raison_combinaison_invalide`, la raison la plus pertinente
  selon que les tuiles réelles partagent une couleur commune (tentative de suite), une valeur
  commune (tentative de groupe), les deux (ambigu) ou ni l'une ni l'autre (incompatibles).
- `valider_plateau` utilise cette raison dans chaque entrée de `"erreurs"` au lieu du message
  générique, et renvoie en plus `"combos_invalides"` : la liste des ids de tuiles de chaque
  combinaison fautive (tapis ET zones de pose), pour permettre son repérage visuel côté JS.

### 3. Surlignage de la combinaison fautive (`partie.py`, `api.py`, `jeu.js`, `jeu.css`)
- `jouer_tour` (plateau invalide) et `jeu_verifier_plateau` propagent désormais
  `combos_invalides` au front.
- `jeu.js` convertit ces listes d'ids en signatures (`id1|id2|...`) comparées au contenu courant
  de chaque combinaison du tapis/des zones de pose (`signatureCombo`) : la combinaison fautive
  reçoit la classe `.combi-invalide` (déjà utilisée pour les combinaisons <3 tuiles, bordure rouge
  pulsante) — et perd automatiquement ce surlignage dès que son contenu change (plus besoin de le
  nettoyer explicitement à chaque manipulation).
- Nouvelle règle CSS `.rangee-travail.combi-invalide` (même traitement que sur le tapis) pour les
  combinaisons encore en zone de pose au moment du contrôle.

## Tests
- `pytest` (25 tests, moteur + IA) : tous passent, aucune régression — les appelants existants de
  `valider_suite/valider_groupe/valider_combinaison/valider_plateau` (IA notamment) n'utilisaient
  que les clés `valide`/`points`/`type`, inchangées.
- `node --check jeu.js` et `python -m py_compile` : OK.

# Issue #135 — Seuil de dé-zoom automatique du tapis + réglage pour l'activer/désactiver

## Investigation : #128 a-t-il avancé le seuil de dé-zoom ?
Mesure réelle (Playwright, chargement direct de `jeu.html`/`jeu.css`, remplissage du tapis par
combinaisons de 3 tuiles jusqu'à détection du débordement `scrollHeight > clientHeight` de
`#zone-plateau-scroll`) comparant l'état juste avant #128 (commit `9c0f9b5`) et l'état actuel,
sur toutes les tailles de fenêtre autorisées par l'appli (`min_size=(900,600)` à la taille par
défaut `1100x750`, plus un format laptop `1366x768`) :

| Fenêtre    | Seuil AVANT #128 | Seuil APRÈS #128 |
|------------|:---:|:---:|
| 900×600 (taille mini)  | 7 combos  | 10 combos |
| 1024×600   | 9 combos  | 13 combos |
| 1100×650   | 11 combos | 16 combos |
| 1100×750 (défaut)      | 11 combos | 16 combos |
| 1366×768   | 13 combos | 19 combos |

Dans **toutes** les configurations testées, le seuil de débordement est plus **haut** après #128,
pas plus bas : le passage de `max-height: 260px` à `330px` sur `#zone-plateau-scroll` (plus
d'espace rendu au tapis) l'emporte largement sur la réduction de la zone de pose (4→2 rangées, qui
libère elle aussi de la place). Conclusion : **les changements de hauteur de #128 n'ont pas
dégradé le seuil — ils l'ont amélioré d'environ 30-45 %.** Aucune régression à corriger de ce
côté ; aucun changement de CSS/seuil n'a donc été apporté.

L'explication la plus probable de la perception d'Alain est documentée dans le code depuis #128 :
le bouton « Placer » permet désormais de transférer une zone de pose sur le tapis **avant**
validation du tour (combinaison visible immédiatement, pourtour vert), alors qu'avant #128 ces
tuiles restaient invisibles sur le tapis jusqu'au clic sur « Jouer ». Le tapis peut donc sembler
se remplir — et donc dézoomer — plus vite **au fil d'un même tour**, même si le seuil en pixels
qui déclenche le dé-zoom (évalué uniquement après « Jouer » ou un tour IA, `autoZoomSiTapisDeborde`
n'étant pas appelée depuis `placerRangee`) n'a lui pas changé. Une taille d'écran/fenêtre plus
petite que la machine de référence reste par ailleurs un facteur à part entière (voir tableau
ci-dessus : le seuil absolu chute fortement entre 1366×768 et 900×600, indépendamment de #128).

## Réglage ajouté : dé-zoom automatique activable/désactivable
- `reglages.py` : nouvelle clé persistée `dezoom_auto` (défaut `True`, comportement historique
  inchangé par défaut).
- `accueil.html`/`accueil.js` : nouvelle case dans l'onglet *Général* des réglages, « Dé-zoomer
  automatiquement le tapis quand il déborde », lue/sauvegardée comme les réglages existants
  (`ia_auto`, `mode_reorg`, etc.).
- `application.py` : la préférence est propagée dans `etat_jeu["config"]["dezoom_auto"]` au
  lancement d'une partie et à la reprise d'une partie existante (même mécanisme que `tri_auto`,
  issue #130).
- `jeu.js` : `autoZoomSiTapisDeborde()` ne fait plus rien si le réglage est désactivé
  (`dezoomAutoActif`, initialisé depuis `etat.config.dezoom_auto` à l'ouverture de la partie ;
  absent sur une vieille partie reprise ⇒ traité comme activé, pour ne pas changer le
  comportement des parties en cours).

# Issue #133 — Suite #131 : le double-clic sur une tuile du tapis ne finalisait pas le placement

## Contexte
L'issue #131 avait conclu, par analyse statique, que le double-clic sur une tuile du tapis
envoyait déjà directement la tuile en zone de pose active. Test en jeu réel : ce n'était pas le
cas — la tuile restait « attachée » au curseur (fantôme visible, zone d'insertion affichée),
nécessitant un clic supplémentaire pour la déposer.

## Investigation (reproduction réelle en navigateur, Playwright)
Contrairement au chevalet, où une tuile sélectionnée reste visible à la même position DOM (le
clic ne fait que basculer une classe CSS), prendre une tuile du tapis la **retire immédiatement**
du DOM (elle rejoint la zone de travail). Le détecteur de double-clic existant comparait
l'identité de la tuile entre les deux clics du geste — mais au moment du 2e clic physique, la
tuile d'origine avait déjà disparu (retirée par le 1er clic lui-même, qui prend déjà la tuile
immédiatement). Le 2e clic retombait donc sur la combinaison source (devenue "cible" au sens du
mode d'insertion ciblée, issue #47), ce qui affichait les zones d'insertion sans rien finaliser —
exactement le symptôme observé.

Un deuxième sous-cas existait : quand une autre tuile était déjà sélectionnée (mode ciblé actif,
ex. une tuile du chevalet), le double-clic sur une tuile du tapis fonctionnait par un mécanisme
différent (comparaison d'id, qui restait valide dans ce sous-cas car rien n'est retiré du DOM au
1er clic) mais laissait quand même la sélection et la combinaison ciblée actives en sortie — même
symptôme, cause différente.

## Correctif (`jeu.js`)
- Le détecteur de double-clic (comparaison d'id + horodatage, < 350 ms) reste attaché à toute
  tuile manipulable du tapis, quel que soit le mode ; sur 2e clic détecté, il prend désormais la
  tuile **et finalise immédiatement** (nouvelle fonction `finaliserSelectionTapis` : efface la
  sélection, la cible d'insertion et le fantôme), au lieu de laisser la sélection en attente.
- Pour le sous-cas où le 1er clic prend déjà la tuile immédiatement (aucune autre tuile en
  attente) : la tuile d'origine n'existe plus au 2e clic, qui retombe alors sur le conteneur de sa
  combinaison source. Ce conteneur mémorise désormais quelle combinaison vient de subir une prise
  (`derniereTuilePriseTapis`) et, si le 2e clic du geste y retombe dans la fenêtre de 350 ms, il
  finalise la sélection au lieu de désigner la combinaison comme nouvelle cible d'insertion.
- Validé par reproduction réelle (Playwright, mock de `window.pywebview.api`) sur : double-clic
  simple, double-clic avec une tuile déjà sélectionnée ailleurs (mode ciblé), simple clic seul
  (comportement préservé), et repositionnement volontaire d'une tuile prise vers une autre
  combinaison hors fenêtre de double-clic (comportement préservé).

## Résultat
Un double-clic sur une tuile du tapis la dépose désormais directement dans la zone de pose
active, en une seule interaction, sans clic supplémentaire — comportement cohérent avec le
double-clic sur une tuile de la main.

## Issue #134 — Mesure de la fréquence réelle de `_coup_scission` via le script de simulation

Suite à l'investigation en lecture seule de l'issue #133 (qui n'avait pas pu exécuter
`python3` sous le système de permissions en mode lecture), relance en écriture : un
script d'observation externe temporaire (non committé) a monkey-patché en mémoire
`rummikub.moteur.ia._coup_scission` pour compter ses déclenchements, sans modifier
`ia.py`, puis a exécuté 500 parties via `scripts/simulation_ia.simuler` (1 manche
chacune) :

- 150 parties « 4× Avancé » : 626 déclenchements, 98,0 % des parties avec ≥ 1
  déclenchement, moyenne 4,17/partie.
- 150 parties « 4× Expert » : 664 déclenchements, 97,3 % des parties, moyenne
  4,43/partie.
- 100 parties « 2× Avancé + 2× Expert » : 445 déclenchements, 98,0 % des parties,
  moyenne 4,45/partie.
- 60 parties multi-niveaux (Débutant/Facile/Intermédiaire/Avancé) : 58
  déclenchements, 63,3 % des parties, moyenne 0,97/partie (un seul joueur sur 4
  invoque le mécanisme).
- 40 parties multi-niveaux (Débutant/Facile/Intermédiaire/Expert) : 42
  déclenchements, 62,5 % des parties, moyenne 1,05/partie.

**Total global : 1835 déclenchements sur 500 parties, 90,8 % des parties avec au
moins un déclenchement, moyenne 3,67/partie.** Aucune anomalie détectée dans les 500
parties. Conclusion : `_coup_scission` n'est pas un cas théorique rarement atteint —
dès qu'un niveau Avancé ou Expert est présent, il se déclenche en pratique dans la
quasi-totalité des parties, plusieurs fois par partie en moyenne.

Aucune modification de `ia.py` ni d'aucun fichier du moteur. Le script d'observation
temporaire n'a pas été committé (conformément à la consigne de l'issue).

## Issue #131 — Double-clic sur une tuile du tapis → zone de pose active (déjà implémenté)

## Contexte
L'issue #131 demande qu'un double-clic sur une tuile du tapis l'envoie
directement dans la dernière zone de pose sélectionnée, sans clic
intermédiaire, sans toucher au simple clic ni au double-clic déjà existant
sur les tuiles du chevalet/zones de pose.

## Constat
Cette fonctionnalité est déjà intégralement implémentée depuis le commit
`a1fac21` (« Issue #103 : double-clic sur une tuile du tapis → la placer
dans la zone de pose active », 2026-08-10), toujours présent dans
`src/rummikub/ui/web/jeu.js` :

- Détection manuelle du double-clic sur une tuile du tapis (`dernierClicTapis`,
  ligne ~20, listener ligne ~336-348), posée avant tout autre handler de clic
  sur la tuile — même mécanisme que pour le chevalet (`dernierClicChevalet`).
- Au second clic (< 350 ms), `prendreTuileTapis(idxCombo, idxTuile)` (ligne
  ~940) retire la tuile de sa combinaison et la pousse directement dans
  `travail[rangeeActive]`, c'est-à-dire la zone de pose actuellement (ou
  dernièrement) activée via `activerRangee()`.
- Le comportement couvre aussi bien les combinaisons jouées lors de tours
  précédents que les tuiles posées pendant le tour en cours (extension
  issue #128), et n'altère ni le simple clic (toujours fonctionnel en dehors
  de la fenêtre de 350 ms) ni le double-clic du chevalet
  (`poserTuileDirectement`, mécanisme indépendant).

## Conclusion
Aucune modification de code nécessaire : le résultat attendu par l'issue
#131 est déjà couvert par l'implémentation de l'issue #103. Aucun fichier
touché.

# Issue #130 — Tri automatique : correction du dysfonctionnement et mémorisation du choix

## Contexte
La case « Tri automatique » (issue #126) était censée insérer chaque tuile
piochée directement à sa place triée dans le chevalet. En test réel, l'effet
ne se produisait pas correctement, et l'état de la case n'était jamais
persisté : il repartait toujours décoché à chaque relance.

## Diagnostic
`insererTrie()` (jeu.js) recherchait la position d'insertion par un simple
balayage linéaire supposant le chevalet **déjà trié**. Or un chevalet n'est
trié que si le joueur a cliqué sur « Trier » : la distribution initiale (et
toute réorg manuelle ultérieure) le laisse dans un ordre quelconque. Sur un
chevalet non trié, le balayage s'arrête dès le premier élément « plus grand »
rencontré en partant du début — une position qui n'a souvent aucun rapport
avec la vraie place triée globale (ex. un 13 rouge pioché atterrissait avant
une tuile bleue placée tôt dans la main, au lieu de rejoindre les autres
tuiles rouges). D'où l'impression que la case n'avait aucun effet.
Par ailleurs, la case n'était reliée à aucun réglage persisté : `reglages.py`
ne connaissait pas de clé `tri_auto`, et `jeu.js` ne faisait que maintenir
une variable JS locale (`triAutoActif`), réinitialisée à `false` à chaque
chargement de l'écran de jeu.

## Corrections
- **Tri** (`jeu.js`, `insererTrie()`) : au lieu d'une recherche de position
  par balayage linéaire, la fonction ajoute la tuile piochée au chevalet
  local puis retrie l'ensemble via `comparerTuiles` (même comparateur que le
  bouton « Trier »). Résultat garanti correct quel que soit l'ordre courant
  du chevalet.
- **Persistance** :
  - `reglages.py` : nouvelle clé `tri_auto` (défaut `False`) dans `DEFAUTS`.
  - `ui/application.py` : `naviguer_vers_jeu()` et `reprendre_jeu()`
    reportent désormais `cfg.get("tri_auto", False)` dans
    `etat_jeu["config"]["tri_auto"]`, selon le même schéma déjà utilisé pour
    `mode_reorg`/`ia_auto`.
  - `jeu.js` :
    - `init()` restaure `triAutoActif` et l'état de la case `#chk-tri-auto`
      depuis `etat.config.tri_auto` au chargement de l'écran de jeu.
    - le gestionnaire `change` de la case appelle désormais
      `window.pywebview.api.sauvegarder_reglages({ tri_auto: ... })` pour
      persister le choix immédiatement dans `config.json`.

## Fichiers touchés
`src/rummikub/reglages.py`, `src/rummikub/ui/application.py`,
`src/rummikub/ui/web/jeu.js`.

## Tests
- `python3 -m pytest` : 25 tests, tous au vert (aucune régression).
- `node --check src/rummikub/ui/web/jeu.js` : OK.
- Script Node ad hoc reproduisant un chevalet non trié + pioche d'un 13
  rouge : confirme que l'ancienne logique plaçait mal la tuile, et que la
  nouvelle la place correctement (regroupée avec les autres tuiles rouges).

## Issue #129 — Suite #128 : pourtour coloré sur extension directe + masquage "Jouer" pendant le jeu auto de l'IA

- **Pourtour du tour en cours (`.ce-tour`) peu visible sur une extension directe d'une combinaison du tapis.**
  Investigation approfondie (tests automatisés Playwright couvrant tous les chemins d'extension :
  zone début/fin/interne, avant/après mise initiale, plusieurs combinaisons) : la classe `.ce-tour`
  est en réalité déjà appliquée correctement par le JS (`jeu.js`) dans tous les cas, y compris
  l'extension directe — ce n'est donc pas un bug de logique. En revanche, une fois la mise initiale
  faite, la tuile du tapis reçoit *aussi* la classe `.tapis-manipulable` (contour pointillé bleu,
  2px, hors-bordure), qui écrase visuellement le pourtour vert de 1px de `.ce-tour` — exactement
  le cas de figure systématique lors d'une extension directe (impossible avant la mise initiale).
  Correction : `.tuile-jeu.ce-tour.tapis-manipulable` reprend désormais la couleur verte pour son
  contour au lieu du bleu, rendant le pourtour du tour en cours incontestable même combiné à l'état
  « manipulable » (`jeu.css`).
- **Bouton « Jouer » de l'IA masqué pendant le jeu automatique.** Quand le réglage "Jouer
  automatiquement le tour de l'ordinateur" (#126) est actif et que c'est au tour de l'IA, le bouton
  manuel `.btn-jouer-ia` n'est plus affiché le temps que le coup automatique se déroule — il
  réapparaît normalement dès que c'est de nouveau au tour d'un joueur humain ou que le réglage est
  désactivé (`jeu.js`, `rafraichirFichesJoueurs`). Supprime le risque de déclenchement concurrent
  identifié dans l'issue.

# Issue #128 — Bouton « Placer » par zone de pose + mise en évidence des tuiles du tour en cours sur le tapis

## Contexte
Jusqu'ici, les tuiles composées dans une zone de pose restaient dans un
espace totalement séparé du tapis jusqu'au clic sur « Jouer », qui les
transférait toutes d'un coup et validait le tour. Il était donc impossible
de combiner les tuiles d'une zone de pose avec celles déjà présentes sur le
tapis (ex. étendre une suite existante) avant la validation définitive.

## Ajouts / changements
- **Bouton « ⬆ Placer » par zone de pose** (`jeu.html`, `jeu.css`,
  `jeu.js` : fonction `placerRangee()`) : transfère immédiatement les tuiles
  de la zone sur le tapis (`plateauLocal`), sans valider le tour — rien n'est
  envoyé au serveur à ce stade, seul « Jouer » le fait. N'apparaît que si la
  zone n'est pas vide (même convention que « Vider »/« Trier »).
- **Pourtour coloré sur le tapis** : les tuiles posées ce tour (via « Placer »,
  une extension de combinaison ou une récupération de joker) portent déjà la
  classe `.ce-tour` (bordure verte) — ce rendu s'applique désormais aussi aux
  tuiles transférées par « Placer ».
- **Réarrangement unifié** (`rafraichirPlateau()`) : une fois la mise initiale
  faite, une tuile du tour en cours se manipule avec EXACTEMENT le même
  mécanisme que les tuiles des tours précédents (clic pour la prendre,
  double-clic, insertion ciblée) — y compris en la combinant avec d'autres
  tuiles du tour en cours ou déjà présentes. Avant la mise initiale (où ce
  mécanisme de réarrangement n'existe pas encore), le comportement précédent
  (reprise directe vers la main) est conservé à l'identique.
- **« Jouer »** reste inchangé : il valide l'ensemble du tapis
  (`plateauLocal` + zones de pose encore non placées), fige les combinaisons
  et retire le pourtour coloré (`tuilesCeTour` est vidé par `reinitTour()`
  après succès).
- **« Annuler »** : vérifié sans changement nécessaire — comme les tuiles
  « Placées » ne vivent que dans l'état local (`plateauLocal`/`travail`)
  jusqu'à « Jouer », `onAnnuler()` les efface déjà intégralement en
  réinitialisant `plateauLocal` depuis l'état serveur (`reinitTour()`).
- **2 zones de pose au lieu de 4** (`jeu.html`, `jeu.css`) : la grille passe
  d'un agencement 2×2 à une seule ligne de 2 colonnes. La hauteur libérée est
  réattribuée au tapis : `#zone-plateau-scroll` passe de 260px à 330px de
  hauteur maximale.

## Validation
- `node --check src/rummikub/ui/web/jeu.js` : OK.
- `python3 -m pytest` : 25 tests, tous au vert (aucune régression — ce
  changement est entièrement côté client, aucun fichier Python modifié).
- Relecture manuelle du flux complet : chevalet → zone de pose → « Placer »
  (tuiles sur le tapis avec pourtour vert) → réarrangement sur le tapis avec
  le mécanisme existant (prise, insertion, combinaison avec d'autres tuiles
  du tour) → « Jouer » (validation, pourtour retiré) ou « Annuler » (retour
  complet à l'état de début de tour, y compris les tuiles déjà « Placées »).

# Issue #127 — Réorganisation des tuiles dans une zone de pose, comme sur le tapis

## Contexte
Le mécanisme d'insertion d'une tuile entre deux tuiles déjà placées existait
déjà dans le code des zones de pose (ajouté aux issues #27 et #31, zones
`.zone-ext-interne` + `insererTuileRangee`), au même titre que sur le tapis.
Mais `selectionnerTuile()` — appelée au clic sur une tuile du chevalet —
rafraîchissait le chevalet et le tapis, sans jamais rafraîchir la zone de
travail. Les zones d'insertion internes des rangées de pose (et les
gestionnaires de clic associés) restaient donc figés dans l'état « aucune
tuile sélectionnée », rendant l'insertion interne invisible et inopérante :
seul un clic sur le fond de la rangée (= ajout systématique en fin) restait
disponible.

## Correction
`src/rummikub/ui/web/jeu.js` — `selectionnerTuile()` appelle désormais aussi
`rafraichirZoneTravail()`, au même titre que `rafraichirChevalet()` et
`rafraichirPlateau()`. Les zones d'insertion (avant la première tuile, entre
deux tuiles, après la dernière) apparaissent donc correctement dès qu'une
tuile du chevalet est sélectionnée, avec le même comportement que sur le
tapis.

## Validation
- `node --check src/rummikub/ui/web/jeu.js` : OK.
- `python3 -m pytest` : 25 tests, tous au vert (aucune régression).
- Relecture manuelle du flux : sélection d'une tuile du chevalet → zones
  `.zone-ext-interne` recréées dans chaque rangée de travail non vide, avec
  les bons gestionnaires de clic (`insererTuileRangee` au lieu de l'ancien
  `reprendreTuileRangee` figé).

# Issue #126 — Ergonomie : jeu automatique de l'IA, tri automatique au pioché, suppression d'un texte inutile

## Contexte
Trois petites améliorations d'ergonomie identifiées en jouant, indépendantes
les unes des autres.

## Ajouts / changements
- **Jeu automatique de l'IA** : nouveau réglage « Jouer automatiquement le
  tour de l'ordinateur » (onglet Général des réglages, clé `ia_auto` dans
  `config.json`). Quand il est actif, dès que c'est le tour d'une IA, son
  coup se déclenche seul après une latence d'environ 1 seconde (pour ne pas
  paraître brusque), sans qu'il faille cliquer sur le bouton « Jouer » de sa
  fiche. Ce bouton manuel reste affiché et fonctionnel (clic possible pendant
  la latence, ou si le réglage est désactivé).
- **Tri automatique à la pioche** : nouvelle case à cocher « Tri automatique »
  à côté du bouton « Trier » du chevalet. Quand elle est active, chaque tuile
  piochée est insérée directement à sa place triée (couleur puis valeur,
  jokers en fin) plutôt qu'ajoutée en fin de chevalet. Le bouton « Trier »
  existant est inchangé et reste utilisable indépendamment de la case.
- **Suppression du texte « Mes tuiles — cliquez, réarrangez »** affiché
  au-dessus du chevalet du joueur : n'apportait rien à l'utilisateur.

## Fichiers touchés
`src/rummikub/reglages.py`, `src/rummikub/ui/application.py`,
`src/rummikub/ui/web/{accueil.html,accueil.js,jeu.html,jeu.css,jeu.js}`.

# Issue #125 — Script headless de simulation de parties IA vs IA

## Contexte
Le moteur de jeu est pur Python, découplé de l'UI pywebview, mais il n'existait
aucun moyen de vérifier qu'une partie complète se déroule sans erreur sans
passer par l'interface (lancement manuel, clics répétés sur « tour IA »).

## Ajout
`scripts/simulation_ia.py` (nouveau) : script headless qui fait s'affronter
2 à 4 IA entre elles sur une ou plusieurs manches complètes, en pilotant
directement `rummikub.moteur` (sans pywebview). La boucle de tour reproduit
exactement la logique de `Api.jeu_ia_jouer` (même traitement du cas « coup IA
invalide » : annulation + pioche de secours), afin que la simulation couvre le
même chemin de code que le jeu réel.

- Options CLI : `--joueurs` (2-4, défaut 4), `--niveaux` (liste explicite par
  joueur, sinon répartition cyclique sur les 5 niveaux), `--manches` (défaut
  1), `--max-tours` (garde-fou anti-blocage par manche, défaut 500), `--seed`
  (reproductibilité), `-v/--verbose` (log de chaque tour).
- Toute exception levée par l'IA, tout coup invalide proposé, toute action IA
  inconnue ou tout blocage (dépassement de `--max-tours` sans fin de manche)
  est journalisé (`logging`) et compté comme anomalie.
- Résumé final sur stdout : manches/tours joués, durée, scores cumulés,
  liste des anomalies. Code de sortie 0 si la partie est saine, 1 sinon.

## Validation
- `python3 -m pytest` : 25 tests, tous au vert (aucune régression).
- Exécutions manuelles de confirmation : 60 parties simulées (2/3/4 joueurs,
  5 niveaux mélangés, seeds 100 à 119, 2 manches chacune) + plusieurs runs
  ciblés (4 IA de niveaux différents, 3 joueurs sur 3 manches, 2 IA Expert
  face à face, mode verbeux) — **aucune anomalie détectée dans tous les cas**.
  Exemple de résumé obtenu :
  ```
  RÉSUMÉ : 3/3 manche(s) jouée(s), 268 tour(s) au total, 0.17s.
  Scores cumulés finaux : {'IA-1 (Débutant)': -387, 'IA-2 (Facile)': -159, 'IA-3 (Intermédiaire)': -286}
  Aucune anomalie détectée.
  ```

# Issue #104 — Zoom automatique quand le tapis déborde après une pose

## Contexte
Quand une combinaison posée dépassait la zone visible du tapis, le joueur ne
s'en rendait pas compte (combinaison hors écran) et devait dézoomer manuellement.

## Modification
`src/rummikub/ui/web/jeu.js` :

- Nouvelle fonction `autoZoomSiTapisDeborde()` (placée après `brancherZoomTapis`).
  Elle mesure le débordement de la zone visible du tapis (`#zone-plateau-scroll` :
  `scrollHeight > clientHeight` ou `scrollWidth > clientWidth`). En cas de
  débordement, elle réduit le zoom d'UN cran en réutilisant la fonction de zoom
  existante `appliquerZoomTapis()` (100 % → 75 % → 50 %), et mémorise le niveau
  dans `localStorage` comme le font les boutons manuels.
  - Les niveaux sont lus depuis les boutons `#zoom-tapis .btn-zoom` (aucune valeur
    codée en dur), donc restent synchronisés avec le HTML.
  - Ne descend jamais sous le niveau minimal (dernier bouton).
  - Ne fait rien si le contenu est déjà entièrement visible.
  - Un seul cran par pose : le joueur garde la main et peut rezoomer librement ;
    l'automatisme ne se redéclenche qu'à la pose suivante.

- Appel de `autoZoomSiTapisDeborde()` après le rafraîchissement du plateau aux
  deux seuls points de pose réelle de tuiles :
  - `onJouer()` (pose humaine validée), après `rafraichirTout()`.
  - `jouerIA()` (pose de l'IA), après le `rafraichirTout()` final. Les cas
    « pioche » / « passe » de l'IA sortent avant ce point (aucune tuile ajoutée),
    donc n'y déclenchent pas de zoom.

## Résultat
- Après une pose faisant déborder le tapis, le zoom se réduit d'un cran.
- Le joueur ajuste ensuite librement ; l'auto-zoom ne se réimpose qu'à la pose
  suivante.
- Le zoom minimal n'est jamais dépassé.
- Tests existants : 25 passés. Syntaxe JS vérifiée (`node --check`).

# CHANGELOG — Issue #113

## Correction rebuild_rummikub.bat : chemin Z:\CCW\rummikub à l'étape 8

- `build/rebuild_rummikub.bat` (étape 8, hors mode `--publier`) : la commande
  `git -C Z:\CCW\rummikub reset --hard origin/master` référençait le lecteur
  réseau `Z:` qui n'existe plus sur le PC fixe physique (échec silencieux).
  Remplacement du chemin par `C:\CCW_Share\CCW\rummikub` (même correctif que
  `rebuild_scrabble.bat`, issue #410).
- Correction également du commentaire stale ligne 349
  (`%ORIGDIR% = Z:\CCW\rummikub` → `%ORIGDIR% = C:\CCW_Share\CCW\rummikub`)
  afin qu'il ne subsiste plus aucune référence à `Z:\CCW` dans le fichier.

## Contexte
Retours de tests sur machine réelle (public âgé) : le terme « IA » est anxiogène.

## Modifications
- `src/rummikub/ui/web/accueil.html` : le paramètre « Vitesse de l'IA » (bloc
  `<select id="rgl-vitesse">`) est déplacé de l'onglet « Règles du jeu »
  (`#panneau-regles`) vers l'onglet « Général » (`#panneau-general`), et son
  label affiché est renommé en « Vitesse de l'ordinateur ».
- `src/rummikub/ui/web/jeu.js` : commentaire mis à jour pour refléter le
  nouveau libellé (« Vitesse de l'ordinateur »).

## Points d'attention
- Les identifiants techniques internes sont conservés inchangés :
  `id="rgl-vitesse"` (DOM) et la clé `vitesse_ia` (config.json, `reglages.py`,
  `application.py`, `accueil.js`, `jeu.js`). Seul le libellé affiché change,
  conformément à la demande.
- Aucun fichier Python modifié : la logique de lecture/écriture du réglage
  (par `id`) reste valide après le déplacement du bloc.

---

# CHANGELOG — Issue #61

## Mise à jour TACHES.md — icône et intégration Actualise

- Déplacé « Icône application (assets/rummikub.ico) » de « À faire » vers
  « Fonctionnalités implémentées » (le fichier existe déjà dans le dépôt).
- Ajouté une note « Intégration Actualise (Issue #59, #60) » dans les
  fonctionnalités implémentées : `rummikub.iss` et `rebuild_rummikub.bat`
  embarquent l'updater autonome, raccourcis pointant vers `Actualise.exe`,
  génération automatique de `config.json`, production de `rummikub.zip`,
  suppression de la section [Run].
- Conservé « Build Windows via CCW » dans « À faire » avec la précision que
  le pipeline d'installation est désormais prêt.
# Issue #93 — Lancement d'Actualise au démarrage de Rummikub

## Contexte
Même refonte architecturale que Scrabble — symétrique. Au démarrage, Rummikub
doit lancer Actualise en arrière-plan s'il est présent sur la machine.

## Modifications
- `main.py` : nouvelle fonction `_lancer_actualise_au_demarrage()`.
  - Si `C:\Actualise\Actualise.exe` existe → le lance en subprocess
    non-bloquant (`subprocess.Popen`) avec l'argument `--config rummikub`.
  - Si absent → retour immédiat, aucun effet.
  - Si le lancement échoue → exception avalée, simple log discret sur
    `stderr`, jamais d'exception propagée.
  - Appelée dans `__main__`, avant `_lancer_actualise_ui_si_flag()` et avant
    l'ouverture de la fenêtre.

## Points d'attention
- Le check `actualise_update.flag` existant (`_lancer_actualise_ui_si_flag()`)
  reste **inchangé** : les deux mécanismes coexistent.
- Chemin Windows codé en dur (`C:\Actualise\Actualise.exe`) conforme à la
  demande de l'issue ; sur Linux le fichier n'existe pas → `return` silencieux,
  le jeu démarre normalement.
- Non-bloquant : `Popen` n'attend pas la fin du processus, le démarrage du jeu
  n'est ni bloqué ni retardé.

---

# Issue #75 — Mode `--publier` dans `rebuild_rummikub.bat` (SHA-256 + version.json automatiques)

## Contexte
Automatiser la publication d'une nouvelle version pour éviter les erreurs
manuelles (numéro de build, calcul du SHA-256, rédaction de `version.json`).
La référence mentionnée (`build/rebuild_actualise.bat` du dépôt
`AlainDelree/Bridge_Agent`, issue #365) n'était pas accessible au moment du
traitement (HTTP 404 : chemin absent de l'arbre `master`) ; l'implémentation
s'appuie donc sur la spécification détaillée de l'issue.

## Modifications
- `build/rebuild_rummikub.bat` :
  - **Analyse d'arguments** (nouveau bloc après `setlocal`) : `--publier`
    (active la publication) et `--build N` (force le numéro de build). Sans
    argument, le comportement historique est strictement inchangé.
  - **Étape 8bis (`--publier` uniquement)**, insérée après l'étape 8 (une fois
    `rummikub.zip` généré) :
    - lecture du build courant depuis `%ORIGDIR%\version.json` via PowerShell
      (`ConvertFrom-Json`), puis `build + 1` ; surchargé par `--build N` ;
    - réécriture de `manifest.json` avec le nouveau numéro et régénération de
      `rummikub.zip` (`Compress-Archive` de `dist\Rummikub\*` + `manifest.json`),
      recopié vers le partage ;
    - calcul du **SHA-256** du zip via `Get-FileHash` (PowerShell), en
      minuscules ;
    - écriture de `version.json` à la racine du clone partagé (`%ORIGDIR%`,
      soit `Z:\CCW\rummikub`) au format `{"build": N, "sha256": "..."}` ;
    - **commit local** de `version.json` (`git -C "%ORIGDIR%" commit -- version.json`).
  - **Étape 9** : en mode `--publier`, le `git reset --hard origin/master` du
    clone partagé est **désactivé** afin de préserver le commit `version.json`
    fraîchement créé (il serait sinon effacé). Comportement normal inchangé
    hors `--publier`.
  - **Fin de script** : en mode `--publier`, rappel explicite des étapes
    restées **manuelles** — `git push` puis création de la Release GitHub (tag
    `vN`) avec `Rummikub-Setup.exe` et `rummikub.zip` en pièces jointes.

## Points d'attention
- **Jamais de `git push` ni de `gh release create`** dans le script,
  conformément à l'issue et aux consignes du bridge : seul un commit local est
  réalisé.
- Le `reset --hard` de l'étape 9 aurait supprimé le commit `version.json` en
  mode publication : il est donc explicitement contourné dans ce mode. En mode
  normal (sans `--publier`), aucun commit n'est fait et le reset garde son
  rôle de nettoyage habituel.
- `--build N` fixe le build à **N** exactement (pas `N+1`) ; sans lui, le build
  vaut `version.json.build + 1`.
- Script Windows (`.bat`) : non exécutable/validable sous Linux ; revue
  statique de la syntaxe batch effectuée (labels, blocs `if`/parenthèses,
  échappements `^( ^)`, expansion différée `!VAR!`).
