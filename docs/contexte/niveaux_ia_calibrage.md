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
> **Expert et Avancé sont de nouveau STRICTEMENT IDENTIQUES** (même solveur
> exact complet, aucune étape additionnelle) : le plateau statistique
> Avancé ≈ Expert décrit plus haut n'est donc plus une approximation
> provisoire mais l'état réel et définitif de l'échelle.

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

