# Issue #267 — Applique l'échelle d'IA calibrée (Débutant/Facile/Intermédiaire/Avancé)

## Contexte

Suite de la méthode de calibration par duels de #240
(`scripts/calibrer_echelle.py`) : appliquer dans `moteur/niveaux.BRIDAGES`
les réglages retenus pour les quatre niveaux du bas, Expert restant la
référence fixe. Issue interrompue trois fois par le délai de 1800 s ;
terminée à la main, commit `bf4cbb0`. Sa documentation (ce changelog, la
section « Échelle calibrée » de `docs/contexte/niveaux_ia_calibrage.md`)
n'avait jamais été écrite — c'est l'objet de #269, qui produit ce fichier
rétroactivement et ajoute le contrôle à budget de production.

## 1. Réglages appliqués (`src/rummikub/moteur/niveaux.py`)

Méthode DESCENDANTE (#240) : chaque niveau validé contre le niveau juste
au-dessus, déjà figé ; règle de fin de manche réelle (blocage, #255) ;
50 donnes par duel ; cible 60-70 % de victoires pour le niveau supérieur.

| Niveau | `perturbation_max` | `taux_oubli` |
|--------|:--:|:--:|
| Débutant | 0 → **1** | 0,42 → **0,80** |
| Facile | 1 (inchangé) | 0,30 → **0,40** |
| Intermédiaire | 4 → **3** | 0,08 → **0,15** |
| Avancé | ∞ (solveur complet) → **6** | 0 → **0,04** |
| Expert | ∞ (inchangé) | 0 (inchangé) |

`eviter_don_joker` **inchangé** (toujours activé pour Intermédiaire, Avancé,
Expert ; toujours désactivé pour Débutant, Facile).

**Avancé n'est plus identique à Expert** : Avancé devient un solveur un-tour
légèrement bridé (perturbation 6) ; Expert reste seul à jouer le solveur
un-tour complet, sans aucune borne. C'est le changement structurel le plus
important de cette issue — jusque-là (depuis #236), Avancé et Expert étaient
strictement identiques.

## 2. Fichiers modifiés

- `src/rummikub/moteur/niveaux.py` : table `BRIDAGES` (ci-dessus), docstring
  de module et commentaire au-dessus de la table réécrits (ne décrivent plus
  Avancé/Expert comme identiques).
- `src/rummikub/moteur/ia.py` : docstring de `_coup_selon_perturbation`
  corrigée — `perturbation_max is None` ne désigne plus « Avancé/Expert »
  mais Expert seul.
- `scripts/calibrer_echelle.py` : docstring de module mise à jour (l'outil a
  servi à chercher les réglages ci-dessus, campagne close, reste disponible
  pour une recalibration future).
- `scripts/echelle_niveaux.py` : docstring de module et des fonctions
  `_niveaux_identiques`/`_afficher_verdicts` corrigées — la paire
  Avancé–Expert n'est plus une égalité ATTENDUE par construction ; les deux
  fonctions détectent désormais une éventuelle paire identique PAR LA MESURE
  (`Bridage.complet` des deux côtés) plutôt que de la supposer sur les noms.
- `tests/test_niveaux.py` :
  - `test_bridages_monotones_du_plus_faible_au_plus_fort` ne suppose plus
    Avancé identique à Expert (`assert not ...["Avancé"].complet` /
    `assert ...["Expert"].complet`).
  - nouveau test `test_reglages_calibres_267` : épingle les cinq réglages
    ci-dessus, vérifie que chaque niveau est strictement plus fort que le
    niveau juste en dessous sur au moins un des deux leviers (perturbation
    plus grande ou oubli plus faible), Expert seul au solveur complet.
- `docs/contexte/niveaux_ia_calibrage.md` : section « Échelle calibrée »
  ajoutée (réglages, méthode, résultats des duels). Complétée et nettoyée
  par #269 (voir CHANGELOG-269.md) : chiffres réels du duel Avancé/Expert et
  du temps par tour d'Avancé, et ménage de l'historique des sections plus
  anciennes.

## 3. Résultats des duels (campagne de calibration, budget solveur 4,0 s)

- Facile (1/0,40) bat Débutant (1/0,80) à 67,0 % ± 9,2 (IC 95 %).
- Facile (1/0,40) contre Intermédiaire (3/0,15) : Intermédiaire (le plus
  fort) gagne 65,0 %.
- Intermédiaire (3/0,15) validé contre Avancé (déjà figé), dans la cible
  60-70 %.
- Avancé (6/0,04) contre Expert : Expert gagne 127 manches sur 200 (100
  donnes, graine 31, miroir) = 63,5 % ± 6,7 (+96 Elo), dans la cible 60-70 %.

## 4. Contrôle au budget de production (issue #269)

Les campagnes de calibration ci-dessus ont été jouées à budget solveur
4,0 s, alors que le budget réel de production est 1,5 s. Mesure de contrôle
faite sur le PC fixe (#269) : même campagne « Avancé 6/0,04 contre Expert »,
100 donnes (graine 31, miroir), à 1,5 s — résultat **identique** : 127/200
= 63,5 % ± 6,7. Le budget entre 1,5 s et 4,0 s n'a changé aucune issue de
manche sur ces donnes. Temps de calcul par tour mesurés à 1,5 s : Avancé
160 ms en moyenne (maximum 4 594 ms, au-delà du budget — cause probable non
vérifiée : plusieurs appels au solveur par tour, chacun borné
individuellement par le budget) ; Expert 151 ms en moyenne (maximum
1 953 ms) ; manches de 64,4 tours en moyenne, toutes terminées par chevalet
vide.

## Point de vigilance — interruptions et suite de tests cassée

L'issue a été **interrompue trois fois par le délai de 1800 s** avant
d'être terminée à la main (commit `bf4cbb0`). Le travail n'a donc pas suivi
le déroulé normal d'une issue CCL (pas de rapport de clôture ni de
changelog écrits à l'époque — objet de #269 ci-dessus).

Après l'application des réglages, la suite de tests s'est révélée
**bloquée** : `tests/test_export_trace.py` dépendait de l'ancien réglage de
Débutant (`perturbation_max=0`, rapide) comme adversaire faible et rapide ;
avec `perturbation_max=1`, Débutant appelle le solveur exact à chaque tour
(≈ 1 s/tour) et la suite ne se terminait plus. Corrigé par **#268** (fixture
`niveau_debutant_rapide`, garde-fou de durée par test — voir
`docs/contexte/niveaux_ia_calibrage.md`, section « Règle de travail »).
