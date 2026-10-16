# Issue #168 — Légende : chiffre toujours invisible malgré le correctif #167 (CSS trop large)

Suite à #167 (chiffre aléatoire 1-13 sur les mini-tuiles d'exemple sous le
sac de pioche) : Alain signalait, capture à l'appui, que la légende restait
sans chiffre visible après fusion.

**Vérification réelle (Playwright sur `jeu.html`, stub `window.pywebview` +
événement `pywebviewready`)** : le correctif JS de #167 est bien actif —
chaque mini-tuile reçoit bien un chiffre aléatoire injecté dans le DOM
(`.tuile-num` contient bien un texte "6", "12", "1", ...). Le bug n'était
donc **pas** une régression du JS, mais purement visuel (CSS) : le chiffre
était rendu en blanc quasi transparent (`rgba(255,255,255,0.75)`) sur le
fond ivoire de la tuile, donc invisible à l'œil bien que présent dans le DOM.

**Cause** (`jeu.css`) : la règle `.legende-item span { color:
rgba(255,255,255,0.75); }`, destinée au texte descriptif de chaque entrée de
légende ("Nouvelle tuile posée depuis la main ce tour", etc.), utilisait un
sélecteur descendant (`span`) au lieu d'un sélecteur d'enfant direct. Le
`<span class="tuile-num">` du chiffre, imbriqué plusieurs niveaux plus bas
dans la mini-tuile (`.tuile-jeu > .tuile-cercle > .tuile-num`), est lui aussi
un `span` descendant de `.legende-item` : il héritait donc de ce blanc
transparent au lieu de son noir normal (`var(--tuile-noir)`, `#111111`),
pourtant plus spécifique sur l'élément parent mais sans effet puisque aucune
règle ne fixait `color` directement sur `.tuile-num`.

**Correctif** : `.legende-item span` → `.legende-item > span` (combinateur
d'enfant direct) — ne cible plus que le span de texte, enfant direct de
`.legende-item`, sans toucher au `.tuile-num` imbriqué qui garde désormais sa
couleur `.tuile-jeu.noir` normale.

**Vérification** : nouvelle capture Playwright après correctif — couleur
calculée du `.tuile-num` passée de `rgba(255,255,255,0.75)` à `rgb(17,17,17)`
(= `#111111`), chiffres (6, 12, 1, 11, 11) nettement visibles sur les
mini-tuiles de la légende, pourtours vert/orange/bleu inchangés.

Fichier touché : `src/rummikub/ui/web/jeu.css`.
