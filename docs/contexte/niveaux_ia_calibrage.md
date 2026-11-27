# Échelle des niveaux d'IA et calibrage

## 16. Échelle des CINQ niveaux d'IA sur un même modèle exact (issue #213, suite de #206)

Depuis #213, les **cinq** niveaux d'IA sont bâtis sur **un seul moteur** — le
modèle exact d'un tour (`moteur/solveur_exact.py`, le joueur d'Expert depuis
#206) — dont la **force est réglée par des paramètres** réunis en UN SEUL
endroit (`moteur/niveaux.py`), et non plus par des algorithmes de force
inégale. Le point d'entrée reste `moteur/ia.jouer_ia(etat, idx)`.

### Structure cible de l'échelle (répartition voulue par Alain)

Le solveur exact « un tour » (qui pose toujours le maximum) **n'est PAS** le
niveau le plus fort : c'est le niveau **Avancé**.

| Niveau | Moteur | `perturbation_max` | `taux_oubli` (départ #213 — **recalibré #216**, voir plus bas) |
|--------|--------|:--:|:--:|
| Débutant | exact BRIDÉ | 0 | 35 % |
| Facile | exact BRIDÉ | 0 | 22 % |
| Intermédiaire | exact BRIDÉ | 3 | 12 % |
| Avancé | exact COMPLET | ∞ (aucune limite) | 0 |
| Expert | exact complet (multi-tours partielles tentées puis retirées, #235/#236, sans effet mesurable) | ∞ | 0 |

- **Débutant, Facile, Intermédiaire** : le solveur un-tour AFFAIBLI (voit moins
  loin, oublie des coups), de plus en plus bridé vers le bas.
- **Avancé** : le solveur un-tour COMPLET, tel quel.
- **Expert** : solveur un-tour + stratégies multi-tours **partielles** (dosées :
  anticipation sur deux tours plutôt que trois, rétention défensive modérée,
  non-don de joker — §13, pistes 1/8/9).

> **⚠️ État provisoire livré par #213.** Les stratégies multi-tours (§13) **ne
> sont PAS** implémentées par #213. Expert est donc **provisoirement IDENTIQUE
> à Avancé** (solveur un-tour complet), jusqu'à ce que des issues ultérieures
> développent le multi-tours. Un tournoi d'échelle montrera donc une
> progression nette Débutant < Facile < Intermédiaire < Avancé puis un
> **plateau** Avancé ≈ Expert (égalité statistique) — c'est ATTENDU, pas un
> défaut. Repère voulu par Alain : son propre niveau doit correspondre à
> **Intermédiaire**, ou entre Intermédiaire et Avancé (à ajuster par les
> mesures — voir « calibrage » ci-dessous).
>
> **Mise à jour #221** : Expert gagne la première brique multi-tours réelle
> (vérification de finition en fin de partie, §13) — il n'est donc plus
> strictement identique à Avancé en toute fin de partie, même si l'écart
> mesuré reste faible (voir §13 et le rapport de clôture de #221) : le reste
> de l'échelle et le plateau statistique Avancé ≈ Expert décrits ci-dessus
> restent valables ailleurs.
>
> **Mise à jour #235** : un sixième niveau, « Champion du Monde », avait été
> ajouté au-dessus d'Expert pour porter des stratégies multi-tours
> COMPLÈTES (réserve d'une tuile, retenue au début, petits chiffres, chances
> de poser au prochain tour, placement du joker, en plus de « garder un
> joker en main », #225). Une mesure chiffrée (12 configurations de 1 000
> parties, Expert contre Champion du Monde) n'a montré AUCUN effet mesurable
> sur le taux de victoire : le niveau et tout le code propre à ces
> stratégies ont été retirés (voir l'archive en §13, et le tag git
> `archive-strategies-champion` pour retrouver le code). L'échelle compte
> donc cinq niveaux ; Expert reste le niveau le plus fort, inchangé.
>
> **Mise à jour #236** : la vérification de finition elle-même (#221),
> restée active pour Expert après #235, est à son tour retirée — jamais un
> coup changé (4 534 déclenchements sans effet, voir l'archive §13, point g).
> De #236 à #267, Avancé et Expert étaient de nouveau strictement
> identiques (même solveur exact complet) ; **ce n'est plus vrai depuis
> #267**, voir « Échelle calibrée » ci-dessous.

### Recalibrage #216/#217 — état final (récit complet dans CHANGELOG.md, issues #216 et #217)

Après #213, Débutant, Facile et Intermédiaire ont été recalibrés en deux passes
successives (#216 puis #217) pour obtenir des écarts réguliers entre niveaux
voisins, Alain visé entre Intermédiaire et Avancé ; **Avancé et Expert
inchangés**. Réglages finaux retenus (`moteur/niveaux.py`) :

| Niveau | `perturbation_max` | `taux_oubli` |
|--------|:--:|:--:|
| Débutant | 0 | 0,42 |
| Facile | 1 | 0,30 |
| Intermédiaire | 4 | 0,08 |
| Avancé / Expert | ∞ | 0 |

Monotonie garantie par construction (perturbation non décroissante, oubli non
croissant), test `test_bridages_monotones_du_plus_faible_au_plus_fort` au vert.
Outil de balayage : `scripts/calibrer_niveaux.py` ; outil de validation ciblée
du bas de l'échelle : `scripts/valider_bas_echelle.py` (`--facile-perturbation`/
`--facile-oubli` pour comparer un réglage candidat sans toucher `niveaux.py`).

> **⚠️ Cibles OBSOLÈTES depuis #220 (conservées ci-dessus pour l'historique,
> à NE PLUS utiliser) :** les cibles en tuiles restantes en défaite de #216
> (Débutant ≈ 9, Facile ≈ 7, Intermédiaire ≈ 4,5) et de #217 (Facile entre
> 6,0 et 6,3) reposaient sur le relevé en miroir retiré ci-dessous — voir la
> section suivante pour le critère qui les remplace.

### Critère de force depuis #220 : duels entre niveaux voisins (fin du relevé en auto-partie)

**#216 et #217 ont montré que le relevé des tuiles restantes en défaite EN
MIROIR (un niveau contre lui-même) n'est pas un bon critère de force.** Il
mesure surtout la **longueur des parties** (dépend de la vitesse de
l'adversaire, donc pas comparable à un joueur humain, qui affronte des
niveaux différents) ; dès que `perturbation_max >= 1`, les deux joueurs
réarrangent le plateau sans jamais vraiment progresser, si bien que beaucoup
de manches n'atteignent leur fin naturelle que par le garde-fou de tours — ce
qui biaise la moyenne (14 manches sur 40 exclues dans #217). Il a de plus
consommé TOUT le temps imparti des tournois de #216 (2 h) et #217 (1 h 30)
sans que les DUELS entre niveaux voisins — pourtant le vrai test de l'échelle
— n'aient jamais été joués, et sa limite de temps n'était pas ferme (#217 l'a
dépassée de 244 s, puis le processus est resté vivant 30 minutes de plus,
machine au repos, sans rien calculer, jusqu'à l'arrêt manuel d'Alain).

**Décision d'Alain (#220) : le critère de force des niveaux est désormais
EXCLUSIVEMENT le duel entre niveaux VOISINS** — la même donne jouée DEUX fois,
mains des deux IA échangées (le miroir « utile », qui annule l'avantage de la
main et de l'ordre de passage) — avec, pour chaque paire adjacente, un taux
de victoire du niveau le plus fort visé **entre 60 et 75 %**. `scripts/
echelle_niveaux.py` et `scripts/valider_bas_echelle.py` ne mesurent plus que
cela : l'option `--donnes-profil` et tout ce qui en dépendait (fonctions de
mesure, verdicts, textes d'aide) ont été retirés des deux outils. Leur limite
de temps est désormais réellement FERME (garde-fou externe par
sous-processus, voir `scripts/_limite_temps_ferme.py`) et leurs résultats
partiels indiquent toujours, pour chaque paire, les donnes terminées sur le
nombre prévu (marque « partiel » tant qu'elle n'est pas finie), ainsi que le
nom de la machine et la version de Python en en-tête.

**`scripts/calibrer_niveaux.py` et le relevé de `scripts/profil_joueur.py`
reposent ENCORE sur le critère des tuiles restantes en défaite** — hors
périmètre de #220, qui ne retire ce relevé que des deux outils de TOURNOI
ci-dessus. À reconsidérer dans une issue ultérieure si le critère par duels
les rend obsolètes à leur tour. Le **profil humain** exprimé en tuiles
restantes (`profil_joueur.py --journaux …`) reste utile mais **seulement
INDICATIF** — ce n'est pas une mesure de force comparable entre niveaux d'IA.

### Les deux paramètres d'affaiblissement (`moteur/niveaux.py`, le SEUL endroit)

- **`perturbation_max`** — nombre maximal de tuiles **du plateau** que le coup
  peut DÉPLACER (mesure #199, `solveur.mesurer_perturbation`). Ajouter des tuiles
  de la main à une combinaison existante ou créer de nouvelles combinaisons **ne
  compte pas**. Exprime ce qu'un joueur « voit » : `0` = ne touche jamais à la
  structure du plateau (pose + extensions) ; `None` = aucune limite (solveur
  complet). Mécanique (`ia._coup_selon_perturbation`) : à `0`, le coup sans
  réarrangement (`_coup_maximal`, déplacement garanti nul) ; à `k>0`, le coup
  complet s'il déplace ≤ k tuiles, sinon repli sur le coup sans réarrangement.
- **`taux_oubli`** — probabilité, à chaque tour, que le joueur ne « voie » pas le
  meilleur coup et **pioche** à la place. Tirage reproductible dès que
  `config.graine_ia` est fixée (simulations). **Garde-fous d'incohérence** :
  un coup qui **vide la main gagne la partie** et n'est JAMAIS oublié ni dégradé ;
  le taux **décroît quand la main est petite** (`taux_oubli_effectif`, nul à une
  seule tuile, plein au-delà de `SEUIL_OUBLI = 7`) pour ne pas « piocher » bêtement
  en fin de partie. Valeurs de départ INDICATIVES (à resserrer par les mesures).

  **Comportement exact et implications pour la calibration (issue #240,
  point 5)** — ce que `taux_oubli_effectif` fait précisément, à relire avant
  de choisir un réglage candidat avec `scripts/calibrer_echelle.py` :
  - Le taux d'oubli EFFECTIF ne dépend que de la **taille du chevalet au
    moment de jouer** (`taux_oubli_effectif(taux, taille_main)`) : plein
    (= `taux_oubli` tel quel) tant que le chevalet compte au moins
    `SEUIL_OUBLI = 7` tuiles ; décroît ensuite LINÉAIREMENT jusqu'à 0 à une
    seule tuile restante. Un chevalet de 14 tuiles (début de partie) et un
    chevalet de 7 tuiles oublient donc EXACTEMENT au même taux ; un chevalet
    de 4 tuiles oublie à `taux × 3/6 = taux / 2` ; un chevalet de 2 tuiles à
    `taux × 1/6`.
  - **Un coup qui vide le chevalet n'est JAMAIS oublié**, quel que soit le
    taux réglé — même à `taux_oubli = 1.0`, un joueur qui PEUT gagner ce tour
    gagne toujours. Ce n'est pas une approximation à corriger : c'est un
    garde-fou volontaire (un joueur, même très faible, ne laisse jamais
    passer une victoire immédiate évidente).
  - **Implication directe pour le calibrage** : le levier `taux_oubli` ne
    pèse quasiment QUE sur le début et le milieu de partie (chevalet encore
    grand) — en fin de partie (chevalet court), son effet s'annule
    mécaniquement, et le coup gagnant reste de toute façon imposé. Un niveau
    réglé avec un `taux_oubli` élevé mais une `perturbation_max` haute peut
    donc rattraper beaucoup de terrain perdu en fin de partie malgré un début
    hésitant — c'est précisément ce qu'a montré #216/#217 (à `perturbation_max
    = 0`, le taux d'oubli ne déplace quasiment plus les tuiles restantes en
    défaite, seulement le taux de victoire global) : **la perturbation est le
    levier qui sépare le plus nettement deux niveaux voisins, l'oubli affine
    surtout le taux de victoire SANS changer fondamentalement le profil de
    fin de partie.** À réglages de perturbation égaux entre deux candidats,
    comparer leur taux d'oubli donne une mesure fiable ; à perturbations
    DIFFÉRENTES, ne pas s'étonner qu'un écart d'oubli modéré ait un effet
    plus faible qu'attendu sur le taux de victoire mesuré par
    `scripts/calibrer_echelle.py --candidats`.
- **Repli sans dépendances** : si `highspy`/`numpy` manque, le moteur se replie
  sans erreur (recherche arborescente `solveur.py`, puis heuristique Avancé) ; le
  **journal indique le mécanisme** via la clé `solveur` de l'action
  (`exact`/`recherche`/`avance`/`sans-rearrangement`), déjà journalisée (#211).

Les fonctions heuristiques historiques (`jouer_niveau_debutant/facile/
intermediaire/avance`) **demeurent** dans `moteur/ia.py` : elles ne portent plus
l'échelle (c'est le moteur bridé qui le fait, via `jouer_niveau_bride` et
`NIVEAUX_IA`) mais restent le **repli** quand le modèle exact est indisponible et
le support des tests de tactiques de joker (joker_tactiques.md §8). Les parties sauvegardées avec
les 5 anciens niveaux **restent valides** (un libellé inconnu retombe sur
« Débutant », `niveaux.bridage_pour`).

### Personnage / avatar par niveau

Ce projet n'a **pas** de persona fixe par niveau : les adversaires IA tirent un
prénom aléatoire d'un pool partagé (`ui/noms_ordinateur.py`, prénoms genrés) et
un avatar parmi les 15 SVG existants (`ui/web/avatars/`), quel que soit le
niveau. **Aucune liste de personnages de Scrabble n'est disponible dans le
dépôt.**

### Outils de calibrage (`scripts/`)

- **`scripts/calibrer_niveaux.py`** (#216) — RECHERCHE DE RÉGLAGES. Balaye une
  grille `--perturbations` × `--oublis` pour un niveau et mesure, par réglage,
  les **tuiles restantes en défaite** (miroir, graine fixe, reproductible) ;
  `--cible` marque le plus proche. Garde-fous de temps fermes (`--max-tours`,
  `--limite-temps`), `--budget-solveur` réglable. Sert à régler Débutant /
  Facile / Intermédiaire dans `moteur/niveaux.BRIDAGES`.

- **`scripts/echelle_niveaux.py`** — TOURNOI D'ÉCHELLE, par DUELS entre
  niveaux voisins (le relevé des tuiles restantes en défaite par niveau et
  l'option `--donnes-profil` ont été RETIRÉS par #220). `--budget-solveur`
  réduit le budget du solveur exact pour tenir une limite de temps ferme — à
  signaler, la force d'Avancé en dépend. Parties à deux en miroir entre tous
  les niveaux voisins (+ quelques paires non voisines), ≥ 40 donnes par paire,
  tableau des taux de victoire + IC 95 % (Wilson). Vérifie que l'échelle est
  strictement croissante et que l'écart entre voisins est net (**60–75 %**,
  resserré de 60–80 % par #220). Résultats PARTIELS écrits en continu avec
  `--sortie` (nouveauté #220, même format qu'avant : marque « partiel »,
  en-tête machine/version Python), limite de temps RÉELLEMENT ferme
  (`--limite-temps`, garde-fou externe par sous-processus, voir ci-dessous),
  durée indiquée. Réutilise `comparer()` de `comparer_niveaux_ia.py`. Ex. :

  ```
  python scripts/echelle_niveaux.py --donnes 40 --seed 0 --limite-temps 3600 \
      --sortie resultats_echelle.txt
  ```

  Sert de tournoi de **vérification finale** une fois les réglages retenus
  appliqués dans `niveaux.BRIDAGES` — pour les CHERCHER sans y toucher, voir
  `scripts/calibrer_echelle.py` ci-dessous.

- **`scripts/calibrer_echelle.py`** (issue #240, remplace
  `scripts/valider_bas_echelle.py` retiré) — OUTIL DE CALIBRATION par duels,
  avec des réglages (perturbation/oubli) donnés en LIGNE DE COMMANDE, **sans
  jamais modifier `niveaux.py`** (les niveaux non précisés gardent les valeurs
  du jeu). Réutilise directement `comparer()` de `comparer_niveaux_ia.py`
  (garde-fou solveur exact, export par partie, budget de temps), `_rapport_
  duels` (en-tête machine) et `_limite_temps_ferme` (limite de temps FERME,
  Linux et Windows) — aucune logique dupliquée.

  **Méthode de calibration DESCENDANTE décidée par Alain** : Expert reste à
  fond (jamais modifié), on règle Avancé contre Expert (fixe) jusqu'à 60–70 %
  pour le niveau du haut, puis Intermédiaire contre Avancé (désormais figé),
  puis Facile contre Intermédiaire, puis Débutant contre Facile — chaque
  réglage ne dépend QUE du niveau juste au-dessus, déjà figé, donc un niveau
  réglé n'est plus jamais remis en cause par la suite. Avant de commencer, il
  est utile de mesurer l'ÉTENDUE TOTALE de l'échelle (chaque niveau actuel
  contre Expert, `--paire Débutant:Expert` etc.) pour connaître la distance en
  Elo à répartir ; si cette étendue est grande, choisir des marches proches du
  bas de la cible (60–62 %) pour que le niveau le plus bas ne soit pas
  ridiculement faible.

  Format d'un réglage : `--reglage "Niveau=perturbation/oubli"` (répétable),
  perturbation entière `>= 0` ou `inf`/`none`/`illimite` (solveur complet),
  oubli dans `[0, 1]`. Trois modes :

  ```
  # 1. Mesure des quatre paires adjacentes par défaut, avec un réglage candidat :
  python scripts/calibrer_echelle.py --dossier /tmp/calib_240 \
      --reglage "Avancé=inf/0.05" --donnes 40

  # Paire(s) choisie(s), y compris l'étendue totale de l'échelle :
  python scripts/calibrer_echelle.py --dossier /tmp/calib_240 \
      --paire Débutant:Expert --donnes 20

  # 2. Balayage : plusieurs candidats pour UN niveau, contre un niveau FIXE,
  #    classés par proximité de la cible (60-70 % par défaut, --cible-basse/
  #    --cible-haute réglables) :
  python scripts/calibrer_echelle.py --dossier /tmp/calib_240 \
      --candidats "Avancé=inf/0.03,inf/0.06,inf/0.10" --contre Expert \
      --donnes 40 --processus 2

  # 3. Statut (lecture seule, n'interfère jamais avec un calcul en cours) :
  python scripts/calibrer_echelle.py --dossier /tmp/calib_240 --statut
  ```

  - **Reprise après interruption** : relancer EXACTEMENT la même commande sur
    le même `--dossier` saute les donnes déjà écrites et reprend à la
    dernière donne COMPLÈTE (une donne incomplète par coupure brutale, 1 ligne
    au lieu de 2, est rejouée en entier — jamais de ligne JSON corrompue
    exploitée). Augmenter `--donnes` sur un dossier existant PROLONGE la
    série (mesure grossière d'abord, puis affinée) sans la recommencer ; tout
    autre changement de réglage (niveaux, paires/balayage, graine, max_tours,
    budget solveur, cible) est REFUSÉ (`reglages.json` du dossier, empreinte
    comparée à chaque lancement) — le dossier ne mélange jamais deux séries.
  - **Rapport** (`<dossier>/rapport.txt`, réécrit en continu, atomiquement) :
    pour chaque paire/candidat, victoires du niveau le plus fort sur parties
    décidées, taux ± IC 95 %, verdict (« dans la cible » / « trop faible » /
    « trop fort »), écart en Elo (formule habituelle, `400·log10(p/(1-p))`,
    corrigée de continuité pour éviter un écart infini à 0 %/100 %) ; en mode
    paires, distance Elo CUMULÉE de chaque niveau à Expert (arête directe
    préférée si mesurée, sinon chaîne des paires adjacentes). Depuis #257,
    chaque ligne de résultat est suivie d'une ligne « manches : » (durée
    moyenne en tours, répartition des fins, temps de calcul par tour par
    niveau) lue depuis `stats_<label>.jsonl` (un fichier à part par tâche,
    une ligne par donne, en phase avec `resultats_<label>.jsonl` — voir
    `docs/contexte/ia_anti_don_joker.md` §11) ; absent sur un dossier créé
    avant #257, sans erreur (ligne simplement omise).
  - **Parallélisme** (`--processus 1` ou `2`) : chaque paire/candidat est une
    tâche indépendante, écrite dans son propre fichier JSON Lines
    (`resultats_<label>.jsonl`) — à 2 processus, un `ProcessPoolExecutor` joue
    deux tâches à la fois (une par processus, aucun risque de réécriture
    concurrente d'un même fichier) ; le rapport est régénéré depuis le disque
    toutes les ~2s pendant que les travailleurs écrivent.
  - **Budget du solveur** (`--budget-solveur`, défaut : valeur du jeu, 1,5 s)
    et garde-fou anti-blocage (`--max-tours`, défaut 300) appliqués à TOUTES
    les parties, comme les autres outils de ce tableau.
  - Commandes prêtes pour une campagne complète hors agent (budget relevé sur
    machine lente, dossier hors dépôt) :

    ```
    # PC fixe Windows (venv dédié) :
    C:\Tournois\venv\Scripts\python.exe scripts\calibrer_echelle.py ^
        --dossier C:\Tournois\calib_avance_240 --candidats "Avancé=inf/0.03,inf/0.06,inf/0.10" ^
        --contre Expert --donnes 60 --budget-solveur 3.0 --processus 2 --limite-temps 7200

    # ThinkPad (interpréteur système) :
    /usr/bin/python3 scripts/calibrer_echelle.py --dossier /tmp/calib_avance_240 \
        --candidats "Avancé=inf/0.03,inf/0.06,inf/0.10" --contre Expert \
        --donnes 60 --budget-solveur 1.5 --processus 2 --limite-temps 7200
    ```

- **Limite de temps RÉELLEMENT ferme (`scripts/_limite_temps_ferme.py`,
  #220) :** les deux tournois ci-dessus s'arrêtaient déjà PROPREMENT d'eux-
  mêmes dès `--limite-temps` dépassée (aucune nouvelle donne lancée), mais une
  donne déjà EN COURS pouvait dépasser cette limite sans aucune borne (#217 :
  dépassement de 244 s, puis processus resté vivant 30 minutes de plus sans
  rien calculer). Les deux scripts se relancent désormais eux-mêmes dans un
  SOUS-PROCESSUS (argument interne `--_worker`) surveillé par le processus
  parent : si `limite_temps` + une marge bornée (10 s) est dépassée malgré
  tout, le parent TERMINE ce sous-processus — et l'arbre de processus qu'il
  aurait créé — sur Linux (groupe de processus POSIX, `SIGTERM` puis
  `SIGKILL`) comme sous Windows (`taskkill /PID <pid> /T /F`, jamais `/IM` par
  motif de nom). Code de sortie : `0` terminé normalement, `3` arrêté sur la
  limite de temps, `1` erreur — utile pour qu'Alain, sur la machine Windows
  plus lente qui exécute désormais ces campagnes, puisse distinguer les deux
  cas sans relire le fichier de résultats.

- **`scripts/profil_joueur.py`** — PROFIL DE JOUEUR, côte à côte. Pour un
  **humain** (à partir des journaux, fichiers d'une même partie reliés par
  `partie_id`, **jugé par le modèle exact de la maison**) OU un **niveau d'IA**
  (parties simulées), calcule les mêmes indicateurs : tuiles posées/tour vs
  optimum, part des tours où le joueur pioche alors qu'un coup existait,
  répartition des poses par taille (petit/moyen/grand selon le nombre de
  combinaisons touchées), nombre moyen de tours, taux de victoire, et **DEUX
  indicateurs de fin de partie DISTINCTS à ne pas confondre** : (a) **tuiles
  restantes** en main quand le joueur perd = mesure du serrage, donc du NIVEAU
  (était-il près de finir ? un seul 13 restant pèse autant de points que cinq
  petites tuiles, mais est bien plus proche de la victoire) ; (b) **points
  restants** = prudence sur la valeur des tuiles, qui ne compte VRAIMENT qu'en
  match à plusieurs manches (en une manche, perdre à −1 ou −22 revient au même).
  L'affichage sépare (a) et (b) et rappelle leurs rôles. Ex. :

  ```
  # Profil d'un/de niveaux d'IA (le dossier de l'agent n'a pas de journaux) :
  python scripts/profil_joueur.py --niveau "Intermédiaire,Avancé,Expert" --donnes 40
  # Profil d'Alain (commande qu'ALAIN doit lancer, journaux activés) :
  python scripts/profil_joueur.py --journaux data/logs_parties --joueur Alain \
      --niveau "Intermédiaire,Avancé"
  ```

- **`scripts/analyser_coups_rates.py`** — le **juge par défaut est désormais le
  modèle exact de la MAISON** (`moteur/solveur_exact.py`) : plus aucune décision
  « inconclusive » ni coup manqué par gel de combinaisons. L'option `--juge-exact`
  (bibliothèque `rummikub-solver`, #204) devient un **contrôle croisé facultatif**
  et indépendant. Repli sur la recherche arborescente si `highspy`/`numpy` manque.

### Comment établir le niveau d'Alain (à faire par Alain)

Le niveau d'Alain **n'est pas** établi par #213 : il le sera par la comparaison
de SON profil (`profil_joueur.py --journaux …`, journaux inaccessibles à
l'agent) avec les profils des niveaux candidats, ET par quelques parties jouées
contre eux. Procédure : activer `log_parties` dans `config.json`, jouer des
parties jusqu'au terme, puis lancer les commandes ci-dessus.

### Tests

`tests/test_niveaux.py` : l'échelle a cinq niveaux ; un niveau inconnu retombe
sur Débutant (le niveau retiré « Champion du Monde » retombe spécifiquement
sur Expert, issue #235, voir l'archive en §13) ; `perturbation_max=0` ne
déplace **aucune** tuile et `None` récupère le joker ; la borne de
perturbation est respectée ; l'oubli à 100 % fait piocher, un coup gagnant
n'est jamais oublié, l'oubli décroît sur une petite main ; reproductibilité
sous `graine_ia` ; Expert atteint l'optimum exact sur les cas de référence ;
repli propre sans `highspy`/`numpy`.
(#217 : `test_oubli_declenche_pioche_coup_non_gagnant` épingle désormais la
perturbation de Facile à 0 via `monkeypatch` — Facile valant maintenant
perturbation 1, le coup riche de la donne de test VIDE la main, donc n'est
jamais oublié ; le test continue d'exercer le mécanisme d'oubli sur un coup
NON gagnant.)
Les tests existants (IA, moteur, solveurs) restent **inchangés** : les
fonctions heuristiques de niveau, toujours présentes, continuent d'être
testées directement.

`test_reglages_calibres_267` (issue #267) épingle les cinq réglages
ci-dessous et vérifie que chaque niveau est strictement plus fort que le
niveau juste en dessous sur au moins un des deux leviers, Expert au sommet
(seul niveau au solveur complet) ; `test_bridages_monotones_du_plus_faible_
au_plus_fort` ne suppose plus Avancé identique à Expert.

### Échelle calibrée (issue #267, méthode de #240)

Réglages retenus et appliqués dans `moteur/niveaux.BRIDAGES`, par la méthode
DESCENDANTE de #240 (chaque niveau validé contre le niveau juste au-dessus,
déjà figé ; règle de fin de manche réelle — blocage, #255 ; 50 donnes par
duel ; cible 60-70 % de victoires pour le niveau supérieur) :

| Niveau | `perturbation_max` | `taux_oubli` |
|--------|:--:|:--:|
| Débutant | 1 | 0,80 |
| Facile | 1 | 0,40 |
| Intermédiaire | 3 | 0,15 |
| Avancé | 6 | 0,04 |
| Expert | ∞ (solveur complet) | 0 |

**Avancé n'est plus identique à Expert** : Avancé est désormais un solveur
un-tour légèrement bridé (perturbation 6, comme Intermédiaire mais plus large
et avec un oubli bien plus faible) ; Expert reste seul à jouer le solveur
un-tour complet, sans aucune borne. `eviter_don_joker` est INCHANGÉ par #267
(toujours activé pour Intermédiaire, Avancé, Expert ; toujours désactivé pour
Débutant, Facile — voir `moteur/niveaux.BRIDAGES`).

Résultats des duels retenus :
- Facile (1/0,40) bat Débutant (1/0,80) à 67,0 % ± 9,2 (IC 95 %).
- Facile (1/0,40) contre Intermédiaire (3/0,15) : le plus fort des deux
  (Intermédiaire) gagne 65,0 %.
- Intermédiaire (3/0,15) validé dans son duel contre Avancé (déjà figé),
  dans la cible 60-70 %.
- Avancé (6/0,04) contre Expert : Expert gagne 127 manches sur 200 (100
  donnes, graine 31, miroir, règle de fin de manche réelle — blocage,
  #255) = **63,5 % ± 6,7 (+96 Elo)**, dans la cible 60-70 %. Résultat
  **identique** aux deux budgets de solveur mesurés : 4,0 s (campagne de
  calibration d'origine) et 1,5 s (budget de production, mesure de
  contrôle #269) — le budget entre 1,5 s et 4,0 s n'a changé aucune issue
  de manche sur ces donnes.

Temps par tour d'Avancé : mesuré lors du contrôle à 1,5 s (#269, mêmes 100
donnes miroir que ci-dessus) à 160 ms en moyenne, jusqu'à 4 594 ms au
maximum (Expert : 151 ms en moyenne, 1 953 ms au maximum) — manches de
64,4 tours en moyenne, toutes terminées par chevalet vide, aucune bloquée.
Le maximum d'Avancé dépasse nettement le budget de 1,5 s : explication
probable, **non vérifiée**, le niveau bridé appelle le solveur plusieurs
fois par tour (recherche limitée par la perturbation, règles du joker),
chaque appel étant borné par le budget plutôt que le tour dans son
ensemble.

#### Vérification après #272 et #273

Après #272 (contrôles du moteur sur l'origine des tuiles d'ouverture) et
#273 (plus aucune modification de la table pendant le tour d'ouverture,
pour l'IA comme pour le moteur), Alain a rejoué sur le PC fixe les quatre
duels de l'échelle, sans changer aucun réglage de `niveaux.BRIDAGES`
(Débutant 1/0,80, Facile 1/0,40, Intermédiaire 3/0,15, Avancé 6/0,04,
Expert inchangé). Conditions : commit `1136c8c` de master, `scripts/
calibrer_echelle.py`, graine 31, budget du solveur **1,5 s** (budget de
jeu réel, pas les 4,0 s des campagnes de calibration d'origine), règle de
fin de manche réelle (#255), cible 60-70 %, parties jouées en miroir.

- **Expert contre Avancé** : 100 donnes, Expert gagne 127 manches sur 200
  = 63,5 % ± 6,7 (+96 Elo) ; manches de 64,4 tours en moyenne, 100 %
  terminées par chevalet vide ; temps par tour Avancé 160 ms en moyenne
  (maximum 4 578 ms), Expert 149 ms (maximum 2 000 ms). Résultat
  **identique**, au match près, à la mesure d'avant #273 (déjà 127 sur
  200 ci-dessus) : la correction de #273 n'a changé l'issue d'aucune
  manche de ce duel.
- **Avancé contre Intermédiaire** : 50 donnes, Avancé gagne 61 manches
  sur 100 = 61,0 % ± 9,6 (+77 Elo) ; manches de 80,9 tours, 84 % finies
  par chevalet vide et 16 % bloquées ; temps par tour Avancé 419 ms en
  moyenne (maximum 18 765 ms), Intermédiaire 491 ms (maximum 116 156 ms).
- **Intermédiaire contre Facile** : 50 donnes, Intermédiaire gagne 63
  manches sur 100 = 63,0 % ± 9,5 (+91 Elo) ; manches de 109,7 tours, 23 %
  finies par chevalet vide et 77 % bloquées ; temps par tour Facile
  697 ms en moyenne (maximum 4 547 ms), Intermédiaire 837 ms (maximum
  95 578 ms). Mesure d'avant #273 : 65,0 % — léger recul mais toujours
  dans la cible.
- **Facile contre Débutant** : 50 donnes, Facile gagne 68 manches sur
  100 = 68,0 % ± 9,1 (+130 Elo) ; manches de 103,4 tours, 2 % finies par
  chevalet vide et 98 % bloquées ; temps par tour Débutant 728 ms en
  moyenne (maximum 7 625 ms), Facile 672 ms (maximum 4 610 ms). Mesure
  d'avant #273 : 67,0 % — stable.

Les quatre duels restent dans la cible 60-70 % : **l'échelle est validée
après #272 et #273, aucun réglage de `niveaux.BRIDAGES` ne change.**
L'écart total de Débutant à Expert reste d'environ 400 Elo, régulier à
chaque marche. Durées des campagnes : 33 min, 61 min, 140 min et 121 min.

Deux points de vigilance consignés sans cause affirmée (étude séparée
prévue) :
- les temps par tour **maximaux** relevés ici dépassent très largement
  le budget de 1,5 s du solveur (Intermédiaire jusqu'à 116 s et 96 s,
  Avancé jusqu'à 19 s) — cas rares, les moyennes restent sous la seconde ;
- l'ancienne mesure d'Intermédiaire d'avant #267 avait montré un maximum
  de 3 606 594 ms (environ une heure) pour un seul tour, probablement une
  mise en veille du PC, non reproduit depuis.

### Règle de l'ouverture appliquée à l'IA (issue #273, étude #270)

`_coup_maximal` (`moteur/ia.py`, chemin de Facile/Intermédiaire/Avancé en
repli) prolongeait à tort, pendant le tour de l'ouverture, des combinaisons
déjà posées par d'AUTRES joueurs aux tours précédents — interdit par les
règles du jeu (décision d'Alain : aucune combinaison préexistante modifiée
avant la mise initiale, voir `docs/contexte/moteur_regles.md`). Corrigé :
avant la mise initiale, les extensions ne portent plus que sur les
combinaisons posées CE tour depuis le chevalet. **Conséquence attendue** :
légère baisse de force de Facile, Intermédiaire et Avancé (une option
d'ouverture leur est désormais fermée) — non refait par #273 (mesure
d'impact seulement indicative, sur un petit échantillon). **Vérification
faite (issue #274)** : voir « Vérification après #272 et #273 »
ci-dessus — les quatre duels restent dans la cible 60-70 %, aucun réglage
de `niveaux.BRIDAGES` n'a changé.

### Règle de travail (issue #268) : les tests ne dépendent jamais des réglages calibrés

Depuis #267, Débutant vaut `perturbation_max=1` (plus `0`) : il appelle donc
le solveur exact à CHAQUE tour (≈ 1 s/tour), alors qu'avant il ne le faisait
jamais. **Un test ne doit jamais supposer qu'un niveau est rapide ou lent à
cause de SA calibration du moment** — modifier `niveaux.BRIDAGES` ne doit
jamais allonger la suite. Pour un test qui n'a besoin que d'un joueur FAIBLE
et RAPIDE (et non du comportement réel de Débutant), utiliser la fixture
`niveau_debutant_rapide` (`tests/conftest.py`) qui installe, pour la durée du
test seulement, l'ancien réglage rapide (perturbation 0, oubli 0,42,
`eviter_don_joker` faux). Les tests qui vérifient le comportement RÉEL d'un
niveau (`tests/test_niveaux.py`, et ceux qui testent vraiment Débutant ou
Avancé) gardent les réglages réels de `niveaux.py`, sans cette fixture.

### Tournoi à plusieurs niveaux à une même table (issue #276)

`scripts/tournoi_niveaux.py` fait jouer 2 à 4 niveaux ENSEMBLE, à une même
table, avec rotation des sièges — en COMPLÉMENT des duels ci-dessus (qui
restent la seule méthode de calibrage) : voir
`docs/contexte/scripts_simulation.md` §10 pour le détail (usage, métriques,
limites).

