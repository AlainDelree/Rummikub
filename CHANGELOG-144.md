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
