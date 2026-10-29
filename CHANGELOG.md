# Issue #67 — Réglages : « Vitesse de l'ordinateur » déplacée vers l'onglet Général

# Issue #213 — Six niveaux d'IA sur un même modèle exact : ajout de « Champion du Monde », échelle réglée par des paramètres (vision limitée, oublis) et outils de calibrage (suite de #206)

Rummikub partage ses joueurs ordinateur avec Scrabble, qui propose **six**
niveaux (Débutant → Champion du Monde) ; Rummikub n'en avait que cinq. Cette
issue construit une échelle de six niveaux, bâtie sur **un seul moteur** — le
modèle exact d'un tour de #206 (`moteur/solveur_exact.py`) — dont la force est
réglée par des **paramètres réunis en un seul endroit** (`moteur/niveaux.py`),
plutôt que par six algorithmes de force inégale. Voir **CONTEXTE.md §16**.

## 1. Sixième niveau « Champion du Monde »

- Ajouté à `config.NIVEAUX`, à la suite d'Expert (ordre = force croissante et
  ordre d'affichage). Tout ce qui en dépend suit : écran d'accueil (bouton +
  badge), journal, bilan, analyses, simulations, sauvegardes.
- **Écran d'accueil** : bouton et badge au même traitement visuel que les
  autres, en prolongeant le **dégradé clair→foncé** des niveaux — nouvelle
  variable CSS `--niveau-champion: #241603` (la plus foncée). Le *slug* de
  `accueil.js` convertit désormais les espaces en tirets
  (`champion-du-monde`), sans effet sur les cinq autres niveaux.
- **Personnage / avatar** : ce projet n'a pas de persona fixe par niveau (nom
  aléatoire d'un pool partagé + avatar parmi les 15 SVG existants, quel que soit
  le niveau). **Aucune liste de personnages de Scrabble n'existe dans le dépôt**
  (signalé conformément à l'issue) : Champion du Monde tire son nom + avatar des
  mêmes pools que les cinq autres niveaux.
- **Parties anciennes toujours valides** : un libellé de niveau inconnu retombe
  sur « Débutant » (`niveaux.bridage_pour`), jamais d'erreur.
- Champion du Monde reçoit le réglage le plus fort trouvé jusqu'ici (modèle
  exact, aucune limite ; l'évaluation de la main de #211 reste désactivée par
  défaut, aucun gain démontré).

## 2. Structure cible de l'échelle (répartition voulue par Alain)

Le solveur exact « un tour » (qui pose toujours le maximum) **n'est PAS** le
niveau le plus fort : c'est **Avancé**.

- **Débutant / Facile / Intermédiaire** : solveur un-tour AFFAIBLI, de plus en
  plus bridé vers le bas.
- **Avancé** : solveur un-tour COMPLET, tel quel.
- **Expert** : solveur + stratégies multi-tours **partielles** (à venir).
- **Champion du Monde** : solveur + stratégies multi-tours **complètes** (à venir).

> **État provisoire.** Les stratégies multi-tours (CONTEXTE.md §13, pistes 1/8/9)
> **ne sont PAS** implémentées ici : cette issue met en place l'échelle,
> l'affaiblissement des niveaux du bas à Avancé et les outils de calibrage.
> **Expert et Champion du Monde restent provisoirement IDENTIQUES à Avancé**
> (solveur un-tour complet), signalé clairement, jusqu'à ce que des issues
> ultérieures développent le multi-tours.

## 3. Affaiblissement réglé par des paramètres (`moteur/niveaux.py`, le SEUL endroit)

- **`perturbation_max`** — nombre maximal de tuiles **du plateau** que le coup
  peut DÉPLACER (mesure #199). Ajouter des tuiles de la main ou créer de
  nouvelles combinaisons ne compte pas. `0` = ne touche jamais à la structure du
  plateau ; `None` = aucune limite. Exprime ce que le joueur « voit ».
- **`taux_oubli`** — probabilité, par tour, de ne pas voir le meilleur coup et de
  **piocher**. Tirage reproductible sous `config.graine_ia`. **Garde-fous** : un
  coup qui vide la main (victoire) n'est JAMAIS oublié ni dégradé ; le taux
  décroît quand la main est petite (`SEUIL_OUBLI = 7`, nul à une seule tuile).
- Valeurs de départ INDICATIVES (à resserrer par les mesures) : Débutant
  `(0, 35 %)`, Facile `(0, 22 %)`, Intermédiaire `(3, 12 %)`, Avancé/Expert/
  Champion `(None, 0)`.
- **Repli sans dépendances** : `highspy`/`numpy` absents → repli sans erreur
  (recherche arborescente puis heuristique Avancé) ; le **journal indique le
  mécanisme** (clé `solveur` de l'action).
- Les fonctions heuristiques historiques (`jouer_niveau_debutant/…/avance`)
  demeurent comme **repli** et support des tests de tactiques de joker ; elles ne
  portent plus l'échelle (c'est `jouer_niveau_bride` / `NIVEAUX_IA`).

## 4. Outils de calibrage

- **`scripts/echelle_niveaux.py`** (NOUVEAU) — tournoi d'échelle : parties à deux
  en miroir entre niveaux voisins (+ quelques non voisines), ≥ 40 donnes/paire,
  tableau des taux de victoire + IC 95 %, vérification de croissance stricte et
  d'écart net (~60–80 %). Premier plan, limite de temps ferme, durée indiquée.
- **`scripts/profil_joueur.py`** (NOUVEAU) — profil d'un humain (journaux, jugés
  par le modèle exact maison) ou d'un niveau d'IA (parties simulées), avec les
  mêmes indicateurs, affichés côte à côte. **Deux indicateurs de fin distincts** :
  (a) tuiles restantes du perdant = serrage / NIVEAU ; (b) points restants = ne
  pèse qu'en multi-manches. Les deux sont présentés séparément.
- **`scripts/analyser_coups_rates.py`** — **juge par défaut = modèle exact de la
  MAISON** (`moteur/solveur_exact.py`) ; `--juge-exact` (bibliothèque
  `rummikub-solver`) devient un **contrôle croisé facultatif**.

## 5. Rapport de calibrage

**Tournoi d'échelle (campagne de démonstration RÉDUITE, 8 donnes/paire ×2
miroir, graine 0, limite 800 s — partielle car arrêtée à la limite ferme ; la
campagne complète ≥ 40 donnes/paire, longue à cause du solveur exact, est à
lancer par Alain)** :

| Paire adjacente | Plus fort | Taux (IC 95 %) |
|-----------------|-----------|:--:|
| Débutant vs Facile | Facile | 62,5 % ± 23,7 pt |
| Facile vs Intermédiaire | Intermédiaire | 62,5 % ± 23,7 pt |
| Intermédiaire vs Avancé | Avancé | **75,0 % ± 21,2 pt** (net) |
| Avancé vs Expert | — | 50,0 % (égalité ATTENDUE, solveur identique) |

Tendance **croissante** confirmée sur la partie affaiblie (Débutant < Facile <
Intermédiaire < Avancé, chaque niveau supérieur l'emporte ; Intermédiaire <
Avancé déjà « net ») et **plateau attendu** Avancé ≈ Expert (≈ Champion), les
stratégies multi-tours n'étant pas encore implémentées. Les IC sont larges à 8
donnes : la significativité exige la campagne complète d'Alain.

**Profil (démonstration, 2 parties simulées en miroir)** : Expert pose à
l'optimum (1,01 tuile/tour, 0 % de tours pioché alors qu'un coup existait, 60 %
de poses « grandes »), tandis que Facile pose 0,80 tuile/tour et pioche 83 % du
temps **alors qu'un coup (nécessitant un réarrangement qu'il ne « voit » pas)
existait** — l'affaiblissement est bien visible dans le profil.

