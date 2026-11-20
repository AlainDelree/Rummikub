## Issue #251 — Interface : la tuile reprise ne retrouve pas sa place avec le tri automatique, et l'animation IA trop lente en « Rapide »

### Tri automatique (`chevaletLocal`)

Cause : `insererTrie()` (tri à l'insertion, issue #126/#130) n'était appelée
qu'à la pioche. Les trois autres chemins de retour d'une tuile au chevalet
faisaient un simple `chevaletLocal.push(d)` en fin de liste, sans vérifier
`triAutoActif` :
- `reprendreTuileRangee()` — tuile reprise dans la zone de pose (le cas
  signalé : poser puis reprendre avant « Jouer »).
- `viderRangee()` — bouton « ✕ » qui vide toute une rangée de pose.
- `reprendreTuile()` — tuile reprise depuis le tapis (posée ce tour puis
  reprise).
- `onAnnuler()` (bouton « Annuler ») — repart de `reinitChevaletLocal()`
  (ordre serveur, jamais trié) sans réappliquer le tri ensuite ; seul
  l'appel interne depuis `rejouerDernierCoupIA()` le faisait déjà (issue
  #158), le bouton direct non.

Correction : nouvelle fonction partagée `rendreAuChevaletLocal(d)` (trie via
`insererTrie()` si `triAutoActif`, sinon pousse en fin comme avant), utilisée
par les trois premiers chemins ; `onAnnuler()` appelle désormais
`trierChevalet()` lui-même si `triAutoActif` (la duplication dans
`rejouerDernierCoupIA()` devient inutile et est supprimée). Case décochée :
comportement inchangé dans tous les cas.

### Vitesse de l'animation IA

Durées relevées dans `jeu.js` (`VITESSES_IA`, `MULTIPLICATEURS_REJEU_IA`) :

| Vitesse (ordinateur) | attente avant le coup | délai entre tuiles |
|---|---|---|
| Rapide (avant) | 400 ms | 400 ms |
| Rapide (après) | **200 ms** | **250 ms** |
| Normale (inchangé) | 800 ms | 700 ms |
| Lente (inchangé) | 1500 ms | 1200 ms |

Cause principale, non visible dans cette seule table : `animerPoseTuiles()`
avait aussi DEUX pauses fixes, **identiques pour les 4 vitesses** — 200 ms
avant la 1re tuile et 800 ms après la dernière. Pour un coup d'une ou deux
tuiles (le cas le plus fréquent), le délai entre tuiles ne joue aucun rôle
(boucle à une seule itération) : le temps perçu valait alors 200+800 = 1000
ms quelle que soit la vitesse choisie — « Rapide » ne paraissait donc
quasiment pas plus rapide que « Normale ». C'est la cause du symptôme
signalé.

Correction : ces deux pauses deviennent des champs `premiereTuile`/`finPose`
de `VITESSES_IA` (et de la nouvelle table `PAUSES_REJEU_IA` côté rejeu, voir
plus bas), passés en paramètres de `animerPoseTuiles()` (valeurs par défaut
200/800 conservées si non fournies). Seule la ligne « Rapide » change :
`premiereTuile` 200→80 ms, `finPose` 800→250 ms. « Normale » et « Lente »
gardent 200/800, donc un comportement bit-à-bit inchangé.

Effet sur un coup d'une tuile (le cas courant) : 1000 ms → 330 ms en
« Rapide » (×3 environ), « Normale »/« Lente » inchangées. Sur un coup de 4
tuiles : ≈ 2680 ms → ≈ 960 ms en « Rapide » (×2,8 environ). Valeurs choisies
pour rester lisibles : le temps entre deux tuiles (250 ms) reste proche de
la durée de l'animation CSS d'apparition d'une tuile (`tuile-pose`, 600 ms,
inchangée), sans la dépasser excessivement — léger chevauchement visuel déjà
présent avant ce correctif pour « Rapide » sur un coup à plus de 3 tuiles.

Rejeu animé (`vitesse_rejeu_ia`, réglage séparé, issue #160/#164) : même
cause et même défaut. `MULTIPLICATEURS_REJEU_IA.Rapide` repasse de 1.5× à
1.0× (Lente 3.2× et Moyenne 2.2× inchangés) ; nouvelle table
`PAUSES_REJEU_IA` donnant à « Rapide » ses propres pauses courtes (80/250 ms,
comme ci-dessus) au lieu des 200/800 ms partagées avec « Lente » et
« Moyenne » (qui, elles, les gardent).

Aucune modification du calcul de l'IA ni du budget du solveur : seules les
constantes d'animation front-end ont changé.

### Tests

- `tests/test_playwright_tri_automatique.py` (nouveau) : pose puis reprise
  d'une tuile (zone de pose, tapis, vidage de rangée, annulation du tour),
  tri coché et décoché.
- `tests/test_playwright_vitesse_ia.py` (nouveau) : ordre strict
  Rapide < Normale < Lente sur `reflexion`/`tuile` ; Rapide < Normale ≤ Lente
  sur `premiereTuile`/`finPose` ; même ordre côté rejeu
  (`MULTIPLICATEURS_REJEU_IA`, `PAUSES_REJEU_IA`) ; un coup à une seule
  tuile prend au moins deux fois moins de temps en « Rapide » qu'en
  « Normale ».
- Suite complète : `pytest -q` → 468 passed, 13 skipped (aucune régression).

### Documentation

`CONTEXTE.md` non modifié : aucune règle d'interface ni valeur de vitesse n'y
est décrite (seule une mention générale, non chiffrée, de `vitesse_ia` côté
`etat["config"]`, inchangée par cette issue).
