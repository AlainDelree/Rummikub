# Issue #160 — Réglage de la vitesse du rejeu du dernier coup IA (lent/moyen/rapide)

## Contexte
Le rythme du rejeu à la demande du dernier coup IA (#144, ralenti pour les tours à plusieurs
tuiles par #149) restait trop rapide au goût d'Alain, sans qu'il souhaite pour autant un
ralentissement fixe qui serait trop lent dans d'autres cas. Il voulait un choix de vitesse.

## Correctifs

### Nouveau réglage « Vitesse du rejeu du dernier coup IA » (onglet Général)
Ajout d'un `<select>` à 3 niveaux — Lente / Moyenne / Rapide — dans `accueil.html`, persisté via
`reglages.py` (`vitesse_rejeu_ia`, défaut `"Rapide"` pour ne rien changer au comportement existant
par défaut). Chargé/sauvegardé dans `accueil.js` comme les autres préférences UI (`mode_reorg`,
`dezoom_auto`...), et propagé dans `etat_jeu["config"]` par `application.py`
(`naviguer_vers_jeu`/`reprendre_jeu`), à la manière de ces mêmes préférences.

### Application du multiplicateur (`jeu.js`)
Ce réglage est **distinct** de « Vitesse de l'ordinateur » (`vitesse_ia`) qui pilote le délai de
réflexion et le rythme du coup IA joué en direct. Il n'affecte que `rejouerDernierCoupIA()` (bouton
« Dernier coup joué par l'ordinateur ») via un multiplicateur appliqué au délai entre tuiles déjà
calculé par `vitesseIA().tuile` :

```js
const MULTIPLICATEURS_REJEU_IA = { "Lente": 2.2, "Moyenne": 1.5, "Rapide": 1 };
```

« Rapide » (= multiplicateur 1) reproduit exactement le comportement livré par #149, sans
ralentissement additionnel. « Moyenne » et « Lente » ralentissent proportionnellement le rythme
entre chaque tuile animée, sans toucher au ralentissement déjà appliqué par #149 aux tours à plus
de 3 tuiles (qui continue de s'appliquer par-dessus, dans `animerPoseTuiles`).

## Fichiers modifiés
- `src/rummikub/reglages.py` : nouveau défaut `vitesse_rejeu_ia`.
- `src/rummikub/ui/application.py` : propagation de la préférence dans `etat_jeu["config"]`.
- `src/rummikub/ui/web/accueil.html` : nouveau sélecteur dans l'onglet Général des réglages.
- `src/rummikub/ui/web/accueil.js` : chargement/sauvegarde du nouveau champ.
- `src/rummikub/ui/web/jeu.js` : multiplicateur de vitesse appliqué au rejeu à la demande.