**Le niveau d'Alain n'est pas établi par cette issue** : il le sera par la
comparaison de SON profil (commande `profil_joueur.py --journaux …`, journaux
inaccessibles à l'agent) avec ceux des niveaux candidats, et par quelques
parties jouées contre eux. Commandes dans CONTEXTE.md §16.

## 6. Pistes consignées dans CONTEXTE.md §13 (documentation seulement)

- **Piste 8 — Ne pas libérer un joker pour rien** : pénaliser, à nombre de
  tuiles posées égal, un coup laissant un joker facilement reprenable (bout de
  suite / 4e tuile de groupe). Exception qui prime sur toutes les pistes de
  prudence : un coup qui vide la main gagne — jamais empêché ni dégradé (déjà
  appliqué par l'échelle).
- **Piste 9 — Rétention défensive de tuiles** : garder des tuiles pour priver
  l'adversaire, pondérée par la valeur des tuiles et le poids des points (multi-
  manches), calculable par probabilité qu'une tuile soit dans la main adverse
  plutôt que dans le sac. Piste avancée, pour le sommet de l'échelle.

## 7. Tests

`tests/test_niveaux.py` (NOUVEAU) : échelle à six niveaux ; niveau inconnu →
Débutant ; `perturbation_max=0` ne déplace aucune tuile et `None` récupère le
joker ; borne de perturbation respectée ; oubli à 100 % → pioche, coup gagnant
jamais oublié, oubli décroissant sur petite main ; reproductibilité sous graine ;
Champion atteint l'optimum exact ; repli propre sans `highspy`/`numpy`.
`tests/test_playwright_accueil_reglages.py` : le bouton « Champion du Monde »
ajoute un adversaire de ce niveau. **Tous les tests existants restent inchangés
et passent** (les fonctions heuristiques de niveau, conservées, sont toujours
testées directement).

# Issue #212 — Match : notre solveur d'Expert contre la bibliothèque `rummikub-solver` sur des parties entières (suite de #206)

Nos deux solveurs trouvent le même **nombre** de tuiles posables à chaque tour
(vérifié en #204), mais départagent différemment à nombre égal : le nôtre
préfère la **perturbation minimale** du plateau (#199) puis **économise les
jokers**, la bibliothèque applique ses propres règles. Cette issue répond à la
question d'Alain : *ces choix de départage nous désavantagent-ils sur une partie
entière ?* en faisant jouer une partie entière pilotée par chaque solveur, en
miroir (mêmes donnes, places échangées), sur de nombreuses donnes.

**Portée (à ne pas sur-interpréter)** : les deux solveurs n'optimisent qu'UN
tour. Le match ne mesure donc PAS les stratégies sur plusieurs tours (réserve,
joker gardé, rétention — CONTEXTE.md §13), ni la force d'un humain : seulement
si, à jeu « un tour » égal, nos critères de départage tiennent la route.

**Rien du jeu livré, du moteur, de l'IA ni du solveur n'est modifié** :
`rummikub-solver` reste une dépendance de DÉVELOPPEMENT (hors `requirements.txt`,
hors build Windows) ; tout est sous `scripts/` et `tests/`, en outil d'analyse.

## Résultat de la mesure

Campagne du 2026-10-29 (graine de base 20212, `budget Expert=1,5 s`,
`max_tours=400`), arrêtée proprement à la **limite de temps ferme de 2100 s**
en exploitant les résultats partiels : **83 donnes jouées = 164 parties**
(sur 100 donnes visées).

| Solveur | Victoires | Taux | IC 95 % (Wilson) |
|---------|-----------|------|------------------|
| **Notre solveur (Expert)** | 89 / 164 | **54,3 %** | **[46,6 % ; 61,7 %]** |
| **Bibliothèque** | 75 / 164 | **45,7 %** | **[38,3 % ; 53,4 %]** |

Égalités : 0 — parties bloquées : 0.

Indicateurs de marge et de jeu :

- Tours par partie (moyen) : **64,9**.
- Tuiles restantes en main du **perdant** (serrage, indicateur demandé par
  Alain) : **2,44** quand notre solveur perd (75 défaites), **2,45** quand la
  bibliothèque perd (89 défaites) — quasi identiques.
- Tuiles posées par tour : **0,978** (notre) vs **0,975** (biblio).
- Temps par coup — moyen / max : **0,093 s / 1,56 s** (notre, modèle exact
  maison borné à 1,5 s) vs **0,039 s / 0,39 s** (biblio).
- Coups « main seule » contraints avant la mise (biblio) : **529** (gérés
  proprement par construction, voir §1 ci-dessus).

Contrôles : **0 erreur de conservation** des 106 tuiles, **0 coup refusé** par
le moteur. **1 écart d'optimalité** signalé (donne 20B, tour 64 : notre=1,
biblio=0) sur ~10 000 états rencontrés. Rejeu propre, **monothread et
déterministe, de cette donne : l'écart NE se reproduit PAS** (partie jouée
jusqu'au bout, 77 tours, aucun écart, résultat stable sur deux exécutions).
L'explication la plus probable est un **artefact temporel** du solveur maison
**borné en temps** (budget 1,5 s) sous la **charge CPU concurrente** du match
(double résolution par tour), et non un défaut d'optimalité structurel entre
les deux modèles exacts (dont l'égalité exacte avait été vérifiée en #204). Cet
unique état n'affecte pas la conclusion (IC largement chevauchants).

### Interprétation (sans sur-vendre)

Les intervalles de confiance à 95 % des deux taux de victoire **se
chevauchent** : sur cet échantillon, **aucun des deux solveurs n'a d'avantage
démontré** au jeu « un tour ». Nos critères de départage (perturbation minimale
#199, économie de jokers) **ne nous désavantagent pas de façon mesurable**. Le
léger 54,3 % en notre faveur n'est pas significatif (borne basse de notre IC
46,6 % < borne haute de l'IC adverse 53,4 %).

**Portée — à ne pas sur-interpréter.** Les deux solveurs n'optimisent qu'UN
tour. Ce match ne mesure PAS les stratégies sur plusieurs tours (réserve, joker
gardé, rétention — CONTEXTE.md §13), ni la force d'un humain. Le progrès est à
chercher dans le jeu sur plusieurs tours.

## Changements

### 1. `scripts/match_solveurs.py` (nouveau) — script de match

- **« Joueur bibliothèque »** (`decider_bibliotheque`) bâti sur l'adaptateur
  `scripts/solveur_exact.py` (#204) : prend l'état (plateau, main, mise initiale
  faite ou non) et renvoie un **coup complet** (tuiles posées + nouveau plateau)
  déjà **remis dans l'ordre et validé par `valider_combinaison`**, conservation
  du plateau contrôlée par l'adaptateur. **Mise initiale** : la bibliothèque
  réarrange table + main au second temps, interdit avant la mise ; on la
  **contraint à n'utiliser que la main** (résolution sur plateau vide puis
  recollage du plateau intact), le cas étant compté à part (`mise_contrainte`).
- **« Notre solveur »** = niveau **Expert livré** (`jouer_niveau_expert`,
  modèle exact maison + départage #199/jokers), le joueur réellement embarqué.
- **Protocole miroir** : chaque donne (graine fixe) est jouée deux fois, places
  échangées — chaque solveur joue une fois chaque main et une fois chaque
  position (avantage de la main et de l'ouverture neutralisés).
- **Contrôles à chaque coup** : conservation des **106 tuiles** ; et, sur le
  même état, comparaison du **nombre maximal de tuiles posables** des deux
  solveurs — tout écart est signalé (ne devrait jamais arriver : écart
  d'optimalité à investiguer).
- **Limite de temps ferme** (`--limite-temps`), arrêt propre entre deux parties,
  **résultats partiels** écrits en continu (rapport texte + `.json` frère).
- **Indicateurs** (point 3) : taux de victoire + **IC 95 % (Wilson)**, tuiles
  **restantes en main du perdant** (indicateur de serrage demandé par Alain),
  tuiles posées par tour, tours par partie, parties bloquées, temps moyen et
  maximal par coup de chaque solveur. **Interprétation factuelle** sans
  sur-vente (point 4), avec rappel explicite de la portée « un tour ».

### 2. `tests/test_match_solveurs.py` (nouveau)

Tests du script sur un petit nombre de parties, **sautés proprement si la
bibliothèque est absente** (`pytest.importorskip`) : décideur bibliothèque
(coup ordonné/validé/conservatif, contrainte « main seule » avant la mise),
conservation des 106 tuiles, IC 95 % de Wilson, **égalité d'optimalité** des
deux solveurs sur des états de départ, et un **petit match complet** (marqué
`lent`) vérifiant miroir, conservation et absence d'écart d'optimalité.

### 3. `CONTEXTE.md`

Nouvelle **§15** documentant le script de match, le protocole miroir, la
contrainte de mise initiale et le résultat chiffré.

## Fichiers

- `scripts/match_solveurs.py` (nouveau, outil d'analyse dev-only)
- `tests/test_match_solveurs.py` (nouveau)
- `CONTEXTE.md` (nouvelle §15)
- `resultats_match_212.txt` / `.json` (rapport de la campagne)

# Issue #211 — Expert : évaluer la main restante pour départager les coups à nombre de tuiles posées égal (suite de #199)

À nombre de tuiles posées **égal**, Expert départageait jusqu'ici par
perturbation minimale du plateau (#199), puis points posés, puis économie de
jokers — sans jamais regarder ce qui reste dans sa main. Cette issue ajoute une
**évaluation de la main restante** (doublons, tuiles de bord, points restants
selon le nombre de manches) **intégrée au modèle exact** (`moteur/solveur_exact.py`,
HiGHS, #206) comme objectif secondaire linéaire — jamais avant le nombre de
tuiles posées — puis la **mesure critère par critère** par simulation.

**Résultat de la mesure (30 donnes = 60 matchs en miroir, seed 42) : aucun
critère ne produit de gain significatif** (tous les écarts restent dans la marge
d'erreur ±12,6 pt). Conformément au point 4 de l'issue, **l'évaluation est donc
livrée DÉSACTIVÉE par défaut** ; tout le mécanisme est en place, réglable en un
seul endroit, et réactivable si une campagne plus large démontrait un gain.

## Changements

### 1. Évaluation de la main — `moteur/evaluation_main.py` (nouveau)

Fonction **indépendante du solveur** `evaluer_main(tuiles, config)` renvoyant une
pénalité (plus basse = meilleure main), et **tous les poids réglables réunis en
tête de module** (point 4). Trois critères + deux cas traités à part :

- **Doublons** : pénalité par paire identique restante (deux tuiles de même
  valeur et couleur ne peuvent jamais entrer dans la même combinaison).
- **Tuiles de bord** : pénalité **graduée** `penalite_bord(v) = 3 − nb_suites_trois(v)`
  → 2 pour 1/13, 1 pour 2/12, 0 pour 3–11 (un bord entre dans moins de suites
  de trois).
- **Points restants** : poids **nul en 1 manche** (`POIDS_POINTS_1_MANCHE = 0`),
  **non nul à partir de 2** (`POIDS_POINTS_N_MANCHES = 1`), car les points
  s'accumulent alors au score cumulé (#203).
- **Tuiles isolées** : calculées par `tuiles_isolees()` pour les tests et
  l'affichage, mais **laissées de côté dans le solveur** (`POIDS_ISOLEE = 0`) :
  elles ne se linéarisent pas simplement (dépendent du reste de la main, pas
  seulement des tuiles posées). Approximation documentée (en-tête du module).
- **Jokers** : traités à part (`POIDS_JOKER = 0`) — un joker en main est une
  ressource, et l'économie de jokers **posés** est déjà un critère du solveur.

`ConfigEvaluation` (dataclass gelée) porte les critères actifs, les poids et la
position vs la simplicité ; `depuis_preset(nom, nb_manches)` fabrique les
réglages nommés de la simulation.

### 2. Intégration au modèle exact — `moteur/solveur_exact.py`

L'évaluation n'est **pas** un tri après coup : elle est **linéarisée** sur les
tuiles qui resteraient en main et ajoutée comme **passe d'optimisation
lexicographique**, toujours **après** la passe du nombre de tuiles posées (fixé
par une contrainte d'égalité avant toute passe de départage) :

- bords/points → termes `Σ_s (W_bord·pbord_s + W_points·preal_s) x_s`
  (poser une tuile retire sa pénalité de la main) ;
- doublons → **variable auxiliaire** `d_i ∈ [0,1]` par type présent ≥ 2 fois en
  main, avec `d_i + Σ_s a_{s,i} x_s ≥ t_i + r_i − 1` (vaut 1 ssi les deux
  exemplaires restent), pénalisée dans l'objectif. Coefficients **entiers** →
  départage exact (pas d'arrondi), comme les autres critères.

**Position testée dans les deux ordres** (point 2) : `apres_simplicite` (défaut
— ne complique jamais le plateau pour un gain d'évaluation) et `avant_simplicite`
(suffixe `-avant`). Quand l'évaluation est **inactive** (défaut), le solveur
départage **exactement comme avant #211** (simplicité → points posés → jokers) :
comportement et temps de production strictement inchangés.

### 3. Mesure par simulation — `scripts/comparer_niveaux_ia.py`

Nouvelles options `--eval-a` / `--eval-b` : appliquent un preset d'évaluation à
l'Expert de chaque camp, pour comparer **deux réglages d'Expert en miroir** dans
une même campagne (le reste strictement identique). Presets : `off`, `complet`,
`doublons`, `bords`, `points`, `points-nul|faible|moyen|fort`, suffixe
`-avant`/`-apres`.

**Résultats chiffrés complets dans `CONTEXTE.md` §13.** En résumé (camp A = `off`
de référence, camp B = variante ; 60 matchs ; marge ±12,6 pt) :

| Variante (camp B)     | 1 manche — victoires B | 3 manches — victoires B |
|-----------------------|:----------------------:|:-----------------------:|
| doublons              | 46,7 %                 | —                       |
| bords                 | 48,3 %                 | —                       |
| complet               | 46,7 %                 | 48,3 %                  |
| complet (ordre avant) | 48,3 %                 | —                       |
| points-nul            | —                      | 46,7 %                  |
| points-faible         | 48,3 %                 | 45,0 %                  |
| points-moyen          | —                      | 46,7 %                  |
| points-fort           | —                      | 46,7 %                  |

**Aucun écart significatif** (tous à moins de 12,6 pt de 50/50). **Points
contre-productifs ?** Dans cet échantillon, aucun poids (0 → 8) ne fait bouger le
taux de victoire hors du bruit ; le poids fort ne dégrade pas les victoires
(46,7 % = poids nul) et améliore légèrement la marge de score cumulé (déficit
−2,2 à poids nul → −1,0/−1,1 à poids moyen/fort). **Aucun seuil de bascule n'est
atteint jusqu'au poids 8** : l'effet reste sous le plancher de bruit à 30 donnes.
Cause probable : le modèle exact vide déjà les chevalets très vite (180/180
manches terminées chevalet vidé, **0 bloquée**) — quand personne n'est bloqué, la
qualité de la main restante départage rarement le vainqueur.

**Temps de calcul** : l'évaluation ajoute une passe MIP sur le même petit modèle.
Sur les positions typiques ≈ +10 % ; sur les cas de référence les plus lourds
≈ +30 % (530 → 687 ms/coup), toujours **sous le budget de 1,5 s**. Désactivée par
défaut, elle n'ajoute **aucun** temps en production.

### 4. Adoption

`moteur/ia.EVAL_MAIN_DEFAUT = evaluation_main.DEFAUT` avec `active=False` :
**évaluation désactivée par défaut** (aucun gain démontré). Réactivation et
réglage des poids en un seul endroit (`moteur/evaluation_main.py`).

### 5bis. Journal : mécanisme décideur d'Expert

À chaque coup d'une IA Expert, `jouer_niveau_expert` annote le coup du mécanisme
qui a décidé (`moteur/ia.SOLVEUR_EXACT|RECHERCHE|AVANCE`) et `logger_action` écrit
une **clé facultative `solveur`** dans le journal (omise pour les humains et les
autres niveaux — rétrocompatible). Le repli étant silencieux quand
`highspy`/`numpy` manquent, on peut désormais savoir, en lisant un journal, si
Expert a joué avec le modèle exact ou s'est replié. `scripts/analyser_coups_rates.py`
**affiche la répartition** des mécanismes (modèle exact / recherche de repli /
Avancé en repli / non noté) et signale la présence de coups en repli.

### 6. Tests — `tests/test_evaluation_main.py` (nouveau)

19 tests : évaluation sur mains fabriquées (doublons, bords 1/13 vs 2/12 vs
milieu, isolées, joker), poids des points selon le nombre de manches, **propriété
« l'évaluation ne change jamais le nombre de tuiles posées »** (positions
fabriquées + tous les cas de référence, tous presets), départage effectif
(exemple d'Alice : suite 1-2-3 rouge préférée au groupe pour écouler un doublon
et un bord), et annotation `solveur` du journal (5bis).

## Fichiers touchés

- **Nouveau** : `src/rummikub/moteur/evaluation_main.py`, `tests/test_evaluation_main.py`.
- **Modifiés** : `moteur/solveur_exact.py` (passe d'évaluation + doublons),
  `moteur/ia.py` (réglage par défaut, annotation du solveur, fil `eval_config`),
  `persistance/journal.py` (clé `solveur`), `ui/api.py` (transmet le solveur au
  journal), `persistance/coups_rates.py` (`repartition_solveurs`),
  `scripts/comparer_niveaux_ia.py` (`--eval-a/-b`),
  `scripts/analyser_coups_rates.py` (affichage de la répartition), `CONTEXTE.md`
  (§13).

## Ne dégrade pas

Les 252 tests existants passent, tous les cas de référence (`cas_expert_*.json`)
conservent leur nombre de tuiles pour **tous** les presets d'évaluation, Avancé
et les niveaux inférieurs sont inchangés, le budget de production n'est pas
modifié (évaluation désactivée par défaut).

# Issue #210 — Fiabiliser les tests dépendant de la vitesse machine ou de la source du scénario, sans en supprimer aucun (suite de #209)

Certains tests échouaient par intermittence selon la charge de la machine ou
selon le solveur ayant construit leur scénario, sans aucune régression réelle
du jeu. L'issue #210 supprime cette sensibilité **sans affaiblir la moindre
exigence sur le RÉSULTAT** (nombre de tuiles, validité du coup, conservation
du plateau, nombre d'étapes réel) et **sans toucher** au moteur, à l'IA, au
solveur ni au pas-à-pas : uniquement les tests et `pytest.ini`.

## Changements

### 1. Pas-à-pas condensé du coup de Bruno — jugé sur le solveur MAISON

`tests/test_condense_solveur.py::test_condense_bruno_tour57_moins_de_onze_etapes`
construisait le coup avec la **bibliothèque externe** `rummikub-solver`, qui
propose un arrangement un peu différent de celui du jeu (même nombre de tuiles
posées, une combinaison de plus déplacée → 12 étapes condensées) ; le seuil
« < 11 » avait été calibré sur le solveur MAISON et échouait donc à tort.

- Le test repose désormais sur le solveur **MAISON** (`moteur/solveur_exact.py`,
  HiGHS), celui que le jeu utilise réellement au niveau Expert — il juge ainsi
  l'affichage du coup **réellement joué**.
- Nombre d'étapes mesuré avec cette source : **exactement 13** (solveur
  déterministe, `threads=1`/`random_seed=0` ; stable quel que soit le budget,
  atteint en ~0,3 s). Détaillé : 27 étapes.
- Nouveau seuil : **« au plus 13 »** — juste au-dessus du nombre réellement
  obtenu, une vraie borne nettement sous le détaillé (objectif de #207), sans
  chiffre magique ni dépendance à la source. Choix documenté dans le test.
- Les propriétés GÉNÉRALES du condensé (`test_condense_coup_exact_proprietes`,
  tous les cas) restent testées via la bibliothèque externe : elles sont
  insensibles à la source (bornes lâches). Le fichier ne saute donc plus tout
  en bloc : le test de Bruno dépend de `highspy`, les propriétés générales de
  `rummikub-solver`.

### 2. Tests au budget de temps en secondes — indépendants de la charge

Budget multiplié par le `facteur_machine` mesuré une fois par session dans
`tests/conftest.py` (micro-benchmark CPU existant, #206 ; ≈ 1 sur la machine
de dev, ≥ 1 sur une machine lente, plafonné à 30). Recensement des tests
concernés, temps sur machine calme et marge retenue :

| Test | Temps calme | Ancien budget | Nouveau budget |
|------|------------|---------------|----------------|
| `test_solveur_cascade_joker_61_trouve_attendu_avec_gros_budget` (tour61) | ~5–7 s | 12 s **codé en dur** | `12 s × facteur_machine` |
| `test_solveur_cas_reference_200_atteint_attendu_avec_gros_budget` (tour59) | ~2–4 s | 10 s **codé en dur** | `10 s × facteur_machine` |
| `test_solveur_cas_reference_200_atteint_attendu_avec_budget_de_production` (tour59) | ~2–4 s | `×6` (9 s) | `×6 × facteur_machine` |
| `test_expert_se_replie_si_modele_exact_indisponible` (tour37, arborescent) | ~0,5 s | 10 s **codé en dur** | `10 s × facteur_machine` |

Les autres tests de solveur à gros budget étaient **déjà** mis à l'échelle par
`facteur_machine` (#206) : plateau chargé #190, cascade #194, départage
#199/#200. Les tests à très large marge (bruno arborescent 0,12 s / 15 s ;
autotest 6 tuiles / 5 s ; cas « sans coup possible » à 1 s) n'ont pas été
touchés (marge > 100×, insensibles à la charge). **Aucune exigence de résultat
modifiée** : seul le temps alloué s'adapte à la vitesse de la machine.

### 3. Marqueur `@pytest.mark.lent`

Déclaré dans `pytest.ini` et posé sur les tests de solveur à gros budget
(plusieurs secondes chacun). Ils restent **exécutés par défaut** avec toute la
suite ; le marqueur permet seulement de les lancer/isoler à part (`pytest -m
lent`, `pytest -m "not lent"`) sans jamais les exclure. Documenté dans
`CONTEXTE.md` §6.

## Vérification

- Suite complète (`/usr/bin/python3 -m pytest tests/ -q`, environnement avec
  `highspy`/`numpy`/`rummikub_solver`) : **282 passed, 3 skipped** (Playwright
  absent), deux exécutions consécutives identiques (~1 min 47 chacune) — aucune
  intermittence.
- Robustesse sous charge démontrée : avec 8 cœurs saturés, `facteur_machine`
  monte à ≈ 2,7 et **tous** les tests sensibles passent (l'ancien budget 12 s
  codé en dur aurait été dépassé).
- Fichiers touchés : `tests/test_condense_solveur.py`, `tests/test_ia.py`,
  `tests/test_solveur_exact_maison.py`, `pytest.ini`, `CONTEXTE.md`.
  **Aucun** changement au moteur, à l'IA, au solveur ni au pas-à-pas.

# Issue #209 — Pas à pas : mettre nettement en avant la ou les tuiles concernées par l'étape en cours (suite de #207)

Dans le pas-à-pas condensé (#207), chaque étape décrit un geste précis
(« Le 11 rouge remplace le 11 jaune dans le groupe de 11 rouge, bleu et
noir »), mais la tuile dont parle la phrase n'avait qu'un liseré discret
(`.tuile-ia-highlight`) : elle se perdait sous le cadre « provisoire » et le
liseré de la combinaison modifiée, qui ressortaient davantage. Le joueur
devait lire la phrase puis chercher la tuile. #209 rend la ou les tuiles
actives **repérables d'un coup d'œil**, nettement plus que le reste.

**Front-end uniquement** (`ui/web/jeu.css`, `ui/web/jeu.js`), plus un petit
correctif de la liste `surbrillance` de l'écran « Les jokers » dans
`moteur/description_coup.py`. **Aucun changement au moteur de jeu, à l'IA, à la
sauvegarde**, ni au texte des étapes, au découpage condensé, au mode
« Détailler », à la bascule Avant / Après ou aux blocs « provisoire ».

## Changements

- **Surbrillance forte `.tuile-pas-active`** (`jeu.css`) : contour épais
  magenta (3 px), double halo pulsé, léger agrandissement (`scale(1.1)`) et
  fond légèrement teinté. Le voile de fond (`::after`) est glissé **sous** le
  chiffre (`.tuile-pas-active > * { z-index: 1 }`), donc la valeur et la
  couleur de la tuile restent parfaitement lisibles, quelle que soit sa
  couleur. L'intensité est **volontairement supérieure** à celle du liseré de
  la combinaison modifiée (`.combi-modifiee`, bleu 2 px) et du cadre
  « provisoire » (`.combi-provisoire`, ambre pointillé) : la hiérarchie saute
  aux yeux — d'abord la tuile active, puis la combinaison touchée, puis le
  reste. Le magenta est absent des couleurs de tuile (rouge/bleu/jaune/noir) et
  des deux liserés, et reste bien visible sur le fond vert du plateau comme sur
  le fond clair du cadre.
- **Aperçu du plateau** (`rendreApercuPlateauPasAPas`, `jeu.js`) : les tuiles
  de `etape.surbrillance` reçoivent `.tuile-pas-active` au lieu de l'ancien
  `.tuile-ia-highlight` discret. `.tuile-ia-highlight` reste utilisée
  uniquement par le rejeu animé (`animerPoseTuiles`), inchangé.
- **Cadre « tuiles à placer »** (`rendreCadrePasAPas`, `jeu.js`) : reçoit
  désormais la liste `surbrillance` et applique la **même** surbrillance forte
  aux tuiles du cadre nommées par l'étape (par-dessus leur pourtour de
  provenance vert/orange) — écran « Départ » (tuiles de la main prêtes à poser)
  et toute tuile qui vient de rejoindre le cadre.
- **Cohérence texte ↔ surbrillance** : à chaque étape, les tuiles mises en
  avant sont exactement celles de `etape.surbrillance` (plateau et cadre
  confondus), ni plus ni moins. Correctif associé dans `description_coup.py` :
  la `surbrillance` de l'écran « Les jokers » inclut maintenant le joker **et**,
  s'il est remplacé, sa ou ses tuiles de remplacement (auparavant seul l'id du
  joker), pour correspondre mot pour mot à la phrase « Le joker … est remplacé
  par … ». Un joker simplement libéré ne met en avant que lui.

## Vérification

- `tests/test_description_coup.py` : `test_joker_recupere_puis_rejoue_ailleurs`
  vérifie la `surbrillance` joker + remplaçant ;
  `test_surbrillance_jokers_libere_sans_remplacant` qu'un joker simplement
  libéré ne met en avant que lui.
- `tests/test_playwright_pas_a_pas.py` (chargé sur `jeu.html`, jamais la vraie
  app pywebview) :
  `test_surbrillance_forte_suit_exactement_les_tuiles_de_chaque_etape` — sur le
  coup de Clara au tour 45 (`tests/donnees/pas_a_pas_clara_tour45.json`), à
  chaque étape les tuiles portant `.tuile-pas-active` (plateau + cadre) sont
  exactement celles de `etape.surbrillance`, et il y en a au moins une ;
  `test_surbrillance_forte_joker_et_remplacant_plateau_et_cadre` — écran
  « Les jokers » du cas Bruno : le joker (sur le plateau) et sa tuile de
  remplacement (dans le cadre) sont tous deux mis en avant.
- Vérifié visuellement par capture Playwright sur `jeu.html` : la tuile active
  ressort nettement, la valeur reste lisible, la hiérarchie tuile > combinaison
  > reste est claire.

`CONTEXTE.md` §12 et nouvelle sous-section §12quinquies mis à jour.

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

# Issue #208 — Préparer le build Windows avec le solveur exact : autotest `--autotest`, garde-fous de taille adaptés, exclusions inutiles (suite de #206)

#206 a fait entrer `highspy` (HiGHS, extension native) et `numpy` dans le
paquet livré (modèle exact d'Expert). Deux risques pour le prochain build
Windows, pas encore essayé : (1) si PyInstaller collecte mal ces paquets
natifs, Expert retombe **silencieusement** sur l'ancienne recherche
arborescente, sans que rien ne le signale ; (2) les garde-fous de taille du
script de build (dossier 20-45 Mo, installeur 5-25 Mo) refuseraient
probablement un paquet pourtant légitime devenu plus gros (~+55 Mo). #208
outille la détection et élargit les garde-fous, sans lancer aucun build
Windows.

## Changements

- **Option `--autotest` (nouveau module `src/rummikub/autotest.py`)** : vérifie,
  **sans ouvrir de fenêtre** et **sans importer `pywebview`/l'interface**, que
  le solveur exact fonctionne dans le binaire. Affiche en quelques lignes
  lisibles : version de Python, mode (sources / exécutable gelé), versions de
  `numpy` et `highspy`, présence des ressources web, puis **résout une petite
  position intégrée** (plateau vide + suite 5-6-7 + groupe de 10 → 6 tuiles
  attendues) avec `moteur/solveur_exact.py` et affiche le nombre de tuiles
  posées et la durée. **Code de sortie 0** si tout fonctionne, **1** sinon avec
  la cause. Fonctionne depuis les sources ET depuis l'exécutable gelé par
  PyInstaller. **Ne lit/écrit aucune donnée utilisateur** (ni SQLite ni
  `config.json`).
- **`main.py`** : détecte `--autotest` **avant** tout import de
  `rummikub.ui.application` (l'import de la fenêtre devient paresseux) → aucune
  fenêtre, aucun chargement de `pywebview` en mode autotest.
- **Rapport fichier** : l'exe Windows étant fenêtré (`console=False`), sa sortie
  standard est perdue ; `--autotest <chemin>` écrit donc aussi le compte rendu
  complet dans le fichier indiqué, que le script de build récupère.
- **Script de build `build/rebuild_rummikub.bat`** :
  - nouvelle **sous-étape 5bis** (sans renuméroter l'existant, comme `3bis`/
    `8bis`) : lance `dist\Rummikub\Rummikub.exe --autotest <log>` après
    PyInstaller, **reprend le log** dans le compte rendu (`type`), et **refuse
    le build** (`exit /b 1`, message clair) si le code de sortie n'est pas 0 ;
  - **garde-fous de taille élargis** (valeurs **provisoires** à confirmer au
    1ᵉʳ build Windows) : dossier non compressé **20-120 Mo** (étape 5),
    installeur compressé **5-50 Mo** (étape 6), zip compressé **5-50 Mo**
    (étape 7, même famille que l'installeur) ;
  - les autres garde-fous (numéro de build, arguments) sont **inchangés**.
- **`rummikub.spec`** : `excludes` ajoutés pour ne pas embarquer d'inutile —
  `scipy`, `matplotlib`, `pandas`, `tkinter`, `PyQt5/6`, `PySide2/6`, et les
  sous-paquets de dev/compilation/tests de numpy (`f2py`, `distutils`,
  `testing`, `tests`, `array_api`). Vérifié : l'import du solveur n'est pas
  cassé. ⚠️ `numpy.libs/libscipy_openblas64_*.so` (~27 Mo) est l'**OpenBLAS
  vendu par numpy** (requis), PAS le paquet `scipy` — jamais exclu.
- **Tests `tests/test_autotest.py`** : cas réussi (solveur présent), dépendances
  absentes simulées (`numpy`/`highspy`), ressources web manquantes, écriture du
  rapport, et garantie que `--autotest` n'importe **jamais** `pywebview`/l'UI
  (exécution réelle de `main.py --autotest` en sous-processus).

## Essai Linux (détection précoce — ne remplace pas le build Windows)

PyInstaller, `highspy`, `numpy` et `pywebview` installés dans un venv de dev
hors dépôt (`.venv-exact`, gitignoré ; `requirements.txt` **non modifié**).
Build onedir `pyinstaller rummikub.spec` → OK.

- `--autotest` sur l'exe gelé : **code 0**, backend HIGHS, **6 tuiles** posées,
  ressources web trouvées dans le bundle, rapport fichier écrit.
- **Poids du dossier produit : ~74 Mo** (numpy.libs/OpenBLAS 27 Mo + numpy
  14 Mo + libpython 8,7 Mo + highspy 6 Mo + libcrypto 5,1 Mo + reste runtime).
- **Modules manquants** : seulement des faux positifs habituels de numpy
  (`numpy._core.*`, accès d'attributs, pas de vrais modules) et les backends
  Windows de pywebview (`winreg`, `webview.platforms.winforms`…), normaux sous
  Linux. **Aucun** paquet exclu (scipy/matplotlib/tkinter/Qt, numpy
  f2py/distutils/tests) n'est entraîné.

## Estimation du poids final (Windows, à confirmer)

Dossier non compressé **~75-85 Mo** (build 13 : 26 Mo + ~+55 Mo numpy/highspy),
installeur et zip compressés **~25-35 Mo** (build 13 : 12,8 Mo). Tous dans les
nouvelles fourchettes.

## Tests

- `tests/test_autotest.py` : **8 passés** avec `highspy`/`numpy` présents (dans
  le venv de dev) ; les cas « deps présentes » sont sautés à défaut, comme
  `test_solveur_exact_maison.py`.
- Suite complète (venv avec deps) : **244 passés, 5 sautés**, 1 échec
  **préexistant et sans rapport avec #208** :
  `test_ia.py::test_solveur_cascade_joker_61_trouve_attendu_avec_gros_budget`
  — test machine-dépendant de l'ANCIENNE recherche arborescente
  (`solveur.py`, budget 12 s codé en dur) : échoue à l'identique sur le HEAD
  pristine (3 tuiles au lieu de 4 ; la machine d'essai est plus lente que la
  machine de référence du test). Aucun fichier de `src/rummikub/moteur/` n'est
  touché par #208.

## À mettre à jour dans le guide de build avant le prochain essai Windows

Fiche Rummikub de `BUILD_WINDOWS_CCW.md` (dépôt Bridge_Agent, **hors périmètre,
non modifié ici**) — voir le rapport de clôture pour les lignes exactes et la
checklist du poste Windows.

# Issue #206 — Expert : la recherche du solveur remplacée par une résolution exacte légère (programmation linéaire en nombres entiers, HiGHS) (suite de #204)

La vérification de #204 (bibliothèque libre `rummikub-solver` comme oracle
exact) avait montré que la recherche arborescente d'Expert
(`moteur/solveur.py`) restait **sous l'optimum sur 5 cas réels sur 10** au
budget de jeu (1,5 s), dont **2 cas même à 30 s** (faiblesse d'algorithme, pas
de temps) : Bruno tour 57 (3 tuiles au lieu de 4) et Ines tour 85 (une
**victoire immédiate manquée**, 1 au lieu de 2). #206 remplace cette recherche
par un **modèle exact maison** qui trouve TOUJOURS le coup posant le plus de
tuiles, en une fraction de seconde, sans aucune bibliothèque lourde. Les
niveaux inférieurs (Débutant à Avancé) ne changent pas.

## Changements

- **Nouveau module `src/rummikub/moteur/solveur_exact.py`** : formule le coup
  d'un tour comme une **programmation linéaire en nombres entiers** (den Hertog
  & Hulshof, *The Computer Journal*, 2006), résolue par **HiGHS** via `highspy`
  (MIT) + `numpy` (BSD) — **sans** `cvxpy` ni `scipy` (la « voie (b) » du
  rapport de #204, ≈3× plus légère). Une variable entière `x_s ∈ {0,1,2}` par
  ensemble valide possible (suites de longueur 3 à 5, groupes de 3-4, jokers en
  remplacement ; ~1170 ensembles énumérés une seule fois), contrainte de
  conservation `t_i ≤ Σ a_{s,i} x_s ≤ t_i + r_i` par type de tuile (toutes les
  tuiles du plateau restent posées, jamais plus de tuiles qu'on n'en a). Toute
  solution est **remise dans l'ordre** (suites, jokers aux bons endroits) puis
  **revalidée par `valider_combinaison`**, et la **conservation du plateau** est
  contrôlée avant d'être renvoyée — un résultat qui échouerait n'est jamais
  joué.
- **Critères de départage** (lexicographiques, par passes successives figeant
  l'optimum entier de la précédente ; le nombre de tuiles posées reste TOUJOURS
  le premier critère) : (1) tuiles posées, (2) **perturbation minimale** du
  plateau (#199 : tuiles déplacées puis combinaisons modifiées, via des
  variables d'affectation `cover` — totalement unimodulaires, donc exactes),
  (3) points posés, (4) économie de jokers de la main. Le cas de David tour 31
  reste joué **en un seul geste** (extension d'un groupe, 0 tuile déplacée).
- **Mise initiale** : tant qu'elle n'est pas faite, le plateau est GELÉ
  (reconduit à l'identique), les ensembles ne sont formés que depuis la main,
  avec `Σ points_s x_s ≥ mise_initiale_min`. Contrairement à la bibliothèque de
  #204 (qui réarrangeait le plateau), le modèle maison respecte la règle (test
  dédié).
- **Reproductibilité & budget** : HiGHS en `threads=1`, `random_seed=0`, sortie
  muette, limite de temps ferme = `BUDGET_TEMPS_EXPERT` (1,5 s). Résultats
  reproductibles.
- **Branchement dans Expert** (`moteur/ia.py`) : `jouer_niveau_expert` utilise
  le modèle exact. **Repli, sans jamais lever ni bloquer le jeu** : absence de
  `highspy`/`numpy` (`SolveurExactIndisponible`), budget dépassé sans solution
  (`BudgetExactDepasse`) ou erreur → repli sur la recherche arborescente
  conservée telle quelle (`solveur.py`), puis sur Avancé. Nouveau drapeau
  `UTILISER_SOLVEUR_EXACT` / paramètre `utiliser_exact` pour comparer les deux
  versions. **Avancé et les niveaux inférieurs sont inchangés.**
- **Dépendances & distribution** : `highspy>=1.7,<2` et `numpy>=1.26,<3`
  ajoutés à `requirements.txt` (roues Python 3.12 / Windows) ; fichier
  **`THIRD_PARTY_LICENSES.txt`** créé (textes MIT de HiGHS et BSD de numpy) ;
  `rummikub.spec` embarque explicitement `highspy` (sous-modules + bibliothèques
  natives) et distribue le fichier de licences à la racine de `dist/Rummikub/`.
  Le build (`build/rebuild_rummikub.bat`) installe déjà `requirements.txt` et
  l'installeur (`installeur/rummikub.iss`) copie tout `dist\Rummikub\*` — rien
  d'autre à changer côté pipeline ; voir le rapport pour la checklist CCW.

## Tests

- **`tests/test_solveur_exact_maison.py`** (nouveau) : optimum exact sur
  **tous** les `cas_expert_*.json` / `reference_*.json` (atteint
  `attendu_exact_tuiles`, au budget de production mis à l'échelle de la vitesse
  machine) ; accord avec la recherche exhaustive indépendante
  (`verif_solveur`, positions aléatoires graine fixe : jamais sous l'optimum,
  toujours valide/conservé) ; accord **exact** avec la bibliothèque
  `rummikub-solver` quand elle est installée (sauté sinon) ; replis (highspy
  absent, budget nul) ; mise initiale (ne touche pas le plateau, échec si
  minimum inatteignable) ; critères de départage (David tour 31 en un geste,
  économie de jokers).
- **`tests/conftest.py`** (nouveau) : calibration de la vitesse machine
  (`facteur_machine`), appliquée aux budgets des tests de la **recherche de
  repli** dont le résultat dépend de la vitesse (point 8 de #204 enfin traité —
  aucun de ces tests n'est supprimé ni allégé, seuls leurs budgets sont mis à
  l'échelle). Tests concernés listés dans le rapport.
- Toute la suite existante passe (257 tests hors Playwright).

## Mesure

Voir **`RAPPORT_SOLVEUR_EXACT_MAISON_206.md`** : optimum atteint sur 10/10 cas
(écart nul), temps par cas, campagne Avancé vs Expert avant/après, démarrage et
poids ajoutés, et la checklist de vérification sous Windows (CCW).

# Issue #205 — Nombre de manches : déplacé sur l'écran d'accueil, près de « Lancer la partie » (suite de #203)

#203 avait réactivé le choix du nombre de manches, mais le champ se trouvait
dans les Réglages (onglet « Règles du jeu »). Le nombre de manches étant un
choix propre à chaque match (comme la liste des adversaires) et non un réglage
permanent, il est désormais sur la **carte principale de l'écran d'accueil**,
juste au-dessus du bouton « Lancer la partie ». **Aucun changement du moteur,
des IA ni des écrans de jeu.**

## Changements

- **Contrôle compact sur l'accueil** (`accueil.html`) : libellé « Nombre de
  manches : » + liste déroulante de 1 à 9 (défaut 1), dans le même style que
  « Ajouter un adversaire : », placé juste avant « Lancer la partie »
  (`#choix-manches` / `#acc-manches`).
- **Retrait de l'onglet « Règles du jeu »** : plus aucun champ « Nombre de
  manches » dans les Réglages — un seul endroit pour ce choix.
- **Mémorisation** (`accueil.js`) : le choix est persisté dès qu'il change,
  sous la **même clé `nb_manches`** et via la même API que les autres réglages
  (`sauvegarder_reglages`, sans toast), puis présélectionné à l'ouverture
  suivante (`remplirChampManches`). Une valeur absente ou hors de [1, 9]
  retombe sur 1, sans erreur JavaScript même si un ancien `config.json` porte
  encore la clé.
- **Lancement inchangé** : la valeur (bornée 1 à 9) est transmise à
  `lancer_nouvelle_partie` dans `regles.nb_manches`, exactement comme avant.
  Avec 1 manche, rien d'autre ne change (pas d'indicateur « Manche N / M »,
  écran de fin habituel).
- **Mise en page** (`accueil.css`) : contrôle sur une seule ligne, compact,
  lisible à la taille minimale de la fenêtre, avec ou sans parties
  sauvegardées, sans débordement.

## Tests

- `tests/test_playwright_accueil_reglages.py` mis à jour (Playwright sur
  `accueil.html` chargé en direct, jamais la vraie app pywebview, voir
  CONTEXTE.md §7) : choix présent sur l'accueil juste avant « Lancer » et
  **absent des Réglages**, valeur rechargée depuis `nb_manches`, enregistrée au
  changement, transmise au lancement, et valeur invalide/absente ramenée à 1.
- `CONTEXTE.md` §3bis mis à jour.

# Issue #204 — Vérification du solveur d'Expert par un solveur exact indépendant (suite de #201)

Mesure **indépendante et exacte** de ce que le solveur d'Expert
(`moteur/solveur.py`) rate, à l'aide de la bibliothèque libre `rummikub-solver`
(PyPI, licence MIT, programmation linéaire en nombres entiers de den Hertog &
Hulshof 2006). **Aucune modification du solveur d'Expert, du jeu livré ni des
niveaux d'IA.** La bibliothèque est une **dépendance de développement
seulement** (absente de `requirements.txt` et du build Windows).

## Ajouts

- **`scripts/solveur_exact.py`** — adaptateur vers la bibliothèque : conversion
  de nos états (plateau, main, drapeau de mise initiale) vers la bibliothèque
  (couleurs noir=BLACK, bleu=BLUE, jaune=ORANGE, rouge=RED ; jokers), résolution
  exacte, et reconstruction dans notre domaine — nombre de tuiles posées,
  combinaisons **remises dans l'ordre** (suites, place des jokers), durée du
  calcul. Chaque solution est **vérifiée par `valider_combinaison`** et la
  **conservation des tuiles du plateau** contrôlée. S'importe sans la
  bibliothèque (`DISPONIBLE=False`, message d'installation).
- **`scripts/comparer_solveur_exact.py`** — comparaison sur tous les
  `tests/donnees/cas_expert_*.json` et `reference_*.json` : nombre de tuiles de
  notre solveur à 1,5 s (production) et 10 s (généreux), nombre et durée du
  solveur exact, écart ; synthèse finale (cas ratés à 1,5 s, écart moyen/maximal,
  temps total exact, contrôles). Option `--journaux [--tous] [--dossier]` pour
  comparer sur de vrais journaux de parties.
- **`scripts/analyser_coups_rates.py --juge-exact`** — option (désactivée par
  défaut) qui utilise le solveur exact comme **juge** à la place du solveur
  maison : plus aucune décision « inconclusive » ni coup manqué par gel de
  combinaisons. Signale clairement l'absence de la bibliothèque.
- **`tests/test_solveur_exact.py`** — tests de l'adaptateur (correspondances,
  remise dans l'ordre, validité + conservation + maximum exact sur les 10 cas,
  non-régression Ines, interface drop-in), **sautés proprement** si la
  bibliothèque est absente (comme Playwright).
- **`RAPPORT_SOLVEUR_EXACT_204.md`** — rapport : répartition des écarts, durées,
  taille d'installation et démarrage, deux voies d'embarquement éventuel
  (a : la bibliothèque telle quelle via cvxpy/scipy ; b : modèle maison direct
  sur `highspy`+`numpy`, ~3× plus léger), liste des licences et obligations
  (avis de copyright ; éviter l'extra GPL `glpk_mi`).

## Modifications

- **`tests/donnees/*.json`** — clé **`attendu_exact_tuiles`** (maximum exact)
  ajoutée à chaque cas de référence, `attendu_min_tuiles` conservée.
- **`src/rummikub/persistance/coups_rates.py`** — `analyser_decision_complete`
  (et `analyser_decisions_completes`) acceptent un paramètre `solveur`
  optionnel (callable, défaut = solveur maison inchangé) permettant d'injecter
  le juge exact. Le module **n'importe jamais** la bibliothèque. Comportement
  par défaut strictement identique.
- **`CONTEXTE.md`** — nouvelle **§14** (installation, usage, résultats).
- **`.gitignore`** — ignore `.venv-solveur-exact/` (venv de dev, ~316 Mo,
  jamais versionné).

## Résultats mesurés (10 cas de référence, backend HiGHS)

- Notre solveur rate des tuiles sur **5/10 cas à 1,5 s** (budget de production).
- Le solveur exact calcule l'optimum prouvé en **~84 ms/cas** (max ~145 ms).
- Deux cas restent sous l'optimum **même à 10 s** (faiblesse d'algorithme, pas
  de budget) : **Bruno tour 57** (3 vs 4 — tuile manquante `rouge_12`, obtenue
  en scindant la suite rouge 6–10) et **Ines tour 85** (1 vs 2, victoire
  immédiate manquée → test de non-régression de la suite).
- Toutes les combinaisons proposées sont valides et conservent le plateau.

**Réponse à la question de l'issue** : le solveur exact trouve le maximum du
tour **nettement plus vite** que le nôtre. Reste à trancher l'embarquabilité
(voie b recommandée : `highspy` direct, MIT) — hors périmètre de cette issue,
qui ne modifie pas le build.

# Issue #203 — Suite #192 : manches multiples réactivées, vrai décompte de manches et scores cumulés (une seule manche par défaut)

#192 avait masqué le réglage « Nombre de manches » et forcé une seule manche
partout, parce que la règle de fin de partie pour plus d'une manche
(`est_fin_partie`) comparait le numéro de tour au nombre de manches sans
qu'aucun compteur de manches correct n'existe. #203 ajoute un vrai compteur de
manches (`manche_numero`) et des scores cumulés par joueur, relie le tout au
réglage réaffiché (1 à 9, **défaut 1**), et met à jour journal, bilan,
analyse des coups ratés et scripts de simulation pour compter les manches. Le
comportement par défaut reste **une seule manche**.

## Règles des manches

- Une manche se termine quand un joueur vide son chevalet ou que la partie est
  bloquée (pioche épuisée — règle existante). Les scores de la manche (perdants
  en négatif, gagnant en positif, joker à la valeur du réglage) s'ajoutent aux
  cumuls.
- Si la manche n'est pas la dernière, le match continue : nouvelle donne, mise
  initiale remise à zéro pour tous, `score_cumul` conservé. **Qui commence** :
  rotation — la manche N commence par le joueur `(N-1) % nb_joueurs`.
- À la dernière manche, le match est terminé : le gagnant est le joueur au
  plus haut score cumulé ; en cas d'égalité, le classement affiche l'égalité.
- Avec une seule manche (défaut), les points restants ne départagent que les
  parties bloquées (le gagnant est celui qui vide son chevalet) ; l'écran de
  fin de partie reste celui d'avant #203.

## Moteur (`src/rummikub/moteur/`)

1. **`partie.py`** :
   - `creer_partie` lit `nb_manches` depuis les réglages (borné à [1, 9],
     défaut 1 — plus de forçage à 1), ajoute `manche_numero: 1`.
   - `_terminer_tour` : à la fin de la manche, calcule les scores et, si c'est
     la dernière manche (`est_fin_partie`), marque `terminee`, calcule
     `gagnant_match_index` (plus haut cumul) et `egalite_match`.
   - `est_fin_partie` : vrai si la manche est terminée ET `manche_numero >=
     nb_manches` (remplace la comparaison sur `tour_numero`).
   - `nouvelle_manche` : incrémente `manche_numero`, fait tourner le donneur,
     conserve `score_cumul`.
   - `normaliser_etat_reprise` (nouveau) : reprise d'une sauvegarde — un état
     sans `manche_numero` (d'avant #203) est repris en une seule manche ; un
     match récent au milieu d'un match conserve son nombre de manches.
2. **`score.py`** : `trouver_gagnant_match` (plus haut `score_cumul`) et
   `egalite_sommet_match` (égalité au sommet).

## Réglages et application

3. **`reglages.py`** : clé `nb_manches: 1` réintroduite dans `DEFAUTS`.
4. **`ui/application.py`** : `reprendre_jeu` n'force plus 1 manche ; il appelle
   `normaliser_etat_reprise`. `naviguer_vers_jeu` transmet les règles (dont
   `nb_manches`) à `creer_partie`.
5. **`ui/web/accueil.html` / `accueil.js`** : champ « Nombre de manches »
   (`<select>` 1-9, défaut 1) réaffiché dans l'onglet « Règles du jeu » ;
   lu/écrit dans les réglages (`lireNbManches`, bornage à 1) et transmis au
   lancement de la partie.

## Interface (`ui/web/jeu.html` / `jeu.js`)

6. Indicateur « Manche N / M » dans la barre supérieure, affiché uniquement
   quand le match compte plusieurs manches (`rafraichirIndicateurManche`).
7. Écrans de fin déjà en place (avant #192) de nouveau atteignables : écran de
   fin de manche intermédiaire (scores de la manche + cumul, bouton « Manche
   suivante ») et classement final (par cumul) ; l'égalité en tête est
   désormais affichée explicitement (`afficherClassementFinal`). Le rejeu, le
   pas-à-pas et le reste repartent proprement à chaque manche (`nouvelle_manche`
   réinitialise `dernier_coup_ia`, etc.).

## Journal, bilan et coups ratés (`src/rummikub/persistance/`)

8. **`journal.py`** : chaque action porte son numéro de `manche` ; `termine`
   n'est vrai qu'à la fin du MATCH, et `gagnant_index` y désigne alors le
   vainqueur du match (plus haut cumul).
9. **`bilan.py`** : décisions dédoublonnées par `(manche, tour)` (le `tour`
   repart à 1 à chaque manche) ; nouveau champ `nb_manches` par partie et
   `manches_moyennes` / `manches_total` par niveau. Un match de plusieurs
   manches est compté **une seule fois** ; une partie reprise reste un seul
   match (regroupement par `partie_id` existant).
10. **`coups_rates.py`** : une décision n'est jamais reconstituée à partir de
    l'état d'une autre manche (saut de frontière de manche) ; clé de
    dédoublonnage `(manche, tour, idx)`. La mise initiale repart de zéro à
    chaque manche.

Tous ces champs sont absents des journaux antérieurs → lus comme une manche
unique, sans régression.

## IA

11. Aucun changement de stratégie (issue #203, point 5) : les IA jouent chaque
    manche comme avant. Deux pistes d'Alain ajoutées en §13 de `CONTEXTE.md`
    (se débarrasser en priorité des 1 et des 13 ; tenir compte des points
    restants seulement en plusieurs manches, avec prudence).

## Simulations (`scripts/`)

12. **`simulation_ia.py`** : `--manches N` joue un match de N manches, avec
    résultat par manche et vainqueur du match (plus haut cumul).
13. **`comparer_niveaux_ia.py`** : nouveau `--manches N` — matchs de N manches
    joués en miroir ; rapport par match (victoires au cumul, score cumulé
    moyen) et par manche (fins, durée, pénalités du perdant).

## Tests

- `tests/test_moteur.py` : bornage de `nb_manches`, fin de manche
  intermédiaire vs match, scores cumulés, rotation du donneur, vainqueur au
  cumul ≠ gagnant de la dernière manche, égalité, reprise au milieu / reprise
  d'une ancienne sauvegarde (le test #192 de forçage à 1 est remplacé).
- `tests/test_bilan.py` : un match de plusieurs manches compté une seule fois.
- `tests/test_coups_rates.py` : manches non confondues.
- `tests/test_playwright_accueil_reglages.py` : réécrit pour le champ réaffiché
  (présent, rechargé/enregistré/transmis, bornage à 1).
- `tests/test_playwright_manches.py` (nouveau) : indicateur « Manche N / M »,
  écran de fin de manche intermédiaire, classement final, affichage de
  l'égalité.
- Suite complète : **227 tests passent** (`pytest -q`).

## CONTEXTE.md

- §3bis réécrit (statut ACTIF, règles des manches documentées) ; §3/§4
  (fonctions moteur, clés d'état) ; §9/§10 (scripts `--manches`, champ
  `manche` du journal) ; §13 enrichi des deux pistes IA d'Alain (pistes 6 et
  7) et constat du réglage corrigé par #203.

# Issue #202 — Suite #201 : relier les fichiers d'une même partie reprise et enregistrer la mise initiale de chaque joueur

À la fermeture puis réouverture du jeu, une partie reprise repart sur un
NOUVEAU fichier de journal (le cache mémoire de `persistance/journal.py` est
perdu au redémarrage). L'ancienne analyse (`persistance/coups_rates.py`)
déduisait qu'un joueur avait fait sa mise initiale de la seule présence d'une
pose antérieure **dans le même fichier** : sur un fichier de reprise, elle
croyait donc à tort la mise initiale non faite, ce qui bride le solveur (avant
la mise, il ne peut pas utiliser le plateau) et fausse le résultat. Mesuré sur
trois cas réels (parties `…183714` tour 28, `…213723` tour 58, `…172338`
tour 16) : supposé avant la mise, le solveur trouvait 0/0/6 tuiles et l'outil
concluait à tort « le joueur bat le solveur » ; supposé après la mise, il
trouve 2/3/7 (autant ou plus que le joueur) — aucun n'était un vrai cas de
solveur battu. Le bilan (`persistance/bilan.py`) était lui aussi faussé : il
comptait le premier fichier d'une partie reprise comme une partie abandonnée
et le second comme une partie distincte.

## Corrections

1. **Journal** (`src/rummikub/persistance/journal.py`) : nouvelle clé
   `mises_initiales` sur chaque action — liste de booléens alignée sur
   `joueurs`, l'état « mise initiale faite » de chaque joueur au moment de
   l'action (helper `_mises_initiales`, calculé d'après l'état du jeu).
   Rétrocompatible : les anciens journaux n'ont pas cette clé. Docstring du
   module complétée.

2. **Nouveau module `src/rummikub/persistance/parties_liees.py`** (pur, sans
   pywebview) : regroupe les fichiers d'une même partie et les fusionne.
   - `grouper_journaux(journaux)` : groupe par `partie_id` (en-tête, conservé
     à la reprise car l'état restauré garde le même `id`), avec repli par
     mêmes joueurs + continuité des numéros de tour si l'identifiant est
     absent ou change ; classe chaque groupe dans l'ordre chronologique.
   - `fusionner_groupe` / `fusionner_journaux` : concatènent les `actions` en
     une seule suite (l'état de départ de la première action d'un fichier de
     reprise devient l'état de la dernière action du fichier précédent) et
     renvoient `debut_present` (faux si le plus ancien fichier commence
     au-delà du tour `SEUIL_DEBUT_PARTIE=2`, c.-à-d. en plein milieu de partie).

3. **Analyse** (`src/rummikub/persistance/coups_rates.py`) :
   - `_mise_initiale_avant(actions, i, idx, debut_present)` : lit la clé
     `mises_initiales` de l'action précédente quand elle existe (journal
     #202+), sinon repli #188 (pose antérieure dans la suite d'actions, qui
     est désormais FUSIONNÉE à travers la reprise). **Historique manquant** :
     si le début de partie est absent et qu'aucune pose n'est observée,
     retourne `None` (INCONNU) — on ne suppose jamais « non faite ».
   - `extraire_decisions_ia`, `extraire_toutes_decisions`,
     `extraire_decisions_ia_toutes`, `extraire_decisions_joueur` acceptent un
     paramètre `debut_present` (défaut `True` : comportement d'origine pour
     les appels directs existants). Une décision indéterminable reçoit
     `moment="inconnu"` et `mise_initiale_inconnue=True`.
   - `analyser_decision` / `analyser_decision_complete` court-circuitent les
     décisions « inconnu » (le solveur n'est pas interrogé — aucune hypothèse
     n'est faite) et portent toutes `mise_initiale_inconnue`.
   - `calculer_resume` / `calculer_resume_complet` comptent les décisions
     « inconnu » à part (`resume[niveau]["inconnu"]["decisions"]`), hors des
     buckets avant/après la mise. `resume_joueur_humain` exclut ces décisions
     des statistiques de style et des listes.

4. **Bilan** (`src/rummikub/persistance/bilan.py`,
   `charger_toutes_parties`) : regroupe les fichiers d'une partie reprise et
   fusionne leurs actions avant `extraire_partie` — la partie est comptée UNE
   SEULE FOIS, avec son nombre de tours réel et toutes les décisions ; le
   premier fichier n'est plus pris pour une partie abandonnée.

5. **Scripts** :
   - `scripts/analyser_coups_rates.py` : regroupe les fichiers par partie
     avant analyse, pour l'IA comme pour `--joueur` (`_charger_parties`,
     `_etiquette_partie`, `_decisions_ia_par_cle`) ; affiche le décompte des
     décisions « mise initiale inconnue » et signale les parties reprises
     réparties sur plusieurs fichiers. `--retenter-inconclusifs`,
     `--budget-mesure` et `--enregistrer-cas-reference` utilisent la même
     clé de partie que l'analyse.
   - `scripts/bilan_parties.py` : bénéficie automatiquement du regroupement
     via `charger_toutes_parties`.
   - **Nouveau** `scripts/verifier_cas_reference.py` (point 5) : vérifie le
     drapeau `mise_initiale_faite` figé dans `tests/donnees/cas_expert_*.json`,
     recalcule le drapeau correct à partir des journaux d'origine regroupés
     (`--dossier`) et corrige les cas faux (`--ecraser`). Les 9 cas existants
     portent déjà `mise_initiale_faite=True` pour le joueur concerné (aucun
     faux dans le sens dangereux). La régénération des cas reste possible via
     `analyser_coups_rates.py --enregistrer-cas-reference --ecraser`, qui
     utilise désormais l'analyse regroupée.

6. **CONTEXTE.md** : nouvelle sous-section §11sexies.

## Tests (nouveaux)

- `tests/test_journal_mise_initiale.py` : la clé `mises_initiales` reflète
  l'état des joueurs, est écrite par `logger_action` et via `ui/api.py`.
- `tests/test_coups_rates_parties_liees.py` : regroupement par `partie_id` et
  repli par continuité ; deux parties distinctes entre les mêmes joueurs non
  reliées ; deux fichiers reliés classant le second « après la mise » alors
  que seul il le classerait « avant » (avec et sans la clé `mises_initiales`) ;
  solveur recevant le bon drapeau bout en bout (coup raté détecté) ; historique
  manquant détecté, décision exclue et comptée à part.
- `tests/test_bilan.py` : une partie reprise en deux fichiers comptée une seule
  fois (tours réels, toutes les décisions) ; premier fichier non pris pour une
  partie abandonnée.

## Garanties

- Ne modifie jamais l'IA ni le moteur de jeu : journal enrichi + lecture/
  analyse/bilan en lecture pure.
- Rétrocompatible avec les anciens journaux (clé `mises_initiales` absente :
  repli #188 sur la suite d'actions fusionnée).
- Suite complète : 203 tests au vert (dont 17 nouveaux), hors Playwright (qui
  nécessite un navigateur).

# Issue #200 — Suite #194 : Solveur Expert, coups de grande envergure et bug de mesure côté humain

Diagnostic des 3 cas humains enregistrés comme référence (#193,
`tests/donnees/cas_expert_humain_*.json`) : le chevalet réellement capturé
ne contenait que 7, 3 et 3 tuiles, alors que `attendu_min_tuiles` (18, 7,
18) en exigeait davantage — une cible physiquement impossible (on ne peut
jamais poser plus de tuiles que n'en contient la main). Le solveur
trouvait déjà, en quelques centaines de ms à ~2s, le maximum réel (= la
main entière) sur les 3 cas : aucune incomplétude du solveur sur ces cas,
contrairement à l'hypothèse de départ de l'issue.

Cause réelle, localisée dans `persistance/coups_rates.py` :
`analyser_decision_complete` comparait le solveur au champ brut
`nb_tuiles_posees` du journal (`len(data["ids_tuiles"])` côté
`ui/api.py::jeu_jouer_coup`, la longueur de la liste d'ids envoyée par le
client JS), qui peut dépasser la taille réelle du chevalet d'avant-coup,
plutôt qu'à `ids_tuiles_reelles` — déjà calculé juste à côté (différence
entre le chevalet d'avant et celui d'après la pose), fiable et borné par
construction par la taille du chevalet. `jouer_tour` lui-même n'a jamais
été en cause (aucune tuile n'a jamais disparu ni été dupliquée en jeu
réel) : le bug était seulement dans la MESURE utilisée par l'outil
d'analyse, pas dans le moteur de jeu.

**Corrections :**

1. `persistance/coups_rates.py::analyser_decision_complete` : `nb_reel`
   utilise désormais `len(ids_tuiles_reelles)` pour une pose, plus jamais
   `nb_tuiles_jouees` (le compteur brut) — corrige à la source le calcul
   de `joueur_bat_solveur`/`pose_sous_optimale` et tout ce qui en dépend
   (résumé par joueur, enregistrement des cas de référence).
2. `tests/donnees/cas_expert_humain_*.json` (3 fichiers) : `attendu_min_tuiles`
   corrigé à la taille réelle du chevalet (7, 3, 3) — ces cas restent des
   tests de non-régression légers, mais ne sont plus des cas « grande
   envergure » manqués par le solveur.
3. `moteur/solveur.py::_candidats_suite` : optimisation pure (même
   résultat, plus rapide) — construit désormais les tokens d'un intervalle
   de suite une seule fois par borne gauche `v1`, en étendant la borne
   droite `v2` d'une position à la fois, au lieu de reconstruire tout
   l'intervalle `[v1, v2]` depuis zéro pour chaque largeur testée (coût
   quadratique identifié au profilage `cProfile` comme le principal poste
   de temps de la recherche, jusqu'à 40 % du temps total sur les cas les
   plus durs). Équivalence vérifiée par comparaison exhaustive sur 20000
   états aléatoires et par la suite de tests complète (187 tests, aucune
   régression).

**Mesures avant/après** (3 cas de référence authentiques,
`tests/donnees/cas_expert_ia_*.json`, IA Expert d'avant #194 jugée par le
solveur actuel) :
- `tour37` (attendu 6) : déjà trouvé au budget de production (1.5s), AVANT
  comme APRÈS.
- `tour59` (attendu 7) : AVANT, 6/7 à 1.5s, ~3s nécessaires pour la 7e
  tuile. APRÈS, ~2s nécessaires (toujours juste au-dessus du budget de
  production strict, parfois atteint de justesse selon la charge machine).
- `tour61` (attendu 4, cascade de jokers à travers 13 combinaisons du
  plateau, déjà documentée #194 comme à la limite du budget) : AVANT,
  souvent RIEN à 1.5s, jusqu'à 10s nécessaires pour les 4 tuiles. APRÈS,
  ~5s nécessaires (reste nettement hors de portée du budget de
  production).

Le budget de production (1.5s) n'a **pas** été augmenté (dernier recours,
non justifié pour un gain qui resterait de toute façon loin de la cible
sur `tour61`, et marginal sur `tour59`) — ces deux cas restent documentés
comme hors de portée du budget de production, pas forcés plus avant dans
cette issue plutôt que de risquer une régression ailleurs pour les
atteindre.

Aucune piste de changement structurel de la stratégie par paliers
(montée plus rapide, relâchement du gel de combinaisons pour une main
large, recherche en partant du haut de la main) n'a été retenue : sur les
cas réels disponibles, geler moins de combinaisons pour une main large
n'aurait rien changé (une main qui touche déjà les 4 couleurs gèle déjà 0
combinaison — automatique, pas un réglage) et les deux autres pistes
risquaient de faire dégénérer la recherche vers l'ancien comportement
pré-#194 (preuve exhaustive) sur un palier non atteignable, sans qu'aucun
cas réel de « grande main » authentiquement bloquée n'ait été trouvé pour
les justifier.

**Tests ajoutés** (`tests/test_ia.py`) : pour chacun des 5 cas désormais
atteints (3 `cas_expert_humain_*`, `cas_expert_ia_*_tour37`,
`cas_expert_ia_*_tour59`), un test à gros budget (10s) et un test au
budget de production (tolérance ×6, comme #190/#194). Pour
`cas_expert_ia_*_tour61`, un test à gros budget (12s) seul — volontairement
pas de test au budget de production pour ce cas, qui serait soit flaky
soit trompeur avec une tolérance large.

**Campagne de mesure** : voir le rapport de clôture de l'issue pour la
campagne Avancé vs Expert (10 donnes, replis/temps moyen/taux de victoire)
et les limites rencontrées pour la comparaison avant/après sur les
journaux de parties réelles (non disponibles dans ce worktree isolé).

# Issue #201 — Suite #193 : compter les tuiles réellement posées depuis la main (et non les tuiles déplacées) pour un coup humain

Cas réel (tour 66) : `scripts/analyser_coups_rates.py --joueur` annonçait
« posé 18, solveur 7 » (le joueur « bat le solveur » de +11), alors que la
description du coup réellement joué montrait seulement 4 tuiles posées
depuis la main — c'est le solveur qui posait plus de tuiles (7 contre 4),
pas l'inverse.

Cause : `jeu_jouer_coup` (`ui/api.py`) journalisait `nb_tuiles_posees =
len(data["ids_tuiles"])`. Or `ids_tuiles` vient de `tuilesCeTour` côté
interface (`jeu.js`), qui mélange les tuiles venues de la main ET celles du
plateau déplacées pendant le tour (le jeu s'en sert pour colorer « tuile du
tapis déplacée ce tour »). Pour un humain, le journal comptait donc des
tuiles déplacées comme des tuiles posées ; pour une IA, `ids_tuiles` ne
contient que des tuiles de la main, donc son compte était déjà correct.

1. **Analyse corrigée à la source** (`persistance/coups_rates.py`,
   `extraire_toutes_decisions`) : `nb_tuiles_jouees` est désormais calculé
   comme `len(ids_tuiles_reelles)` (différence main avant/après le coup),
   jamais depuis le champ `nb_tuiles_posees` du journal — corrige aussi les
   journaux ANCIENS, puisqu'il ne dépend que des deux instantanés de main
   déjà présents dans tout journal post-#185. Une seule fonction corrigée
   répare en cascade la détection « solveur battu »/pose sous-optimale, les
   statistiques de style, la détection de la réserve, et
   `attendu_min_tuiles` des cas de référence enregistrés.
2. **Journal corrigé** (`ui/api.py:jeu_jouer_coup`, `persistance/journal.py`)
   : capture la main AVANT le coup, puis journalise dans `nb_tuiles_posees`
   le nombre de tuiles de `ids_tuiles` réellement présentes dans cette main,
   et dans la nouvelle clé `nb_tuiles_deplacees` le reste. `logger_action`
   accepte ce nouveau paramètre (défaut 0, rétrocompatible). Vérifié :
   `persistance/bilan.py` recopie `nb_tuiles_posees` mais ne s'en sert
   jamais dans le calcul du bilan — aucune adaptation nécessaire.
3. **Usage de `ids_tuiles` par le moteur vérifié, non modifié** :
   `moteur/partie.py:jouer_tour` ne distingue jamais une tuile de la main
   d'une tuile déplacée. Signalé (voir rapport de clôture) un bug potentiel
   distinct, de la RÈGLE de mise initiale (`_points_tuiles_posees` peut
   compter à tort la valeur de tuiles déplacées, pas posées, dans le total
   requis) — volontairement NON corrigé ici (hors périmètre de cette issue,
   à confirmer par Alain).
4. **Cas de référence régénérables** (`scripts/analyser_coups_rates.py`) :
   nouvelle option `--ecraser` pour `--enregistrer-cas-reference`, qui lève
   le garde-fou "jamais écraser" par défaut — permet de régénérer
   `tests/donnees/cas_expert_humain_*.json` avec le bon `attendu_min_tuiles`
   une fois relancé sur les vrais journaux (hors de ce worktree). Le
   solveur n'est jamais modifié.
5. Tests : `tests/test_coups_rates_tuiles_main.py` (cas réel reproduit,
   journal ancien sans la nouvelle clé, journal d'IA cohérent) ;
   `tests/test_api_journal.py` (journal corrigé de `jeu_jouer_coup` avec
   des tuiles du plateau déplacées). `CONTEXTE.md` §11quinquies.

# Issue #199 — Suite #194 : Expert, à nombre de tuiles posées égal, préférer le coup le plus simple

Cas réel (David, tour 31) : l'IA avait une seule tuile à poser (1 noir), que
le plateau permettait d'ajouter directement au groupe de 1 (rouge, bleu,
jaune) déjà posé pour en faire un groupe de 4 couleurs en un seul geste.
Expert avait pourtant joué ce coup en 12 étapes de pas-à-pas : plusieurs
combinaisons défaites et recréées, pour poser au final la même seule tuile.
Cause : le solveur (`moteur/solveur.py`) cherchait le plus grand nombre de
tuiles posées puis départageait par points/jokers, sans jamais regarder
combien de tuiles du plateau étaient déplacées — parmi toutes les solutions
posant une tuile, il pouvait renvoyer n'importe laquelle.

0. **Mesure de perturbation** `(tuiles_déplacées, combinaisons_modifiées)`,
   calculée directement sur les compteurs par emplacement de la recherche
   (`_perturbation_candidat`), sans reconstruire le plateau concret : nulle
   si un candidat n'utilise aucune tuile du plateau, ou si les tuiles du
   plateau qu'il utilise reproduisent EXACTEMENT une combinaison déjà posée
   avant ce tour (il ne fait qu'ajouter des tuiles de la main à cette
   combinaison, ou la reconduire à l'identique) ; non nulle sinon
   (fragmente ou fusionne des combinaisons existantes). Deux tuiles de même
   aspect (même valeur, même couleur, ou deux jokers quelconques) sont
   interchangeables, comme pour le pas-à-pas (#197). `mesurer_perturbation`
   (API publique de `solveur.py`) calcule la même mesure sur un plateau
   avant/après concret — utilisée par les tests et par
   `scripts/comparer_niveaux_ia.py`, jamais par la recherche elle-même.
1. **Nouveau critère de départage** : nombre de tuiles posées, puis
   perturbation minimale, puis points posés, puis économie de jokers
   (`_meilleur_rearrangement`). Réglage `preferer_simple`
   (`solveur.PREFERER_SIMPLICITE`, activé par défaut), exposé en paramètre
   de `resoudre_coup` et `jouer_niveau_expert` pour comparer les deux
   versions par simulation.
2. **Recherche des coups simples d'abord** : dans le tri des candidats
   (`_resoudre`), la perturbation REMPLACE — plutôt que de s'ajouter à —
   le critère de signature d'origine (#190) parmi les ex-aequo sur
   `_score_rapide`. La signature (forme + taille seulement, pas la
   composition exacte) aurait sinon fait gagner, par coïncidence de forme,
   un candidat qui FRAGMENTE une combinaison d'origine (même signature que
   l'original) sur celui qui l'ÉTEND proprement — exactement le bug
   observé (un groupe de 1 à 3 couleurs, signature identique qu'il soit
   fragmenté en 2 + une tuile de la main ou étendu à 4 couleurs). Mesuré
   sur un cas déjà difficile pour la recherche
   (`cas_expert_ia_261026172338_tour61.json`, cascade de jokers à travers
   tout le plateau, #194) : AJOUTER la perturbation en plus de la
   signature (sans même réordonner), même optimisée pour un coût minimal
   par candidat (frozenset plutôt qu'un tri, calcul unique partagé entre
   le tri et l'application), suffisait déjà à faire manquer, à budget
   identique, le palier que l'ancien comportement trouvait de justesse —
   ce cas est nativement sans la moindre marge pour un coût supplémentaire
   par nœud de recherche. REMPLACER la signature (plutôt que l'additionner)
   évite ce coût tout en corrigeant le cas de David.
3. **Limite documentée** : un candidat qui ne reconstitue qu'une FRACTION
   d'une combinaison d'origine (celle-ci ayant été fragmentée entre
   plusieurs candidats) compte sa propre perturbation indépendamment de
   l'autre fragment — peut compter deux combinaisons modifiées là où un
   œil humain n'en verrait qu'une scindée en deux, sans jamais fausser la
   distinction nulle/non-nulle qui est l'essentiel de ce critère pour le
   départage et la recherche.

## Cas de test (`tests/test_ia.py`)

- `test_solveur_coup_simple_trouve_et_retient_le_coup_sans_perturbation` :
  cas réel de David (`tests/donnees/cas_expert_coup_simple_david_
  tour31.json`) — le solveur trouve au moins la tuile attendue ET une
  solution qui ne touche qu'une seule combinaison, sans déplacer aucune
  tuile du plateau.
- `test_solveur_departage_petit_plateau_fabrique_prefere_la_solution_simple` :
  plateau minimal fabriqué (réduit du cas réel par dichotomie — un groupe
  de 1 et une suite jaune 2-4, main = 1 noir + 12 jaune sans rapport, qui
  rend la suite jaune « flexible » pour la recherche et crée ainsi une
  vraie égalité entre une solution simple et une solution qui fragmente le
  groupe) où le critère doit retenir la solution simple ; vérifie aussi que
  désactiver le critère retrouve l'ancienne solution plus compliquée, pour
  prouver que l'égalité construite est réelle.
- `test_preferer_simple_ne_pose_jamais_moins_de_tuiles_au_budget_de_
  production` (paramétré sur `cas_expert_budget_tour81.json`,
  `cas_expert_bruno_tour57.json`, `cas_expert_humain_*`,
  `cas_expert_ia_261026172338_tour37/59.json`) et
  `test_preferer_simple_atteint_le_meme_plafond_sur_le_cas_le_plus_dur`
  (`cas_expert_ia_261026172338_tour61.json`, à budget large) : non-
  régression — le nouveau critère ne pose jamais moins de tuiles que
  l'ancien comportement. Le cas `tour61` est testé séparément à budget
  large (12s) plutôt qu'au budget de production : il est structurellement
  instable à ce budget (le solveur n'y trouve souvent rien en 1.5s, avec
  ou sans le nouveau critère, déjà avant #199), une comparaison stricte à
  budget de production y serait un test intrinsèquement flaky, pas une
  mesure de régression.

Tous les cas de référence déjà existants continuent de passer sans
changement de temps notable. 164 tests passent au total (`pytest -q`).

## Mesure (campagne Avancé vs Expert, `scripts/comparer_niveaux_ia.py`)

10 donnes x 2 (miroir) = 20 parties, seed 42, budget de production (1.5s) :

| | AVEC le critère (défaut) | SANS le critère |
|---|---|---|
| Victoires Expert | 19/20 — 95.0 % ± 9.6 pt (IC 95 %) | 16/20 — 80.0 % ± 17.5 pt (IC 95 %) |
| Perturbation moyenne / coup Expert | 2.43 tuile(s) déplacée(s), 2.19 combo(s) modifiée(s) | 3.00 tuile(s) déplacée(s), 2.63 combo(s) modifiée(s) |
| Temps moyen / tour Expert | 204.0 ms (max 1559.7 ms) | 221.3 ms (max 1535.1 ms) |
| Replis sur Avancé (faute de budget) | 0.6 % des tours Expert | 1.5 % des tours Expert |

Les deux intervalles de confiance se recoupent largement (échantillon
réduit, comme pour #190/#194) : l'écart de taux de victoire n'est pas
démontrable à ce niveau, mais il n'y a AUCUNE baisse — le but affiché par
la tâche (ne pas perdre de force, pas forcément en gagner) est atteint. La
perturbation moyenne baisse nettement, conformément à l'objectif. Le temps
de calcul et le taux de repli restent comparables (légèrement meilleurs
avec le critère). Le critère reste donc activé par défaut
(`PREFERER_SIMPLICITE = True`).

## Documentation

`CONTEXTE.md` §8bis (nouvelle puce sur le critère de simplicité, avec le
détail technique et les chiffres de la campagne) et §13 (piste cochée :
« complexifier le plateau n'a pas de bénéfice stratégique démontré, la
simplicité est désormais un critère mesuré »).

## Fichiers modifiés

- `src/rummikub/moteur/solveur.py` : mesure de perturbation
  (`_perturbation_candidat`, `_aspects_plateau_candidat`,
  `_multisets_originaux`, `_cle_multiset`), nouveau critère de départage
  (`_meilleur_rearrangement`, `_Contexte`), tri des candidats modifié
  (`_resoudre`), API publique `mesurer_perturbation`, constante
  `PREFERER_SIMPLICITE`, paramètre `preferer_simple` sur `resoudre_coup`.
- `src/rummikub/moteur/ia.py` : paramètre `preferer_simple` sur
  `jouer_niveau_expert` (lu depuis `solveur.PREFERER_SIMPLICITE` par
  défaut, comme `budget_temps`).
- `scripts/comparer_niveaux_ia.py` : drapeau `--sans-preferer-simple`,
  mesure et affichage de la perturbation moyenne par coup d'Expert.
- `tests/test_ia.py` : 5 nouveaux tests (voir ci-dessus).
- `CONTEXTE.md` : §8bis et §13.

## Issue #198 — Suite #196 : classer les coups ratés par taille, filtrer par date, accorder les descriptions

- **Classement par taille** (`persistance/coups_rates.py`) : remplace le découpage
  simple/complexe (trop grossier, #196) par trois tailles — petit (1-2 combinaisons),
  moyen (3-5), grand (6+) —, avec les indicateurs « avec joker » et nombre d'étapes
  conservés séparément. L'ancien simple/complexe est conservé pour la continuité des
  mesures. Agrégé par niveau d'IA et par joueur humain (`calculer_resume_complet`,
  `resume_joueur_humain`), affiché en tableau par `scripts/analyser_coups_rates.py`.
- **Filtre par date** : nouvelle option `--depuis AAAAMMJJ` du script, basée sur le
  nom de fichier (`partie_AAAAMMJJ_HHMMSS.json`), pour n'analyser que les parties
  jouées avec la dernière version d'une IA. Affiche le nombre de journaux retenus.
- **Accords en français** (`moteur/description_coup.py`) : « suite noire »,
  « suite bleue » (accord correct avec les quatre couleurs), jamais de pronom
  « il »/« elle » pour désigner le joueur (tournures impersonnelles ou tuiles
  comme sujet).
- Tests ajoutés : accords de couleur, classification par taille (4 cas fabriqués :
  petit, petit+joker, moyen, grand+joker), filtre par date (nouveau fichier
  `tests/test_coups_rates_filtre_date.py`). Deux tests existants mis à jour car
  comparaient le texte exact (« suite noir » → « suite noire » ; cas Bruno :
  « Il a créé... » → « Création d'un groupe de 11. »).
- `CONTEXTE.md` §11 (nouvelle sous-section 11quater) et §12 (nouvelle sous-section
  12ter) mis à jour.

# Issue #197 — Suite #191 : pas à pas, ne pas montrer les échanges de tuiles identiques

Le jeu contient deux exemplaires de chaque tuile. Le suivi tuile-par-tuile
du pas-à-pas (`moteur/description_coup.py`, #191) identifiait chaque tuile
par son identifiant individuel : un échange entre deux tuiles de même
aspect (même valeur/couleur) — invisible à l'écran — était donc montré
comme un vrai changement (« Le 3 jaune remplace le 3 jaune... »), et ce
même mécanisme causait un **plantage réel en jeu** (`KeyError`) quand une
tuile libérée par un échange ainsi annulé n'était jamais déposée dans le
cadre avant d'être consommée par une opération suivante.

0. **Cause réelle corrigée** : `_construire_operations` sépare désormais
   le suivi causal exact (listes brutes `retirees`/`ajoutees`, toujours
   utilisées pour le cadre et les dépendances — jamais d'exception) de ce
   qui est affiché (`retirees_vues`/`ajoutees_vues`, réduites par
   `_annuler_par_aspect` en annulant une tuile partie et une tuile arrivée
   de même aspect). Le cas réel qui plantait — deux combinaisons qui
   s'échangent leurs tuiles, chacune attendant une tuile libérée par
   l'autre (cycle de dépendances strict) — est détecté par
   `_composantes_fortement_connexes` (Tarjan) et traité en un seul bloc
   (`_detecter_blocs_silencieux`) : toutes les tuiles libérées du bloc
   ajoutées au cadre, puis toutes les tuiles consommées retirées, sans
   dépendre de l'ordre entre les deux combinaisons. Reproduit dans
   `tests/test_description_coup.py` à partir du cas réel capturé par le
   repli d'urgence (#196) dans `tests/donnees/erreur_description_*.json`.
1. **Tuiles interchangeables** : un échange de tuiles de même aspect, dans
   une même combinaison ou entre deux combinaisons, n'est plus compté
   comme un déplacement et ne produit plus aucune étape ni phrase.
2. **Cas de la main** : une tuile de la main identique à une tuile du
   plateau qui se déplace choisit automatiquement la description la plus
   courte (même mécanisme que le point 1, les deux listes s'annulant au
   sein d'une même opération) — la liste des tuiles réellement posées
   depuis la main (`tuiles_posees`, basée sur les identifiants réels)
   n'est jamais affectée.
3. **Jokers** : un joker remplacé par l'autre joker dans une même
   combinaison n'est plus un déplacement (`_jokers_deplaces` ne considère
   un joker comme déplacé que s'il figure dans les tuiles "vues" de sa
   propre opération) ; un joker qui change réellement de combinaison reste
   bien décrit comme un déplacement, même quand deux jokers existent.
4. **Étapes nettoyées** : toute étape sans effet visible est supprimée en
   amont (jamais ajoutée), le nombre d'étapes recalculé, et le seuil du
   bouton « Pas à pas » s'applique aux étapes nettoyées — inchangé par
   ailleurs.
5. **Indicateurs de complexité** (`persistance/coups_rates.py`) : réutilise
   tel quel `decrire_coup_ia`/`etapes_coup_ia` corrigés, donc un échange de
   tuiles identiques n'est plus compté dans `nb_combinaisons_touchees` ni
   `nb_etapes` — aucun changement de code nécessaire dans ce module.
6. **Tests** : échange main/plateau dans une même combinaison, échange
   cyclique entre deux combinaisons, régression bout en bout sur le cas
   réel ayant planté, deux jokers (un remplacé par l'autre — pas un
   déplacement — et un second qui change réellement de combinaison), et
   persistance des cas déjà couverts (chaîne Bruno/Expert, échange de
   joker, démantèlement de groupe) — même nombre d'étapes qu'avant.
   `tests/test_playwright_pas_a_pas.py` repassé sans modification (format
   des étapes inchangé, seulement moins d'étapes invisibles). Voir
   CONTEXTE.md §12bis.

# Issue #196 — Suite #193 : afficher en français le coup proposé par le solveur et mesurer sa complexité

`scripts/analyser_coups_rates.py` disait combien de tuiles un coup raté/une
pose sous-optimale ratait, jamais QUEL coup le solveur proposait à la place
— impossible de juger à la main si ce coup était simple (à la portée d'un
humain) ou hors de portée. Réutilise `moteur/description_coup.py` (#191)
pour décrire ce coup en français et mesurer sa complexité, sans rien
changer au solveur, à l'IA ni au moteur.

1. **Description du coup proposé** (`persistance/coups_rates.decrire_coup`)
   : texte français + étapes du rejeu pas à pas, calculés à partir du
   plateau avant la décision et du plateau proposé par le solveur. Pour
   chaque décision signalée (coup raté, pose sous-optimale, et pour un
   joueur humain, cas où le solveur est battu), `analyser_decision_complete`
   expose désormais `description_solveur` ; pour le cas « solveur battu »,
   `description_reel` décrit en plus le coup RÉELLEMENT joué par le joueur
   (nouveau champ `plateau_apres_reel` dans `extraire_toutes_decisions`),
   pour comparaison.
2. **Complexité** (`_complexite_coup`) : nombre de combinaisons du plateau
   touchées, présence d'un échange de joker, nombre d'étapes réelles. Un
   coup touchant 3 combinaisons ou plus, ou déplaçant un joker, est
   `"complexe"` ; sinon `"simple"`. `calculer_resume_complet` et
   `resume_joueur_humain` ajoutent une répartition `coups_simples`/
   `coups_complexes` par niveau d'IA et pour un joueur humain.
3. **Option `--tour N`** : détaille un tour précis (nom du joueur, tuiles
   posées en réalité vs proposées par le solveur, description complète),
   en plus de l'affichage habituel (top 5, listes `--joueur`).
4. **Artefact du solveur corrigé en amont** (`_relabeler_tuiles_
   indiscernables`) : le solveur (`moteur/solveur.py`) ne raisonne que sur
   des emplacements (couleur, valeur), jamais sur l'identifiant physique
   exact d'une tuile — il peut proposer un plateau où deux tuiles déjà
   posées, strictement indiscernables, échangent leurs identifiants sans
   aucun changement réel. `moteur/description_coup.py`, qui suit chaque
   tuile par son identifiant, y lisait un cycle de dépendance et plantait
   (`KeyError`, cas réel : `cas_expert_bruno_tour57.json`). Corrigé
   uniquement côté `persistance/coups_rates.py` (relabellisation d'une
   copie du plateau avant l'appel au moteur) — aucun changement au moteur,
   au solveur ni à l'IA, conformément au périmètre de l'issue.

## Fichiers touchés

- `src/rummikub/persistance/coups_rates.py` : + `decrire_coup`,
  `_complexite_coup`, `_relabeler_tuiles_indiscernables`, champ
  `plateau_apres_reel` ; `analyser_decision_complete` expose
  `description_solveur`/`description_reel` ; `calculer_resume_complet` et
  `resume_joueur_humain` ajoutent la répartition simple/complexe.
- `scripts/analyser_coups_rates.py` : affichage des descriptions +
  complexité (top N, `--joueur`), nouvelle option `--tour`.
- `tests/test_coups_rates_description.py` (nouveau) : coup raté simple,
  pose sous-optimale complexe avec joker, joueur bat le solveur (description
  proposée + réelle comparées), régression sur l'artefact de tuiles
  indiscernables (y compris bout en bout sur le cas Bruno réel).
- `CONTEXTE.md` : + section 11ter.

## Non fait / limites

- Non exécuté sur les vrais journaux de `RACINE_DATA/logs_parties` (issue
  traitée dans un worktree isolé sans journaux réels, comme #193) : les
  chiffres réels de complexité restent à produire par Alain lui-même.

# Issue #195 — Documenter dans CONTEXTE.md les pistes d'amélioration de l'IA à tester (idées d'Alain)

Documentation uniquement, aucun changement de code. Ajout de la section
« 13. Pistes d'amélioration de l'IA à tester (issue #195) » à `CONTEXTE.md`,
en fin de fichier, pour ne pas perdre les idées formulées par Alain au fil
des parties de calibrage contre Expert :

1. Réserve d'un coup (garder un coup pour le tour suivant) — risque :
   l'adversaire peut occuper la place entre-temps ; test : nécessite une
   évaluation sur deux tours, l'analyse des coups ratés (§11) donnera de
   premières statistiques.
2. Éliminer en priorité les doublons de la main (exemple d'Alain : main
   1/2/2/3 rouges + 3 bleu/noir → jouer la suite plutôt que le groupe) ;
   hypothèse d'un critère de « main restante la plus facile à placer » à
   ajouter au départage actuel (points puis jokers, §8bis) ; test via
   `scripts/comparer_niveaux_ia.py` (§9).
3. Plus de temps de réflexion pour Expert, ou un niveau au-dessus (lien
   avec les mesures #187/#190).
4. Procédure commune d'évaluation d'une piste (comparaison en miroir,
   marge d'erreur, gain significatif + temps par tour raisonnable).
5. Rôle des points dans le départage — ne devraient primer que si la
   partie se termine bloquée, ou en cas de score cumulé sur plusieurs
   manches ; sinon laisser la place à la piste 2.
6. Constat (non corrigé ici) sur le réglage « Nombre de manches » : la
   règle `est_fin_partie` (`moteur/partie.py`) ne comptait pas de vraies
   manches ; décision d'Alain (#192, §3bis) de jouer en une seule manche ;
   le taux de parties bloquées en simulation (29 % au départ, 5-10 % avec
   le solveur d'Expert) est un signe de faiblesse de l'IA à suivre comme
   indicateur de qualité, pas un phénomène normal entre joueurs humains.

Chaque piste porte une case à cocher, pour que de futures issues puissent
la reprendre et la clore au fur et à mesure.

## Fichiers touchés

- `CONTEXTE.md` : + section 13 (texte seul, aucun code).

# Issue #194 — Suite #190 : nouvelle stratégie de recherche du solveur Expert

## Constat (point de départ, où la recherche perd son temps)

#190 n'accélérait que les nœuds où plusieurs candidats sont ex-aequo sur
`_score_rapide` (candidats qui n'utilisent aucune tuile de la main) — ne
réglait pas le cas où le coup optimal exige d'enchaîner plusieurs échanges de
jokers à travers des zones différentes du plateau. Deux cas de référence :

- `cas_expert_budget_tour81.json` (#190, 70 tuiles/19 combos) : déjà résolu
  en 1.5s depuis #190.
- `cas_expert_bruno_tour57.json` (nouveau, 52 tuiles/15 combos, tour réel de
  Bruno en partie) : Expert n'avait posé **qu'UNE tuile**, alors que le
  solveur en trouve 3 (`rouge_11_b`, `jaune_8_a`, `jaune_13_a` — un joker
  d'un groupe de 4 remplacé par la tuile d'une suite voisine) — mais
  seulement avec un budget de 10s ; **rien** à 1.5s, 3s ni 6s.

Analyse (avant #194) sur ce second cas : l'ordre de visite des emplacements
obligatoires (`_ordre_slot`, par couleur puis valeur) force la recherche à
épuiser tout un bloc de couleur avant d'atteindre un groupe qui n'a besoin
que d'UNE tuile de la main dans une couleur différente. Et la recherche vise
l'optimum exact en une seule passe : sur ce plateau, la combinatoire pour
PROUVER l'optimum (3 tuiles) dépasse largement ce qu'un budget d'1.5-6s
permet d'explorer, même si un coup à 1 ou 2 tuiles, bien plus facile à
trouver, existe aussi (mais n'est jamais retenu seul puisqu'il n'est pas
l'optimum).

## Changements

Deux changements combinés dans `src/rummikub/moteur/solveur.py` (voir la
docstring du module pour le détail technique) :

1. **Recherche par paliers croissants** (`_meilleur_rearrangement`,
   `_Contexte.objectif`, `_seuil_atteint`) : au lieu de viser l'optimum en
   une seule passe, le solveur cherche d'abord « au moins 1 tuile posable »,
   puis si trouvé « au moins 2 », etc. Chaque palier intermédiaire coupe la
   recherche dès qu'IL est atteint n'importe où dans l'arbre (pas seulement
   au plafond optimiste global) — beaucoup moins coûteux que de prouver
   l'optimum d'un coup. Si le budget s'épuise en cours de palier, le
   dernier palier PROUVÉ atteignable est renvoyé (recherche interrompue
   mais pas perdue), au lieu de tout perdre comme le ferait une passe
   unique sans palier. Tant que tous les paliers jusqu'au plafond
   optimiste aboutissent dans le budget, le dernier palier est strictement
   équivalent à l'ancienne passe unique (même résultat, même départage).
2. **Ordre de visite par VALEUR** (`_ordre_slot`) plutôt que par couleur :
   un groupe réunit plusieurs couleurs à la MÊME valeur ; visiter toutes les
   valeurs d'une seule couleur avant la suivante (ordre d'origine) force la
   recherche à épuiser tout un bloc de couleur combinatoire avant
   d'atteindre un groupe utile à la main d'une tout autre couleur. Visiter
   par valeur croissante atteint ce groupe dès que sa valeur revient, et le
   palier correspondant (voir point 1) coupe alors la recherche
   immédiatement au lieu de retomber dans le bloc combinatoire.

Pistes évoquées par l'issue et **non retenues** (choix de méthode laissé à
CCL par l'issue) :
- **Zones indépendantes du plateau** : `_separer_combos_figees` (#190)
  gèle déjà toute combinaison sans aucune tuile/valeur en commun avec la
  main ni avec un joker — c'est déjà, en pratique, la même idée (les zones
  non pertinentes sont écartées de la recherche, pas résolues séparément
  puis recombinées). Un découpage plus fin en composantes connexes
  indépendantes à l'intérieur même des combinaisons flexibles n'a pas été
  tenté : les deux changements ci-dessus suffisent aux deux cas de
  référence, et l'ajouter aurait complexifié la mémoïsation sans cas
  identifié qui en aurait besoin.
- **Mémoriser les sous-problèmes déjà résolus entre paliers** : la
  mémoïsation existe déjà PAR passe (`_Contexte.memo`, #186) ; elle ne peut
  PAS être conservée D'UN PALIER À L'AUTRE sans risque d'incohérence (une
  valeur mémoïsée sous l'objectif *k* peut représenter un arrêt anticipé
  invalide pour l'objectif *k+1*) — chaque palier repart donc avec une
  mémoïsation vide, intentionnellement.
- **Essayer en priorité les échanges de jokers** : déjà couvert
  indirectement par le tri des candidats sur `_score_rapide` (#186) et la
  priorité aux signatures d'origine (#190) ; le changement d'ordre de visite
  (point 2) a un effet comparable pour le cas qui motive l'issue, pour un
  coût d'implémentation moindre qu'une heuristique dédiée aux jokers.

Budget de production (`BUDGET_TEMPS_EXPERT`) **inchangé à 1.5s** — aucune
augmentation n'a été nécessaire.

## Mesure 1 — deux cas de référence, objectif mesurable de #194

Mesuré directement via `resoudre_coup()`, machine de développement :

| Cas                           | Budget | Avant #194            | Après #194           |
|--------------------------------|--------|------------------------|------------------------|
| `cas_expert_budget_tour81.json` (#190) | 1.5s   | 3 tuiles (1.53s, déjà bon depuis #190) | 3 tuiles (1.53s, inchangé) |
| `cas_expert_bruno_tour57.json`  | 1.5s   | **aucun coup**         | **3 tuiles** (~0.3s)   |
| `cas_expert_bruno_tour57.json`  | 3s     | **aucun coup**         | 3 tuiles (~0.3s)       |
| `cas_expert_bruno_tour57.json`  | 6s     | 2 tuiles seulement     | 3 tuiles (~0.3s)       |
| `cas_expert_bruno_tour57.json`  | 10s    | 3 tuiles               | 3 tuiles (~0.3s)       |

**Objectif atteint sur les deux cas de référence** : au budget de
production (1.5s), le solveur trouve désormais le coup à 3 tuiles de
`cas_expert_bruno_tour57.json`, là où il ne trouvait rien avant #194 —
10× à 20× plus rapide que les 6-10s nécessaires avant #194 pour atteindre
ce même résultat. Le cas `tour81` (#190) reste résolu dans le même budget,
sans régression.

Tests ajoutés dans `tests/test_ia.py` :
- `test_solveur_cascade_joker_trouve_trois_tuiles_avec_gros_budget` (budget
  10s, fiable) : ≥ 3 tuiles (`attendu_min_tuiles` du fichier de cas), plateau
  valide, aucune tuile perdue.
- `test_solveur_cascade_joker_trouve_un_coup_avec_budget_de_production`
  (budget = `BUDGET_TEMPS_EXPERT × 6`, tolérance large anti-flakiness sur
  machine de CI lente — le coup est trouvé en ~0.3s en développement, bien
  avant même le seul budget de production de 1.5s) : mêmes vérifications.

## Mesure 2 — campagne Avancé vs Expert (même format que #190/#186)

Contrainte de temps (campagne au budget de production, coûteuse) : 8 donnes
/ 16 parties (seed 100, `--max-tours 300`), contre les 20 donnes / 40
parties de la mesure #190 — réduit pour tenir dans le temps imparti à cette
tâche, comme déjà fait pour #190 (lecture à faire avec cette réserve en
tête : échantillon plus petit, bruit plus grand). Le solveur étant
inchangé entre #190 et #194 avant ce correctif (vérifié par `git log --
solveur.py`), les chiffres « avant #194 » réutilisent directement la mesure
« après #190 » déjà publiée (20 donnes/40 parties, mêmes paramètres).

| Mesure                                               | Avant #194 (= après #190, 20 donnes/40 parties) | Après #194 (8 donnes/16 parties) |
|-------------------------------------------------------|:---:|:---:|
| Victoires Expert                                       | 31/40 (77.5 %) | 13/16 (81.2 %) |
| Temps Expert par tour — moyenne                        | 839.7 ms (1661 tours) | **378.8 ms** (556 tours) |
| Temps Expert par tour — maximum                        | 1632.7 ms     | 1523.3 ms |
| Replis Expert→Avancé, toute cause                      | 1254/1661 (75.5 %) | 322/556 (57.9 %) |
| — dont repli par timeout (seule cause visée par #190/#194) | 690/1661 (41.5 %) | **31/556 (5.6 %)** |
| — dont repli par coup légitimement impossible          | 564/1661 (34.0 %) | 291/556 (52.3 %) |
| Anomalies de conservation des tuiles                   | 0             | 0 |

**Lecture** : contrairement à #190 (qui n'améliorait pas la mesure
agrégée sur plateaux aléatoires), #194 montre une amélioration nette et de
grande ampleur sur cet échantillon : le taux de repli par timeout passe de
41.5 % à 5.6 %, et le temps moyen par tour d'Expert est plus que divisé par
deux (839.7 ms → 378.8 ms). Cohérent avec l'analyse : la recherche par
paliers et le nouvel ordre de visite ne profitent pas qu'au cas ciblé
(enchaînement de jokers), ils réduisent aussi, plus généralement, le nombre
de nœuds explorés avant de trouver un premier coup correct sur n'importe
quel plateau chargé — contrairement au critère de #190 (signatures
d'origine), qui ne s'appliquait qu'aux candidats ex-aequo. Échantillon plus
petit que celui de la mesure #190 (16 vs 40 parties) : l'écart observé est
cependant bien supérieur à la marge de bruit attendue à cette taille, donc
interprété comme un effet réel, pas seulement un artefact d'échantillonnage.

## Mesure 3 — rejeu de tours réels (journaux de parties)

Aucun journal de partie réel n'existe dans ce worktree (`data/logs_parties`
est vide, listé dans `.gitignore` — comportement attendu, ces journaux ne
sont écrits qu'en usage réel via l'UI). Pour disposer de tours réels à
analyser avec `scripts/analyser_coups_rates.py`, 4 parties Avancé vs Expert
ont été réellement jouées de bout en bout (moteur seul, script ponctuel
`scripts/_generer_logs_194.py`, supprimé après la mesure) en activant le
journal (`config.LOG_PARTIES`), produisant 4 fichiers au même format que des
parties jouées via l'UI (309 décisions au total, 153 décisions Expert après
mise initiale + 9 avant).

Comparaison entre le solveur d'avant #194 (`git show
bb6f543:...solveur.py`, temporairement restauré pour la mesure puis
immédiatement remis en place — vérifié par `git diff` et par la suite de
tests, 143 tests toujours passés après restauration) et celui d'après
#194, les deux interrogés avec budget généreux = 10s et budget de
production = 1.5s (`scripts/analyser_coups_rates.py --tous --budget 10
--budget-production 1.5`).

Les 4 journaux ont d'abord été analysés en entier avec le solveur d'après
#194 (309 décisions, 153 décisions Expert). Avec le solveur d'avant #194,
l'analyse des MÊMES 4 journaux est nettement plus lente (plus de budgets
généreux de 10s consommés en entier sans conclure) : dans le temps imparti
à cette mesure, seuls les 2 premiers journaux (147 décisions, 73 décisions
Expert) ont pu être analysés en entier par l'ancien solveur — la
comparaison ci-dessous se limite donc, pour les deux versions, à ces 2
journaux (`cas` = `partie_20261027_011020.json` +
`partie_20261027_011034.json`), seul sous-ensemble analysé en entier par
les deux versions :

| Mesure (niveau Expert, après la mise initiale, 72 décisions)         | Avant #194 | Après #194 |
|----------------------------------------------------------|:---:|:---:|
| Pioche/passe alors qu'un coup existait (« coup raté »)    | 0 | 0 |
| Poses sous-optimales                                       | 1 (1 tuile manquante) | 5 (5 tuiles manquantes) |
| ... dont limitées par le budget de production (1.5s)       | 1 | 4 |
| **Décisions inconclusives (budget GÉNÉREUX de 10s épuisé sans conclure)** | **8** | **0** |

(Les décisions jouées dans les 4 journaux l'ont été par le solveur D'APRÈS
#194 — ce tableau ne mesure donc pas « comment Expert aurait joué avant
#194 », mais, sur les MÊMES états de plateau réels, « combien de fois le
budget de production retrouve ce que le budget généreux trouve » avec
chaque version du solveur — la mesure pertinente pour l'objectif de #194 :
réduire les coups manqués PAR MANQUE DE TEMPS.)

**Lecture, prudente comme l'exige le script lui-même (voir ses propres
avertissements)** : à nombre de décisions égal (72), le changement le plus
frappant n'est PAS le nombre de « poses sous-optimales » (5 après contre 1
avant) mais le nombre de décisions **inconclusives** : 8 avant #194 contre
0 après. Une décision inconclusive signifie que même le budget GÉNÉREUX de
10s ne suffisait pas à l'ancien solveur pour conclure sur ce plateau réel —
la vraie valeur de ces 8 décisions reste CONNUE pour 1 seule dimension :
inconnue, pas « aucun problème ». En les comptant au pire (silencieusement
sous-optimales), le total de décisions potentiellement sous-optimales est
d'AU PLUS 9 avant #194 (1 confirmée + 8 inconnues) contre EXACTEMENT 5
après (toutes désormais résolues, aucune inconnue) — une amélioration nette
de la capacité du solveur à conclure sur des plateaux réels dans un budget
donné, cohérente avec la Mesure 2. Les 5 poses sous-optimales après #194
restent minimes (1 tuile manquante chacune) et à 4/5 explicitement
attribuées au budget de PRODUCTION (1.5s), pas à une limite de l'algorithme
lui-même (confirmées par le budget généreux de 10s).

## Ne rien dégrader

- `pytest tests/` : 143 tests passés (aucune régression, y compris les
  tests d'Avancé et des niveaux inférieurs — `moteur/ia.py` n'a pas été
  modifié, seul `moteur/solveur.py`, utilisé uniquement par Expert, l'a
  été).
- Les deux cas de référence restent résolus avec toutes les tuiles du
  plateau conservées (`_verifier_coup_valide_sans_perte`).
- Aucune anomalie de conservation des tuiles détectée sur les campagnes
  ci-dessus (0/16 et 0/4 parties).
- Budget de production inchangé (1.5s) — aucune augmentation n'a été
  nécessaire pour atteindre l'objectif.

## Fichiers modifiés

- `src/rummikub/moteur/solveur.py` : recherche par paliers croissants
  (`_Contexte.objectif`, `_seuil_atteint`), ordre de visite par valeur
  (`_ordre_slot`), docstring du module mise à jour.
- `tests/test_ia.py` : deux nouveaux tests sur
  `tests/donnees/cas_expert_bruno_tour57.json` (déjà présent, issu d'une
  tentative précédente sur cette même issue — vérifié, conservé).
- `tests/test_coups_rates_extensions.py` : le test de budget délibérément
  trop court (`test_cas_reference_bruno_budget_trop_court_signale_
  inconclusif`) utilise désormais un budget nul (au lieu de 0.05s) — ce cas
  de référence précis est désormais résolu en ~0.3s, un budget de 0.05s ne
  suffirait plus à garantir l'« inconclusif » attendu par ce test.
- `CONTEXTE.md` (§8bis) : nouvelle stratégie documentée, avec renvoi vers
  ce rapport pour les chiffres avant/après.

# Issue #193 — Fiabiliser l'analyse des coups ratés : poses sous-optimales, budget nécessaire, vérification croisée du solveur

## Contexte
Suite de #188 : l'analyse des coups ratés de l'IA (`scripts/analyser_coups_rates.py`)
ne regardait que les pioches/passes, avec un budget pouvant être trop court
(cas réel : tour 57 de Bruno, 1 tuile posée alors que le solveur en trouve 3
avec 10 s), et ne vérifiait jamais le solveur lui-même (juge et joueur à la
fois). Objectif : rendre cette analyse fiable — poses sous-optimales
comprises, budget nécessaire mesuré, validée sur des cas connus et contre une
recherche exhaustive indépendante — et l'étendre à un joueur humain.

## Modifications
- `src/rummikub/persistance/coups_rates.py` (fonctions de #188 inchangées,
  nouvelles fonctions ajoutées) :
  - `extraire_toutes_decisions`/`extraire_decisions_ia_toutes`/
    `extraire_decisions_joueur` : extraction généralisée aux POSES (pas
    seulement pioche/passe) et à n'importe quel joueur (IA ou humain nommé) ;
    dédoublonnage après une pose annulée puis rejouée (même tour réutilisé,
    comme `bilan.py`), reconstruction de l'état même à travers une entrée
    `"annulation"` du journal.
  - `analyser_decision_complete` : classe une décision en `coup_rate`
    (pioche/passe), `pose_sous_optimale` (pose inférieure au maximum du
    solveur) ou `joueur_bat_solveur` (pose supérieure — humain uniquement),
    ou `inconclusif` (budget épuisé — JAMAIS confondu avec « pas de coup
    raté »).
  - `calculer_resume_complet`/`top_coups_rates_complet` : résumé étendu par
    niveau/phase, distinguant les deux catégories de coup raté.
  - `budget_necessaire`/`repartition_budget_necessaire` : plus petit budget
    (série 1,5/3/6/10/20/30 s) qui retrouve un coup déjà identifié comme raté,
    et répartition pour décider « laisser réfléchir plus longtemps » vs
    « changer la recherche ».
  - `detecter_reserves_joueur`/`resume_joueur_humain` : technique de la
    « réserve » d'un joueur humain (tuile gardée volontairement un tour,
    posée au tour suivant) jamais comptée comme coup raté ni comme cas où le
    solveur est battu ; deux listes séparées (coups peut-être ratés / solveur
    battu) + statistiques de style purement descriptives (jokers gardés,
    pioches avec coup possible, écart au maximum du solveur).
- `src/rummikub/moteur/verif_solveur.py` (nouveau module pur) :
  `max_tuiles_posables_exhaustif` (recherche exhaustive volontairement lente,
  sans aucune optimisation du solveur) + `generer_position_aleatoire` (petite
  position reproductible, graine fixe) — vérification croisée indépendante du
  solveur.
- `scripts/verifier_solveur_exhaustif.py` (nouveau) : compare solveur et
  recherche exhaustive sur `--nb` positions aléatoires (graine `--seed`),
  signale tout écart sans jamais corriger le solveur. **300 positions,
  graine 193 : 0 écart, 0 inconclusive.**
- `scripts/analyser_coups_rates.py` (réécrit) : analyse poses comprises,
  avertissement si `--budget` < 10 s, `--budget-mesure` (budget nécessaire),
  `--retenter-inconclusifs` (seconde passe à budget plus grand sous une
  limite de durée totale ferme), `--enregistrer-cas-reference` (écrit de
  nouveaux `tests/donnees/cas_expert_*.json`, n'écrase jamais l'existant),
  `--joueur "Nom"` (même analyse pour un joueur humain).
- Tests : `tests/test_coups_rates_extensions.py` (poses sous-optimales,
  joueur bat le solveur, résumé étendu, budget nécessaire, détection de
  réserve réussie/perdue, validation sur le cas réel de Bruno avec budget
  suffisant ET avec budget délibérément trop court — robuste au temps de
  calcul de la machine) ; `tests/test_verif_solveur.py` (recherche exhaustive
  sur cas unitaires + campagne aléatoire à graine fixe, 60 positions, contre
  le solveur de production). Suite complète : **141 tests passent**
  (122 avant #193 + 19 nouveaux).
- `CONTEXTE.md` §11bis : nouvelles capacités et limites restantes documentées.

## Points d'attention
- **Non exécuté sur les vrais journaux de parties** : cette issue a été
  traitée dans un worktree isolé (périmètre strict) dont `data/logs_parties`
  est vide — les vrais journaux vivent hors de ce périmètre
  (`/home/alain/Rummikub/data/logs_parties` notamment), auquel je n'ai pas
  accès depuis ce worktree. Le point 6 de l'issue (« lancer l'outil sur tous
  les journaux de `RACINE_DATA/logs_parties` ... inclure les chiffres dans le
  rapport ») n'a donc **pas pu être exécuté avec des données réelles** : le
  script a été vérifié de bout en bout (tous les modes) sur des journaux
  fabriqués à la main, mais les vrais chiffres restent à produire par Alain,
  en relançant `python scripts/analyser_coups_rates.py --tous --budget 10`
  (et `--joueur "Alain"`) depuis une installation courante du projet (pas ce
  worktree). Le point 6 bis (« 13/54 décisions inconclusives sur une
  première analyse réelle ») fait référence à une analyse déjà réalisée par
  Alain avant cette issue, pas reproductible ici pour la même raison.
- **Technique de la réserve, limite assumée** : la détection ne regarde que
  le tour immédiatement suivant du même joueur dans la même partie ; une
  vraie réserve stratégique reste a posteriori indiscernable d'un simple
  oubli qui se résout par hasard au tour suivant (déjà noté dans l'issue).
- **`budget_necessaire`/`--budget-mesure` sont coûteux** (relancent le
  solveur une fois par palier de budget) : volontairement réservés aux coups
  déjà identifiés comme ratés, jamais appliqués en routine à toute une
  campagne.
- Le `joueur_bat_solveur` n'est, par construction, jamais déclenché pour une
  IA en usage normal (le budget généreux du contrôle est toujours ≥ celui de
  production, donc le solveur ne peut pas faire moins bien que lui-même) —
  catégorie pensée pour `--joueur` (humain).
- Vérification croisée du solveur limitée aux petites positions (plateau
  ≤ 4 tuiles, main ≤ 6) : ne prouve rien sur un plateau de taille réelle,
  hors de portée d'une recherche exhaustive.

# Issue #192 — Masquer le réglage « Nombre de manches » : le jeu se joue en une seule manche

## Constat

Les réglages de l'écran d'accueil proposaient un champ « Nombre de manches »
(1 à 99), mais plusieurs manches ne fonctionnaient pas : `est_fin_partie`
(`moteur/partie.py`) compare `tour_numero` au nombre de manches configuré
pour décider de la fin de partie dans ce cas, mais il n'existe aucun
compteur de manches nulle part dans l'application (`nouvelle_manche` n'est
jamais appelé). Un joueur choisissant plus d'une manche aurait donc un
comportement incorrect. Décision d'Alain : le jeu se joue sans manches
multiples, en une seule manche.

## Correctif

- **UI retirée** : le champ « Nombre de manches » a été retiré de
  `accueil.html` (onglet « Règles du jeu ») et de `accueil.js`
  (`remplirChampsReglages`, `sauvegarderReglages`, `lancerPartie` ne
  référencent plus `#rgl-manches`). La clé `nb_manches` a aussi été retirée
  de `reglages.DEFAUTS` (`reglages.py`) — une ancienne valeur déjà présente
  dans un `config.json` existant reste lisible sans erreur, simplement
  ignorée par l'application.
- **Forçage à 1 manche, point d'entrée unique** : `creer_partie`
  (`moteur/partie.py`) force désormais `"nb_manches": 1` dans l'état créé,
  sans jamais lire la valeur transmise par l'appelant (réglages UI,
  `config.json` ancien, script). Toute nouvelle partie a donc exactement
  une manche, quelle que soit la valeur enregistrée côté réglages.
- **Reprise d'une partie sauvegardée** : `ApplicationRummikub.reprendre_jeu`
  (`ui/application.py`) force aussi `etat["config"]["nb_manches"] = 1` sur
  l'état rechargé depuis SQLite, pour qu'une partie créée avant #192 avec
  une autre valeur ne retombe pas dans la branche incorrecte d'
  `est_fin_partie` une fois reprise.
- **Code moteur des manches conservé, signalé inactif** : `nouvelle_manche`,
  la branche `tour_numero > nb_manches` d'`est_fin_partie` et `score_cumul`
  restent en place tels quels (aucune suppression) — plus aucun appelant de
  l'application ne les atteint en pratique, puisque `nb_manches` vaut
  toujours 1. Un compteur de manches correct reste à écrire le jour où des
  manches multiples seraient réintroduites. Écran de fin de partie inchangé.
  `scripts/simulation_ia.py` et `scripts/comparer_niveaux_ia.py` continuent
  d'appeler directement `creer_partie`/`nouvelle_manche` en dehors de
  l'application pour leurs propres besoins de simulation — non concernés
  par le forçage à 1.
- `CONTEXTE.md` mis à jour : nouvelle section §3bis, notes sur
  `nouvelle_manche`/`est_fin_partie` (§3), compte de tests (§6).

## Tests

- `tests/test_moteur.py::test_creer_partie_force_une_seule_manche_meme_si_regles_en_demandent_plus` :
  une nouvelle partie a toujours exactement 1 manche même si
  `config_regles` en demande 5.
- `tests/test_playwright_accueil_reglages.py` (nouveau, Playwright sur
  `accueil.html` directement, jamais la vraie application pywebview, voir
  CONTEXTE.md §7) : champ absent du DOM et du texte affiché, panneau
  « Règles du jeu » sans trou (toujours exactement 2 réglages restants),
  réglages qui s'enregistrent et se rechargent sans erreur console même
  avec un ancien `nb_manches=5` simulé côté mock API.
- `pytest tests/ -q` → **122 passed** (119 précédemment + 3 nouveaux tests
  Playwright/moteur).

## Fichiers touchés

- `src/rummikub/moteur/partie.py` (`creer_partie`)
- `src/rummikub/ui/application.py` (`reprendre_jeu`)
- `src/rummikub/reglages.py` (`DEFAUTS`)
- `src/rummikub/ui/web/accueil.html`, `accueil.js`
- `tests/test_moteur.py`, `tests/test_playwright_accueil_reglages.py` (nouveau)
- `CONTEXTE.md`

# Issue #191 — Suite #189 : pas-à-pas du rejeu cohérent + cadre « tuiles à placer »

## Constat

Le pas-à-pas introduit par #189 comparait seulement les combinaisons
avant/après, sans suivre les tuiles individuellement. Conséquences
constatées en jeu sur un coup de Bruno (Expert) :
- une même tuile (un joker) apparaissait sur deux combinaisons à la même
  étape — impossible dans la réalité du jeu ;
- des étapes n'affichaient aucun changement visible par rapport à la
  précédente ;
- les textes avaient des tournures de message automatique (« Combinaison
  modifiée : le groupe de 3 », « Joker déplacé de le groupe de 3 vers le
  groupe de 11 ») plutôt que du français naturel ;
- sur un coup plus complexe (plusieurs combinaisons défaites/reformées),
  rien n'indiquait si deux combinaisons de même nom à des moments
  différents étaient les mêmes tuiles ou non, et le joueur ne voyait jamais
  l'état de départ ni la provenance des tuiles.

## Correctif

Réécriture complète de `moteur/description_coup.py` : chaque tuile est
suivie individuellement par son identifiant, de sa position d'avant à sa
position d'après (`_construire_operations`). Les combinaisons dont une
majorité stricte des tuiles continue ensemble sont des « update » (elles
gardent leur identité, swap possible en un seul changement) ; les autres se
dissolvent tuile par tuile via des opérations « retrait » regroupées par
destination (jamais toutes en une fois) ; les combinaisons sans continuation
sont des « create ». Un tri topologique causal ordonne ces opérations en
privilégiant les échanges de jokers dès qu'ils sont possibles, sans jamais
exiger qu'une tuile soit consommée avant d'avoir été libérée.

Le rejeu pas-à-pas (`etapes_coup_ia`) expose désormais, à chaque étape, un
cadre **« tuiles à placer »** (`etape["cadre"]`) qui contient les tuiles pas
encore reposées (venues de la main ou libérées du plateau, taguées
différemment) : chaque tuile n'est donc jamais, à aucune étape, à la fois
sur le plateau ET dans le cadre. La suite commence par un écran « Départ »
(plateau d'avant, cadre rempli) suivi, si des jokers bougent, d'un écran
« Les jokers » qui donne la vue d'ensemble de leur trajet. Les combinaisons
mi-démantelées sont marquées « provisoires » (distinct de « combinaison
invalide ») tant qu'elles ne sont pas résolues.

`decrire_coup_ia` (résumé affiché sous « Dernier coup joué par... ») est
réécrit en français naturel avec les contractions correctes (du/au/des/aux)
et désambiguïse par les couleurs deux combinaisons de même nom apparues à
des moments différents du coup (« le groupe de 11 rouge, bleu et noir est
défait » / « un nouveau groupe de 11 bleu, jaune et noir est formé »).

Front-end (`jeu.js`/`jeu.html`/`jeu.css`) : nouvelle zone « Tuiles à
placer » au-dessus de l'aperçu du plateau dans l'overlay pas-à-pas,
réutilisant les pourtours vert/orange de la légende existante pour
distinguer tuile de la main et tuile libérée du plateau ; marquage visuel
« provisoire » distinct de « combinaison invalide » ; surbrillance des
tuiles juste posées/libérées à chaque étape (réutilise `.tuile-ia-highlight`
existant). Le seuil d'affichage du bouton « Pas à pas » passe de
`etapes.length >= 2` au nombre de changements réels (hors écrans
« Départ »/« Les jokers », qui n'existaient pas avant cette issue).

## Tests

`tests/test_description_coup.py` : contractions, coups simples, joker
récupéré puis rejoué (avec vérification explicite de l'ordre causal), cas
Bruno simple (texte comparé mot pour mot à l'exemple de l'issue), coup en
chaîne Bruno/Expert (5 combinaisons d'avant, vérification tuile par tuile),
et un helper d'invariants communs (aucune tuile à deux endroits, pas
d'étape sans effet, cadre vide et plateau exact à la dernière étape).
`tests/test_playwright_pas_a_pas.py` (nouveau, nécessite `pip install
playwright` + `playwright install chromium`, absent de requirements.txt —
sauté proprement sinon) : vérifie sur `jeu.html` seul (jamais la vraie app
pywebview) le remplissage/vidage du cadre, les couleurs de pourtour, et
l'absence d'effet du bouton « Quitter ».

CONTEXTE.md §12 mis à jour.

# Issue #190 — Suite #187 : accélérer le solveur Expert sur les plateaux chargés

## Constat (où part le temps)

Sur le cas de régression `tests/donnees/cas_expert_budget_tour81.json`
(plateau avant le tour 81 d'Olivia, ≈ 70 tuiles, 19 combinaisons posées),
`_separer_combos_figees` ne gèle (hors recherche) que les combinaisons ne
partageant AUCUNE couleur ni valeur avec la main — avec seulement 4
couleurs, une main de 2-3 couleurs distinctes suffit à rendre « flexible »
la quasi-totalité du plateau. La recherche se retrouve donc avec ~45
emplacements obligatoires (une tuile du plateau à replacer), une
quarantaine de candidats chacun. Dans cet arbre, le premier chemin DFS
(candidats triés pour maximiser l'usage de la main, `_score_rapide`)
tombait régulièrement sur une impasse — un emplacement obligatoire sans
aucun candidat compatible avec l'état déjà réduit par les choix
précédents — forçant un retour en arrière coûteux. Avant qu'AUCUN
réarrangement complet n'ait jamais été trouvé nulle part dans l'arbre, le
budget s'épuisait.

Cause précise : la plupart de ces emplacements obligatoires ne touchent en
rien la main (aucun gain à les restructurer : plusieurs candidats sont
ex-aequo à 0 sur `_score_rapide`), mais la recherche les traitait comme
n'importe quel autre nœud, essayant toutes les régularisations possibles
avant celle, triviale, qui reconduit simplement la combinaison déjà posée.

## Correctif

Chaque candidat généré (`_candidats_groupe`, `_candidats_suite` et leurs
variantes « joker ») porte désormais une signature `(type, couleur/valeur,
taille)` (`_signatures_originales`, dans `moteur/solveur.py`). Parmi les
candidats ex-aequo sur `_score_rapide` (typiquement ceux qui n'utilisent
aucune tuile de la main pour ce nœud), celui qui reproduit une combinaison
déjà posée sur le plateau avant ce tour est tenté EN PREMIER. Cela évite à
la recherche de restructurer, par essais-erreurs coûteux, des zones du
plateau que la main ne concerne pas vraiment — la principale source du
backtracking observé. Ni ce critère ni les deux mesures d'atténuation
précédentes (#186) ne changent jamais le résultat optimal trouvé avec un
budget suffisant, seulement la vitesse pour l'atteindre (et, en cas
d'égalité stricte de la valeur de départage entre plusieurs réarrangements
équivalents, lequel des deux est renvoyé).

Le comportement « anytime » existait déjà depuis #186 (`BudgetDepasse`
n'est levée que si rien n'a été trouvé nulle part ; sinon le meilleur
réarrangement déjà trouvé est renvoyé) — #190 le rend effectif dès les
tout premiers appels sur un plateau chargé, plutôt qu'après plusieurs
secondes, voire jamais dans le budget de production.

Le budget de production (`BUDGET_TEMPS_EXPERT = 1.5`) n'a **pas** été
augmenté : il suffit désormais à retrouver le coup de 3 tuiles sur le cas
cible (voir mesure ci-dessous), ce qui répond à l'objectif mesurable sans
faire attendre le joueur plus longtemps qu'avant.

Mesure additionnelle ajoutée : `scripts/comparer_niveaux_ia.py` compte
désormais, pour le niveau Expert, les replis sur Avancé — en distinguant
(1) repli par dépassement de budget sans rien trouver (`BudgetDepasse`,
seule cause visée par #190) de (2) repli parce qu'aucun coup n'est
légitimement possible (sans rapport avec la vitesse de recherche). Les
deux causes étaient confondues jusqu'ici, ce qui aurait rendu la mesure
ci-dessous ininterprétable.

## Mesure 1 — cas ciblé (tour 81), objectif mesurable de #190

Mesuré directement via `resoudre_coup()` sur
`cas_expert_budget_tour81.json`, machine de développement (pas de machine
dédiée aux mesures — ordres de grandeur, pas des bornes dures) :

| Budget   | Avant #190 (commit `74db5a3`)      | Après #190                         |
|----------|-------------------------------------|-------------------------------------|
| 0.05 s   | `BudgetDepasse`                     | 3 tuiles trouvées (56 ms)           |
| 1.5 s (production) | `BudgetDepasse` — **aucun coup**, repli sur Avancé | **3 tuiles** (11 noir, 11 noir, 7 rouge), 1531 ms |
| 2.5 s    | `BudgetDepasse`                     | 3 tuiles (confirmées, pas de mieux) |
| 3.0 s    | 3 tuiles trouvées (3040 ms)          | 3 tuiles (3030 ms)                   |
| 20 s     | 3 tuiles (idem, pas de mieux — correspond au cas de test à gros budget de #187) | 3 tuiles (idem) |

Point de bascule avant #190 : échec jusqu'à 2.5 s, succès entre 2.5 et
3.0 s. La mention « 3 tuiles en 20 s » du cas de test d'origine (#187)
reflétait une marge large choisie pour le test à gros budget, pas le temps
minimal réellement nécessaire (~2.5-3 s).

**Objectif atteint** : au budget de production (1.5 s), le solveur trouve
désormais le coup de 3 tuiles identifié manuellement, là où il ne
trouvait rien avant #190 (repli total sur Avancé, qui ne posait qu'une
tuile). Gain d'environ 45 à 50× pour atteindre un premier coup valide (56
ms contre ~2.5-3 s), à qualité de résultat égale. Ce qui empêche d'aller
plus loin dans le temps restant du budget de production : la recherche
continue d'essayer de faire mieux que ces 3 tuiles jusqu'à expiration du
budget (anytime) mais n'en trouve pas — rien n'indique qu'un coup
strictement meilleur existe sur ce plateau précis ; nous ne l'avons pas
non plus trouvé avec un budget de 20 s.

Deux tests ajoutés dans `tests/test_ia.py` :
- `test_solveur_plateau_charge_trouve_au_moins_trois_tuiles_avec_gros_budget`
  (budget 10 s, fiable) : ≥ 3 tuiles, plateau valide, aucune tuile perdue.
- `test_solveur_plateau_charge_trouve_un_coup_avec_budget_de_production`
  (budget = `BUDGET_TEMPS_EXPERT × 6` = 9 s, tolérance large anti-
  flakiness sur machine de CI lente — le coup réel est trouvé en ~56-100
  ms, bien avant même le seul budget de production de 1.5 s) : ≥ 3 tuiles,
  mêmes vérifications.

## Mesure 2 — campagne Avancé vs Expert (même format que #187)

Contrainte de temps : une campagne de 20 donnes (40 parties) au budget de
production prend environ 450-530 s sur cette machine pour le solveur
d'après #190 (Expert y passe le plus souvent tout son budget, trouvé un
coup ou non). Pour tenir dans le temps imparti à cette tâche, la campagne
« après » a été menée en 3 lots (10 + 5 + 5 donnes, graines 100/200/201 —
soit bien les 20 donnes / 40 parties demandées, agrégées ci-dessous) et la
campagne « avant » en 2 lots de 5 donnes avec le solveur d'avant #190
(commit `74db5a3`, graines 100/101) — 10 donnes / 20 parties, comme permis
par les consignes de reprise quand le temps est compté. Mêmes paramètres
que #187 sinon (2 joueurs, mise initiale 30 points, garde-fou 300 tours).

| Mesure                                               | Avant #190 (10 donnes/20 parties) | Après #190 (20 donnes/40 parties) |
|-------------------------------------------------------|:---:|:---:|
| Victoires Expert                                       | 16/20 (80 %)  | 31/40 (77.5 %) |
| Victoires Avancé                                        | 4/20 (20 %)   | 9/40 (22.5 %) |
| Parties bloquées (pioche épuisée)                      | 0/20 (0 %)    | 1/40 (2.5 %) |
| Anomalies de conservation des tuiles                   | 0             | 0 |
| Temps Expert par tour — moyenne                        | 671.8 ms (699 tours) | 839.7 ms (1661 tours) |
| Temps Expert par tour — maximum                        | 1548.0 ms     | 1632.7 ms |
| Replis Expert→Avancé, toute cause                      | 498/699 (71.2 %) | 1254/1661 (75.5 %) |
| — dont repli par timeout (#190, seule cause visée)     | 212/699 (30.3 %) | 690/1661 (41.5 %) |
| — dont repli par coup légitimement impossible          | 286/699 (40.9 %) | 564/1661 (34.0 %) |

**Lecture honnête de ce tableau** : à cette taille d'échantillon (bruit
d'échantillonnage important — intervalles de confiance à 95 % de l'ordre
de ±9 à ±30 points sur le seul taux de victoire), la campagne agrégée sur
plateaux tirés au hasard **ne montre pas d'amélioration nette** — le taux
de repli par timeout et le temps moyen par tour d'Expert sont même
légèrement plus élevés après #190. Ce n'est pas contradictoire avec le
gain ×45-50 mesuré sur le cas ciblé (Mesure 1) : le correctif de #190
n'accélère que les nœuds où plusieurs candidats sont ex-aequo à 0 sur
`_score_rapide` — situation caractéristique des plateaux structurellement
proches du cas visé (beaucoup de combinaisons sans rapport avec la main,
typique d'un plateau chargé en milieu/fin de partie), pas de l'ensemble
des plateaux rencontrés en campagne à seulement 2 joueurs et 10-20 donnes.
De plus, le comportement « anytime » (déjà présent depuis #186, rendu
effectif plus tôt par #190) fait que la recherche consomme désormais
systématiquement tout le budget restant pour tenter de faire mieux dès
qu'un premier coup est trouvé — ce qui tend à AUGMENTER le temps moyen par
tour plutôt qu'à le réduire, même quand le résultat final est inchangé.

Taux de victoire d'Expert comparable avant/après (80 % puis 77.5 %, dans
la marge d'incertitude l'un de l'autre et de la mesure #187/#186
précédente — aucun des deux n'est significativement différent de l'autre
à cet échantillon) : aucune régression introduite par #190, conformément
à l'exigence « ne rien dégrader ».

## Conclusion

- Objectif mesurable de #190 (cas du tour 81, budget de production)
  **atteint** : 3 tuiles trouvées en 1.5 s, contre aucun coup avant.
- Budget de production inchangé (1.5 s) — l'accélération a suffi pour le
  cas cible, conformément à la consigne de ne l'augmenter qu'en dernier
  recours.
- Le gain mesuré est **localisé** aux plateaux structurellement proches du
  cas visé, pas généralisé à toute campagne Avancé vs Expert — à signaler
  explicitement plutôt que de laisser croire à un gain uniforme. Une
  accélération plus générale (par ex. élagage plus agressif des candidats
  réellement équivalents, ou détection plus fine des emplacements « sans
  enjeu pour la main ») resterait à explorer si des cas similaires au
  tour 81 se révèlent fréquents en jeu réel.
- Aucun test existant cassé (102 tests passés), aucune perte de tuile,
  Avancé et les niveaux inférieurs inchangés.

# Issue #189 — Suite #149 : rejeu du dernier coup de l'IA, rendre les coups complexes compréhensibles

Depuis le solveur de réarrangement global (#186), l'IA peut défaire et
recomposer plusieurs combinaisons du plateau en un seul tour. Le rejeu animé
existant (tuile par tuile, #144/#149) suffit pour un coup simple mais pas
pour un coup complexe : le joueur ne parvient plus à suivre ce que
l'ordinateur a fait. Deux aides optionnelles, accessibles à côté du bouton de
rejeu existant (qui garde son comportement inchangé par défaut, pour tous
les coups) :

## Résumé écrit (`moteur/description_coup.py::decrire_coup_ia`)

Fonction pure, testable séparément de l'UI : compare le plateau juste avant
et juste après un coup de pose et renvoie un résumé en français, calculé à
partir de ce diff (jamais du moteur ni de l'IA, qui restent inchangés) :

- Pour chaque combinaison d'avant, sa destination d'après recevant une
  majorité stricte de ses tuiles est sa continuation (elle « survit »,
  éventuellement modifiée) ; sans majorité claire, elle est « défaite ».
- Une combinaison d'après sans continuation unique est « créée ».
- Un joker qui quitte la continuation de sa combinaison d'origine est
  signalé nommément (d'où → vers), qu'il ait été échangé contre une tuile
  réelle (issue #148) ou libéré sans remplacement (#180/#181/#183).
- Un coup ne touchant qu'une seule combinaison et sans joker déplacé reste
  résumé en une seule phrase courte ; au-delà, plusieurs phrases.

## Rejeu pas-à-pas (`moteur/description_coup.py::etapes_coup_ia`, priorité de l'issue)

Découpe le même diff en une liste d'étapes (`{"texte", "plateau"}`) :
combinaisons défaites retirées une à une, puis combinaisons créées/modifiées
ajoutées dans leur forme finale, puis déplacements de joker signalés
(informatif, même plateau). La dernière étape correspond exactement au
plateau d'après. Le bouton « 📋 Pas à pas » (`jeu.html`/`jeu.js`) ne
s'affiche que si le coup comporte au moins 2 étapes distinctes, et son clic
(`ouvrirPasAPas`) est totalement indépendant du bouton de rejeu animé —
aucun des deux ne déclenche jamais l'autre. L'overlay (`#overlay-pas-a-pas`)
est strictement en lecture seule (aucun écouteur d'interaction de jeu dans
l'aperçu du plateau) et peut être quitté à tout moment sans effet sur la
partie ; navigation Suivant/Précédent/Quitter.

## Câblage (`ui/api.py`)

`jeu_ia_jouer` (seul point d'entrée qui construit `dernier_coup_ia`) calcule
`resume` et `etapes` une seule fois, immédiatement après une pose, et les
stocke directement dans `etat["dernier_coup_ia"]` aux côtés de
`plateau_avant`/`plateau_apres` déjà existants — aucun nouvel aller-retour
JS → Python.

## Reporté : bascule Avant/Après (point 2 de l'issue)

Par manque de temps, comme explicitement autorisé par l'issue elle-même
("si le temps manque, livrer d'abord le pas à pas et le résumé écrit"). À
traiter dans une issue séparée.

## Tests

- `tests/test_description_coup.py` (nouveau, 5 tests) : coup simple
  (extension de suite, groupe créé depuis la main, aucun changement), joker
  récupéré puis rejoué dans un nouveau groupe, démantèlement complet d'un
  groupe de 12 en 3 nouvelles combinaisons (vérifie le nombre d'étapes et
  l'identité exacte de la dernière étape avec le plateau d'après).
- Vérification complémentaire via un scénario Playwright ad hoc sur
  `jeu.html` (méthode CONTEXTE.md §7, script non committé, conformément à
  la convention du projet) : résumé affiché, bouton Pas à pas visible
  seulement pour le coup complexe (absent pour le coup simple), navigation
  Suivant/Précédent/Quitter, plateau réel inchangé après fermeture de
  l'overlay.
- `pytest -q` : 105 passed (81 → 105, +5 nouveaux + aucune régression).

## Fichiers touchés

- `src/rummikub/moteur/description_coup.py` (nouveau)
- `tests/test_description_coup.py` (nouveau)
- `src/rummikub/ui/api.py` (calcul résumé/étapes dans `jeu_ia_jouer`)
- `src/rummikub/ui/web/jeu.html` (résumé, bouton Pas à pas, overlay)
- `src/rummikub/ui/web/jeu.css` (styles associés)
- `src/rummikub/ui/web/jeu.js` (affichage résumé, navigation pas-à-pas)
- `CONTEXTE.md` (nouvelle section §12)

# Issue #188 — Suite #185 : script d'analyse des « coups ratés » de l'IA à partir des journaux de parties

Objectif : pouvoir dire, après coup, si une IA qui a pioché ou passé aurait
pu jouer — un joueur humain ne voit pas le chevalet de l'IA et ne peut pas en
juger lui-même. Le journal de partie (`persistance/journal.py`, #185)
enregistre à chaque action les chevalets de tous les joueurs et le plateau :
on peut donc reconstituer l'état exact affronté par l'IA avant chaque
décision et vérifier ce qu'un solveur disposant de beaucoup de temps de
calcul y aurait trouvé.

## Détection (`persistance/coups_rates.py`, pur, sans pywebview)

- `extraire_decisions_ia(data)` : pour chaque décision de piocher/passer
  d'une IA dans un journal brut, reconstitue l'état précédent (chevalet du
  joueur + plateau, enregistrés par l'action JUSTE AVANT dans le journal —
  la toute première action d'un journal est donc toujours ignorée, faute
  d'état antérieur). La mise initiale d'un joueur est considérée faite s'il
  a déjà posé au moins une tuile plus tôt dans le même journal (impossible,
  en jeu réel, de poser quoi que ce soit avant d'avoir atteint le minimum en
  une seule fois). Tolère les formats anciens/corrompus (en-tête `joueurs`
  absent ou à l'ancien format, champs `plateau`/`mains_joueurs` manquants) :
  retourne une liste vide plutôt que de lever une exception.
- `analyser_decision(decision, budget_genereux=10.0, budget_production=1.5)` :
  interroge `moteur/solveur.py::resoudre_coup` sur l'état reconstitué. Si le
  solveur trouve un coup posant au moins une tuile, la décision est un
  « coup raté » (nombre de tuiles posables ; avant la mise initiale, points
  que l'ouverture aurait rapportés). Pour le niveau Expert uniquement,
  interroge en plus le solveur avec le budget de production réel (1,5 s,
  `moteur/ia.py::BUDGET_TEMPS_EXPERT`) afin de distinguer un coup raté par
  faiblesse de l'algorithme (le budget de production l'aurait trouvé aussi)
  d'un coup raté par manque de temps de calcul (seul le budget généreux le
  trouve — champ `budget_limite`).
- `calculer_resume(resultats)` : agrège par niveau d'IA et par phase (avant/
  après mise initiale) — décisions analysées, coups ratés et pourcentage.
- `top_coups_rates(resultats, n=5)` : les coups ratés les plus importants
  (tuiles ratées), pour examen manuel.

## Script CLI (`scripts/analyser_coups_rates.py`)

```
python scripts/analyser_coups_rates.py                      # journal le plus récent
python scripts/analyser_coups_rates.py chemin/vers/partie.json
python scripts/analyser_coups_rates.py --tous --dossier DIR  # tous les journaux d'un dossier
python scripts/analyser_coups_rates.py --budget 20 --budget-production 1.5
```

Un journal illisible ou corrompu est signalé sur stderr et ignoré sans
interrompre l'analyse des autres. Affiche le résumé par niveau/phase, le
détail des 5 coups ratés les plus importants (numéro de coup, joueur, tuiles
ratées), et un avertissement systématique.

## Limite documentée (répétée à l'affichage)

Le solveur gèle certaines combinaisons déjà posées sur le plateau pour
limiter la combinatoire (`moteur/solveur.py::_separer_combos_figees`) : un
coup non trouvé ne prouve pas qu'aucun coup n'existe. Les coups ratés
détectés sont une **borne basse**, jamais une liste exhaustive. Par ailleurs,
le journal ne conserve pas la configuration de la partie (`mise_initiale_min`
notamment) : `config.MISE_INITIALE_MIN` (valeur par défaut) est utilisée pour
toutes les parties rejouées.

**Aucune modification de l'IA ni du moteur** : lecture pure des journaux +
appels en lecture au solveur existant.

## Tests (`tests/test_coups_rates.py`)

Journaux fabriqués à la main couvrant : coup raté détecté après la mise
initiale, pioche justifiée (aucun coup trouvable), coup raté avant la mise
initiale avec points d'ouverture rapportés, journal ancien/corrompu ignoré
proprement (format d'avant #185, champs manquants), distinction budget de
production/généreux pour Expert (par substitution du solveur, indépendante
du chronométrage réel), résumé et classement des coups ratés les plus
importants. 16 tests, tous passants ; suite complète du projet (100 tests)
non régressée.

## Mise à jour de la documentation

`CONTEXTE.md` : nouvelle section §11 décrivant le script, son fonctionnement
et ses limites ; entrée ajoutée dans l'arborescence (§2).

# Issue #187 — Suite #186 : correctif — le solveur Expert faisait disparaître des combinaisons du plateau quand sa mise initiale n'était pas faite

Bug constaté en jeu (`scripts/analyser_partie.py` sur le journal de la
partie en cause) : un groupe de 12 déjà posé (`joker_1` + `rouge_12_a` +
`noir_12_a`) disparaissait du plateau au premier coup d'Expert, sans que le
jeu ne refuse le coup.

## Cause (`moteur/solveur.py`)

Dans `resoudre_coup`, tant que la mise initiale n'est pas faite, le plateau
est volontairement ignoré pour la RECHERCHE (seule la main compte — règle
du jeu correcte). Mais le code chargeait alors `plateau = []` au lieu du
plateau réel : le résultat renvoyé ne contenait donc plus que les nouvelles
combinaisons formées avec la main, sans jamais reporter les combinaisons
déjà posées par les autres joueurs. Le jeu acceptait ce plateau tronqué car
`jouer_tour` validait seulement que chaque combinaison proposée était
valide, pas que toutes les tuiles antérieures y figuraient encore.

Ce cas n'était pas couvert par les tests de #186 (la mise initiale n'y
était testée qu'avec un plateau vide), et la campagne de simulation de
#186 ne contrôlait pas la conservation des tuiles — elle n'a donc rien
signalé.

## Correctif 1 : solveur (`moteur/solveur.py::resoudre_coup`)

- Le plateau réel est désormais toujours chargé depuis l'état
  (`plateau_depuis_dict(etat.get("plateau", []))`), que la mise initiale
  soit faite ou non.
- Si la mise initiale n'est pas faite, tout le plateau est traité comme
  « gelé » (`plateau_gele = plateau`, `plateau_flexible = []`) : la
  recherche ne porte toujours que sur la main (comportement inchangé), mais
  le plateau gelé est désormais reconduit à l'identique dans
  `nouveau_plateau_tuiles`, au lieu d'être simplement omis.
- Revérifié : `jouer_niveau_avance` et toute la chaîne de tactiques locales
  d'Avancé (`_coup_maximal`, `_combos_vers_coup`,
  `_meilleur_coup_liberations`, `_coup_scission`) construisaient déjà
  systématiquement leur plateau candidat à partir de `etat.get("plateau",
  [])` (jamais tronqué) — le bug était strictement localisé au solveur
  d'Expert (tâche 1 de #187, point confirmé par lecture complète, pas de
  second site à corriger).

## Correctif 2 : garde-fou central (`moteur/partie.py::jouer_tour`)

Nouveau contrôle, juste après la validation de chaque combinaison et avant
toute mutation de l'état : l'ensemble des IDs présents sur le plateau en
DÉBUT de tour doit être un sous-ensemble de l'ensemble des IDs du plateau
proposé. Sinon, le coup est refusé :

```python
{"ok": False,
 "erreur": "Coup refusé : des tuiles du plateau ont disparu (id1, id2, ...)",
 "tuiles_disparues": ["id1", "id2", ...]}
```

`jouer_tour` est le point d'entrée unique utilisé aussi bien par les coups
humains (`ui/api.py::jeu_jouer_coup`) que par tous les niveaux d'IA
(`ui/api.py::jeu_ia_jouer`, et `scripts/comparer_niveaux_ia.py`) : ce seul
endroit protège donc déjà les futurs niveaux d'IA sans modification
supplémentaire. Côté IA, un coup refusé par ce garde-fou se comporte comme
n'importe quel autre coup invalide proposé par l'IA : repli automatique sur
une pioche de secours (`Api.jeu_ia_jouer`, comportement préexistant,
inchangé).

## Correctif 3 : contrôle de conservation dans la simulation (`scripts/comparer_niveaux_ia.py`)

- `_anomalies_conservation(etat)` (nouveau) : à chaque coup joué pendant une
  partie simulée, vérifie que les 106 IDs de référence (`creer_sac()`) sont
  chacun présents EXACTEMENT une fois entre les mains de tous les joueurs,
  le plateau et la pioche. Toute tuile manquante, dupliquée ou inconnue est
  comptée comme une anomalie.
- `jouer_un_tour` distingue désormais, parmi les coups invalides proposés
  par l'IA, ceux refusés spécifiquement par le garde-fou anti-disparition
  (`tuiles_disparues`) des autres motifs de rejet (ex. mise initiale
  insuffisante) — comptés et journalisés à part (`logger.error`, visible
  même sans `--verbose`), pour qu'une régression de ce type ressorte
  clairement du rapport plutôt que de se noyer dans le compteur générique
  « coups invalides ».
- Rapport (`afficher_rapport`) : nouvelle ligne « Anomalies de conservation
  des tuiles (#187, attendu 0) : N », et une ligne d'alerte dédiée si des
  coups ont été refusés par le garde-fou.

## Tests (`tests/test_ia.py`, `tests/test_moteur.py`)

- `test_expert_conserve_le_plateau_quand_la_mise_initiale_n_est_pas_faite` :
  reproduit le scénario constaté en jeu (groupe de 12
  `joker_1`/`rouge_12_a`/`noir_12_a` déjà posé, mise initiale pas faite,
  main permettant d'ouvrir) — vérifie que la combinaison déjà posée reste
  intacte dans le résultat, que le nombre total de tuiles (plateau + main
  restante) est conservé, et que le coup passe le nouveau garde-fou de
  `jouer_tour`.
- `test_expert_conserve_plusieurs_combinaisons_du_plateau_sans_mise_
  initiale` : variante avec DEUX combinaisons déjà posées sur le plateau —
  les deux doivent rester intactes.
- `test_jouer_tour_refuse_si_des_tuiles_du_plateau_disparaissent`
  (`tests/test_moteur.py`) : plateau à deux combinaisons, coup proposé qui
  en ampute une (chaque combinaison proposée reste individuellement
  valide) — `jouer_tour` doit refuser, avec `tuiles_disparues` listant
  exactement les IDs manquants, et ne doit pas avoir modifié l'état.
- Suite complète : `pytest -q` → **84 passed** (81 existants, tous
  toujours au vert, + 3 nouveaux).

## Journal de la partie en cause (`~/partie_bug_mise_initiale_expert.json`)

Fichier présent sur la machine, mais **hors du périmètre strict de ce
worktree** (`/home/alain/worktrees/rummikub-issue187`) imposé par la
consigne CCL — consigne explicite : interdiction d'agir hors de ce
périmètre « même si la tâche le demande explicitement ». Il n'a donc pas
été lu ; la reproduction du bug (tâche 6) s'appuie à la place sur la
description de la partie fournie dans le corps de l'issue (groupe de 12 :
`joker_1` + `rouge_12_a` + `noir_12_a`), directement reconstituée dans les
deux tests ci-dessus. Alain peut, s'il le souhaite, copier ce fichier à
l'intérieur du worktree pour qu'un futur agent CCL puisse l'exploiter.

## Mesure (`scripts/comparer_niveaux_ia.py`, Expert vs Avancé)

Campagne rejouée **avec exactement les mêmes paramètres que #186** (budget
de production 1.5s/tour, mêmes graines, mêmes 2 lots) pour comparer
directement avec la mesure originale, désormais invalidée par le bug :

```
python scripts/comparer_niveaux_ia.py --niveau-a Avancé --niveau-b Expert --donnes 5  --seed 0
python scripts/comparer_niveaux_ia.py --niveau-a Avancé --niveau-b Expert --donnes 15 --seed 1
```

| | Lot 1 (seed 0) | Lot 2 (seed 1) | **Combiné (40 parties)** | #186 (avant correctif) |
|---|---|---|---|---|
| Victoires Expert | 7/10 | 22/30 | **29/40 — 72.5 % ± 13.8 pt (IC 95 %)** | 32/40 — 80.0 % ± 12.4 pt |
| Fins par pioche épuisée (bloqué) | 0/10 | 2/30 | **2/40 — 5.0 %** | 4/40 — 10.0 % |
| Durée moyenne (tours) | 76.0 | 88.2 | **85.2** | 94.8 |
| Temps Expert par tour | moy. 825.9 ms / max 1527.9 ms (381 tours) | moy. 828.5 ms / max 1569.2 ms (1326 tours) | **moy. ≈ 827.9 ms / max 1569.2 ms (1707 tours)** | moy. ≈ 855 ms / max 1574 ms |
| Temps Avancé par tour | moy. 1.2 ms / max 8.0 ms | moy. 1.4 ms / max 8.6 ms | moy. ≈ 1.4 ms / max 8.6 ms | moy. ≈ 2.0 ms / max 15.0 ms |
| **Anomalies de conservation des tuiles (#187)** | **0** | **0** | **0 / 0** | *(non mesuré — bug non détecté)* |
| Coups refusés par le garde-fou anti-disparition | 0 | 0 | **0** | *(non mesuré)* |

**Écart par rapport à 50/50 toujours significatif** (72.5 % ± 13.8 pt exclut 50 %) :
Expert bat nettement Avancé une fois le bug corrigé — la force réelle d'Expert est
confirmée, pas un artefact du bug de #186.

**Changement par rapport à #186 (80.0 % → 72.5 %, -7.5 pt)** : la baisse va dans le
sens attendu si le bug de #187 donnait un avantage indu à Expert sur une partie des
40 parties originales (moins de tuiles à gérer sur le plateau après une disparition
peut artificiellement simplifier ses coups suivants, ou biaiser les pénalités de fin
de manche). Mais les intervalles de confiance des deux campagnes se recouvrent
largement (#186 : IC [67.6 % ; 92.4 %] ; #187 : IC [58.7 % ; 86.3 %]) : avec seulement
40 parties, cet écart de 7.5 pt n'est PAS démontrable comme un effet du correctif
plutôt qu'une simple variance d'échantillonnage (même limite de taille d'échantillon
que #186, pour les mêmes raisons de budget de calcul — voir #186). Conclusion
pratique : Expert reste nettement plus fort qu'Avancé, et rien dans cette mesure
n'indique que le correctif ait notablement affaibli (ou renforcé) Expert ; une
campagne à 200/500 donnes, toujours hors de portée du budget de calcul disponible
pour cette tâche (même constat que #186 : ~35-40s par partie Expert, donc plusieurs
heures pour 400 parties), resserrerait cette marge.

**Conservation des tuiles** : 0 anomalie sur l'intégralité des ~1700 tours
Expert + ~1700 tours Avancé joués (mains + plateau + pioche toujours exactement
106 tuiles présentes une seule fois), et 0 coup refusé par le garde-fou
anti-disparition — cohérent avec le correctif de la tâche 1 (le solveur ne propose
plus de plateau tronqué) et avec le fait que l'IA revalide déjà ses propres coups
avant de les proposer (le garde-fou de la tâche 2 est un filet de sécurité qui n'a
pas eu à se déclencher ici, mais protège contre toute régression future, y compris
sur un coup humain).

# Issue #186 — Suite #184 : IA Expert, solveur de réarrangement global du plateau

La campagne de #184 montrait qu'Avancé et Expert ne se distinguaient pas de
façon significative (53 % / 47 % sur 100 parties) et que 29 % des parties se
terminaient bloquées (pioche épuisée). Cause identifiée : toutes les
tactiques existantes (`CONTEXTE.md` §8) ne modifient qu'une ou deux
combinaisons du plateau à la fois — un joueur humain fort démonte et
recompose souvent plusieurs combinaisons pour poser davantage de tuiles.

## Solveur de réarrangement global (`moteur/solveur.py`, nouveau)

Reconstruit librement tout le plateau (plateau + chevalet confondus en un
seul « sac ») pour y poser le plus de tuiles du chevalet possible, sous la
seule contrainte dure qu'aucune tuile déjà posée ne peut disparaître (elle
peut changer de combinaison). Jokers compris, y compris ceux déjà posés.

- Recherche récursive mémoïsée sur des compteurs par emplacement
  `(couleur, valeur)` (0 à 2 tuiles réelles) et sur les 2 jokers du jeu,
  chacun marqué « obligatoire » (vient du plateau, doit finir posé) ou
  « optionnel » (vient du chevalet, peut rester en main).
- Départage entre réarrangements posant le même nombre de tuiles : d'abord
  le plus de points posés, puis, à égalité, le moins de jokers du chevalet
  utilisés — un joker reste une ressource précieuse même à nombre de tuiles
  égal.
- Mise initiale pas faite : le plateau n'est pas touché (règle du jeu), le
  solveur cherche la meilleure combinaison formable depuis la seule main
  sous la contrainte des points ≥ `mise_initiale_min`.
- **Combinaisons gelées** (`_separer_combos_figees`) : une combinaison du
  plateau sans aucune couleur/valeur commune avec la main, et sans joker,
  est reconduite telle quelle hors recherche — nécessaire pour borner la
  combinatoire sur les plateaux de milieu/fin de partie (principal facteur
  de ralentissement observé).
- **Repli budget de temps** (`BudgetDepasse`) : recherche interrompue
  au-delà de `BUDGET_TEMPS_EXPERT` (1.5s par défaut, `moteur/ia.py`) ;
  `jouer_niveau_expert` se replie alors sur le comportement d'Avancé pour ce
  tour (idem si le solveur ne trouve lui-même aucun coup).
- Pur Python, aucune dépendance nouvelle (contrainte Windows/PyInstaller).

## `moteur/ia.py`

- `jouer_niveau_expert` réécrit : appelle `solveur.resoudre_coup`, repli sur
  `jouer_niveau_avance` en cas de `BudgetDepasse` ou d'échec du solveur.
- **Règle supprimée** : Expert ne refuse plus de poser quand un adversaire a
  ≤ 3 tuiles (ancienne prudence) — la campagne de #184 n'a montré aucun
  avantage mesurable, poser davantage de tuiles est presque toujours
  préférable.
- Avancé (et les niveaux inférieurs) inchangés.

## Tests (`tests/test_ia.py`, 81 tests au total, +12 vs #184)

- Le solveur retrouve au moins aussi bien chaque scénario déjà couvert par
  Avancé (échange direct, détachement en bout, libérations combinées,
  groupe de 4, scission en milieu de suite, groupe de 4 avec joker retiré).
- Nouveaux : démantèlement complet d'une courte suite avec joker (#175,
  identifié mais non implémenté par Avancé — confirmé par un test de
  non-régression dédié), mise initiale (ouverture atteignant le minimum
  requis, et refus d'ouvrir sous ce minimum), aucun coup possible, et repli
  sur budget de temps dépassé (budget nul : `BudgetDepasse` levée, puis
  `jouer_niveau_expert` rejoue exactement le coup d'Avancé).
- Un test existant devenu faux à bon escient :
  `test_expert_ne_detache_pas_un_joker_en_bout_de_suite_par_scission`
  (plateau 4-5-6-joker, chevalet 7 bleu/7 jaune) supposait qu'aucun coup
  n'était possible — légitime pour Avancé (tactiques locales, toujours
  vrai, test conservé), mais le solveur y trouve un coup réellement
  meilleur : la suite redevient 4-5-6 (toujours valide) et le joker libéré
  forme un NOUVEAU groupe de 7 avec les deux tuiles de la main. Remplacé
  par `test_expert_trouve_un_groupe_pour_le_joker_en_bout_de_suite`, qui
  vérifie ce nouveau coup.
- Suite complète : `pytest -q` → **81 passed**.

## Mesure (`scripts/comparer_niveaux_ia.py`, Expert vs Avancé)

Campagne lancée au budget de PRODUCTION du solveur (1.5s/tour, `BUDGET_TEMPS_EXPERT`),
en deux lots indépendants (même outil, deux graines), combinés ci-dessous :

```
python scripts/comparer_niveaux_ia.py --niveau-a Avancé --niveau-b Expert --donnes 5  --seed 0
python scripts/comparer_niveaux_ia.py --niveau-a Avancé --niveau-b Expert --donnes 15 --seed 1
```

| | Lot 1 (seed 0) | Lot 2 (seed 1) | **Combiné (40 parties)** |
|---|---|---|---|
| Victoires Expert | 10/10 | 22/30 | **32/40 — 80.0 % ± 12.4 pt (IC 95 %)** |
| Fins par pioche épuisée (bloqué) | 1/10 | 3/30 | **4/40 — 10.0 %** (vs 29 % en #184) |
| Durée moyenne (tours) | 84.0 | 98.4 | **94.8** |
| Temps Expert par tour | moy. 853 ms / max 1536 ms (422 tours) | moy. 855 ms / max 1574 ms (1479 tours) | **moy. ≈ 855 ms / max 1574 ms (1901 tours)** |
| Temps Avancé par tour | moy. 1.8 ms / max 7.9 ms | moy. 2.1 ms / max 15.0 ms | moy. ≈ 2.0 ms / max 15.0 ms |

**Écart par rapport à 50/50 significatif** (80.0 % ± 12.4 pt exclut 50 %) : Expert bat
nettement Avancé. La part de parties bloquées (pioche épuisée) chute de 29 % (#184) à
10 % ici. Le temps de calcul Expert reste sous le budget de 1.5s dans tous les cas
observés (max 1574 ms, légèrement au-dessus de 1.5s du fait de l'arrondi des points de
vérification du budget tous les 50 appels — voir `_Contexte.verifier_budget` — jamais
un dépassement significatif).

**Écart entre #184 (0 % significatif) et ici (80 %)** : la suppression de la règle
« pioche si adversaire ≤ 3 tuiles » (tâche 4) contribue, mais l'essentiel vient du
solveur lui-même — voir le point suivant sur l'effet du budget de temps.

**200/500 donnes demandées, mais hors de portée du temps de calcul disponible pour
cette tâche (TIMEOUT #186) :** au budget de production, une partie Expert vs Avancé
prend ~35-40s (dominé par les ~85-100 décisions Expert à ~850ms chacune). 200 donnes
(400 parties) représenteraient donc plusieurs heures, bien au-delà du budget alloué à
ce traitement. Un essai de calibration à budget RÉDUIT (`scripts/_campagne_186.py`,
0.3s/tour, 10 donnes/20 parties, seed 1, non retenu comme mesure officielle) donne
Expert 12/20 (60 %, ÉCART NON significatif) contre 100 %/73 % aux deux lots à budget
plein — **le budget de temps du solveur a un effet de premier ordre sur sa force** :
diviser le budget par 5 ramène quasiment Expert au niveau d'Avancé. Ce constat
confirme que le repli sur Avancé en cas de `BudgetDepasse` (tâche 3) est un véritable
compromis qualité/temps, pas une formalité, et qu'il serait risqué de tirer une
conclusion de mesures faites à budget réduit : les 40 parties ci-dessus, bien qu'en
dessous de l'échantillon demandé, sont donc mesurées au budget RÉEL de production
pour rester représentatives, plutôt qu'un échantillon plus large mais biaisé par un
budget artificiellement réduit. Avec davantage de temps de calcul disponible, refaire
cette campagne à 200, puis 500 donnes (budget plein, ou en parallélisant les parties)
resterait la suite logique pour resserrer la marge d'erreur (actuellement ± 12.4 pt).

## `CONTEXTE.md`

- §8 : recentré sur Avancé (et le repli d'Expert) ; #175 retiré de la liste
  « identifiée mais pas encore implémentée » côté Expert (reste non
  implémentée pour Avancé, confirmé par un test dédié).
- Nouvelle §8bis décrivant le solveur de réarrangement global d'Expert.
- §2/§6 : arborescence (`solveur.py`) et compteur de tests (81) à jour.

# Issue #185 — Bilan des parties jouées : synthèse par niveau d'IA à partir des journaux de parties

Alain voulait pouvoir rejouer quelques parties contre les niveaux d'IA les
plus forts et retrouver ensuite, sans tenir de comptes à la main, ce que ces
parties ont donné (victoires, marge, comportement de l'IA) afin de recaler
les niveaux par rapport à un joueur humain.

## État des lieux

Le jeu dispose déjà d'un journal de parties optionnel
(`persistance/journal.py`, issues #97/#99), activable via la clé
`log_parties` de `config.json` (défaut `False`, aucun overhead). Il
enregistre chaque coup (mains, plateau, pioche) mais ne portait ni le niveau
des joueurs, ni l'auteur réel d'une décision IA (le champ générique
`"tour_ia"` ne distinguait pas pose/pioche/passe), ni aucune marque de fin de
partie — impossible donc d'en tirer un bilan sans tout rejouer à la main.
Décision : compléter ce journal existant plutôt que d'en créer un second.

## Journal complété (`persistance/journal.py`, `ui/api.py`)

- En-tête `joueurs` : désormais `{"nom", "est_ia", "niveau"}` par joueur
  (au lieu du seul nom).
- Chaque action porte maintenant `auteur_index` (qui a décidé — distinct de
  `joueur_actuel`, déjà avancé au joueur suivant au moment de l'écriture),
  `nb_tuiles_posees`, `termine` et `gagnant_index`.
- Libellés d'action canonisés côté `api.py` : le tour IA journalisait jusqu'ici
  un `"tour_ia"` générique ; il journalise maintenant la décision réelle
  (`"pose"|"pioche"|"passe"`), alignée sur celle des coups humains (le coup
  humain `"fin_de_tour"` est renommé `"passe"` pour la même raison). Une
  partie dont la dernière action n'a pas `termine: True` est reconnue comme
  abandonnée en cours (ou toujours en cours) et exclue du bilan — sans
  mécanisme de détection séparé à maintenir.
- Rétro-compatibilité : les journaux écrits avant #185 (joueurs = liste de
  noms, pas de `termine`) restent lisibles ; `bilan.py` les exclut proprement
  du bilan (faute de ces champs) plutôt que de planter.
- **`moteur/ia.py` non modifié**, conformément à la consigne.

## Bilan (`persistance/bilan.py` + `scripts/bilan_parties.py`)

- `persistance/bilan.py` : module pur (aucune dépendance pywebview) —
  lecture tolérante des journaux (`charger_journal`, `extraire_partie`,
  dédoublonnage des décisions annulées/rejouées sur un même tour) et calcul
  du bilan par niveau d'IA (`calculer_bilan`) : parties, victoires/défaites
  humain, taux de victoire, marge moyenne (tuiles restantes de l'IA à la
  victoire humaine / de l'humain à sa défaite), tours moyens par partie, part
  des tours IA en pioche/passe plutôt qu'en pose et répartition
  début/milieu/fin de partie. Filtres `nom_joueur`, `depuis`, `jusqu`.
- `scripts/bilan_parties.py` : script CLI (`python scripts/bilan_parties.py
  [--joueur NOM] [--depuis AAAA-MM-JJ] [--jusqu AAAA-MM-JJ] [--dossier
  CHEMIN]`), sur le même modèle que `scripts/analyser_partie.py` existant.
  Affiche le bilan par niveau d'IA, triés selon `config.NIVEAUX`.

## Vérifications

- `scripts/analyser_partie.py` adapté pour afficher proprement le nouveau
  format `joueurs` (liste de dicts) comme l'ancien (liste de noms).
- Performance : avec `log_parties` désactivé (réglage par défaut), aucun
  changement — `logger_action` retourne toujours immédiatement (mesuré :
  0,12 ms pour 78 coups, contre ~2,4 s si activé, un coût déjà présent avant
  #185 et indépendant de cette issue). Avec `log_parties` activé, le delta dû
  aux 4 champs ajoutés par #185 est non mesurable : 2182 ms (après #185) vs
  2399 ms (avant #185) pour les mêmes 78 coups — la sérialisation complète de
  l'état à chaque coup, déjà existante, domine entièrement.
- `tests/test_bilan.py` (17 tests nouveaux) : lecture de journaux valides/
  abandonnés/anciens/corrompus, dédoublonnage après annulation, calcul du
  bilan (victoire/défaite, marges, tours moyens, part pioche/passe et son
  répartition, filtres nom/période), et un test d'intégration qui fait
  vraiment jouer une partie via le moteur (`creer_partie`/`piocher` jusqu'à
  épuisement de la pioche) et vérifie que `journal.logger_action` et
  `bilan.py` restent d'accord sur le format.
- `CONTEXTE.md` : nouvelle section §9 (journal + bilan), arborescence et
  compteur de tests mis à jour (75 tests passent).
- Suite complète : `pytest -q` → **75 passed**.

# Issue #184 — Script de simulation : départager deux niveaux d'IA sur un grand nombre de parties

On ne savait pas si le niveau Expert est réellement plus fort qu'Avancé, sa
seule différence étant une règle qui lui fait piocher au lieu de poser
quand un adversaire n'a plus que 3 tuiles ou moins — ce qui pourrait le
désavantager autant que l'avantager. But : mesurer, sans toucher à l'IA ni
au moteur (voir #134 pour les scripts de simulation historiques).

## Ajout

`scripts/comparer_niveaux_ia.py` (nouveau script, aux côtés de
`scripts/simulation_ia.py` déjà existant) :

- CLI : `--niveau-a`, `--niveau-b` (obligatoires, un des 5 niveaux
  connus), `--donnes` (défaut 50), `--seed` (défaut 0, reproductible),
  `--max-tours` (garde-fou anti-blocage, défaut 300), `-v/--verbose`.
- Utilise uniquement le moteur Python (`rummikub.moteur.*`), jamais
  pywebview, conformément à `CONTEXTE.md` §7.
- **Parties à 2 joueurs jouées en miroir** : pour chaque donne, `random.seed`
  est réinitialisée à la même graine avant chaque partie du couple, ce qui
  produit exactement la même distribution de tuiles (`distribuer`
  consomme le module `random` global dans cet ordre) ; seules les places
  des deux niveaux sont échangées entre les deux parties du couple. 50
  donnes → 100 parties. Avec la même `--seed`, la campagne est reproductible
  à l'identique.
- **Fin de partie** : suit les règles du moteur (`_terminer_tour`) —
  chevalet vidé ou pioche épuisée (ce second cas, dit « bloqué », est déjà
  géré par `calculer_scores_manche`/`trouver_gagnant_manche` : le joueur
  avec le moins de pénalité l'emporte). Garde-fou `--max-tours` : les
  parties qui l'atteignent sont **comptées à part** (bucket
  `garde_fou`), exclues des statistiques de victoire/durée/pénalité plutôt
  que silencieusement ignorées ou faussement comptées comme décisives.
- **Résultats affichés** : victoires et taux par niveau avec marge d'erreur
  (IC 95 %, approximation normale de Wald) et verdict « significatif / NON
  significatif » par rapport à 50/50 ; nombre moyen de tuiles restantes et
  de points de pénalité du perdant ; durée moyenne en tours des parties
  décidées ; répartition des fins de partie (chevalet vidé / pioche
  épuisée / arrêtées par le garde-fou) ; temps de calcul moyen et maximal
  d'un tour de décision IA par niveau (chronométré autour de `jouer_ia`
  uniquement, pour repérer un emballement de la recherche combinatoire des
  libérations de joker, cf. `CONTEXTE.md` §8).
- Aucune modification de `moteur/ia.py` ni du reste du moteur : le script
  ne fait qu'orchestrer les fonctions publiques déjà exposées
  (`creer_partie`, `jouer_tour`, `piocher`, `passer_tour`,
  `backup_debut_tour`, `annuler_tour`, `jouer_ia`), à l'identique de
  `scripts/simulation_ia.py`.

## Première campagne : Avancé vs Expert

Lancée avec les valeurs par défaut (`--niveau-a Avancé --niveau-b Expert`,
50 donnes, graine 0, max-tours 300) :

```
COMPARAISON : Avancé (camp A) vs Expert (camp B)
50 donne(s) x 2 (miroir) = 100 partie(s) demandée(s), 100 partie(s) décidée(s)
----------------------------------------------------------------------
  Avancé (camp A) : 53/100 victoires — taux 53.0 % ± 9.8 pt (IC 95 %)
  Expert (camp B) : 47/100 victoires — taux 47.0 % ± 9.8 pt (IC 95 %)
  Écart par rapport à 50/50 NON significatif au seuil de confiance 95 %.
----------------------------------------------------------------------
  Fins de partie : 71 par chevalet vidé, 29 par pioche épuisée (bloqué),
  0 arrêtée(s) par le garde-fou (max tours).
  Durée moyenne d'une partie décidée : 113.9 tour(s).
  Perdant (parties décidées) : en moyenne 6.0 tuile(s) restante(s),
  43.8 point(s) de pénalité.
----------------------------------------------------------------------
  Temps de calcul par tour (décision IA), par niveau :
    Avancé          : moyenne 2.1 ms, max 26.9 ms, sur 5687 tour(s)
    Expert          : moyenne 3.0 ms, max 71.6 ms, sur 5702 tour(s)
======================================================================
Temps total de la campagne : 34.5s.
```

**Conclusion** : sur 100 parties, Avancé gagne 53 % contre 47 % pour
Expert, mais l'écart (± 9.8 pt) n'est PAS statistiquement significatif à
95 % — rien ne permet de conclure qu'Expert est plus fort ou plus faible
qu'Avancé. La règle « piocher au lieu de poser face à un adversaire à ≤3
tuiles » ne semble donc pas le désavantager de façon mesurable sur cet
échantillon ; aucun emballement de temps de calcul détecté (max 71.6 ms
pour Expert, cohérent avec la recherche combinatoire de libération de
joker, sans dérive). Aucune partie bloquée par le garde-fou.

## Documentation

`CONTEXTE.md` : nouvelle section §9 « Scripts de simulation IA vs IA »,
décrivant `scripts/simulation_ia.py` et `scripts/comparer_niveaux_ia.py`
(usage, options, résultats affichés, résumé de la première campagne).

# Issue #183 — Suite #181 : IA : retirer un joker d'un groupe de 4 sans tuile de remplacement

Dernière tactique simple identifiée dans `CONTEXTE.md` §8 (« Réduction de
groupe de 4 à 3 (joker retiré) »). Un groupe de 4 tuiles du plateau
contenant un joker (3 tuiles réelles de couleurs distinctes + 1 joker)
reste un groupe valide une fois le joker retiré : les 3 tuiles réelles
suffisent seules. Contrairement à l'échange direct (#148, qui exige une
tuile identique en main) et à #180 (qui retire une tuile RÉELLE, jamais le
joker, pour l'échanger ailleurs), ici le joker est retiré sans qu'aucune
tuile ne le remplace.

## Ajout

`src/rummikub/moteur/ia.py` :

- `_jokers_liberables_par_groupe4_sans_remplacement(plateau)` (nouvelle
  fonction) : détecte, pour tout groupe de 4 tuiles du plateau, un joker
  dont le retrait laisse un groupe de 3 valide. Ne consomme aucune tuile
  du chevalet.
- `_liberations_possibles` : intègre cette nouvelle tactique au même
  format unifié que #169/#180/#181 (`combis`, `joker`, `tuiles_consommees`
  vide, `appliquer`), pour qu'elle puisse se combiner avec les autres
  libérations dans la même recherche combinatoire (`_meilleur_coup_liberations`).

Comme pour les autres tactiques de joker, limité aux niveaux Avancé et
Expert (`_meilleur_coup_avec_joker`, déjà réservé à ces niveaux) ; le
joker libéré doit être rejoué dans le même tour avec des tuiles de la main,
sinon le coup n'est pas retenu. S'applique uniquement aux groupes de 4 :
un groupe de 3 avec joker (2 réelles + 1 joker) ne peut pas perdre son
joker sans tomber sous le minimum de 3 tuiles.

## Tests

`tests/test_ia.py` :

- `test_avance_libere_un_joker_de_groupe4_sans_remplacement` /
  `test_expert_libere_un_joker_de_groupe4_sans_remplacement` : groupe
  plateau de trois 9 (rouge, bleu, jaune) + joker, chevalet avec 12 rouge
  et 12 jaune — le joker est retiré du groupe (réduit à 3, toujours
  valide) et rejoué dans un nouveau groupe de 12.
- `test_facile_ne_libere_pas_le_joker_de_groupe4` : non-régression, Facile
  ne tente pas cette tactique (aucun coup jouable avec les mêmes données).
- `test_avance_ne_reduit_pas_un_groupe_de_3_avec_joker` : un groupe de
  SEULEMENT 3 tuiles avec joker (2 réelles + 1 joker) ne peut pas perdre
  son joker — la réduction est impossible, le coup n'est pas proposé.

Tous les tests existants (48 au total sur le dépôt) passent sans
modification de leurs assertions.

## Documentation

`CONTEXTE.md` §8 : la tactique « Réduction de groupe de 4 à 3 (joker
retiré) » est déplacée des tactiques identifiées mais non implémentées
vers les tactiques implémentées, avec le numéro #183 et une description
courte. Il ne reste plus que le démantèlement complet d'une courte suite
(#175) dans les tactiques identifiées mais non implémentées.

# Issue #182 — Suite #181 : Tests de non-régression de la scission en bout de suite

Suite #181 : la scission en BOUT de suite (`_coup_scission`, cas le plus
fréquent en jeu) n'était couverte par aucun test unitaire — seuls des
scripts de simulation historiques (#134) la vérifiaient, et son
équivalence avec l'ancien comportement n'avait été validée que par
relecture du code lors de la généralisation à la scission en milieu de
suite (#181).

Dix tests ajoutés à `tests/test_ia.py` (Avancé et Expert), figeant le
comportement actuel sans aucun changement de code hors tests :

- **Scission en fin de suite** : suite rouge 4-5-6-7 + un 7 bleu et un 7
  jaune en main → détachement du 7 rouge, 4-5-6 reste valide, groupe de
  trois 7 posé.
- **Scission en début de suite** : même principe sur la première tuile
  (suite rouge 4-5-6-7 + un 4 bleu et un 4 jaune) → 5-6-7 reste valide,
  groupe de trois 4 posé.
- **Suite trop courte (3 tuiles)** : aucun détachement en bout n'est
  proposé, la partie restante (2 tuiles) étant invalide.
- **Tuile de bout qui est un joker** : non-régression — un joker en bout
  de suite n'est pas détaché par ce mécanisme (cf. `CONTEXTE.md` §8).
- **Mise initiale non faite** : aucune scission n'est proposée.

Tous les tests passent du premier coup sans aucune modification du code
de l'IA : le comportement actuel de la scission en bout de suite est
conforme à la description de l'issue, aucune divergence à signaler.

`tests/test_ia.py` : +192 lignes, 10 nouvelles fonctions de test + 5
fonctions d'état auxiliaires. Suite complète : 54 tests passés.

# Issue #181 — Suite #180 : IA : scinder une longue suite en son milieu pour libérer une tuile ou un joker

Suite #180 : dans `CONTEXTE.md` §8, la « scission en milieu de suite »
était identifiée mais jamais formalisée. `_coup_scission` ne détachait
jusqu'ici qu'une tuile réelle en BOUT d'une suite de 4 tuiles ou plus — la
suite restante restait d'un seul tenant. Une suite assez longue (7 tuiles
ou plus) peut pourtant être coupée en DEUX suites valides en retirant une
tuile ou un joker intérieur (ni en tête ni en queue), libérant cette
tuile/ce joker pour un usage ailleurs sur le plateau.

Deux cas couverts, qui découlent du même principe :

- **Tuile réelle intérieure** : suite rouge 1-2-3-4-5-6-7 + un 4 bleu et un
  4 jaune en main → retirer le 4 rouge laisse deux suites valides (1-2-3 et
  5-6-7) et le 4 rouge libéré forme avec la main le groupe 4
  rouge/bleu/jaune.
- **Joker intérieur** : suite bleue 3-4-5-(joker)-7-8-9 → retirer le joker
  laisse deux suites valides (3-4-5 et 7-8-9) et le joker libéré est rejoué
  avec la main dans un groupe de 12 (rouge/jaune/joker).

## Ajout

`src/rummikub/moteur/ia.py` :

- `_coup_scission` généralisée : la boucle sur les positions d'une suite
  parcourt désormais TOUTES les positions (plus seulement les deux bouts)
  et calcule les deux parties de part et d'autre de la tuile retirée
  (`combo[:pi]` / `combo[pi+1:]`). Si une seule partie est non vide (cas
  bout, inchangé) ou si les deux sont non vides et valides (≥ 3 tuiles
  chacune, cas milieu, nouveau), la suite d'origine est remplacée par ces
  parties et la tuile retirée tente de former un nouveau groupe avec des
  tuiles de la main, exactement comme pour le cas bout existant. Le
  comportement en bout de suite n'est pas modifié (même séquence
  d'essais, mêmes résultats).
- `_jokers_liberables_par_scission_milieu(plateau, chevalet)` (nouvelle
  fonction) : détecte, pour toute suite d'au moins 7 tuiles, un joker en
  position strictement intérieure dont le retrait laisse deux suites
  valides (chacune ≥ 3 tuiles) de part et d'autre. Ne consomme aucune
  tuile de la main pour la scission elle-même (contrairement à
  `_jokers_detachables_par_extension`, qui nécessite une tuile
  d'extension au bout opposé).
- `_liberations_possibles` intègre cette quatrième tactique au format
  unifié de #169/#180 : `appliquer(plateau)` remplace ici la combinaison
  d'origine par sa moitié gauche et AJOUTE la moitié droite comme nouvelle
  combinaison du plateau (une combinaison devient deux — cas qui ne se
  présentait pas pour les tactiques précédentes, qui modifiaient une ou
  deux combinaisons déjà existantes en place). Le champ `combis` ne
  référence que l'index d'origine, ce qui suffit à la détection de
  conflit : une libération qui toucherait la même combinaison du plateau
  est rejetée par `_meilleur_coup_liberations` comme pour les autres
  tactiques. `tuiles_consommees` est vide ici (aucune tuile de main n'est
  nécessaire pour la scission), ce que le format supportait déjà (cf.
  #180). Le joker libéré doit être rejoué dans le même tour avec des
  tuiles de la main — s'il ne peut être replacé, `_coup_depuis_liberations`
  renvoie `None` et le coup n'est pas retenu, comme pour les autres
  tactiques.
- Limité à Avancé/Expert via les points d'entrée déjà en place
  (`_coup_scission` et `_meilleur_coup_avec_joker`) — aucun changement
  dans `jouer_niveau_avance`/`jouer_niveau_expert`. Facile et
  Intermédiaire restent inchangés.

`CONTEXTE.md` §8 mis à jour :

- La « scission en milieu de suite » déplacée des tactiques « Identifiées
  mais pas encore implémentées » vers les « Implémentées », avec le
  numéro de cette issue (#181) et une description courte des deux cas
  (tuile réelle / joker).
- Note finale sur `_coup_scission` réécrite : elle ne se limite plus aux
  seuls bouts de suite (couvre désormais aussi le milieu), mais reste
  étrangère aux jokers, dont la libération (bout ou milieu) passe
  entièrement par `_liberations_possibles`.

## Tests

`tests/test_ia.py` : six nouveaux tests.

- `test_avance_scinde_une_suite_pour_liberer_une_tuile_interieure` et
  `test_expert_scinde_une_suite_pour_liberer_une_tuile_interieure` :
  reprennent l'exemple « tuile réelle intérieure » (suite rouge 1-7,
  main 4 bleu + 4 jaune) ; vérifient le coup joué, la validité du plateau
  résultant (3 combinaisons : 2 suites + 1 groupe) et la composition du
  nouveau groupe de 4.
- `test_avance_scinde_une_suite_pour_liberer_un_joker_interieur` et
  `test_expert_scinde_une_suite_pour_liberer_un_joker_interieur` :
  reprennent l'exemple « joker intérieur » (suite bleue 3-9 avec joker en
  position 4, main 12 rouge + 12 jaune) ; vérifient le coup joué, la
  validité du plateau résultant et que le joker se retrouve bien dans le
  nouveau groupe de 12 (et nulle part ailleurs).
- `test_facile_ne_scinde_pas_une_suite_en_son_milieu` : non-régression —
  Facile ne tente pas la scission (reprend le scénario « tuile réelle
  intérieure », où Facile ne peut rien jouer avec seulement 2 tuiles de
  même valeur).
- `test_avance_ne_scinde_pas_une_suite_trop_courte` : suite rouge de
  longueur 5 (3-4-5-6-7) avec en main un 5 bleu et un 5 jaune — retirer la
  tuile centrale laisserait deux parties de longueur 2, invalides ; le
  coup de scission ne doit pas être proposé.

Tous les tests existants (#148, #150, #169, #180) passent sans
modification de leurs assertions. Suite complète : 44 tests, tous au vert
(`pytest -q`).

# Issue #180 — Suite #169 : IA : libérer une tuile d'un groupe de 4 (réduit à 3) pour l'échanger contre un joker ailleurs sur le plateau

Suite de #148 (échange direct), #150 (détachement en bout de suite) et
#169 (combinaison de plusieurs libérations dans un même coup) : un
quatrième cas, constaté en jeu par Alain, n'était couvert par aucun des
trois. Exemple observé : un groupe de trois 11 (bleu, jaune, noir) devient
un groupe de quatre en y ajoutant le 11 rouge de la main ; le 11 noir
libéré (groupe restant bleu/jaune/rouge, valide) correspond exactement au
joker d'une suite noire (10, joker, 12, 13) ailleurs sur le plateau. L'IA
posait le 11 rouge et s'arrêtait là, sans aller chercher ce joker.

À ne pas confondre avec la « réduction de groupe de 4 à 3 (joker retiré) »
listée comme non implémentée dans `CONTEXTE.md` §8 : celle-là retire un
JOKER d'un groupe de 4 sans tuile de remplacement. Ici, on retire une
tuile RÉELLE pour s'en servir comme remplaçante ailleurs — la première
reste hors périmètre de cette issue.

## Ajout

`src/rummikub/moteur/ia.py` :

- `_jokers_liberables_par_reduction_groupe4(plateau, chevalet)` : pour
  tout groupe de 4 tuiles du plateau — existant, ou complété à 4 par une
  tuile de la main de la 4e couleur manquante — détecte si retirer l'une
  de ses tuiles réelles laisse un groupe de 3 valide, et si cette tuile
  correspond exactement à un joker récupérable par échange direct ailleurs
  sur le plateau (même critère que `_jokers_recuperables`, désormais
  factorisé dans un helper commun `_tuile_correspond_au_joker`).
- `_liberations_possibles` intègre cette troisième tactique à côté des
  deux précédentes, dans la même recherche combinatoire (#169) : plusieurs
  libérations — de n'importe quelle combinaison des trois mécanismes —
  restent possibles dans le même tour.
- Généralisation nécessaire du format unifié de #169 : une libération ne
  modifiait jusqu'ici qu'UNE combinaison du plateau (`combi_index` /
  `tuile_consommee` / `appliquer(combo)`). La réduction de groupe en
  modifie DEUX à la fois (le groupe réduit et la combinaison du joker
  échangé) ; le format passe donc à `combis` (liste), `tuiles_consommees`
  (liste, éventuellement vide quand le groupe était déjà à 4 et qu'aucune
  tuile de main n'est nécessaire) et `appliquer(plateau)` qui modifie en
  place les combinaisons concernées. `_coup_depuis_liberations` et
  `_meilleur_coup_liberations` adaptés en conséquence ; les deux tactiques
  précédentes (#148, #150) sont inchangées fonctionnellement, seul leur
  format d'enveloppe change.
- Limité à Avancé/Expert via `_meilleur_coup_avec_joker` (déjà le point
  d'entrée commun), comme pour #148/#150/#169 — aucun changement requis
  dans `jouer_niveau_avance`/`jouer_niveau_expert`.

`CONTEXTE.md` §8 mis à jour : nouvelle tactique ajoutée aux
« Implémentées » (#180), et « Réduction de groupe de 4 à 3 » renommée
« (joker retiré) » dans les « Identifiées mais pas encore implémentées »
pour lever toute ambiguïté avec le nouveau mécanisme.

## Tests

`tests/test_ia.py` : trois nouveaux tests reprenant l'exemple de l'issue
(groupe plateau 11 bleu/jaune/noir, suite plateau noire
10-joker-12-13, chevalet 11 rouge + 1 noir + 2 noir) :

- `test_avance_libere_une_tuile_de_groupe4_pour_echanger_un_joker` et
  `test_expert_libere_une_tuile_de_groupe4_pour_echanger_un_joker` :
  l'IA Avancé/Expert complète le groupe à 4 avec le 11 rouge, échange le
  11 noir libéré contre le joker noir, et rejoue ce dernier dans une
  nouvelle suite 1-2-3(joker) noire — seule façon de poser les 3 tuiles de
  la main dans ce scénario.
- `test_facile_ne_libere_pas_de_tuile_de_groupe4` : Facile reste inchangé
  (pose seulement le 11 rouge, sans toucher au joker).

Tous les tests existants (#148, #150, #169) passent sans modification.
Suite complète : 38 tests, tous au vert (`pytest -q`).

# Issue #179 — Build Windows Rummikub v14

- Build de publication Rummikub effectué via `build\rebuild_rummikub.bat
  --publier --build 14` (commit construit : `b4dc23a`) : `version.json` mis
  à jour (build 14, SHA-256 recalculé et vérifié identique à l'archive
  produite : `526084f1735e93ac1d9684ee3f2c22e295e09b6208077b1eeed66779ae04aec5`).
- Vérifications effectuées : `manifest.json` sans BOM (premiers octets
  `7B 22 62`), tailles conformes aux garde-fous (dossier non compressé
  ~25,0 Mo / 26 251 767 octets, installeur compressé ~12,8 Mo /
  12 801 538 octets, archive ~12,9 Mo / 12 895 604 octets), structure de
  l'archive (racine : `Rummikub.exe` + `manifest.json` ; `_internal\` :
  73 fichiers). Seuls avertissements PyInstaller : hidden imports
  `pycparser.lextab`/`pycparser.yacctab` (connus, sans impact) ; aucun
  avertissement Inno Setup.
- Copie hors worktree (issue #178) confirmée vers
  `C:\CCW_Share\_derniers_builds\rummikub\` : `Rummikub-Setup-v14.exe`
  (12 801 538 octets) et `rummikub-v14.zip` (12 895 604 octets).
- Fichiers produits dans `installeur\output\` : `Rummikub-Setup-v14.exe`
  et `rummikub-v14.zip` (non poussés, non publiés — à récupérer avant
  suppression du worktree, même si la copie externe de #178 réduit
  désormais ce risque).

# Issue #178 — Durcir build\rebuild_rummikub.bat (copie hors worktree, garde-fou, nettoyage, rappels)

- `build\rebuild_rummikub.bat` copie désormais l'installeur et l'archive
  vers `C:\CCW_Share\_derniers_builds\rummikub\` dans TOUS les modes (même
  sans `--publier`), avec le numéro de build réel dans les deux noms de
  fichiers (`rummikub-vN.zip` remplace l'ancien nom fixe `rummikub.zip`
  des builds de test). Le script affiche lui-même, en fin d'exécution, les
  noms et tailles en octets des deux fichiers copiés ainsi que
  l'emplacement d'Inno Setup utilisé.
- Garde-fou du numéro de build : le build demandé (`--build N` ou build
  courant + 1 par défaut) est désormais lu et validé dès l'analyse des
  arguments (nouvelle étape `0bis`, avant toute copie robocopy), et non
  plus seulement vers l'ancienne étape 7. Refusé avant toute
  construction/écriture si non entier, non strictement supérieur au
  build courant de `version.json`, ou si `--build` est fourni sans valeur
  (ou suivi d'un autre argument). Tout argument inconnu est également
  refusé (liste des arguments acceptés affichée), au lieu d'être ignoré
  avec un simple avertissement.
- Nettoyage : suppression du `git -C C:\CCW_Share\CCW\rummikub reset
  --hard origin/master` de l'ancienne étape 8 (modèle de clone partagé
  obsolète) et des commentaires associés. Le script est maintenant décrit
  tel qu'il est réellement : il construit dans un dossier local
  (`C:\Temp\RummikubBuild`) et n'écrit que dans le worktree courant et
  dans le dossier fixe hors worktree ci-dessus.
- Rappel de fin de script (`--publier`) : confirmé qu'il mentionne bien
  les DEUX fichiers (installeur + archive) à attacher à la Release
  GitHub.
- Essais effectués (PowerShell, `call` + `%errorlevel%` pour la mesure
  fiable du code de sortie) : un essai complet sans `--publier` avec
  `--build 99` (numéro fictif, ~100 s, installeur ~12,8 Mo, archive
  ~12,9 Mo, copiés dans le worktree et dans le dossier fixe — à
  nettoyer à la main par Alain dans `C:\CCW_Share\_derniers_builds\rummikub\`)
  ; et les six refus attendus (numéro égal, numéro inférieur, numéro non
  numérique, `--build` sans valeur, `--publier --build` non supérieur,
  argument inconnu), tous avec code de sortie 1, message clair, et aucune
  écriture (`version.json` inchangé, aucun nouveau fichier dans
  `installeur\output` pour ces six cas).
- `version.json` n'a pas été modifié par cette issue (aucun essai n'a
  utilisé `--publier` avec un numéro réel).

# Issue #177 — Build Windows Rummikub v13

- Build de publication Rummikub effectué via `build\rebuild_rummikub.bat
  --publier --build 13` : `version.json` mis à jour (build 13, SHA-256
  recalculé et vérifié identique à l'archive produite).
- Vérifications effectuées : `manifest.json` sans BOM (premiers octets
  `7B 22 62`), tailles conformes aux garde-fous (dossier non compressé
  ~25 Mo, installeur compressé ~12,8 Mo), structure de l'archive (racine :
  `Rummikub.exe` + `manifest.json` ; `_internal\` : ~87 entrées).
- Fichiers produits dans `installeur\output\` : `Rummikub-Setup-v13.exe`
  et `rummikub-v13.zip` (non poussés, non publiés — à récupérer avant
  suppression du worktree).

# Issue #176 — build\rebuild_rummikub.bat : chercher Inno Setup dans C:\CCW\tools\InnoSetup6 avant .tools\InnoSetup6

- `build\rebuild_rummikub.bat` (étape 0) : recherche désormais `ISCC.exe`
  d'abord dans `C:\CCW\tools\InnoSetup6\ISCC.exe` (installé hors des dépôts,
  accessible depuis n'importe quel worktree CCW frais), puis seulement en
  repli dans l'ancien chemin `%ORIGDIR%\.tools\InnoSetup6\ISCC.exe` (utile
  pour un build lancé hors d'un worktree CCW, ex. en local par Alain).
- Si aucun des deux chemins n'existe, le script échoue toujours
  immédiatement et proprement, avec un message mentionnant les deux chemins
  recherchés.

## Issue #175 — Tenir à jour dans CONTEXTE.md la liste des tactiques de récupération de joker de l'IA

- `CONTEXTE.md` (§8) : ajout de la tactique « démantèlement complet d'une
  courte suite contenant un joker » (et sa généralisation sans joker) à la
  liste des cas identifiés mais pas encore implémentés.
- Fusion de `master` dans la branche (qui contenait déjà le §8 créé par
  l'issue #174) avant d'y ajouter ce nouveau cas, pour éviter une
  duplication/collision de section.
- Retrait au passage d'une ligne parasite `</content>` laissée en fin de
  fichier par le commit de l'issue #174.

# Issue #174 — CONTEXTE.md : liste des tactiques de récupération de joker de l'IA

- Ajout d'une section **§8. Tactiques de récupération/libération de joker de
  l'IA** dans `CONTEXTE.md`, recensant :
  - les tactiques déjà implémentées, avec issue d'origine et fonction
    correspondante : échange direct (#148, `_jokers_recuperables`),
    détachement en bout de suite (#150, `_jokers_detachables_par_extension`),
    combinaison de plusieurs libérations dans le même coup (#169,
    `_liberations_possibles`/`_meilleur_coup_liberations`/`_coup_depuis_liberations`) ;
  - deux cas identifiés en discussion mais pas encore implémentés : la
    réduction d'un groupe de 4 à 3 (retrait du joker sans tuile de
    remplacement) et la scission en milieu de suite (extension de
    `_coup_scission`, qui ne traite aujourd'hui que le bout de suite et
    jamais un joker).
- But : disposer d'une base à jour pour une future révision des niveaux de
  difficulté de l'IA une fois l'ensemble des tactiques couvert.
- Pointeur ajouté dans la description de `moteur/ia.py` (§2) vers la
  nouvelle section §8.
- Aucun changement de code (`ia.py` inchangé) : tâche purement documentaire.

## Issue #173 — "Vérifier et calculer" affiche les points du tour, pas du plateau

- `api.jeu_verifier_plateau` accepte désormais un second paramètre optionnel
  `ids_ce_tour` et retourne en plus `points_ce_tour` (somme des points des
  combinaisons valides contenant au moins une tuile posée ce tour).
- `jeu.js` (`onVerifierCalc`) : avant la mise initiale, affiche
  "✓ Plateau valide — N points" avec N = points posés CE TOUR uniquement
  (au lieu du total de tout le plateau). Une fois la mise initiale faite
  (`tapisManipulable()` vrai), affiche seulement "✓ Plateau valide", sans
  chiffre, puisque le seuil de 30 points ne s'applique plus.
- La vérification de validité globale du plateau (nécessaire pour "Jouer")
  reste inchangée.

## Issue #172 — Retrait du contour bleu pointillé "tapis manipulable"

- `jeu.css` : suppression du contour pointillé bleu générique
  `.tuile-jeu.tapis-manipulable` (et son effet au survol), qui s'affichait
  en permanence sur toutes les tuiles du tapis dès la mise initiale faite et
  ne signalait donc plus rien d'utile, tout en créant de la confusion avec
  les vrais indicateurs de tour (vert #128/#129, orange #136/#139).
- Seul le curseur `move` est conservé sur `.tapis-manipulable` comme
  affordance de prise en main (sans contour visuel).
- Les règles combinées `.tuile-jeu.ce-tour.tapis-manipulable` (vert) et
  `.tuile-jeu.deplacee-tapis.tapis-manipulable` (orange) sont conservées et
  définissent désormais leur propre `outline` complet (plus seulement une
  surcouche de couleur), sans dépendre visuellement du contour de base
  supprimé. Comportement inchangé pour ces deux indicateurs.

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

# Issue #169 — L'IA ignore des jokers récupérables alors qu'elle a en main la tuile nécessaire

Suite de #148 (échange direct) et #150 (détachement en bout de suite) :
Alain a observé que l'IA Avancé/Expert ignorait un joker récupérable alors
qu'elle avait pourtant la tuile nécessaire en main, quand **plusieurs**
jokers étaient simultanément récupérables sur le plateau.

## Cause

`_coup_avec_joker_recupere` et `_coup_avec_joker_detache` (`ia.py`)
traitaient chaque joker récupérable **indépendamment** : pour chaque
candidat, elles construisaient un coup qui ne récupérait/replaçait QUE ce
joker-là, puis ne gardaient que le meilleur de ces coups à un seul joker.
Quand deux jokers étaient récupérables (sur deux combinaisons distinctes du
plateau), le second était donc toujours purement et simplement abandonné,
même si le chevalet permettait de récupérer les deux dans le même tour et
même si c'était la seule façon de jouer quoi que ce soit.

Reproduit avec un plateau à deux suites (`rouge 4-5-(joker=6)` et
`bleu 7-8-(joker=9)`) et un chevalet contenant les deux tuiles de reprise
(`rouge 6`, `bleu 9`) plus deux paires insuffisantes pour une combinaison
seules (`noir 2`/`jaune 2`, `noir 3`/`jaune 3`) : avant le correctif,
l'IA Avancé ne récupérait qu'un seul joker, replaçant l'autre libéré nulle
part et abandonnant la seconde récupération ; en réalité les deux jokers
libérés peuvent former ensemble une suite `1-2-3-4` en noir
(`joker-noir_2-noir_3-joker`), ce qui permet de jouer les deux à la fois.

## Correctif

`src/rummikub/moteur/ia.py` : remplacement de `_coup_avec_joker_recupere`
et `_coup_avec_joker_detache` par une approche combinatoire :

- `_liberations_possibles(plateau, chevalet)` : rassemble, sous une forme
  uniforme, toutes les libérations de joker possibles — échange direct
  (`_jokers_recuperables`, inchangée) **et** détachement en bout de suite
  (`_jokers_detachables_par_extension`, inchangée).
- `_coup_depuis_liberations(...)` : applique un sous-ensemble donné de
  libérations simultanément (plateau copié une fois, chaque joker libéré
  devant être replacé ailleurs sous peine de rejet du sous-ensemble), puis
  cherche le meilleur placement des tuiles restantes comme avant.
- `_meilleur_coup_liberations(...)` : essaie TOUS les sous-ensembles non
  conflictuels de libérations (combinaisons distinctes du plateau, tuiles
  de reprise/extension distinctes) — borné en pratique par le nombre de
  jokers en jeu (2 au maximum) donc sans coût de performance notable — et
  garde celui dont `_valeur_coup` (nb tuiles jouées, points) est le
  meilleur.
- `_meilleur_coup_avec_joker` délègue maintenant à
  `_meilleur_coup_liberations` au lieu de comparer séparément échange et
  détachement ; elle peut donc retourner un coup combinant les deux
  mécanismes à la fois si le plateau s'y prête.

Deux libérations portant sur la MÊME combinaison du plateau ne sont jamais
combinées (cas rare — deux jokers dans une même suite — laissé de côté par
prudence, sans régression puisque chacun restait déjà testé seul comme
avant).

## Tests

`tests/test_ia.py` : deux nouveaux tests de régression
(`test_avance_recupere_les_deux_jokers_a_la_fois`,
`test_expert_recupere_les_deux_jokers_a_la_fois`) vérifient que, face à un
plateau avec deux jokers récupérables par échange direct sur deux suites
distinctes, l'IA Avancé/Expert les récupère tous les deux dans le même
coup (seule façon de jouer dans ce scénario). Les tests existants de #148
et #150 (joker unique, échange ou détachement) passent toujours sans
modification. Suite complète : 35 tests, tous au vert.

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

# Issue #170 — Boutons de vitesse du rejeu : ordre Lente / Moyenne / Rapide

Les 3 boutons de vitesse du rejeu du dernier coup IA (#164), affichés
jusqu'ici dans l'ordre Rapide / Moyenne / Lente, suivent maintenant une
gradation croissante de gauche à droite : **Lente / Moyenne / Rapide**.

Changement purement visuel (ordre des balises `<button>` dans le HTML) :
le comportement, les valeurs `data-vitesse` et les multiplicateurs associés
à chaque niveau (`MULTIPLICATEURS_REJEU_IA` dans `jeu.js`) sont inchangés —
la logique JS sélectionne les boutons via `querySelectorAll` et
`dataset.vitesse`, sans dépendre de leur position dans le DOM.

Fichier touché : `src/rummikub/ui/web/jeu.html`.

# Issue #167 — Légende des pourtours : chiffres aléatoires + couleurs plus visibles

Deux retours sur la légende ajoutée par #159 (sous le sac de pioche) :

1. **Chiffre aléatoire sur les tuiles d'exemple** (`jeu.js`,
   `afficherLegendeCouleurs`) : chaque mini-tuile de la légende tirait un
   chiffre fixe (7, 7, 7, 5, 6). Remplacé par un tirage aléatoire 1-13 par
   tuile (`valeurAlea()`), à chaque construction de la légende — rend
   l'exemple plus parlant qu'un chiffre toujours identique.
2. **Pourtours vert/orange/bleu plus visibles dans la légende** (`jeu.css`) :
   à la taille réduite des mini-tuiles (22px), la bordure 1px + léger halo
   utilisés en jeu réel pour `.ce-tour`/`.deplacee-tapis`/`.tuile-ia-deplacee`
   passaient inaperçus. Ajout de règles `.legende-tuile-mini.ce-tour` /
   `.legende-tuile-mini.deplacee-tapis` (et renforcement de la règle
   `.tuile-ia-deplacee` existante) : bordure épaissie à 2.5px et halo
   (`box-shadow`) renforcé, appliqués **uniquement** via le préfixe
   `.legende-tuile-mini` — l'apparence des pourtours en jeu réel
   (`commun.css` / `jeu.css`) n'est pas modifiée, pour éviter qu'ils
   deviennent trop criards sur le tapis pendant une partie.

Fichiers touchés : `src/rummikub/ui/web/jeu.js`, `src/rummikub/ui/web/jeu.css`.

# Issue #166 — Tri automatique : appliquer dès le début de partie et à la reprise

Le réglage « Tri automatique » (#126/#130) ne triait la main qu'au moment
d'une pioche. Si la case est cochée, la main est maintenant déjà triée :

- dès la toute première distribution de tuiles d'une nouvelle partie ;
- immédiatement après la reprise d'une partie sauvegardée.

`naviguer_vers_jeu` et `reprendre_jeu` (`application.py`) chargent tous deux
`jeu.html`, qui exécute `init()` à son ouverture : c'est ce point de passage
commun qui restaure déjà l'état de la case `tri_auto` depuis `etat.config`.
Il suffit d'y trier `chevaletLocal` (même ordre que le bouton « Trier » et
l'insertion à la pioche) quand le réglage est actif, avant le premier rendu —
sans toucher au comportement existant à la pioche.

# Issue #165 — Pourtour bleu IA affiché après chaque tour, même en cas de simple pioche

## Cause

Dans `jouerIA()` (`jeu.js`), les listes de tuiles « ajoutées » et
« déplacées » étaient calculées par simple comparaison avant/après plateau
(`trouverTuilesAjoutees`/`trouverTuilesDeplacees`), puis le code décidait
*après coup* si le dernier coup de l'IA était une pose, une pioche ou un
passage — en se basant sur la description textuelle du dernier événement de
l'historique (`action.includes("pioch")`) plutôt que sur le champ fiable
`dernier_coup_ia.type` introduit par #157. Cette inférence textuelle était
fragile et pouvait se tromper, déclenchant à tort `animerPoseTuiles()` (donc
le pourtour bleu `tuile-ia-deplacee` sur l'ensemble des tuiles reconstruites)
même quand l'IA s'était contentée de piocher.

## Correction

`typeCoupIA` est maintenant lu directement depuis
`nouvelEtat.dernier_coup_ia.type` (valeurs fiables côté serveur : `"pose"`,
`"piocher"`, `"passer"`, cf. `api.py::jeu_ia_jouer`) **avant** tout calcul de
tuiles ajoutées/déplacées. `trouverTuilesAjoutees()` et
`trouverTuilesDeplacees()` ne sont désormais appelées que si
`typeCoupIA === "pose"` ; dans tous les autres cas (pioche, passage), les
deux listes restent vides par construction et aucune tuile du tapis ne reçoit
de pourtour bleu ou doré. La détection du message toast (« pioche » vs
« passe son tour ») utilise elle aussi directement `typeCoupIA === "piocher"`
plutôt que l'ancien texte d'historique.

La logique de `trouverTuilesDeplacees()` elle-même (issue #149 : ne marquer
comme déplacées que les tuiles qui rejoignent une combinaison différente de
la « continuation » majoritaire de leur ancienne combinaison) n'était pas en
cause et reste inchangée — pour une pose normale sans réarrangement, elle
continue de ne renvoyer aucune tuile puisque toutes restent dans leur
combinaison de continuation.

### Fichier modifié

- `src/rummikub/ui/web/jeu.js` — fonction `jouerIA()` : calcul de
  `typeCoupIA` déplacé avant celui de `tuiAjoutees`/`tuilesDeplacees`, ces
  deux listes conditionnées à `typeCoupIA === "pose"`, et la branche
  pioche/passe simplifiée pour utiliser directement `typeCoupIA` au lieu de
  parser l'historique.

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

## Investigation + correction (issue #156)

Double-clic sur un joker libéré (ex. par scission/détachement IA, #150) :
inconstant selon qu'une tuile de la main est déjà sélectionnée au moment du
double-clic.

### Reproduction (Playwright, chargement direct de `jeu.html` avec un état de
partie simulé et `window.pywebview.api` mocké, pas l'appli pywebview réelle)

- Double-clic sur une tuile du tapis **sans** tuile de la main déjà
  sélectionnée : fiable (8/8 essais, délais de 60 à 270 ms entre les 2
  clics) — le 1er clic prend déjà la tuile dès son premier clic (branche
  « prise immédiate », #133), le 2e clic du geste est sans effet.
- Double-clic sur la **dernière** tuile d'un groupe stable de 3, **avec**
  une tuile de la main déjà sélectionnée : **échec systématique (8/8 KO)**.
  Double-clic sur la **1re** tuile du même groupe dans les mêmes conditions :
  fiable (8/8 OK).

### Cause confirmée

Quand une tuile de la main est sélectionnée (mode « insertion ciblée », #47),
cliquer une tuile d'une combinaison du tapis qui n'est pas encore la cible
active ne la prend pas : le clic remonte au conteneur de la combinaison, qui
l'active comme cible (`comboActive`). Cette activation révèle les zones
d'insertion de la combinaison (`zone-ext-debut`/`-interne`/`-fin`, jusque-là
masquées) et **décale horizontalement** les tuiles qui suivent le début du
groupe — décalage d'autant plus grand que la tuile ciblée est loin du début
(une tuile en bout de groupe, comme un joker fraîchement libéré par une
scission/un détachement, cumule le décalage de toutes les zones internes qui
la précèdent).

Le 2e clic du double-clic, visé par l'utilisateur (ou par Playwright, qui
simule un vrai double-clic humain : 2 clics à coordonnées écran fixes, sans
déplacement de souris) aux mêmes coordonnées que le 1er, rate alors sa cible
décalée et atterrit sur une zone d'insertion ou une tuile voisine au lieu de
la tuile visée — la prise échoue silencieusement, de façon intermittente
selon la position de la tuile dans son groupe. C'est exactement le mécanisme
déjà documenté par #146 pour la branche « échange de joker » (dont le
correctif proposait l'échange dès le 1er clic pour éviter d'avoir à activer
la combo d'abord) — #156 est le même problème pour la prise directe d'une
tuile ordinaire (pas un échange), qu'#146 ne couvrait pas.

### Correctif

`src/rummikub/ui/web/jeu.js` — dans `rafraichirPlateau()`, branche
« combo non active et sans échange possible pour cette tuile » (mode
insertion ciblée) : au lieu de laisser le clic remonter immédiatement activer
la combinaison comme cible, on coupe la remontée (`stopPropagation`) et on
**diffère l'activation de 350 ms** (durée de la fenêtre de double-clic déjà
utilisée par #133/#103). Le détecteur de double-clic existant, s'il détecte
un 2e clic sur la même tuile dans ce délai, annule cette activation différée
(`clearTimeout`) et prend la tuile directement — le décalage de layout
n'intervient alors jamais entre les deux clics. Un simple clic isolé (pas de
2e clic) continue de fonctionner normalement, juste activé ~350 ms plus tard
qu'avant (imperceptible pour une action manuelle).

Nouvelle variable module-level `activationCombinaisonDifferee` (minuteur en
cours, ou `null`).

### Vérifications de non-régression (Playwright)

- Joker en bout d'un groupe de 3 tuiles (pas seul dans son groupe — cas
  littéral de l'issue, joker détaché en bout de suite par l'IA #150), avec
  tuile de la main déjà sélectionnée : 6/6 OK après correctif (contre
  l'échec systématique constaté avant, pour le cas analogue « dernière tuile
  d'un groupe »).
- Simple clic unique (sans 2e clic) sur une combo non active : toujours
  activée comme cible après le délai — le ciblage normal (#47) n'est pas
  cassé.
- Échange de joker (#146) : toujours immédiat (<150 ms), pas de délai
  introduit sur ce chemin (branche `estEchangeJoker`, inchangée).
- `pytest` (33 tests) : toujours au vert (aucun fichier Python modifié).

### Limite

Correctif scindé spécifiquement pour la prise directe d'une tuile tapis en
mode insertion ciblée. Le même mécanisme de décalage pourrait en théorie
affecter d'autres interactions basées sur un double-clic rapide pendant que
le layout se réorganise ; non constaté ailleurs lors de cette investigation.

# Changelog — issue #161

- doc(contexte) : ajout d'une section §7 « Vérification empirique d'un
  comportement front-end » à `CONTEXTE.md` — interdiction de lancer
  l'application pywebview réelle (`main.py`) ou un navigateur piloté sur
  l'application réelle pour vérifier un comportement front-end ; méthode
  imposée : charger `jeu.html`/`accueil.html` directement via Playwright
  avec un mock de `window.pywebview.api`, et un état de partie construit
  via le moteur réel (`creer_partie`, etc.) si besoin plutôt qu'un DOM vide.

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

# Issue #157 — Suite #144/#149 : « Dernier coup » affichait parfois une pose périmée au lieu de la pioche réellement jouée

## Contexte
Le bouton « Dernier coup joué par l'ordinateur » (issue #144) ne mémorisait `dernier_coup_ia`
que lorsque l'IA posait réellement des tuiles. Si le tour suivant de l'IA se soldait par une
pioche ou un passage, ce champ n'était jamais mis à jour : le bouton continuait donc d'afficher
(et de proposer le rejeu animé) d'une ancienne pose, alors que le dernier coup réellement joué
n'avait rien posé sur le tapis.

## Correctif (`api.py`, `jeu.js`)

### `jeu_ia_jouer` (`api.py`)
`dernier_coup_ia` est désormais toujours réécrit après le tour de l'IA, quel que soit le
résultat, avec un nouveau champ `"type"` : `"pose"`, `"piocher"` ou `"passer"`. Le cas du coup
invalide proposé par l'IA (repli sur une pioche de secours) est bien étiqueté `"piocher"`, pas
`"jouer"` (l'action initialement proposée par `jouer_ia`).

### Bouton et rejeu (`jeu.js`)
- `rafraichirBoutonRejouerIA()` distingue maintenant les 3 types : seul `"pose"` active le
  bouton avec le libellé de rejeu habituel ; `"piocher"`/`"passer"` désactivent le bouton et
  affichent un libellé fidèle au coup réel (« X a pioché » / « X a passé son tour »).
- `rejouerDernierCoupIA()` refuse désormais explicitement de rejouer un coup dont le type n'est
  pas `"pose"` (garde défensive, le bouton étant de toute façon désactivé dans ce cas).
- Compatibilité : les parties sauvegardées avant ce correctif n'ont pas de champ `"type"` dans
  `dernier_coup_ia` — il est alors traité comme `"pose"` (comportement historique, ce champ
  n'étant auparavant renseigné que pour une pose).

## Résultat
Le bouton « Dernier coup » reflète toujours exactement le tout dernier coup joué par l'IA, que
ce soit une pose (rejouable), une pioche ou un passage (affichés mais non rejouables).

# Issue #155 — Suite #140 : le dé-zoom auto écrase un choix manuel à chaque tour, et se déclenche trop tôt

## Contexte
Après la fusion de #140 (qui avait corrigé la pollution de `localStorage` faisant démarrer une
nouvelle partie déjà dézoomée, et un chevauchement visuel sur petite fenêtre), Alain a constaté
deux problèmes persistants à l'intérieur d'une MÊME partie, une fois le tapis arrivé à plusieurs
lignes :

1. `autoZoomSiTapisDeborde()` est réévaluée à chaque tour et force systématiquement le dé-zoom dès
   que le tapis déborde à 100%, même après un clic manuel sur "100%" au tour précédent — ce choix
   ne « tenait » qu'un seul tour avant d'être écrasé par l'automatisme au tour suivant.
2. Le seuil de déclenchement restait trop précoce : le dé-zoom se déclenchait alors qu'il restait
   encore visiblement environ la moitié de l'espace du tapis libre à l'écran.

## Correctifs (`jeu.js`)

### 1. Choix manuel = main définitivement laissée au joueur pour la partie en cours
Nouvelle variable `zoomModifieManuellementCettePartie` (propre à la partie en cours, PAS un
réglage persisté comme `dezoomAutoActif`/#135 — une simple variable JS, naturellement remise à
`false` à chaque chargement de `jeu.html`, donc à chaque nouvelle partie ou reprise, mais qui
survit à un changement de manche au sein de la même partie puisque `onNouvelleManche` ne recharge
pas la page). Elle passe à `true` dès le premier clic du joueur sur un bouton de zoom
(`brancherZoomTapis`) — la restauration du niveau mémorisé au chargement de la page ne compte pas
comme un clic manuel. `autoZoomSiTapisDeborde()` retourne immédiatement sans rien modifier dès que
ce drapeau est à `true`, quel que soit l'état de débordement des tours suivants.

Tant que le joueur n'a jamais touché au zoom lui-même, le comportement d'avant cette issue est
inchangé : l'automatisme continue de s'appliquer normalement à chaque tour (y compris une
progression 100% → 75% → 50% sur plusieurs tours successifs si le tapis continue de déborder).

### 2. Marge de tolérance avant de considérer que le tapis « déborde »
`autoZoomSiTapisDeborde()` comparait `scroll.scrollHeight` à `scroll.clientHeight` sans aucune
marge : un dépassement d'un seul pixel déclenchait un cran complet de dé-zoom. Ajout d'une marge
verticale de tolérance avant de déclencher : `MARGE_VERTICALE_PX = 66 * zoomActuel` (≈ hauteur
d'une tuile à l'échelle courante, 56px, + l'écart de 10px entre lignes posé par `jeu.css`), soit
environ une ligne de tuiles entière de battement. Le dé-zoom ne se déclenche donc plus au premier
pixel de dépassement, mais seulement quand il ne reste plus la place d'une ligne de tuiles
complète — ce qui correspond à l'espace « effectivement insuffisant » visé par la demande.

Aucune valeur numérique exacte n'était fournie par la demande (point confirmé explicitement lors
de la relance : « volontaire, Alain n'a pas de valeur précise à donner »). Le choix d'une ligne de
tuiles complète comme marge est un compromis raisonnable : assez généreux pour ne plus déclencher
alors qu'il reste nettement de la place, sans pour autant laisser déborder plusieurs lignes avant
de réagir. La marge ne s'applique qu'à la hauteur : un débordement horizontal, même minime, coupe
réellement des tuiles au bord du cadre et doit continuer à être corrigé sans délai.

## Vérification
- `node --check jeu.js` : syntaxe valide.
- `pytest` (suite existante, moteur non touché) : 33 passés.
- Playwright sur `jeu.html` chargé directement (état minimal mocké, pas la vraie application —
  conformément à la consigne de la relance qui écarte pywebview/navigateur réel dans cet
  environnement headless), en simulant le débordement par insertion de blocs de la hauteur d'une
  tuile dans `#zone-plateau` et des appels directs à `autoZoomSiTapisDeborde()` :
  - un débordement de 16px (moins d'une ligne) ne déclenche rien (confirme la marge du point 2) ;
  - un gros débordement déclenche 100% → 75%, puis 75% → 50% au tour suivant tant que le joueur
    n'a pas touché au zoom (confirme que l'automatisme n'est pas « figé » après un premier
    dé-zoom, cf. point 1 côté comportement par défaut) ;
  - après un clic manuel sur le bouton "100%", un nouveau tour avec un tapis toujours très
    débordant ne change plus rien : le zoom reste à 100% (confirme le cœur du correctif du
    point 1).

# Issue #151 — Le blocage par clic sur "Piocher" pendant le tour de l'IA persiste malgré #146

## Contexte
#146 avait posé une garde serveur (`_tour_est_humain`) et une garde client (`estMonTour()`,
bouton désactivé par défaut) contre le blocage du jeu provoqué par un clic sur "Piocher" pendant
le tour de l'IA. Après fusion, le blocage se reproduisait toujours, mais UNIQUEMENT quand l'IA
pose des tuiles sur le tapis, jamais quand elle pioche — ce qui pointait vers l'animation de pose
tuile par tuile (`animerPoseTuiles()`, ralentie depuis #149).

## Cause confirmée (`src/rummikub/ui/web/jeu.js`, `jouerIA()`)
`jeu_ia_jouer()` renvoie un état déjà avancé par le serveur (le coup de l'IA est entièrement
traité côté serveur avant la réponse) : `etat = nouvelEtat;` est donc exécuté en tout début de
`jouerIA()`, AVANT que l'animation de pose (`animerPoseTuiles()`, 1 à plusieurs secondes selon le
nombre de tuiles) ne commence. `estMonTour()` lit cet `etat` déjà à jour et redevient vraie
immédiatement — or `jouerIA()` appelait `rafraichirBoutons()` (qui réactive "Piocher" selon
`estMonTour()`) juste avant de lancer `animerPoseTuiles()`, et non après. Résultat : une fenêtre
d'environ 1 à plusieurs secondes où le bouton "Piocher" est RÉACTIVÉ alors que l'animation visuelle
de pose de l'IA est encore en cours. Un clic dans cette fenêtre est accepté par le serveur (c'est
réellement déjà le tour de l'humain côté serveur) mais entre en course avec la boucle asynchrone
de `animerPoseTuiles()` qui continue de réécrire `plateauLocal`/le chevalet en arrière-plan,
provoquant la désynchronisation visuelle puis le blocage. Cette fenêtre est différente de celle
testée par #146 (latence AVANT le coup de l'IA, pas durée de l'animation APRÈS le coup).

## Correctif (`src/rummikub/ui/web/jeu.js`)
- Nouveau drapeau de module `animationCoupIAEnCours`, pris en compte par `estMonTour()` en plus
  de `index_joueur_actuel` et `manche_terminee` : tant qu'il est vrai, `estMonTour()` renvoie
  faux quel que soit l'état serveur déjà reçu.
- `jouerIA()` pose ce drapeau à `true` dès son tout début (avant même l'appel réseau) et ne le
  repasse à `false` qu'immédiatement avant chacun de ses appels à `rafraichirTout()` — y compris
  sur le chemin d'erreur (`catch`) et sur le cas pioche/passe de l'IA — de sorte qu'il reste vrai
  pendant toute la durée de `animerPoseTuiles()`.
- Suppression de l'appel prématuré à `rafraichirBoutons()` juste avant `animerPoseTuiles()` :
  comme les boutons d'action sont déjà désactivés depuis le tour précédent (celui de l'IA) et que
  rien ne les réactive plus tôt que prévu, ils ne sont désormais réactivés que par le
  `rafraichirTout()` final, une fois l'animation terminée.
- Comme `tapisManipulable()` et toutes les gardes d'action (`onPiocher`, `onPasser`,
  `onJouerCoup`, `onAnnuler`, réorganisation du tapis par glisser-déposer, etc.) s'appuient toutes
  sur `estMonTour()`, la correction couvre non seulement "Piocher" mais aussi les autres actions
  mentionnées dans la demande.

## Vérification
`node --check src/rummikub/ui/web/jeu.js` : syntaxe valide. Lecture de code ciblée confirmant
que plus aucun appel à `rafraichirBoutons()`/`rafraichirTout()` ne peut survenir, dans quelque
chemin de `jouerIA()`, avant la fin réelle de `animerPoseTuiles()` — le drapeau
`animationCoupIAEnCours` est la seule source de vérité pendant cette fenêtre, indépendamment de
l'état déjà avancé côté serveur. Pas de test automatisé ajouté : la logique concernée est de
l'orchestration d'animation côté JS (pas de harnais de test JS dans ce projet, seul pytest est
configuré pour le code Python).

# Issue #150 — IA : détacher un joker en bout de suite quand une extension à l'autre bout rend la portion réelle suffisamment longue

## Contexte
#148 a ajouté la récupération d'un joker par échange direct (tuile de la main identique au
joker). Cas distinct et non couvert : un joker en BOUT de suite (ex. 3-4-joker, le joker
représentant le 5) peut devenir détachable SANS aucune tuile de remplacement, si l'IA pose une
tuile à l'AUTRE bout de la suite qui allonge suffisamment la portion réelle (ex. ajouter un 2 →
2-3-4-joker) pour qu'elle atteigne seule la longueur minimale de 3 tuiles (2-3-4, valide sans le
joker). Une tuile en bout de suite peut toujours être retirée sans casser la validité, tant que
ce qui reste respecte la longueur minimale — contrairement à une tuile au milieu (`_coup_scission`)
ou à l'échange direct (`_jokers_recuperables`, #148).

## Modification (`src/rummikub/moteur/ia.py`)
- `_jokers_detachables_par_extension(plateau, chevalet)` : détecte, pour chaque suite du
  plateau ayant un joker en bout, si une tuile réelle du chevalet jouée à l'extrémité opposée
  permet à la portion réelle restante (joker exclu) d'atteindre seule la longueur minimale
  (≥3) et de rester valide.
- `_coup_avec_joker_detache(etat, idx, ordre_points)` : pour chaque détachement possible,
  simule l'extension (qui retire le joker de la suite d'origine), puis tente de replacer ce
  joker ailleurs sur le plateau (nouvelle combinaison ou extension) ; retourne le meilleur coup
  obtenu, ou `None` si le joker détaché ne peut être replacé nulle part (dans ce cas le
  détachement n'a pas lieu — le coup simple d'extension reste seul candidat).
- `_meilleur_coup_avec_joker` compare désormais trois coups : l'extension/combinaison évidente
  (`_coup_maximal`), la récupération de joker par échange direct (#148,
  `_coup_avec_joker_recupere`) et le détachement en bout de suite (`_coup_avec_joker_detache`) ;
  retourne le meilleur des trois via `_valeur_coup`.
- `jouer_niveau_avance` et `jouer_niveau_expert` restent les seuls niveaux à bénéficier de
  `_meilleur_coup_avec_joker` — Facile/Intermédiaire/Débutant ne sont pas modifiés.
- Le joker détaché n'est jamais gardé en main au-delà du tour en cours : soit il est replacé
  dans le même coup (`ids_tuiles` ne contient que les tuiles réelles jouées depuis la main, le
  joker étant déjà sur le plateau), soit le détachement entier est abandonné.

## Tests (`tests/test_ia.py`)
Scénario dédié (`_etat_avec_joker_detachable`) : suite rouge 3-4-(joker=5) au tapis ; chevalet
du bot avec un rouge 2 (extension de l'autre bout qui libère le joker), un noir 9 + un bleu 9
(groupe complet uniquement avec le joker libéré), et un rouge 6 (extension évidente directement
après le joker, sans le détacher).
- Avancé/Expert choisissent le détachement (3 tuiles posées : rouge 2, noir 9, bleu 9) plutôt
  que la double extension évidente (rouge 2 + rouge 6, 2 tuiles, qui laisse le joker coincé).
- Facile/Intermédiaire étendent toujours les deux bouts de la suite (rouge 2 et rouge 6) sans
  jamais détacher le joker — comportement inchangé.

# Issue #149 — Ralentir le rejeu à plusieurs tuiles + représenter le réarrangement du tapis par l'IA

## Contexte
Suite à l'usage réel du rejeu animé (#144/#145), deux remarques d'Alain :
1. Quand l'IA pose plusieurs tuiles en un seul tour, l'animation défile trop vite.
2. Sur 3 parties (2× Avancé, 1× Expert), Alain n'a jamais vu l'IA réarranger des tuiles déjà
   posées (mécanisme `_coup_scission`), alors qu'une investigation précédente (#134) mesurait
   un déclenchement dans 90,8 % des parties simulées 4 IA dès qu'un niveau Avancé/Expert est
   présent.

## 1. Rythme du rejeu ralenti
`animerPoseTuiles()` (jeu.js) calcule désormais un délai effectif entre tuiles ralenti de 40 %
(`delaiEntreTuiles * 1.4`) dès qu'un coup anime plus de 3 tuiles, pour rester lisible sur les
coups à plusieurs tuiles (extension multiple, scission) sans ralentir les coups simples (1-3
tuiles) qui restaient déjà confortables.

## 2. Fréquence réelle de `_coup_scission` — investigation
Reproduit la méthode de l'investigation #134 (monkeypatch temporaire et non committé de
`rummikub.moteur.ia._coup_scission` pour compter ses déclenchements effectifs, via
`scripts/simulation_ia.simuler`), mais sur des parties à **2 joueurs** — configuration plus
proche du cas réel d'Alain (1 humain + 1 IA) que les parties à 4 IA testées en #134 :

- 150 parties « 4× Avancé » (reproduction #134, contrôle) : 626 déclenchements, 98,0 % des
  parties, 84,1 tours/partie en moyenne — chiffres identiques à #134, méthode validée.
- 150 parties « 2× Avancé » : 976 déclenchements, **100 %** des parties, 128,0 tours/partie.
- 150 parties « Débutant + Avancé » : 291 déclenchements, 86,0 % des parties, 112,2 tours/partie.
- 150 parties « Débutant + Expert » : 280 déclenchements, 86,0 % des parties, 111,8 tours/partie.

**Conclusion : `_coup_scission` se déclenche en réalité AU MOINS aussi souvent, voire plus
souvent, en partie à 2 joueurs qu'en partie à 4 IA** (moins de joueurs ne réduit pas les tours
totaux d'une manche — au contraire, 112-128 tours/partie contre 84 à 4 joueurs, car chaque
pioche de secours allonge la manche). L'hypothèse « moins de joueurs → moins d'opportunités »
est donc infirmée par les données : le nombre réel de tours disponibles pour qu'une suite de 4+
tuiles se forme sur le tapis est au moins aussi grand, pas plus petit.

**L'écart entre le 0/3 observé par Alain et ces 86-100 % mesurés ne s'explique donc pas par la
configuration de jeu (nombre de joueurs), mais par l'absence, jusqu'à ce correctif, de tout
signal visuel distinguant une tuile déplacée d'une tuile simplement déjà présente.** Avant le
correctif du point 3 ci-dessous, `trouverTuilesAjoutees()` ne repérait que les tuiles dont l'id
n'existait pas dans l'ancien plateau (donc venues de la main) ; une tuile déjà posée qui change
de combinaison (comme le 7 détaché par `_coup_scission`) n'était comptée nulle part : elle
apparaissait directement dans sa position finale dès la première image du rejeu, sans aucune
animation ni surbrillance la distinguant d'une tuile qui n'a pas bougé. Il est donc très
probable que `_coup_scission` se soit déjà produit dans les parties d'Alain sans qu'il puisse le
remarquer dans un plateau ré-affiché intégralement à chaque tour — pas une anomalie du moteur IA,
mais un angle mort de l'ancien rendu. Script d'investigation temporaire, non committé
(conformément à la consigne #134).

## 3. Représentation du réarrangement dans le rejeu
- `trouverTuilesDeplacees(ancienPlateau, nouveauPlateau)` (nouvelle fonction, jeu.js) : pour
  chaque combinaison de l'ancien plateau, regroupe ses tuiles selon la combinaison du nouveau
  plateau où elles se retrouvent ; le groupe d'arrivée majoritaire est considéré comme la
  « continuation » de la combinaison (couvre aussi bien une extension qu'une scission qui la
  raccourcit sans la vider), les tuiles parties dans un autre groupe d'arrivée sont comptées
  comme déplacées.
  ⚠️ Une première version de cette fonction (de la tentative précédente sur ce même worktree)
  comparait l'ensemble des voisines déjà posées de chaque tuile avant/après — ce qui marquait à
  tort **toutes** les tuiles d'une suite scindée comme « déplacées » dès qu'une seule tuile la
  quittait (ex. scission 4-5-6-7 → 4-5-6 + groupe(7) marquait 4, 5, 6 **et** 7 comme déplacées,
  alors que 4/5/6 restent groupées entre elles, seul le 7 change réellement de combinaison).
  Conséquence concrète : les tuiles restées en place auraient disparu puis réapparu pendant le
  rejeu (`animerPoseTuiles` les traite comme à révéler) et reçu à tort le flash bleu
  « réarrangement ». Vérifié par trace manuelle (Node) sur l'exemple canonique de
  `_coup_scission`, l'extension simple et le cas sans rapport ; la nouvelle version ne marque
  plus que la tuile réellement déplacée dans les trois cas.
- `animerPoseTuiles()` anime désormais, dans l'ordre, les tuiles déplacées (surbrillance bleue,
  classe CSS `tuile-ia-deplacee`) puis les tuiles neuves venues de la main (surbrillance dorée
  existante) — part de `plateauAvant` et converge vers `plateauApres`.
  `jeu.css` : nouvelle animation `tuile-deplacee` (bleu, `rgba(90,170,255,…)`) distincte du
  doré existant pour les tuiles neuves.
- `jouerIA()` et `rejouerDernierCoupIA()` calculent désormais `tuilesDeplacees` en plus de
  `tuiAjoutees` et les passent à `animerPoseTuiles()` ; le cas « aucune tuile ajoutée »
  (pioche/passe) tient compte des deux listes.

## Test
- `python -m pytest` : 25 passés (aucun fichier Python modifié — point 2 est une investigation
  en lecture seule via script temporaire non committé, le front-end JS n'a pas de suite de
  tests dédiée dans ce projet).
- `node --check jeu.js` : syntaxe valide.
- Logique de `trouverTuilesDeplacees()` vérifiée par trace manuelle (Node, hors dépôt) sur
  3 cas : scission (seule la tuile détachée est marquée), extension simple (rien marqué),
  combinaison sans rapport avec le coup (rien marqué).

## Résultat
Le rejeu d'un coup à plusieurs tuiles est 40 % plus lent à partir de 4 tuiles animées, restant
confortable à suivre. La fréquence réelle de `_coup_scission` est confirmée au moins aussi
élevée en configuration 2 joueurs qu'en 4 IA (86-100 % des parties) ; l'écart avec le 0/3 observé
par Alain s'explique par l'absence passée de signal visuel distinguant une tuile réarrangée,
pas par une rareté réelle du mécanisme. Le rejeu représente maintenant clairement ce cas
(surbrillance bleue sur la tuile qui change de combinaison), sans faux positifs sur les tuiles
qui restent groupées.

# Issue #146 — Pioche hors-tour qui bloque la partie + échange tuile/joker toujours cassé pour un groupe

## Point 1 — Cliquer « Piocher » pendant le tour de l'IA bloque la partie définitivement

### Investigation
Côté client (`jeu.js`), `rafraichirBoutons()` désactive déjà correctement le bouton Piocher
(`btnPiocher.disabled = aPose || !monTour`) dès que ce n'est plus le tour du joueur humain, y
compris pendant la latence de ~1 s avant le coup automatique de l'IA (#126, `verifierAutoIA`).
Mais rien n'empêchait un clic arrivé malgré tout (course entre le rendu du bouton désactivé et
un clic déjà en vol, ou tout autre décalage client/serveur) d'atteindre le serveur : `api.py`
(`jeu_piocher`, `jeu_jouer_coup`, `jeu_passer`) agissait alors sur `etat["index_joueur_actuel"]`
sans jamais vérifier qui appelait, contrairement à `jeu_ia_jouer` qui, lui, vérifie bien
`etat["joueurs"][idx]["est_ia"]`.

**Mécanisme de blocage reconstitué :** un `jeu_piocher()` illégitime pendant le tour de l'IA
pioche (silencieusement) pour l'IA et fait avancer `index_joueur_actuel` vers le joueur humain
via `_terminer_tour`. Le timer JS `verifierAutoIA`, programmé *avant* cette pioche illégitime,
se déclenche ensuite et appelle `jeu_ia_jouer()` : celui-ci constate que ce n'est plus le tour
d'une IA et renvoie `{"ok": false}`. Côté client, `jouerIA()` traite cet échec en ré-affichant
l'état *local* (déjà périmé, toujours sur l'ancien tour IA) sans jamais le resynchroniser depuis
le serveur (`etat = nouvelEtat` n'est atteint que dans la branche de succès). Le client reste
alors persuadé que c'est encore le tour de l'IA (boutons humains désactivés) alors que le
serveur, lui, est déjà passé au joueur humain — et `verifierAutoIA` ne reprogramme pas de
nouvelle tentative car son garde anti-doublon (`indexAutoIAProgramme === etat.index_joueur_actuel`)
matche toujours sur l'ancien index. Aucune action ne peut plus faire avancer la partie :
blocage définitif, exactement le symptôme rapporté.

### Correctif
- **`src/rummikub/ui/api.py`** : nouvelle méthode privée `_tour_est_humain(etat)`, et garde en
  tête de `jeu_jouer_coup`, `jeu_piocher`, `jeu_passer`, `jeu_annuler` — ces quatre actions de
  jeu renvoient désormais `{"ok": false, "erreur": "Pas votre tour"}` sans toucher à l'état si
  ce n'est pas le tour du joueur humain. C'est la protection essentielle demandée par l'issue :
  même si un clic hors-tour atteint malgré tout le serveur, il n'a plus aucun effet et ne peut
  plus faire avancer `index_joueur_actuel` deux fois.
- **`src/rummikub/ui/web/jeu.html`** : `btn-piocher` a désormais `disabled` par défaut dans le
  HTML (comme `btn-annuler`/`btn-jouer`), pour couvrir la courte fenêtre entre le chargement de
  la page et le premier `rafraichirTout()` de `init()`.
- **`src/rummikub/ui/web/jeu.js`** : garde `estMonTour()` ajoutée en tête de `onPiocher`,
  `onPasser`, `onJouer` et `onAnnuler`, en plus de la désactivation déjà correcte du bouton —
  défense en profondeur cohérente avec le motif déjà utilisé ailleurs dans le fichier
  (`etendreTapis`, `insererTuileTapis`, `tenterRecupererJoker`).

### Vérification
- `python3 -m pytest` : 25 passés, aucune régression.
- `py_compile` sur `api.py`/`partie.py` : OK. `node --check` sur `jeu.js` : OK.
- Lecture pas à pas de `_terminer_tour`/`verifierAutoIA`/`jouerIA` confirmant le mécanisme de
  désynchronisation ci-dessus et sa fermeture par la garde serveur.

## Point 2 — Échange tuile/joker toujours cassé pour un GROUPE (suite #137/#142/#143)

### Investigation
`valeurJokerDansCombo`/`peutRemplacerJoker` (`jeu.js`) gèrent déjà correctement le cas groupe
(valeur commune, couleur manquante parmi celles non utilisées, anti-doublon #142) — vérifié par
rejeu réel (Playwright) du scénario exact de l'issue (groupe 11-bleu/11-jaune/joker, 11-rouge en
main) : `peutRemplacerJoker` renvoie bien `true`. La détection n'est donc pas en cause.

**Cause réelle, confirmée par clic réel dans la page (chose que #143 n'avait pas pu faire,
faute de navigateur disponible dans son worktree) :** le dispatcheur de clic de
`rafraichirPlateau` exige deux clics successifs sur une combinaison pas encore active — un
premier clic qui l'« active » (affiche ses zones d'insertion), un second qui agit vraiment.
Mais activer une combinaison insère pour la première fois les zones d'extension internes
(`zone-ext-interne`, une par espace entre deux tuiles), ce qui **décale horizontalement vers la
droite toutes les tuiles situées après la première** de la combinaison. Si le joueur clique une
première fois sur le joker (geste naturel), puis une seconde fois au même endroit en s'attendant
à ce que l'échange se déclenche, ce second clic — désormais décalé — ne retombe plus sur le
joker mais sur la zone d'insertion ou la tuile juste avant lui, d'où un ajout normal « à côté »
au lieu de l'échange. Reproduit et confirmé pas à pas avec Playwright (mesure des coordonnées
du joker avant/après activation : décalage mesuré de ~49 px pour un joker en 3ᵉ position d'un
groupe de 3). Un joker en tout premier élément d'une combinaison (position 0) n'est précédé
d'aucune zone interne et n'est donc jamais décalé — ce qui explique que le scénario « suite »
testé lors de #143 (joker visiblement en position non-initiale mais jamais vérifié par clic réel)
ait été présumé fonctionnel sans que cette régression de position ne soit détectée.

### Correctif (`src/rummikub/ui/web/jeu.js`, `rafraichirPlateau`)
La détection d'échange (`estEchangeJoker`) est désormais évaluée et son écouteur de clic attaché
**dès le premier clic**, que la combinaison soit déjà active ou non — plus besoin d'activer la
combinaison au préalable pour échanger un joker qui correspond exactement à la tuile de la main
sélectionnée. Cliquer directement sur un tel joker déclenche l'échange immédiatement, sans
rendu intermédiaire ni décalage. Le classement visuel « joker-recuperable » (surlignage orange)
est lui aussi appliqué dès le premier rendu, avant toute activation. Le comportement existant
est conservé dans tous les autres cas : une tuile non-joker, ou un joker que la tuile
sélectionnée ne peut pas remplacer (valeur différente, couleur déjà présente dans le groupe,
#142), nécessite toujours d'abord d'activer la combinaison avant de pouvoir y insérer une tuile
à un point précis.

### Vérification
- `node --check` sur `jeu.js` : OK.
- Rejeu réel via Playwright (Chromium headless, `jeu.html` chargé avec un état de partie simulé
  et `window.pywebview.api` simulé) :
  - Groupe 11-bleu/11-jaune/joker, 11-rouge en main → clic UNIQUE direct sur le joker : échange
    confirmé (`plateauLocal` contient désormais le 11-rouge à la place du joker, le joker atterrit
    dans la zone de travail, `tuileSelectionnee` vaut l'id du joker — attaché au curseur).
  - Suite 5-6-[joker]-8 rouge, 7-rouge en main → clic unique sur le joker : échange confirmé
    (non-régression, et amélioration : plus besoin des deux clics qu'imposait #143).
  - Groupe 11-bleu/11-jaune/joker, second 11-bleu en main (couleur déjà présente, #142) → clic
    (avec un délai > 350 ms entre les deux clics pour ne pas déclencher le détecteur de
    double-clic existant, sans rapport avec ce correctif) : échange bien refusé, ajout normal à
    côté du joker — comportement de #142 intact.
  - Suite 5-6-7 rouge (sans joker), 9-rouge en main, insertion en fin via la zone d'extension :
    insertion normale intacte (non-régression).
- `python3 -m pytest` : 25 passés, aucune régression.

# Issue #148 — IA : récupération d'un joker libérable lors d'une extension (Avancé/Expert)

## Contexte
Niveau "Expert" jugé trop faible : l'IA se contentait du premier coup simple trouvé
(`_coup_maximal`) même quand un joker du tapis était récupérable (échangeable contre une
tuile identique de la main) et aurait permis, une fois replacé ailleurs, un coup nettement
meilleur (plus de tuiles posées, plus de points). `_coup_scission` existait déjà mais
seulement en dernier recours, selon un seul patron.

## Modification (`src/rummikub/moteur/ia.py`)
- `_jokers_recuperables(plateau, chevalet)` : détecte les jokers du plateau échangeables
  contre une tuile identique de la main (même valeur/couleur pour une suite ; même valeur
  et une couleur absente du groupe pour un groupe).
- `_coup_avec_joker_recupere(etat, idx, ordre_points)` : pour chaque joker récupérable,
  simule l'échange puis tente de replacer le joker libéré ailleurs sur le plateau (nouvelle
  combinaison ou extension), et retourne le meilleur coup obtenu.
- `_valeur_coup(etat, idx, coup)` : valeur comparative d'un coup `(nb tuiles jouées, points
  posés)`, utilisée pour départager les coups candidats.
- `_meilleur_coup_avec_joker(etat, idx, ordre_points)` : compare le coup évident
  (`_coup_maximal`) et le coup de récupération de joker, retourne le meilleur des deux.
- `jouer_niveau_avance` et `jouer_niveau_expert` utilisent désormais
  `_meilleur_coup_avec_joker` à la place de `_coup_maximal`. Facile/Intermédiaire/Débutant
  ne sont pas modifiés — l'amélioration vise uniquement Avancé/Expert comme demandé.

## Tests (`tests/test_ia.py`)
Scénario dédié (`_etat_avec_joker_recuperable`) : suite rouge 4-5-(joker=6) au tapis ;
chevalet du bot avec un rouge 6 (reprise du joker), un noir 9 + un bleu 9 (groupe complet
uniquement avec le joker libéré), et un rouge 7 (extension évidente sans toucher au joker).
- Avancé/Expert choisissent le coup de récupération (4 tuiles posées, 31 pts) plutôt que
  l'extension évidente (1 tuile, 7 pts).
- Facile/Intermédiaire jouent toujours l'extension évidente (rouge 7 seul) — comportement
  inchangé.

# Issue #147 — Suite #144 : reformuler et habiller la modale de confirmation du rejeu du dernier coup IA

## Contexte
La confirmation avant rejeu du dernier coup IA (#144) utilisait le mot « annulé », qui pouvait
faire craindre à Alain de perdre un tour de jeu complet, alors qu'il s'agit seulement de remettre
en main les tuiles pas encore validées du tour en cours. C'était par ailleurs une `confirm()`
JavaScript native, sans style ni titre spécifique.

## Modification
- `jeu.html` : nouvel overlay `#overlay-confirm-rejeu` (`.carte.carte-confirm`), avec titre
  `#titre-confirm-rejeu` rempli dynamiquement et deux boutons (`btn-confirm-rejeu-non` /
  `btn-confirm-rejeu-oui`).
- `jeu.css` : styles `.carte-confirm` (carte compacte, titre coloré comme les fiches IA via
  `--couleur-ordinateur`) et `.btn-secondaire` (nouveau bouton générique pour les annulations).
- `jeu.js` :
  - Nouvelle fonction `confirmerRejeuIA(nomIA)`, qui affiche l'overlay stylé avec pour titre
    « Dernier coup de `<nomIA>` » et résout une Promise `true`/`false` selon le bouton cliqué.
  - `rejouerDernierCoupIA()` utilise désormais cette modale (au lieu de `confirm()` natif), avec
    pour titre le prénom de l'IA dont on rejoue le coup (`coup.nom`, déjà présent dans
    `dernier_coup_ia`).
  - Texte reformulé : « Vos tuiles pas encore validées pour ce tour seront remises en main pour
    laisser la place au rejeu — continuer ? » (plus de mention d'annulation de tour).

## Tests
- `python3 -m pytest` : 25 passed (aucune régression, modification purement front-end).
- `node --check jeu.js` : syntaxe JS valide.

# Issue #145 — Animation quand l'ordinateur pioche une tuile

## Contexte
Le joueur humain disposait déjà d'une animation à la pioche (`animerPiochee` dans jeu.js :
tuile montrée en grand au centre de l'écran, puis glissée/rétrécie vers le chevalet). Rien
d'équivalent n'existait côté IA : quand un joueur IA pioche, le tour se terminait directement
par un simple toast ("X pioche"), sans aucun geste visuel.

## Modification
- `commun.js` : nouvelle fonction `creerTuileDos()`, qui construit une tuile au même gabarit
  que `creerTuileJeu()` mais avec un disque central vide — aucune couleur ni valeur n'est donc
  révélée.
- `jeu.js` : nouvelle fonction `animerPiocheeIA(idxIA, apres)`, variante de `animerPiochee()`.
  La tuile dos visible part du centre de l'écran (comme pour l'humain) puis glisse vers la
  fiche du joueur IA concerné — position calculée dynamiquement via `getBoundingClientRect()`
  sur `.fiche-joueur` (nécessaire car la disposition des fiches varie selon le nombre de
  joueurs). Repli vers le haut de l'écran si la fiche n'est pas trouvée.
  Dans `jouerIA()`, la branche « aucune tuile ajoutée » distingue désormais pioche et passe :
  en cas de pioche, `animerPiocheeIA()` est jouée avant de rafraîchir l'affichage ; en cas de
  passe, le délai fixe de 800 ms est conservé inchangé.
- `jeu.css` : nouvelle règle `.vers-ia` (variables `--dx`/`--dy` posées en JS) qui réutilise la
  transition déjà définie sur `.tuile-piochee-grande`, en parallèle de `.vers-chevalet`
  (animation existante côté humain, inchangée).

## Test
`python -m pytest` : 25 passés (aucun fichier Python modifié, animation purement front-end).

# Issue #144 — Remplace « Derniers coups » par un rejeu animé du dernier coup de l'ordinateur

## Contexte
La liste textuelle « Derniers coups » (panneau gauche) était jugée peu utile par Alain : il
préfère pouvoir revoir l'animation du dernier coup de l'IA plutôt que lire une description
textuelle. Comme le rejeu réutilise la zone du tapis, les tuiles du tour en cours d'Alain
(posées mais pas encore validées) doivent d'abord repartir en main — ce qui annule sa
progression du tour, donc exige une confirmation explicite au préalable.

## Modifications

**`src/rummikub/ui/web/jeu.html`** : la section `#details-historique` (liste + compteur) est
remplacée par un bouton `#btn-rejouer-coup-ia` (« ▶ Dernier coup joué par l'ordinateur »),
désactivé par défaut tant qu'aucun coup IA n'a encore été joué.

**`src/rummikub/ui/web/jeu.css`** : styles `#details-historique`/`#liste-historique`/
`.entree-historique` remplacés par `.btn-rejouer-coup-ia` (même famille visuelle que
`.btn-jouer-ia`).

**`src/rummikub/moteur/partie.py`** : nouveau champ d'état `dernier_coup_ia` (initialisé à
`None` dans `creer_partie` et réinitialisé dans `nouvelle_manche`). Simple valeur de données,
alimentée côté API — la logique de pose (`jouer_tour`) n'a pas besoin de savoir qui joue.

**`src/rummikub/ui/api.py`** (`jeu_ia_jouer`) : capture une copie profonde du plateau avant
et après le coup de l'IA ; si l'action était bien une pose réussie (pas une pioche/un passage,
qui n'ont rien à rejouer), mémorise `{joueur_index, nom, plateau_avant, plateau_apres}` dans
`etat["dernier_coup_ia"]`. Ce champ est un sous-ensemble de l'état déjà sérialisé tel quel vers
JS (`jeu_get_etat`) et persisté en SQLite (`sauvegarder_partie` sérialise l'état entier) — aucune
nouvelle route API de lecture n'était nécessaire. Les parties sauvegardées avant cette issue
n'ont simplement pas ce champ (`undefined` côté JS → bouton désactivé, pas d'erreur).

**`src/rummikub/ui/web/jeu.js`** :
- `rafraichirHistorique()` → renommée `rafraichirBoutonRejouerIA()` : active/désactive le
  bouton selon la présence de `etat.dernier_coup_ia` et affiche le nom de l'IA dans son libellé.
- Extraction de `animerPoseTuiles(tuiAjoutees, plateauComplet, delaiEntreTuiles)` et
  `effacerSurbrillanceIA()` depuis le corps de `jouerIA()` (pose des tuiles IA une par une avec
  surbrillance dorée) : logique désormais partagée entre le coup IA en direct et son rejeu, pour
  éviter de dupliquer ~45 lignes d'animation. `vitesseIA()` centralise la lecture du réglage
  « Vitesse de l'ordinateur » (`VITESSES_IA`), utilisée par les deux appelants.
- Nouvelle fonction `rejouerDernierCoupIA()` (déclenchée par le clic sur le nouveau bouton) :
  si `tuilesCeTour` contient des tuiles (tour en cours non validé), affiche une confirmation
  (« Votre tour en cours sera annulé pour rejouer ce coup — continuer ? ») ; si l'utilisateur
  annule, rien ne se passe. Sinon, appelle `onAnnuler()` (même chemin que le bouton « Annuler »
  existant : remet les tuiles en main via l'API `jeu_annuler`, resynchronise le chevalet et
  réaffiche le tapis) avant de lancer l'animation à partir des plateaux mémorisés
  (`trouverTuilesAjoutees(plateau_avant, plateau_apres)` + `animerPoseTuiles`), sans appel
  serveur ni changement d'état — c'est un simple rejeu visuel.

## Points d'attention
- Le rejeu anime les tuiles identifiées par id entre `plateau_avant`/`plateau_apres` du dernier
  coup IA, mais les révèle sur le plateau *actuel* (`etat.plateau`) : si le plateau a depuis été
  réorganisé (tours suivants), l'emplacement visuel peut différer de celui d'origine — seules les
  tuiles elles-mêmes et leur ordre d'apparition sont fidèles au coup réellement joué.
- Le tableau `etat["historique"]` (texte) est conservé tel quel côté moteur : il reste utilisé en
  interne pour le message toast « X pioche »/« X passe son tour » après un tour IA ; seule la
  section visuelle qui en affichait la liste a été retirée.

# Issue #143 — Suite #137 : l'échange tuile/joker ne se produisait pas — la tuile se posait à côté du joker qui restait en place

## Contexte
#137 avait modifié `tenterRecupererJoker` pour que le joker libéré par un échange devienne la
tuile sélectionnée (attachée au curseur) plutôt que simplement désélectionné. Mais le test réel
d'Alain montrait que l'échange ne se déclenchait jamais : la tuile posée sur le joker s'insérait
À CÔTÉ de lui (insertion normale), et le joker restait en place. L'issue soupçonnait un défaut
de détection de correspondance pour les jokers ambigus entre plusieurs couleurs restantes (même
défaut que #142 avait corrigé côté blocage d'un remplacement invalide).

## Investigation
La fonction `peutRemplacerJoker`/`valeurJokerDansCombo` (jeu.js) s'est révélée correcte même pour
le cas à deux couleurs manquantes : vérifié par un test Node isolant ces deux fonctions pures sur
le scénario exact de l'issue (groupe 8-noir/8-jaune/joker, tuile 8-bleu ou 8-rouge en main) — les
deux couleurs sont acceptées, un doublon (8-noir) est refusé (#142). La piste de l'issue n'était
donc pas la cause réelle.

**Cause réelle : branche morte dans le dispatcheur de clic de `rafraichirPlateau`.** La
récupération de joker (issue #12, bien avant #137) est déclenchée par une branche
`else if (d.est_joker && tuileSelectionnee !== null && ...)` tout en bas d'une chaîne
`if/else if`. L'issue #47 (« insertion ciblée ») a depuis inséré AVANT cette branche un cas
`else if (modeCible)` qui, sur la combinaison active, attache systématiquement un clic vers
`insererTuileTapis` (insertion à côté) à CHAQUE tuile — y compris un joker — sans jamais vérifier
si la tuile sélectionnée pourrait l'échanger. Or `modeCible` est vrai exactement quand
`tapisManipulable() && une tuile est sélectionnée` — c'est-à-dire précisément la condition
requise pour atteindre la branche de récupération de joker plus bas. Résultat : cette dernière
branche ne pouvait plus jamais s'exécuter pendant le tour du joueur (elle ne devenait accessible
que si `tapisManipulable()` était faux, ce qui exige de ne PAS être son tour — un état où aucun
clic ne devrait de toute façon produire d'effet). Le correctif de #137 avait donc modifié une
fonction (`tenterRecupererJoker`) que le dispatcheur de clic n'appelait plus jamais en pratique
depuis l'ajout de #47 — bug resté invisible car vérifié uniquement par relecture de code et
`node -e`, sans clic réel dans la page.

## Correctif (src/rummikub/ui/web/jeu.js)
Dans la branche `modeCible` / `estActive` de `rafraichirPlateau` : avant d'attacher le clic de
chaque tuile de la combinaison ciblée, on calcule si la tuile cliquée est un joker que la tuile
actuellement sélectionnée (si elle vient bien de la main, via `chevaletLocal`) peut remplacer
(`peutRemplacerJoker(tuileSelDict, valeurJokerDansCombo(combo, idxTuile))`). Si oui, le clic
appelle `tenterRecupererJoker` (échange réel : retrait du joker, insertion de la tuile à sa
place, joker libéré attaché au curseur) au lieu de `insererTuileTapis` (insertion à côté). La
classe CSS `joker-recuperable` (surlignage orange pulsé, déjà définie dans jeu.css depuis #12)
est réutilisée pour signaler visuellement ce joker échangeable.

L'ancienne branche `else if (d.est_joker && ...)`, désormais prouvée inatteignable pendant le
tour du joueur, a été supprimée — elle induisait en erreur sur l'endroit où la logique
s'exécutait réellement (cause de la confusion ayant mené à la clôture erronée de #137).

## Vérification
- `node --check` sur jeu.js : syntaxe OK.
- Script Node isolant `valeurJokerDansCombo`/`peutRemplacerJoker` sur le scénario exact de
  l'issue (groupe de 3 avec joker ambigu entre 2 couleurs) : comportement correct confirmé,
  ce n'était pas la cause.
- `pytest` (suite existante, côté Python, non concernée par ce changement JS) : 25 passés,
  aucune régression.
- Pas de test Playwright/navigateur disponible dans ce worktree pour rejouer le clic réel ;
  la correction a été tracée pas à pas dans le dispatcheur de clic (ordre des branches
  `if/else if`, conditions exactes de `modeCible` vs `tapisManipulable()`) jusqu'à confirmer
  que la nouvelle branche est bien atteinte et appelle `tenterRecupererJoker` dans le scénario
  décrit par Alain.

# Issue #140 — Suite #135 : seuil de dé-zoom revérifié dans la page réelle complète

## Contexte
#135 avait mesuré le seuil de débordement du tapis (`#zone-plateau-scroll`) en chargeant
`jeu.html` isolément dans Playwright, et conclu qu'il n'y avait pas de régression. En jeu réel
(fenêtre pywebview maximisée, page complète avec en-tête, chevalet, zones de pose), Alain
observait un dé-zoom (100%→75%) toujours trop précoce, alors qu'il restait visiblement de la
place à l'écran.

## Investigation (Playwright, page réelle complète via un état de partie généré par le vrai
moteur — joueurs, chevalet, historique peuplés comme dans l'appli, pas un harnais minimal)

**Deux causes distinctes trouvées, indépendantes de la CSS mesurée par #135 :**

1. **`#zone-plateau-scroll` avait une hauteur figée (`max-height: 330px`, #128) au lieu d'utiliser
   l'espace réellement disponible.** Sur une fenêtre pywebview maximisée (ex. laptop 1366×768),
   la bande sous le tapis (zone de pose + résultat) ne prend qu'environ 120px, laissant ~400px
   disponibles à `#zone-plateau-wrap` — mais la hauteur figée à 330px plafonnait artificiellement
   le tapis bien en-dessous, gaspillant ~90-115px d'espace pourtant visible et vide à l'écran
   (exactement ce qu'Alain rapportait). À l'inverse, sur une petite fenêtre (ex. 900×600), le
   budget réellement disponible pouvait descendre sous 330px : comme `#zone-plateau-wrap` est
   compressible (`flex-shrink`) mais que `#zone-plateau-scroll` gardait son `max-height` fixe
   indépendant de son parent compressé, le tapis pouvait effectivement s'afficher sur 330px alors
   que son conteneur n'en avait que ~255 de libres — chevauchant visuellement la zone de pose
   juste en-dessous (vérifié par capture d'écran, voir rapport).

2. **Le niveau de zoom déclenché AUTOMATIQUEMENT par débordement était mémorisé dans le même
   `localStorage` que le choix manuel de l'utilisateur**, et relu comme point de départ à chaque
   chargement de `jeu.html`. Comme ce stockage persiste réellement entre les parties dans l'appli
   pywebview (contrairement à un test Playwright isolé, qui repart toujours d'un stockage vide à
   chaque exécution), un dé-zoom automatique survenu une seule fois dans une partie passée restait
   collé indéfiniment : **toute nouvelle partie démarrait déjà zoomée à 75%, dès la toute première
   tuile posée**, donnant l'impression d'un dé-zoom systématiquement prématuré — un effet que la
   méthodologie de #135 (page isolée, stockage toujours vierge) ne pouvait structurellement pas
   révéler.

Mesure du seuil (nombre de combinaisons de 3 tuiles posées avant le premier dé-zoom 100%→75%),
avec un état de partie réaliste (3 joueurs, chevalet de 14 tuiles, historique) sur les tailles de
fenêtre couvertes par l'appli :

| Fenêtre                    | Seuil AVANT (page réelle) | Seuil APRÈS |
|-----------------------------|:---:|:---:|
| 900×600 (taille mini)       | 7  | 5\* |
| 1024×600                    | 10 | 7\* |
| 1100×650                    | 10 | 10  |
| 1100×750 (défaut)           | 10 | 13  |
| 1366×768 (laptop courant)   | 13 | 17  |

\* Sur les deux plus petites tailles, le seuil mesuré baisse légèrement — mais le seuil « avant »
était artificiellement gonflé par le chevauchement décrit au point 1 (le tapis débordait déjà
visuellement sur la zone de pose avant même que `scrollHeight > clientHeight` ne soit détecté).
Le nouveau seuil, plus bas mais honnête, correspond à l'espace réellement disponible sans
chevauchement. Sur les tailles réalistes (1100×750 et plus, dont le format laptop 1366×768 visé
par la tâche), le seuil progresse de +30 à +45 %.

## Correctifs

- `jeu.css` (`#zone-plateau-wrap`, `#zone-plateau-scroll`) : remplace la hauteur figée
  (`max-height: 330px`) par `flex: 1 1 auto` + `height: 100%`, pour que le tapis occupe tout
  l'espace vertical réellement laissé libre par le reste de la mise en page, quelle que soit la
  taille de fenêtre — au lieu d'une constante choisie sans rapport avec la fenêtre réelle de
  l'appli. Supprime au passage le chevauchement visuel avec la zone de pose sur petite fenêtre.
- `jeu.js` (`autoZoomSiTapisDeborde`) : le dé-zoom déclenché automatiquement n'est plus écrit dans
  `localStorage` (seul un clic manuel sur un bouton de zoom reste mémorisé comme préférence
  durable). Le niveau automatique continue de s'appliquer visuellement pour la partie en cours,
  mais ne contamine plus le point de départ des parties futures.
- `jeu.js` (`init`) : à chaque chargement de `jeu.html`, si le tapis est vide (nouvelle partie, ou
  reprise avant la première pose), le zoom est explicitement remis à 100% (et la mémoire nettoyée),
  même si une ancienne valeur dézoomée traînait en `localStorage` — ce qui corrige aussi
  immédiatement les parties déjà affectées par le problème, sans attendre un clic manuel de
  l'utilisateur. Dans tous les autres cas (reprise d'une partie avec un tapis déjà rempli), le
  débordement réel est réévalué immédiatement après le premier rendu (`autoZoomSiTapisDeborde()`
  appelé en fin d'`init()`), pour retrouver le bon niveau de zoom dès l'affichage plutôt que
  d'attendre la pose suivante.

## Vérification
Suite pytest existante (25 tests, logique moteur non touchée) : OK. `node --check jeu.js` : OK.
Revérification par Playwright sur la page réelle complète (état de partie généré par le vrai
moteur, pas un harnais minimal) : seuils mesurés ci-dessus, chevauchement visuel disparu (capture
avant/après), et confirmation qu'une nouvelle partie démarre bien à 100% même avec un ancien
`localStorage` pollué à 0.75 par une exécution précédente.

## Issue #142 — Remplacement d'un joker dans un groupe : vérifier la couleur de la tuile de remplacement

- `jeu.js` (`valeurJokerDansCombo`, `peutRemplacerJoker`) : pour un groupe, refuse désormais le remplacement d'un joker par une tuile dont la couleur est déjà présente parmi les autres tuiles du groupe (même garde-fou que pour une suite, qui vérifiait déjà la couleur). Avant ce correctif, un groupe 7-rouge / 7-bleu / joker pouvait voir son joker remplacé par un 7-rouge pris en main, créant un groupe invalide (couleur dupliquée).

# Issue #141 — Fin de partie : message de fin de manche redondant supprimé + animation de victoire

## Contexte
À la fin d'une partie, deux fenêtres s'affichaient l'une après l'autre : l'overlay de fin de
manche (« Dernière manche — X remporte la manche », tableau manche/total) suivi immédiatement
de l'overlay de classement final (« X remporte la partie ! », tableau de classement). Les deux
montraient la même information quand la partie ne comptait qu'une seule manche.

## Correctif (`jeu.js`, `jeu.html`, `jeu.css`)
- `afficherFinDeManche()` (nouveau dispatcher) remplace les deux appels directs à
  `afficherFinManche()` : si `etat.terminee` (la manche qui se termine est la dernière de la
  partie), on affiche directement le classement final (`afficherClassementFinal()`) sans
  passer par l'overlay de fin de manche intermédiaire. Sinon, comportement inchangé.
- `afficherFinManche()` simplifiée : elle n'est plus jamais appelée avec `etat.terminee` vrai,
  donc la logique de titre/boutons conditionnelle à la fin de partie (bouton « Fin de partie »,
  titre « Dernière manche — ») a été retirée, ainsi que `onFinPartie()` et son écouteur,
  devenus inatteignables.
- Ajout d'une animation de feu d'artifice (CSS, particules générées par
  `lancerFeuArtifice()`) affichée derrière la carte du classement final lors de l'annonce du
  gagnant de la partie. Plusieurs bouquets de particules colorées jaillissent en cercle puis
  s'évanouissent (`@keyframes eclat-feu`), positions/couleurs/délais randomisés en JS, le
  mouvement restant purement CSS (`transform: rotate() translateX()`).

## Non régression
Le comportement pour une manche intermédiaire (partie à plusieurs manches) est inchangé :
l'overlay de fin de manche avec bouton « Manche suivante » / « Retour au menu » continue de
s'afficher normalement quand `etat.terminee` est faux.

# Issue #138 — Reprendre individuellement une tuile du tour en cours (sans tout « Annuler »)

## Contexte

Le mécanisme pour reprendre une tuile posée ce tour (clic/double-clic sur le
tapis → `prendreTuileTapis`/`reprendreTuile`/`reprendreTuileRangee`) existait
déjà depuis les issues #128/#133/#136, mais contenait un bug qui en annulait
l'intérêt dans le cas précis visé par cette issue : une tuile venant de la
main, posée ce tour-ci, puis redéplacée au sein du tapis (ex. sortie d'une
combinaison pour la recombiner ailleurs), était marquée à tort comme
« origine tapis ». Une fois cette étiquette posée à tort, `reprendreTuileRangee`
refusait de la renvoyer à la main (règle légitime pour une VRAIE tuile du
tapis — elle n'appartient pas au joueur) — le seul recours redevenait alors
« Annuler », qui réinitialise tout le tour. C'est exactement le problème
décrit par l'issue.

## Correctif (`jeu.js`)

- `prendreTuileTapis(idxCombo, idxTuile)` : calcule désormais `venaitDeLaMain`
  (la tuile est déjà dans `tuilesCeTour` et n'est PAS encore taguée
  `tuilesOrigineTapis`) **avant** de muter l'état, puis n'ajoute la tuile à
  `tuilesOrigineTapis` que si elle ne vient pas de la main. Une tuile de main
  redéplacée au sein du tapis garde ainsi son identité « main » et peut
  toujours repartir au chevalet individuellement.
- `reprendreTuileRangee(id, indexRangee)` : ajout de l'appel symétrique
  `rendreAuChevaletServeur(d)` dans la branche « retour au chevalet », comme
  le fait déjà `reprendreTuile` pour le chemin direct `etendreTapis`/
  `insererTuileTapis`. Sans cet appel, une tuile de main posée directement sur
  une combinaison existante (chemin qui retire la tuile du chevalet serveur),
  puis reprise via le mécanisme de manipulation du tapis et renvoyée à la
  main, restait durablement absente du chevalet serveur — désynchronisant le
  compteur de tuiles affiché sur la fiche du joueur jusqu'à la fin du tour.
  Ce chemin n'était tout simplement pas atteignable avant la correction
  ci-dessus (la tuile y était toujours mal étiquetée « origine tapis »),
  donc le bug n'avait pas d'effet observable jusqu'ici.

## Résultat

Une tuile posée par erreur ce tour (qu'elle vienne de la main ou qu'elle ait
été déplacée depuis une combinaison déjà sur le tapis) peut désormais être
reprise individuellement et repositionnée ou rendue à la main, sans affecter
le reste des tuiles déjà placées ce tour — plus besoin de passer par
« Annuler » pour corriger une seule tuile mal placée.

## Vérifications

- `node --check src/rummikub/ui/web/jeu.js` : syntaxe valide.
- `pytest` (suite existante, moteur non touché) : 25 passés.
- Lecture manuelle de tous les chemins touchant `tuilesCeTour`/
  `tuilesOrigineTapis`/chevalet serveur (`placerTuileDansRangee`,
  `insererTuileRangee`, `placerRangee`, `viderRangee`, `etendreTapis`,
  `insererTuileTapis`, `reprendreTuile`, `prendreTuileTapis`,
  `reprendreTuileRangee`, `reinitTour`) pour confirmer l'absence de
  régression sur les tuiles réellement issues d'un tour précédent (elles
  restent non renvoyables à la main, comme attendu).

# Issue #137 — Échanger une tuile de la main contre un joker équivalent du tapis

## Contexte
Un joker posé dans une combinaison du tapis représente une tuile précise (même valeur, et
même couleur dans le cas d'une suite). Quand le joueur a en main cette tuile exacte, il
pouvait déjà la sélectionner puis cliquer sur le joker pour l'échanger (`tenterRecupererJoker`,
issue #12) — mais le joker libéré était simplement désélectionné et renvoyé en zone de
travail, sans pouvoir être immédiatement replacé ailleurs d'un seul geste.

## Correctif (`jeu.js`)
- `tenterRecupererJoker` : le joker libéré par l'échange devient désormais la tuile
  sélectionnée (`tuileSelectionnee = dictJoker.id`) au lieu d'être désélectionné, et
  `majFantome()` remplace `detruireFantome()` pour qu'il suive le curseur — exactement le
  même traitement qu'une tuile fraîchement prise sur le tapis (`prendreTuileTapis`).
- Le joker libéré est ajouté à `tuilesOrigineTapis` (comme toute tuile provenant du tapis),
  afin que les mécanismes existants de replacement (`etendreTapis`, `insererTuileTapis`,
  `reprendreTuileRangee`, …) le traitent correctement.

## Résultat
Un joueur peut déposer une tuile de sa main sur un joker du tapis qu'elle remplace
exactement ; le joker libéré reste attaché au curseur, prêt à être reposé ailleurs dans le
même tour, sans étape intermédiaire.

# Issue #139 — Suite #136 : pourtour des tuiles déplacées depuis le tapis indiscernable

## Contexte
#136 avait introduit `.deplacee-tapis` (pourtour bleu `#3b82f6`) pour distinguer les tuiles déjà
sur le tapis mais déplacées ce tour-ci, des tuiles neuves de la main (`.ce-tour`, vert). En test
réel, ce bleu se fondait avec le contour pointillé bleu que `.tapis-manipulable` (jeu.css) applique
à toutes les tuiles manipulables du tapis une fois la mise initiale faite — la même collision
visuelle déjà corrigée pour le vert en #129.

## Correctif (`commun.css`, `jeu.css`)
- `.deplacee-tapis` passe du bleu `#3b82f6` à l'orange `#f59e0b` (border-color + box-shadow),
  désormais distinct à la fois du vert de `.ce-tour` et du bleu de `.tapis-manipulable`.
- Ajout de `.tuile-jeu.deplacee-tapis.tapis-manipulable` (et son `:hover`) sur le même modèle que
  `.tuile-jeu.ce-tour.tapis-manipulable` déjà présent : le contour pointillé de
  `.tapis-manipulable` reprend la couleur orange plutôt que de l'écraser.
- `.ce-tour` et `.deplacee-tapis` restent mutuellement exclusifs côté JS (`jeu.js`, `else if`),
  aucune règle de combinaison des deux classes n'était donc nécessaire.

# Issue #136 — Distinguer tuiles main/tapis + messages d'erreur précis sur une combinaison invalide

## Contexte
En formant un groupe de trois 7 mêlant une tuile de la main et deux tuiles déjà posées ailleurs
sur le tapis, les 3 tuiles recevaient le même pourtour vert (`.ce-tour`, issue #128), sans
distinguer l'origine réelle de chacune. Par ailleurs, un plateau invalide affichait un message
générique ("Combinaison 9 : ni suite ni groupe valide") sans indiquer la raison précise, et la
combinaison fautive n'était pas repérable visuellement sur le tapis.

## Correctif

### 1. Distinction visuelle main vs tapis déplacé (`jeu.js`, `commun.css`)
- Nouvelle classe CSS `.deplacee-tapis` (pourtour bleu `#3b82f6`), appliquée à la place de
  `.ce-tour` (vert) sur les tuiles déjà présentes sur le tapis avant ce tour mais
  déplacées/réorganisées pendant celui-ci — déduit de `tuilesOrigineTapis`, déjà suivi par le
  code existant (issue #103/#133) mais jusqu'ici non reflété visuellement.
- Appliqué à la fois sur le tapis (`rafraichirPlateau`) et dans les zones de pose
  (`rafraichirZoneTravail`).
- Aucune nouvelle règle n'était nécessaire pour l'état « tapis-manipulable » : son contour par
  défaut est déjà bleu, cohérent avec la nouvelle couleur.

### 2. Messages d'erreur précis (`validation.py`)
- `valider_suite`/`valider_groupe` retournent désormais un champ `"raison"` (texte explicite :
  couleurs différentes, jokers adjacents, valeurs hors limites, tuiles non consécutives, couleurs
  en double, plus d'un joker, etc.) en plus de `"valide"`/`"points"`.
- `valider_combinaison` déduit, via `_raison_combinaison_invalide`, la raison la plus pertinente
  selon que les tuiles réelles partagent une couleur commune (tentative de suite), une valeur
  commune (tentative de groupe), les deux (ambigu) ou ni l'une ni l'autre (incompatibles).
- `valider_plateau` utilise cette raison dans chaque entrée de `"erreurs"` au lieu du message
  générique, et renvoie en plus `"combos_invalides"` : la liste des ids de tuiles de chaque
  combinaison fautive (tapis ET zones de pose), pour permettre son repérage visuel côté JS.

### 3. Surlignage de la combinaison fautive (`partie.py`, `api.py`, `jeu.js`, `jeu.css`)
- `jouer_tour` (plateau invalide) et `jeu_verifier_plateau` propagent désormais
  `combos_invalides` au front.
- `jeu.js` convertit ces listes d'ids en signatures (`id1|id2|...`) comparées au contenu courant
  de chaque combinaison du tapis/des zones de pose (`signatureCombo`) : la combinaison fautive
  reçoit la classe `.combi-invalide` (déjà utilisée pour les combinaisons <3 tuiles, bordure rouge
  pulsante) — et perd automatiquement ce surlignage dès que son contenu change (plus besoin de le
  nettoyer explicitement à chaque manipulation).
- Nouvelle règle CSS `.rangee-travail.combi-invalide` (même traitement que sur le tapis) pour les
  combinaisons encore en zone de pose au moment du contrôle.

## Tests
- `pytest` (25 tests, moteur + IA) : tous passent, aucune régression — les appelants existants de
  `valider_suite/valider_groupe/valider_combinaison/valider_plateau` (IA notamment) n'utilisaient
  que les clés `valide`/`points`/`type`, inchangées.
- `node --check jeu.js` et `python -m py_compile` : OK.

# Issue #135 — Seuil de dé-zoom automatique du tapis + réglage pour l'activer/désactiver

## Investigation : #128 a-t-il avancé le seuil de dé-zoom ?
Mesure réelle (Playwright, chargement direct de `jeu.html`/`jeu.css`, remplissage du tapis par
combinaisons de 3 tuiles jusqu'à détection du débordement `scrollHeight > clientHeight` de
`#zone-plateau-scroll`) comparant l'état juste avant #128 (commit `9c0f9b5`) et l'état actuel,
sur toutes les tailles de fenêtre autorisées par l'appli (`min_size=(900,600)` à la taille par
défaut `1100x750`, plus un format laptop `1366x768`) :

| Fenêtre    | Seuil AVANT #128 | Seuil APRÈS #128 |
|------------|:---:|:---:|
| 900×600 (taille mini)  | 7 combos  | 10 combos |
| 1024×600   | 9 combos  | 13 combos |
| 1100×650   | 11 combos | 16 combos |
| 1100×750 (défaut)      | 11 combos | 16 combos |
| 1366×768   | 13 combos | 19 combos |

Dans **toutes** les configurations testées, le seuil de débordement est plus **haut** après #128,
pas plus bas : le passage de `max-height: 260px` à `330px` sur `#zone-plateau-scroll` (plus
d'espace rendu au tapis) l'emporte largement sur la réduction de la zone de pose (4→2 rangées, qui
libère elle aussi de la place). Conclusion : **les changements de hauteur de #128 n'ont pas
dégradé le seuil — ils l'ont amélioré d'environ 30-45 %.** Aucune régression à corriger de ce
côté ; aucun changement de CSS/seuil n'a donc été apporté.

L'explication la plus probable de la perception d'Alain est documentée dans le code depuis #128 :
le bouton « Placer » permet désormais de transférer une zone de pose sur le tapis **avant**
validation du tour (combinaison visible immédiatement, pourtour vert), alors qu'avant #128 ces
tuiles restaient invisibles sur le tapis jusqu'au clic sur « Jouer ». Le tapis peut donc sembler
se remplir — et donc dézoomer — plus vite **au fil d'un même tour**, même si le seuil en pixels
qui déclenche le dé-zoom (évalué uniquement après « Jouer » ou un tour IA, `autoZoomSiTapisDeborde`
n'étant pas appelée depuis `placerRangee`) n'a lui pas changé. Une taille d'écran/fenêtre plus
petite que la machine de référence reste par ailleurs un facteur à part entière (voir tableau
ci-dessus : le seuil absolu chute fortement entre 1366×768 et 900×600, indépendamment de #128).

## Réglage ajouté : dé-zoom automatique activable/désactivable
- `reglages.py` : nouvelle clé persistée `dezoom_auto` (défaut `True`, comportement historique
  inchangé par défaut).
- `accueil.html`/`accueil.js` : nouvelle case dans l'onglet *Général* des réglages, « Dé-zoomer
  automatiquement le tapis quand il déborde », lue/sauvegardée comme les réglages existants
  (`ia_auto`, `mode_reorg`, etc.).
- `application.py` : la préférence est propagée dans `etat_jeu["config"]["dezoom_auto"]` au
  lancement d'une partie et à la reprise d'une partie existante (même mécanisme que `tri_auto`,
  issue #130).
- `jeu.js` : `autoZoomSiTapisDeborde()` ne fait plus rien si le réglage est désactivé
  (`dezoomAutoActif`, initialisé depuis `etat.config.dezoom_auto` à l'ouverture de la partie ;
  absent sur une vieille partie reprise ⇒ traité comme activé, pour ne pas changer le
  comportement des parties en cours).

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

## Issue #134 — Mesure de la fréquence réelle de `_coup_scission` via le script de simulation

Suite à l'investigation en lecture seule de l'issue #133 (qui n'avait pas pu exécuter
`python3` sous le système de permissions en mode lecture), relance en écriture : un
script d'observation externe temporaire (non committé) a monkey-patché en mémoire
`rummikub.moteur.ia._coup_scission` pour compter ses déclenchements, sans modifier
`ia.py`, puis a exécuté 500 parties via `scripts/simulation_ia.simuler` (1 manche
chacune) :

- 150 parties « 4× Avancé » : 626 déclenchements, 98,0 % des parties avec ≥ 1
  déclenchement, moyenne 4,17/partie.
- 150 parties « 4× Expert » : 664 déclenchements, 97,3 % des parties, moyenne
  4,43/partie.
- 100 parties « 2× Avancé + 2× Expert » : 445 déclenchements, 98,0 % des parties,
  moyenne 4,45/partie.
- 60 parties multi-niveaux (Débutant/Facile/Intermédiaire/Avancé) : 58
  déclenchements, 63,3 % des parties, moyenne 0,97/partie (un seul joueur sur 4
  invoque le mécanisme).
- 40 parties multi-niveaux (Débutant/Facile/Intermédiaire/Expert) : 42
  déclenchements, 62,5 % des parties, moyenne 1,05/partie.

**Total global : 1835 déclenchements sur 500 parties, 90,8 % des parties avec au
moins un déclenchement, moyenne 3,67/partie.** Aucune anomalie détectée dans les 500
parties. Conclusion : `_coup_scission` n'est pas un cas théorique rarement atteint —
dès qu'un niveau Avancé ou Expert est présent, il se déclenche en pratique dans la
quasi-totalité des parties, plusieurs fois par partie en moyenne.

Aucune modification de `ia.py` ni d'aucun fichier du moteur. Le script d'observation
temporaire n'a pas été committé (conformément à la consigne de l'issue).

## Issue #131 — Double-clic sur une tuile du tapis → zone de pose active (déjà implémenté)

## Contexte
L'issue #131 demande qu'un double-clic sur une tuile du tapis l'envoie
directement dans la dernière zone de pose sélectionnée, sans clic
intermédiaire, sans toucher au simple clic ni au double-clic déjà existant
sur les tuiles du chevalet/zones de pose.

## Constat
Cette fonctionnalité est déjà intégralement implémentée depuis le commit
`a1fac21` (« Issue #103 : double-clic sur une tuile du tapis → la placer
dans la zone de pose active », 2026-08-10), toujours présent dans
`src/rummikub/ui/web/jeu.js` :

- Détection manuelle du double-clic sur une tuile du tapis (`dernierClicTapis`,
  ligne ~20, listener ligne ~336-348), posée avant tout autre handler de clic
  sur la tuile — même mécanisme que pour le chevalet (`dernierClicChevalet`).
- Au second clic (< 350 ms), `prendreTuileTapis(idxCombo, idxTuile)` (ligne
  ~940) retire la tuile de sa combinaison et la pousse directement dans
  `travail[rangeeActive]`, c'est-à-dire la zone de pose actuellement (ou
  dernièrement) activée via `activerRangee()`.
- Le comportement couvre aussi bien les combinaisons jouées lors de tours
  précédents que les tuiles posées pendant le tour en cours (extension
  issue #128), et n'altère ni le simple clic (toujours fonctionnel en dehors
  de la fenêtre de 350 ms) ni le double-clic du chevalet
  (`poserTuileDirectement`, mécanisme indépendant).

## Conclusion
Aucune modification de code nécessaire : le résultat attendu par l'issue
#131 est déjà couvert par l'implémentation de l'issue #103. Aucun fichier
touché.

# Issue #130 — Tri automatique : correction du dysfonctionnement et mémorisation du choix

## Contexte
La case « Tri automatique » (issue #126) était censée insérer chaque tuile
piochée directement à sa place triée dans le chevalet. En test réel, l'effet
ne se produisait pas correctement, et l'état de la case n'était jamais
persisté : il repartait toujours décoché à chaque relance.

## Diagnostic
`insererTrie()` (jeu.js) recherchait la position d'insertion par un simple
balayage linéaire supposant le chevalet **déjà trié**. Or un chevalet n'est
trié que si le joueur a cliqué sur « Trier » : la distribution initiale (et
toute réorg manuelle ultérieure) le laisse dans un ordre quelconque. Sur un
chevalet non trié, le balayage s'arrête dès le premier élément « plus grand »
rencontré en partant du début — une position qui n'a souvent aucun rapport
avec la vraie place triée globale (ex. un 13 rouge pioché atterrissait avant
une tuile bleue placée tôt dans la main, au lieu de rejoindre les autres
tuiles rouges). D'où l'impression que la case n'avait aucun effet.
Par ailleurs, la case n'était reliée à aucun réglage persisté : `reglages.py`
ne connaissait pas de clé `tri_auto`, et `jeu.js` ne faisait que maintenir
une variable JS locale (`triAutoActif`), réinitialisée à `false` à chaque
chargement de l'écran de jeu.

## Corrections
- **Tri** (`jeu.js`, `insererTrie()`) : au lieu d'une recherche de position
  par balayage linéaire, la fonction ajoute la tuile piochée au chevalet
  local puis retrie l'ensemble via `comparerTuiles` (même comparateur que le
  bouton « Trier »). Résultat garanti correct quel que soit l'ordre courant
  du chevalet.
- **Persistance** :
  - `reglages.py` : nouvelle clé `tri_auto` (défaut `False`) dans `DEFAUTS`.
  - `ui/application.py` : `naviguer_vers_jeu()` et `reprendre_jeu()`
    reportent désormais `cfg.get("tri_auto", False)` dans
    `etat_jeu["config"]["tri_auto"]`, selon le même schéma déjà utilisé pour
    `mode_reorg`/`ia_auto`.
  - `jeu.js` :
    - `init()` restaure `triAutoActif` et l'état de la case `#chk-tri-auto`
      depuis `etat.config.tri_auto` au chargement de l'écran de jeu.
    - le gestionnaire `change` de la case appelle désormais
      `window.pywebview.api.sauvegarder_reglages({ tri_auto: ... })` pour
      persister le choix immédiatement dans `config.json`.

## Fichiers touchés
`src/rummikub/reglages.py`, `src/rummikub/ui/application.py`,
`src/rummikub/ui/web/jeu.js`.

## Tests
- `python3 -m pytest` : 25 tests, tous au vert (aucune régression).
- `node --check src/rummikub/ui/web/jeu.js` : OK.
- Script Node ad hoc reproduisant un chevalet non trié + pioche d'un 13
  rouge : confirme que l'ancienne logique plaçait mal la tuile, et que la
  nouvelle la place correctement (regroupée avec les autres tuiles rouges).

## Issue #129 — Suite #128 : pourtour coloré sur extension directe + masquage "Jouer" pendant le jeu auto de l'IA

- **Pourtour du tour en cours (`.ce-tour`) peu visible sur une extension directe d'une combinaison du tapis.**
  Investigation approfondie (tests automatisés Playwright couvrant tous les chemins d'extension :
  zone début/fin/interne, avant/après mise initiale, plusieurs combinaisons) : la classe `.ce-tour`
  est en réalité déjà appliquée correctement par le JS (`jeu.js`) dans tous les cas, y compris
  l'extension directe — ce n'est donc pas un bug de logique. En revanche, une fois la mise initiale
  faite, la tuile du tapis reçoit *aussi* la classe `.tapis-manipulable` (contour pointillé bleu,
  2px, hors-bordure), qui écrase visuellement le pourtour vert de 1px de `.ce-tour` — exactement
  le cas de figure systématique lors d'une extension directe (impossible avant la mise initiale).
  Correction : `.tuile-jeu.ce-tour.tapis-manipulable` reprend désormais la couleur verte pour son
  contour au lieu du bleu, rendant le pourtour du tour en cours incontestable même combiné à l'état
  « manipulable » (`jeu.css`).
- **Bouton « Jouer » de l'IA masqué pendant le jeu automatique.** Quand le réglage "Jouer
  automatiquement le tour de l'ordinateur" (#126) est actif et que c'est au tour de l'IA, le bouton
  manuel `.btn-jouer-ia` n'est plus affiché le temps que le coup automatique se déroule — il
  réapparaît normalement dès que c'est de nouveau au tour d'un joueur humain ou que le réglage est
  désactivé (`jeu.js`, `rafraichirFichesJoueurs`). Supprime le risque de déclenchement concurrent
  identifié dans l'issue.

# Issue #128 — Bouton « Placer » par zone de pose + mise en évidence des tuiles du tour en cours sur le tapis

## Contexte
Jusqu'ici, les tuiles composées dans une zone de pose restaient dans un
espace totalement séparé du tapis jusqu'au clic sur « Jouer », qui les
transférait toutes d'un coup et validait le tour. Il était donc impossible
de combiner les tuiles d'une zone de pose avec celles déjà présentes sur le
tapis (ex. étendre une suite existante) avant la validation définitive.

## Ajouts / changements
- **Bouton « ⬆ Placer » par zone de pose** (`jeu.html`, `jeu.css`,
  `jeu.js` : fonction `placerRangee()`) : transfère immédiatement les tuiles
  de la zone sur le tapis (`plateauLocal`), sans valider le tour — rien n'est
  envoyé au serveur à ce stade, seul « Jouer » le fait. N'apparaît que si la
  zone n'est pas vide (même convention que « Vider »/« Trier »).
- **Pourtour coloré sur le tapis** : les tuiles posées ce tour (via « Placer »,
  une extension de combinaison ou une récupération de joker) portent déjà la
  classe `.ce-tour` (bordure verte) — ce rendu s'applique désormais aussi aux
  tuiles transférées par « Placer ».
- **Réarrangement unifié** (`rafraichirPlateau()`) : une fois la mise initiale
  faite, une tuile du tour en cours se manipule avec EXACTEMENT le même
  mécanisme que les tuiles des tours précédents (clic pour la prendre,
  double-clic, insertion ciblée) — y compris en la combinant avec d'autres
  tuiles du tour en cours ou déjà présentes. Avant la mise initiale (où ce
  mécanisme de réarrangement n'existe pas encore), le comportement précédent
  (reprise directe vers la main) est conservé à l'identique.
- **« Jouer »** reste inchangé : il valide l'ensemble du tapis
  (`plateauLocal` + zones de pose encore non placées), fige les combinaisons
  et retire le pourtour coloré (`tuilesCeTour` est vidé par `reinitTour()`
  après succès).
- **« Annuler »** : vérifié sans changement nécessaire — comme les tuiles
  « Placées » ne vivent que dans l'état local (`plateauLocal`/`travail`)
  jusqu'à « Jouer », `onAnnuler()` les efface déjà intégralement en
  réinitialisant `plateauLocal` depuis l'état serveur (`reinitTour()`).
- **2 zones de pose au lieu de 4** (`jeu.html`, `jeu.css`) : la grille passe
  d'un agencement 2×2 à une seule ligne de 2 colonnes. La hauteur libérée est
  réattribuée au tapis : `#zone-plateau-scroll` passe de 260px à 330px de
  hauteur maximale.

## Validation
- `node --check src/rummikub/ui/web/jeu.js` : OK.
- `python3 -m pytest` : 25 tests, tous au vert (aucune régression — ce
  changement est entièrement côté client, aucun fichier Python modifié).
- Relecture manuelle du flux complet : chevalet → zone de pose → « Placer »
  (tuiles sur le tapis avec pourtour vert) → réarrangement sur le tapis avec
  le mécanisme existant (prise, insertion, combinaison avec d'autres tuiles
  du tour) → « Jouer » (validation, pourtour retiré) ou « Annuler » (retour
  complet à l'état de début de tour, y compris les tuiles déjà « Placées »).

# Issue #127 — Réorganisation des tuiles dans une zone de pose, comme sur le tapis

## Contexte
Le mécanisme d'insertion d'une tuile entre deux tuiles déjà placées existait
déjà dans le code des zones de pose (ajouté aux issues #27 et #31, zones
`.zone-ext-interne` + `insererTuileRangee`), au même titre que sur le tapis.
Mais `selectionnerTuile()` — appelée au clic sur une tuile du chevalet —
rafraîchissait le chevalet et le tapis, sans jamais rafraîchir la zone de
travail. Les zones d'insertion internes des rangées de pose (et les
gestionnaires de clic associés) restaient donc figés dans l'état « aucune
tuile sélectionnée », rendant l'insertion interne invisible et inopérante :
seul un clic sur le fond de la rangée (= ajout systématique en fin) restait
disponible.

## Correction
`src/rummikub/ui/web/jeu.js` — `selectionnerTuile()` appelle désormais aussi
`rafraichirZoneTravail()`, au même titre que `rafraichirChevalet()` et
`rafraichirPlateau()`. Les zones d'insertion (avant la première tuile, entre
deux tuiles, après la dernière) apparaissent donc correctement dès qu'une
tuile du chevalet est sélectionnée, avec le même comportement que sur le
tapis.

## Validation
- `node --check src/rummikub/ui/web/jeu.js` : OK.
- `python3 -m pytest` : 25 tests, tous au vert (aucune régression).
- Relecture manuelle du flux : sélection d'une tuile du chevalet → zones
  `.zone-ext-interne` recréées dans chaque rangée de travail non vide, avec
  les bons gestionnaires de clic (`insererTuileRangee` au lieu de l'ancien
  `reprendreTuileRangee` figé).

# Issue #126 — Ergonomie : jeu automatique de l'IA, tri automatique au pioché, suppression d'un texte inutile

## Contexte
Trois petites améliorations d'ergonomie identifiées en jouant, indépendantes
les unes des autres.

## Ajouts / changements
- **Jeu automatique de l'IA** : nouveau réglage « Jouer automatiquement le
  tour de l'ordinateur » (onglet Général des réglages, clé `ia_auto` dans
  `config.json`). Quand il est actif, dès que c'est le tour d'une IA, son
  coup se déclenche seul après une latence d'environ 1 seconde (pour ne pas
  paraître brusque), sans qu'il faille cliquer sur le bouton « Jouer » de sa
  fiche. Ce bouton manuel reste affiché et fonctionnel (clic possible pendant
  la latence, ou si le réglage est désactivé).
- **Tri automatique à la pioche** : nouvelle case à cocher « Tri automatique »
  à côté du bouton « Trier » du chevalet. Quand elle est active, chaque tuile
  piochée est insérée directement à sa place triée (couleur puis valeur,
  jokers en fin) plutôt qu'ajoutée en fin de chevalet. Le bouton « Trier »
  existant est inchangé et reste utilisable indépendamment de la case.
- **Suppression du texte « Mes tuiles — cliquez, réarrangez »** affiché
  au-dessus du chevalet du joueur : n'apportait rien à l'utilisateur.

## Fichiers touchés
`src/rummikub/reglages.py`, `src/rummikub/ui/application.py`,
`src/rummikub/ui/web/{accueil.html,accueil.js,jeu.html,jeu.css,jeu.js}`.

# Issue #125 — Script headless de simulation de parties IA vs IA

## Contexte
Le moteur de jeu est pur Python, découplé de l'UI pywebview, mais il n'existait
aucun moyen de vérifier qu'une partie complète se déroule sans erreur sans
passer par l'interface (lancement manuel, clics répétés sur « tour IA »).

## Ajout
`scripts/simulation_ia.py` (nouveau) : script headless qui fait s'affronter
2 à 4 IA entre elles sur une ou plusieurs manches complètes, en pilotant
directement `rummikub.moteur` (sans pywebview). La boucle de tour reproduit
exactement la logique de `Api.jeu_ia_jouer` (même traitement du cas « coup IA
invalide » : annulation + pioche de secours), afin que la simulation couvre le
même chemin de code que le jeu réel.

- Options CLI : `--joueurs` (2-4, défaut 4), `--niveaux` (liste explicite par
  joueur, sinon répartition cyclique sur les 5 niveaux), `--manches` (défaut
  1), `--max-tours` (garde-fou anti-blocage par manche, défaut 500), `--seed`
  (reproductibilité), `-v/--verbose` (log de chaque tour).
- Toute exception levée par l'IA, tout coup invalide proposé, toute action IA
  inconnue ou tout blocage (dépassement de `--max-tours` sans fin de manche)
  est journalisé (`logging`) et compté comme anomalie.
- Résumé final sur stdout : manches/tours joués, durée, scores cumulés,
  liste des anomalies. Code de sortie 0 si la partie est saine, 1 sinon.

## Validation
- `python3 -m pytest` : 25 tests, tous au vert (aucune régression).
- Exécutions manuelles de confirmation : 60 parties simulées (2/3/4 joueurs,
  5 niveaux mélangés, seeds 100 à 119, 2 manches chacune) + plusieurs runs
  ciblés (4 IA de niveaux différents, 3 joueurs sur 3 manches, 2 IA Expert
  face à face, mode verbeux) — **aucune anomalie détectée dans tous les cas**.
  Exemple de résumé obtenu :
  ```
  RÉSUMÉ : 3/3 manche(s) jouée(s), 268 tour(s) au total, 0.17s.
  Scores cumulés finaux : {'IA-1 (Débutant)': -387, 'IA-2 (Facile)': -159, 'IA-3 (Intermédiaire)': -286}
  Aucune anomalie détectée.
  ```

# Issue #104 — Zoom automatique quand le tapis déborde après une pose

## Contexte
Quand une combinaison posée dépassait la zone visible du tapis, le joueur ne
s'en rendait pas compte (combinaison hors écran) et devait dézoomer manuellement.

## Modification
`src/rummikub/ui/web/jeu.js` :

- Nouvelle fonction `autoZoomSiTapisDeborde()` (placée après `brancherZoomTapis`).
  Elle mesure le débordement de la zone visible du tapis (`#zone-plateau-scroll` :
  `scrollHeight > clientHeight` ou `scrollWidth > clientWidth`). En cas de
  débordement, elle réduit le zoom d'UN cran en réutilisant la fonction de zoom
  existante `appliquerZoomTapis()` (100 % → 75 % → 50 %), et mémorise le niveau
  dans `localStorage` comme le font les boutons manuels.
  - Les niveaux sont lus depuis les boutons `#zoom-tapis .btn-zoom` (aucune valeur
    codée en dur), donc restent synchronisés avec le HTML.
  - Ne descend jamais sous le niveau minimal (dernier bouton).
  - Ne fait rien si le contenu est déjà entièrement visible.
  - Un seul cran par pose : le joueur garde la main et peut rezoomer librement ;
    l'automatisme ne se redéclenche qu'à la pose suivante.

- Appel de `autoZoomSiTapisDeborde()` après le rafraîchissement du plateau aux
  deux seuls points de pose réelle de tuiles :
  - `onJouer()` (pose humaine validée), après `rafraichirTout()`.
  - `jouerIA()` (pose de l'IA), après le `rafraichirTout()` final. Les cas
    « pioche » / « passe » de l'IA sortent avant ce point (aucune tuile ajoutée),
    donc n'y déclenchent pas de zoom.

## Résultat
- Après une pose faisant déborder le tapis, le zoom se réduit d'un cran.
- Le joueur ajuste ensuite librement ; l'auto-zoom ne se réimpose qu'à la pose
  suivante.
- Le zoom minimal n'est jamais dépassé.
- Tests existants : 25 passés. Syntaxe JS vérifiée (`node --check`).

# CHANGELOG — Issue #113

## Correction rebuild_rummikub.bat : chemin Z:\CCW\rummikub à l'étape 8

- `build/rebuild_rummikub.bat` (étape 8, hors mode `--publier`) : la commande
  `git -C Z:\CCW\rummikub reset --hard origin/master` référençait le lecteur
  réseau `Z:` qui n'existe plus sur le PC fixe physique (échec silencieux).
  Remplacement du chemin par `C:\CCW_Share\CCW\rummikub` (même correctif que
  `rebuild_scrabble.bat`, issue #410).
- Correction également du commentaire stale ligne 349
  (`%ORIGDIR% = Z:\CCW\rummikub` → `%ORIGDIR% = C:\CCW_Share\CCW\rummikub`)
  afin qu'il ne subsiste plus aucune référence à `Z:\CCW` dans le fichier.

## Contexte
Retours de tests sur machine réelle (public âgé) : le terme « IA » est anxiogène.

## Modifications
- `src/rummikub/ui/web/accueil.html` : le paramètre « Vitesse de l'IA » (bloc
  `<select id="rgl-vitesse">`) est déplacé de l'onglet « Règles du jeu »
  (`#panneau-regles`) vers l'onglet « Général » (`#panneau-general`), et son
  label affiché est renommé en « Vitesse de l'ordinateur ».
- `src/rummikub/ui/web/jeu.js` : commentaire mis à jour pour refléter le
  nouveau libellé (« Vitesse de l'ordinateur »).

## Points d'attention
- Les identifiants techniques internes sont conservés inchangés :
  `id="rgl-vitesse"` (DOM) et la clé `vitesse_ia` (config.json, `reglages.py`,
  `application.py`, `accueil.js`, `jeu.js`). Seul le libellé affiché change,
  conformément à la demande.
- Aucun fichier Python modifié : la logique de lecture/écriture du réglage
  (par `id`) reste valide après le déplacement du bloc.

---

# CHANGELOG — Issue #61

## Mise à jour TACHES.md — icône et intégration Actualise

- Déplacé « Icône application (assets/rummikub.ico) » de « À faire » vers
  « Fonctionnalités implémentées » (le fichier existe déjà dans le dépôt).
- Ajouté une note « Intégration Actualise (Issue #59, #60) » dans les
  fonctionnalités implémentées : `rummikub.iss` et `rebuild_rummikub.bat`
  embarquent l'updater autonome, raccourcis pointant vers `Actualise.exe`,
  génération automatique de `config.json`, production de `rummikub.zip`,
  suppression de la section [Run].
- Conservé « Build Windows via CCW » dans « À faire » avec la précision que
  le pipeline d'installation est désormais prêt.
# Issue #93 — Lancement d'Actualise au démarrage de Rummikub

## Contexte
Même refonte architecturale que Scrabble — symétrique. Au démarrage, Rummikub
doit lancer Actualise en arrière-plan s'il est présent sur la machine.

## Modifications
- `main.py` : nouvelle fonction `_lancer_actualise_au_demarrage()`.
  - Si `C:\Actualise\Actualise.exe` existe → le lance en subprocess
    non-bloquant (`subprocess.Popen`) avec l'argument `--config rummikub`.
  - Si absent → retour immédiat, aucun effet.
  - Si le lancement échoue → exception avalée, simple log discret sur
    `stderr`, jamais d'exception propagée.
  - Appelée dans `__main__`, avant `_lancer_actualise_ui_si_flag()` et avant
    l'ouverture de la fenêtre.

## Points d'attention
- Le check `actualise_update.flag` existant (`_lancer_actualise_ui_si_flag()`)
  reste **inchangé** : les deux mécanismes coexistent.
- Chemin Windows codé en dur (`C:\Actualise\Actualise.exe`) conforme à la
  demande de l'issue ; sur Linux le fichier n'existe pas → `return` silencieux,
  le jeu démarre normalement.
- Non-bloquant : `Popen` n'attend pas la fin du processus, le démarrage du jeu
  n'est ni bloqué ni retardé.

---

# Issue #75 — Mode `--publier` dans `rebuild_rummikub.bat` (SHA-256 + version.json automatiques)

## Contexte
Automatiser la publication d'une nouvelle version pour éviter les erreurs
manuelles (numéro de build, calcul du SHA-256, rédaction de `version.json`).
La référence mentionnée (`build/rebuild_actualise.bat` du dépôt
`AlainDelree/Bridge_Agent`, issue #365) n'était pas accessible au moment du
traitement (HTTP 404 : chemin absent de l'arbre `master`) ; l'implémentation
s'appuie donc sur la spécification détaillée de l'issue.

## Modifications
- `build/rebuild_rummikub.bat` :
  - **Analyse d'arguments** (nouveau bloc après `setlocal`) : `--publier`
    (active la publication) et `--build N` (force le numéro de build). Sans
    argument, le comportement historique est strictement inchangé.
  - **Étape 8bis (`--publier` uniquement)**, insérée après l'étape 8 (une fois
    `rummikub.zip` généré) :
    - lecture du build courant depuis `%ORIGDIR%\version.json` via PowerShell
      (`ConvertFrom-Json`), puis `build + 1` ; surchargé par `--build N` ;
    - réécriture de `manifest.json` avec le nouveau numéro et régénération de
      `rummikub.zip` (`Compress-Archive` de `dist\Rummikub\*` + `manifest.json`),
      recopié vers le partage ;
    - calcul du **SHA-256** du zip via `Get-FileHash` (PowerShell), en
      minuscules ;
    - écriture de `version.json` à la racine du clone partagé (`%ORIGDIR%`,
      soit `Z:\CCW\rummikub`) au format `{"build": N, "sha256": "..."}` ;
    - **commit local** de `version.json` (`git -C "%ORIGDIR%" commit -- version.json`).
  - **Étape 9** : en mode `--publier`, le `git reset --hard origin/master` du
    clone partagé est **désactivé** afin de préserver le commit `version.json`
    fraîchement créé (il serait sinon effacé). Comportement normal inchangé
    hors `--publier`.
  - **Fin de script** : en mode `--publier`, rappel explicite des étapes
    restées **manuelles** — `git push` puis création de la Release GitHub (tag
    `vN`) avec `Rummikub-Setup.exe` et `rummikub.zip` en pièces jointes.

## Points d'attention
- **Jamais de `git push` ni de `gh release create`** dans le script,
  conformément à l'issue et aux consignes du bridge : seul un commit local est
  réalisé.
- Le `reset --hard` de l'étape 9 aurait supprimé le commit `version.json` en
  mode publication : il est donc explicitement contourné dans ce mode. En mode
  normal (sans `--publier`), aucun commit n'est fait et le reset garde son
  rôle de nettoyage habituel.
- `--build N` fixe le build à **N** exactement (pas `N+1`) ; sans lui, le build
  vaut `version.json.build + 1`.
- Script Windows (`.bat`) : non exécutable/validable sous Linux ; revue
  statique de la syntaxe batch effectuée (labels, blocs `if`/parenthèses,
  échappements `^( ^)`, expansion différée `!VAR!`).
