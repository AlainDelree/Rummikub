# Issue #171 — Suite #165 : vérification du pourtour bleu après une vraie pose de l'IA

## Reproduction

Conformément à CONTEXTE.md §7, deux scénarios réalistes de pose IA « sans
scission apparente » ont été construits avec le moteur réel
(`creer_partie`, `jouer_ia`, `jouer_tour`) puis joués via Playwright sur
`jeu.html` (API `window.pywebview.api` mockée, mock = l'état produit par le
moteur) :

1. **Extension d'un groupe + nouvelle suite** (exactement le cas décrit par
   Alain : ajout d'un `12-noir` à un groupe de 12, plus une suite
   `8-9-10 noir`), sur un tapis à plusieurs combinaisons préexistantes
   (groupe de 12, suite rouge 1-4, groupe de 7).
2. **Récupération de joker** (cas plus retors : un groupe de 7 déjà plein
   avec un joker, l'IA a en main la tuile exacte que le joker représente et
   doit l'échanger puis replacer le joker ailleurs — un vrai déplacement de
   tuile, sans qu'aucune « scission » ne soit visible de l'extérieur).

## Résultat

Dans les deux cas, `trouverTuilesDeplacees()` se comporte exactement comme
l'analyse de #165 l'affirmait : **aucune tuile non concernée par le coup**
ne reçoit la classe `tuile-ia-deplacee`/`tuile-ia-highlight`. Dans le cas 2,
seule la tuile réellement déplacée (le joker) est correctement signalée ;
toutes les autres tuiles anciennes du tapis restent sans aucune classe de
surbrillance, à tout instant de l'animation. `trouverTuilesAjoutees()` ne
marque que les tuiles effectivement nouvelles. Aucune régression ni défaut
n'a été trouvé dans ces deux fonctions pour une pose normale (avec ou sans
réarrangement de joker).

## Cause probable du pourtour bleu observé par Alain

Le snapshot pris **après l'effacement de la surbrillance IA** (2 s après la
fin de l'animation, donc l'état que voit réellement l'utilisateur la plupart
du temps) montre que **toutes** les tuiles du tapis portent la classe
`tapis-manipulable` — un mécanisme totalement différent et préexistant
(`jeu.css` : `.tuile-jeu.tapis-manipulable { outline: 2px dashed
rgba(59,130,246,0.7); }`), appliqué à **toutes** les tuiles du plateau dès
que c'est le tour de l'humain (pour indiquer qu'elles sont toutes
déplaçables par glisser-déposer). Ce contour bleu pointillé apparaît après
**chaque** tour de l'IA — pose, pioche ou passage confondus — puisqu'il ne
dépend que de « c'est maintenant mon tour », pas du contenu du dernier coup
IA. Contrairement au halo `tuile-ia-highlight` (doré, effacé après 2 s), ce
contour **persiste** tant que l'humain n'a pas commencé à jouer — ce qui
correspond très précisément au mot « persiste » du titre de l'issue.

Hypothèse la plus probable : ce que Alain a observé après la pose réelle de
l'IA est ce contour `.tapis-manipulable`, intentionnel et sans rapport avec
le bug de #165, plutôt qu'une régression de `trouverTuilesDeplacees()`.

## Conclusion

Aucune anomalie trouvée dans `trouverTuilesDeplacees()`/`trouverTuilesAjoutees()`
pour une pose normale : **aucun changement de code n'a été apporté**. Si le
contour bleu généralisé et persistant gêne malgré tout (confusion possible
avec le pourtour « IA » bleu), il s'agirait d'une demande distincte portant
sur `.tapis-manipulable` (ex. couleur différente, ou limiter l'indicateur
aux tuiles réellement survolées) plutôt que d'un correctif de la logique de
détection de #165.
