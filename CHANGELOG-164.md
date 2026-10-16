# Issue #164 — Vitesse du rejeu : choix déplacé dans l'écran de jeu + échelle décalée vers le bas

Suite de #160, qui avait ajouté le réglage « Vitesse du rejeu du dernier
coup IA » (3 niveaux Lente/Moyenne/Rapide) dans l'écran Réglages.

## Déplacement du contrôle

Le sélecteur est retiré de l'écran Réglages (`accueil.html`/`accueil.js`) et
remplacé par un groupe de 3 boutons directement dans l'écran de jeu
(`jeu.html`), juste sous le bouton « Dernier coup joué par l'ordinateur »,
sur le même modèle visuel que le contrôle de zoom du tapis (`#zoom-tapis`).
Un clic change immédiatement le niveau actif et persiste la préférence via
la même API `sauvegarder_reglages` déjà utilisée par les autres réglages
modifiables en jeu (ex. « Tri automatique »), sans toucher au reste de la
configuration (fusion côté `reglages.sauvegarder`).

## Échelle décalée vers le bas

Les multiplicateurs appliqués au délai entre tuiles (`MULTIPLICATEURS_REJEU_IA`
dans `jeu.js`) sont recalés, globalement plus lents :

| Niveau  | Avant (#160) | Après (#164) |
|---------|--------------|--------------|
| Rapide  | 1× (#149)    | 1.5× (ex-Moyenne) |
| Moyenne | 1.5×         | 2.2× (ex-Lente) — **nouveau défaut** |
| Lente   | 2.2×         | 3.2× (nouveau palier, plus lent qu'avant) |

L'ancien « Rapide » (1×, comportement #149) disparaît de l'échelle.

### Migration

Les 3 libellés (`Lente`/`Moyenne`/`Rapide`) sont conservés tels quels — seule
leur signification (le multiplicateur associé) change. Une préférence déjà
enregistrée dans `config.json` sous un de ces 3 libellés, y compris l'ancien
« Rapide » (supprimé en tant que *comportement* mais pas en tant que
*libellé*), reste donc une clé valide dans la nouvelle table et bascule
automatiquement vers le nouveau palier correspondant — pas de valeur
orpheline, aucune conversion de valeur nécessaire. Le défaut (`reglages.py`
et les 2 points de lecture dans `application.py`) passe de `"Rapide"` à
`"Moyenne"`.

## Vérification

Suite pytest (33 tests) inchangée et passante. Contrôle testé visuellement
via Playwright (chargement direct de `jeu.html`/`accueil.html` avec un état
de partie simulé et `window.pywebview.api` mocké) : le groupe de 3 boutons
s'affiche sous le bouton de rejeu, « Moyenne » est actif par défaut, un
clic sur un autre niveau le met en surbrillance et appelle
`sauvegarder_reglages` avec la bonne valeur ; l'ancien sélecteur a bien
disparu de l'écran Réglages.
