# Issue #159 — Légende visuelle des couleurs de pourtour des tuiles, sous le sac de tuiles

## Contexte
Plusieurs couleurs de pourtour de tuiles coexistent désormais (vert = nouvelle de la main ce
tour, orange = déplacée depuis le tapis ce tour, rouge = combinaison invalide, bleu = tuile de
l'IA réarrangée pendant un rejeu — issues #128, #136, #139). Leur signification n'était explicitée
nulle part dans l'interface.

## Correctif
Ajout d'une légende statique sous le sac de pioche (`#legende-couleurs`, colonne gauche), construite
avec de **vraies tuiles miniatures** (`creerTuileJeu`, mêmes classes CSS qu'en jeu — `ce-tour`,
`deplacee-tapis`, `tuile-ia-deplacee`, `groupe-combinaison.combi-invalide`) plutôt qu'une simple
liste de texte, pour que la légende reste toujours fidèle aux couleurs réellement affichées.

- `jeu.html` : nouveau conteneur vide `#legende-couleurs` sous `#compteur-pioche`.
- `jeu.js` : nouvelle fonction `afficherLegendeCouleurs()`, appelée une fois à l'init (contenu
  statique, indépendant de l'état de la partie). Pour le rouge (combinaison invalide), qui est
  normalement un pourtour de *groupe* (`.groupe-combinaison.combi-invalide`) et non de tuile
  individuelle, la légende montre un mini-groupe de 2 tuiles avec ce pourtour, plus fidèle que
  d'inventer un pourtour rouge sur une tuile seule qui n'existe pas en jeu.
- `jeu.css` : `.legende-tuile-mini` (tuile réduite, `--tw: 22px`) ; `.legende-groupe-mini` coupe
  l'animation de clignotement (`pulse-invalide`) pour un affichage calme en légende ; override
  figeant le pourtour bleu (`.tuile-ia-deplacee`, normalement une animation transitoire de rejeu)
  en état statique.
