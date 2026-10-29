# Issue #214 — Pas à pas : un découpage « une étape = une modification », des repères d'origine et une bascule Avant/Après corrigée (suite de #207)

Sur un gros coup d'Expert (Léo), le pas-à-pas ne se lisait bien ni en condensé
(#207, plusieurs modifications fusionnées dans une même étape) ni en détaillé
(une tuile à la fois, trop fin), et la bascule Avant/Après (#207) avait trois
défauts. Cette issue ajoute un **troisième découpage, désormais le mode par
défaut**, et corrige la bascule. **Aucun changement au moteur de jeu, à l'IA ni
à la sauvegarde.** Voir **CONTEXTE.md §12sexies**.

## 1. Nouveau découpage « une étape = une modification » (mode par défaut)

- `moteur/description_coup.py` : `etapes_coup_ia(avant, apres, mode=...)` avec
  trois modes — `"modification"` (**défaut**, remplace le condensé comme mode
  affiché), `"detaille"` (bouton « Détailler », inchangé) et `"condense"`
  (conservé pour `coups_rates.py` et la non-régression). L'ancien booléen
  `condense` reste accepté (rétrocompatibilité).
- Chaque étape porte sur **UNE SEULE combinaison** et dit toujours CE qui bouge
  et D'OÙ ça vient / vers où :
  - **Défaire une combinaison = UNE étape** : toutes ses tuiles réelles (joker
    compris) rejoignent le cadre d'un coup, puis elle disparaît
    (« Le groupe de 9 est défait : le 9 bleu, le 9 jaune et le 9 noir rejoignent
    les tuiles à placer. »). C'est le point qui distingue ce mode du condensé
    (défaite invisible) et du détaillé (une étape par destination).
  - **Créer / compléter = UNE étape chacune**. Une combinaison qui ne fait que
    perdre une tuile précise où elle va (« Le 11 rouge sort de la suite rouge
    (8 à 11) et rejoint les tuiles à placer. »).
  - Ordre causal, cadre, écrans « Départ » / « Les jokers », dernière étape
    (plateau d'après exact, cadre vide) et surbrillance forte `.tuile-pas-active`
    (#209) : inchangés.
- Résultat : coup de Clara tour 45 = **16 étapes** (condensé 10, détaillé 30),
  bien entre les deux. Chaque étape ne touche qu'une combinaison (vérifié par
  aspect — une relabellisation invisible ne compte pas). Borne :
  `combinaisons modifiées + créées + 3`.
- `ui/api.py` stocke `etapes` = `"modification"`, `etapes_detaillees` =
  `"detaille"`. `persistance/coups_rates.py` épinglé à `"condense"`.

## 2. Repères d'origine dans l'aperçu du plateau (front-end)

- À chaque étape, pour chaque tuile nommée qui change de place, un **couple de
  pastilles de même couleur** : un bandeau « Départ » dans la zone quittée
  (`.bandeau-departs`) et une pastille « arrivée » en coin de la tuile à sa
  nouvelle place (`.pastille-arrivee`). Calcul par diff avec l'étape précédente
  (`calculerReperesOrigine`).
- **Limite signalée (comme prévu par l'issue)** : une vraie flèche reliant les
  deux points n'est pas réalisable proprement dans la mise en page actuelle
  (cadre et plateau sont deux zones séparées, re-rendues à chaque étape) — on
  livre donc le repère par pastilles, explicitement prévu en repli.

## 3. Bascule Avant/Après corrigée

- **5a** : combinaisons comparées par **contenu visible** (multiset d'aspects,
  ids ignorés), plus par identifiants — une combinaison identique avant/après
  n'est plus entourée de bleu. Repères de tuile posés uniquement dans une
  combinaison mise en évidence.
- **5b** : vert (« venue de la main ») et orange (« déplacée ») **bien plus
  visibles** dans l'overlay (contour épais + halo + voile teinté), lisibles sur
  n'importe quelle couleur de tuile et sur les deux thèmes — auparavant les
  liserés du vrai tapis ne s'y appliquaient pas.
- **5c** : **légende illustrée** — un vrai exemple dans chaque repère : UNE
  mini-tuile dans le repère vert et orange, TROIS côte à côte dans le repère
  bleu, pour comprendre la forme (une tuile vs une combinaison) sans lire le
  texte.

## 4. Mode détaillé conservé

Le bouton « Détailler » ouvre toujours le découpage tuile par tuile, inchangé.
Ligne de taille, bascule Avant/Après, seuil d'affichage du bouton « Pas à pas »
inchangés.

## 5. Tests

- `tests/test_description_coup.py` : nouvelle section « une modification »
  (défaite en une étape, sortie explicite vers le cadre, Clara entre condensé et
  détaillé, invariants sur les gros coups réels Clara/Alice, coup court inchangé,
  rétrocompat `condense`).
- `tests/test_playwright_pas_a_pas.py` : repères d'origine présents quand une
  tuile bouge et absents au « Départ », combinaison inchangée non surlignée,
  légende illustrée par des tuiles.
- `tests/test_condense_solveur.py` et `coups_rates` épinglés à `mode="condense"`
  (comportement inchangé).

Suite complète : 319 tests passés, 13 sautés (Playwright sur `jeu.html`, jamais
la vraie app pywebview).
