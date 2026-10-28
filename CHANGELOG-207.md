# Issue #207 — Pas à pas : regrouper les gestes par combinaison (coups de 20 à 30 étapes) et bascule Avant / Après (suite de #197)

Depuis l'Expert exact (#206), un coup de l'IA déplace souvent beaucoup de
tuiles : le pas-à-pas tuile-par-tuile (#191) devenait interminable — un vrai
coup de Clara au tour 45 (4 tuiles posées, 14 tuiles du plateau déplacées,
6 combinaisons modifiées) donnait **30 étapes**, dont presque une par tuile
quittant une combinaison. #207 condense le découpage, annonce l'ampleur du coup
avant de commencer, ajoute un mode détaillé optionnel et la bascule Avant/Après
réclamée depuis #189, et corrige deux défauts d'affichage. **Aucun changement
au moteur de jeu, à l'IA ni à la sauvegarde** ; le rejeu animé est inchangé.

## Changements

- **Pas-à-pas condensé par défaut** (`moteur/description_coup.py` :
  `etapes_coup_ia(..., condense=True)`) : les gestes sont regroupés par
  combinaison. Les tuiles libérées d'une combinaison défaite transitent par le
  cadre « tuiles à placer » **sans étape dédiée** (la combinaison rétrécie
  reste affichée « provisoire ») ; **chaque combinaison créée ou complétée est
  UNE étape**. Le départ, l'écran « Les jokers », les provisoires, les
  surbrillances et la dernière étape (plateau d'après exact, cadre vide) ne
  changent pas. Résultat mesuré : le coup de Clara passe de **30 à 10 étapes**
  (< 12), celui de Bruno au tour 57 de 27 à < 11. **Les coups courts restent
  inchangés** (découpage identique).
- **Mode détaillé facultatif** : bouton « Détailler » dans la fenêtre du
  pas-à-pas, qui rebascule vers le découpage tuile-par-tuile de #191
  (`etapes_coup_ia(..., condense=False)`) ; le condensé reste le mode par
  défaut à chaque ouverture. `ui/api.py` calcule les deux découpages une seule
  fois après le coup et les stocke (`etapes` condensé, `etapes_detaillees`).
- **Taille du coup annoncée en tête** : nouvelle mesure `mesurer_coup_ia`
  (tuiles posées, tuiles du plateau déplacées, combinaisons modifiées, mot
  d'ampleur) affichée avant la première étape — « Coup de grande taille :
  14 tuiles du plateau déplacées, 6 combinaisons modifiées, 4 tuiles posées
  depuis la main. ». Le seuil des mots « petit »/« moyen »/« grand » reprend
  celui de `persistance/coups_rates.py` (combinaisons touchées : 1-2, 3-5, 6+).
- **Bascule Avant / Après** (point 2 de #189, enfin réalisé) : un contrôle
  « Avant / Après » montre côte à côte le plateau avant et après le coup, en
  **lecture seule**, combinaisons modifiées ou créées mises en évidence,
  tuiles distinguées selon leur origine (venue de la main de l'IA / déplacée
  d'une autre combinaison) avec une légende. La partie n'est jamais modifiée.
- **Défaut 1 corrigé — le résumé n'évoque plus d'échange de tuiles
  identiques** : `decrire_coup_ia` neutralise d'abord, comme les étapes, les
  échanges de tuiles de même aspect (même valeur/couleur, ou deux jokers) dans
  une même combinaison OU entre combinaisons ; une combinaison identique avant
  et après n'est ni « modifiée » ni « défaite ». Plus de « Le 13 … remplace le
  13 … » parasite. (Remontée et fiabilisation du relabeling de `coups_rates.py`
  — appariement bijectif global + garde-fou contre la duplication d'un joker.)
- **Défaut 2 corrigé — le bouton « Pas à pas » suit l'ampleur réelle du
  coup** : il apparaît dès que le coup déplace au moins une tuile du plateau
  OU modifie au moins deux combinaisons (échanges de tuiles identiques
  ignorés), au lieu du seul « deux étapes nettoyées ». Un coup qui ne fait
  qu'ajouter des tuiles de la main à une seule combinaison, ou en créer, reste
  sans bouton.

## Fichiers touchés

- `src/rummikub/moteur/description_coup.py` : `_relabeler_tuiles_indiscernables`
  (+ appariement bijectif/garde-fou), appliqué à `decrire_coup_ia` ;
  `etapes_coup_ia(condense=...)` et mode condensé dans `_etapes_coup_ia` ;
  `mesurer_coup_ia` + helpers `_taille_mot`, `_nb_tuiles_plateau_deplacees`.
- `src/rummikub/ui/api.py` : stockage de `etapes` (condensé),
  `etapes_detaillees` et `mesure` dans `dernier_coup_ia`.
- `src/rummikub/ui/web/jeu.html` / `jeu.js` / `jeu.css` : ligne de taille,
  boutons « Détailler » et « Avant / Après », vue comparative + légende,
  critère `coupMeriteePasAPas` d'affichage du bouton « Pas à pas ».
- `tests/test_description_coup.py` : condensé Clara (< 12 étapes), invariants
  condensés, position fabriquée, coup court inchangé, mesure, défaut 1 (échange
  entre combinaisons). `tests/test_condense_solveur.py` (nouveau) : coups réels
  du modèle exact (dont Bruno #57 < 11), sauté sans `rummikub-solver`.
  `tests/test_playwright_pas_a_pas.py` : bouton présent pour Clara, absent pour
  une création pure, ligne de taille, bouton « Détailler », bascule
  Avant/Après.
- `CONTEXTE.md` : §12quater (nouveau) et mises à jour de §12.

## Notes

- La relabellisation des tuiles indiscernables n'est volontairement PAS
  appliquée au découpage en étapes (elle peut casser le suivi causal d'un très
  gros coup, qui retomberait sur le repli à deux étapes) : les étapes
  neutralisent déjà ces échanges par ailleurs. Elle n'agit que sur le résumé
  et la mesure.
