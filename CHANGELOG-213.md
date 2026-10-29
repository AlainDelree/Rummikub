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
