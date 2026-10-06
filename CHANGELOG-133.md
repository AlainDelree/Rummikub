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
