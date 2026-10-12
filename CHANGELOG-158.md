# Issue #158 — Suite #144 : la main n'est plus triée après un rejeu du dernier coup IA

## Contexte
Le tri du chevalet (bouton « Trier » et case « Tri automatique », #126) est un état purement
côté client : la variable `chevaletLocal` n'est jamais renvoyée au serveur, qui conserve de son
côté l'ordre de distribution/pioche (non trié). Le rejeu du dernier coup IA (#144), quand des
tuiles du tour en cours étaient encore sur le tapis, appelait `onAnnuler()` pour les remettre en
main avant de lancer l'animation. Or `onAnnuler()` appelle `reinitChevaletLocal()`, qui repart
délibérément de l'ordre serveur (comportement voulu pour un vrai clic sur « Annuler ») — ici
invoqué silencieusement en coulisse par le rejeu, ce qui écrasait le tri de la main sans que le
joueur l'ait demandé.

## Correctif (`jeu.js`)
Dans `rejouerDernierCoupIA()`, après l'appel interne à `onAnnuler()`, réapplique le tri du
chevalet (`trierChevalet()`) si le réglage « Tri automatique » est actif — cohérent avec ce que
produirait normalement l'ajout d'une tuile en main pendant que ce réglage est actif.

Si « Tri automatique » est désactivé, le comportement est inchangé (main dans l'ordre serveur,
comme pour un vrai « Annuler »).
