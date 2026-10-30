# Issue #216 — Recalibrer l'échelle des niveaux (Débutant → Avancé) pour des écarts réguliers, Alain visé entre Intermédiaire et Avancé (suite de #213)

L'échelle de #213 était **ordonnée mais mal étalée** : mesurée sur le bon
critère de force — les **tuiles restantes en main quand le niveau PERD** (plus
bas = plus fort) — Facile donnait ≈ 7,7, Intermédiaire ≈ 6,0 et Avancé ≈ 2,7.
L'écart Intermédiaire→Avancé (6,0 → 2,7) était énorme tandis que
Facile→Intermédiaire (7,7 → 6,0) était minuscule, et le profil provisoire
d'Alain (≈ 3,5 tuiles) tombait pile dans le **trou** entre Intermédiaire et
Avancé. #216 **recalibre** Débutant, Facile et Intermédiaire (leurs deux
paramètres de bridage) pour des écarts réguliers, Alain visé **entre**
Intermédiaire et Avancé. **Avancé (solveur complet), Expert et Champion du Monde
ne sont pas touchés.** Voir **CONTEXTE.md §16** (section « Recalibrage #216 »).

## 1. Outil de recherche de réglages — `scripts/calibrer_niveaux.py`

- Nouveau script. Pour un **niveau** et une **grille de candidats**
  (`--perturbations` × `--oublis`), remplace TEMPORAIREMENT l'entrée du niveau
  dans `moteur/niveaux.BRIDAGES`, simule des donnes **en miroir** du niveau
  contre lui-même (graine fixe, reproductible — réutilise `comparer()` de
  `scripts/comparer_niveaux_ia.py`) et mesure, pour chaque réglage, la **moyenne
  des tuiles restantes du perdant**. Affiche la mesure de chaque réglage et,
  avec `--cible`, marque le **plus proche** (et signale si l'écart > 1 tuile :
  cible possiblement non atteignable avec les deux seuls paramètres, cf. §2).
- **Deux garde-fous de temps** (un niveau faible peut jouer > 300 tours) :
  `--max-tours` (défaut 150) borne chaque manche ; `--limite-temps` fixe une
  limite FERME pour toute la campagne (résultats partiels exploités).
- `--budget-solveur` (défaut 0,5 s, contre 1,5 s en production) raccourcit le
  balayage ; le réglage retenu est revérifié au tournoi complet.

## 2. Mesures et réglages retenus

Mesuré en miroir (graine 0), tuiles restantes en défaite :

| Niveau | #213 (perturbation / oubli → tuiles) | **#216 retenu** | **tuiles mesurées** |
|---|---|---|---|
| Débutant | 0 / 35 % (non mesuré, > 7,7) | **0 / 42 %** | **≈ 9,3** |
| Facile | 0 / 22 % → 7,7 | **0 / 15 %** | **≈ 7,0** |
| Intermédiaire | 3 / 12 % → 6,0 | **4 / 8 %** | **≈ 5,0** |
| Avancé | ∞ / 0 % → 2,7 | ∞ / 0 % *(inchangé)* | ≈ 2,7 |

- **Écarts réguliers** obtenus : 9,3 → 7,0 → 5,0 → 2,7, soit des sauts de
  l'ordre de **2,0 à 2,3 tuiles**. Alain (≈ 3,5) se situe désormais **entre
  Intermédiaire (≈ 5,0) et Avancé (≈ 2,7)**, comme voulu.
- **Cible Débutant ≈ 9 — limite des deux paramètres signalée (§2 de l'issue) :**
  avec `perturbation_max = 0`, la mesure sature vers **7–8** et le `taux_oubli`
  n'y pèse quasiment plus (il déplace surtout le **taux de victoire**, pas les
  tuiles restantes). On retient le réglage le plus faible utile (**oubli 0,42**,
  mesuré ≈ 9,3 sur la graine du tournoi) ; c'est le plus proche atteignable, pas
  un réglage calculé à la décimale.
- **Intermédiaire — attention mesure :** à `perturbation_max = 4`, chaque tour
  appelle le **solveur complet** (pour mesurer la perturbation du coup maximal
  avant de replier si > 4 tuiles déplacées) ; en MIROIR les parties s'éternisent
  et beaucoup atteignent le garde-fou de tours (puis sont écartées), ce qui
  **biaise la mesure vers le bas** si on borne trop court. La valeur ≈ 5,0 est
  cohérente avec l'ancrage fiable de #213 (perturbation 3 → 6,0) et la cible
  4,5 ; à revérifier par Alain sur un plus grand nombre de donnes au budget de
  production.

## 3. Application — `moteur/niveaux.py`

- Table `BRIDAGES` mise à jour (le SEUL endroit à régler), avec un commentaire
  qui documente la mesure justifiant chaque valeur et la limite de la cible
  Débutant. Avancé, Expert, Champion du Monde **inchangés**.

## 4. Tournoi de validation — `scripts/echelle_niveaux.py` (étendu)

- Ajout `--budget-solveur` (réduire le budget du solveur exact pour tenir une
  limite de temps ferme ; signalé dans l'en-tête du rapport) et `--donnes-profil`
  (mesure des **tuiles restantes en défaite par niveau**, en miroir, désormais
  **incluse dans le rapport** comme demandé).
- Campagne menée au premier plan, limite de temps ferme, sortie fichier. Voir
  les résultats en §5 de CONTEXTE.md et le rapport joint.

## 5. Tests & périmètre

- `tests/test_niveaux.py` : nouveau
  `test_bridages_monotones_du_plus_faible_au_plus_fort` — du plus faible au plus
  fort, `perturbation_max` ne décroît jamais (None = ∞) et `taux_oubli` ne croît
  jamais. Les tests existants de #213 **passent** inchangés (reproductibilité
  sous graine incluse).
- **Non touchés** : solveur, moteur de jeu hors `niveaux.py`, interface.
