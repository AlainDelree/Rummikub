## Investigation + correction (issue #156)

Double-clic sur un joker libéré (ex. par scission/détachement IA, #150) :
inconstant selon qu'une tuile de la main est déjà sélectionnée au moment du
double-clic.

### Reproduction (Playwright, chargement direct de `jeu.html` avec un état de
partie simulé et `window.pywebview.api` mocké, pas l'appli pywebview réelle)

- Double-clic sur une tuile du tapis **sans** tuile de la main déjà
  sélectionnée : fiable (8/8 essais, délais de 60 à 270 ms entre les 2
  clics) — le 1er clic prend déjà la tuile dès son premier clic (branche
  « prise immédiate », #133), le 2e clic du geste est sans effet.
- Double-clic sur la **dernière** tuile d'un groupe stable de 3, **avec**
  une tuile de la main déjà sélectionnée : **échec systématique (8/8 KO)**.
  Double-clic sur la **1re** tuile du même groupe dans les mêmes conditions :
  fiable (8/8 OK).

### Cause confirmée

Quand une tuile de la main est sélectionnée (mode « insertion ciblée », #47),
cliquer une tuile d'une combinaison du tapis qui n'est pas encore la cible
active ne la prend pas : le clic remonte au conteneur de la combinaison, qui
l'active comme cible (`comboActive`). Cette activation révèle les zones
d'insertion de la combinaison (`zone-ext-debut`/`-interne`/`-fin`, jusque-là
masquées) et **décale horizontalement** les tuiles qui suivent le début du
groupe — décalage d'autant plus grand que la tuile ciblée est loin du début
(une tuile en bout de groupe, comme un joker fraîchement libéré par une
scission/un détachement, cumule le décalage de toutes les zones internes qui
la précèdent).

Le 2e clic du double-clic, visé par l'utilisateur (ou par Playwright, qui
simule un vrai double-clic humain : 2 clics à coordonnées écran fixes, sans
déplacement de souris) aux mêmes coordonnées que le 1er, rate alors sa cible
décalée et atterrit sur une zone d'insertion ou une tuile voisine au lieu de
la tuile visée — la prise échoue silencieusement, de façon intermittente
selon la position de la tuile dans son groupe. C'est exactement le mécanisme
déjà documenté par #146 pour la branche « échange de joker » (dont le
correctif proposait l'échange dès le 1er clic pour éviter d'avoir à activer
la combo d'abord) — #156 est le même problème pour la prise directe d'une
tuile ordinaire (pas un échange), qu'#146 ne couvrait pas.

### Correctif

`src/rummikub/ui/web/jeu.js` — dans `rafraichirPlateau()`, branche
« combo non active et sans échange possible pour cette tuile » (mode
insertion ciblée) : au lieu de laisser le clic remonter immédiatement activer
la combinaison comme cible, on coupe la remontée (`stopPropagation`) et on
**diffère l'activation de 350 ms** (durée de la fenêtre de double-clic déjà
utilisée par #133/#103). Le détecteur de double-clic existant, s'il détecte
un 2e clic sur la même tuile dans ce délai, annule cette activation différée
(`clearTimeout`) et prend la tuile directement — le décalage de layout
n'intervient alors jamais entre les deux clics. Un simple clic isolé (pas de
2e clic) continue de fonctionner normalement, juste activé ~350 ms plus tard
qu'avant (imperceptible pour une action manuelle).

Nouvelle variable module-level `activationCombinaisonDifferee` (minuteur en
cours, ou `null`).

### Vérifications de non-régression (Playwright)

- Joker en bout d'un groupe de 3 tuiles (pas seul dans son groupe — cas
  littéral de l'issue, joker détaché en bout de suite par l'IA #150), avec
  tuile de la main déjà sélectionnée : 6/6 OK après correctif (contre
  l'échec systématique constaté avant, pour le cas analogue « dernière tuile
  d'un groupe »).
- Simple clic unique (sans 2e clic) sur une combo non active : toujours
  activée comme cible après le délai — le ciblage normal (#47) n'est pas
  cassé.
- Échange de joker (#146) : toujours immédiat (<150 ms), pas de délai
  introduit sur ce chemin (branche `estEchangeJoker`, inchangée).
- `pytest` (33 tests) : toujours au vert (aucun fichier Python modifié).

### Limite

Correctif scindé spécifiquement pour la prise directe d'une tuile tapis en
mode insertion ciblée. Le même mécanisme de décalage pourrait en théorie
affecter d'autres interactions basées sur un double-clic rapide pendant que
le layout se réorganise ; non constaté ailleurs lors de cette investigation.
