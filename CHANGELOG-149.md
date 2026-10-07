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
