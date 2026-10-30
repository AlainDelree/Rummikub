# Issue #217 — Remonter le niveau Facile pour l'écarter de Débutant (suite de #216)

Après #216, le **bas** de l'échelle restait mal réparti : Débutant (0 / 0.42) et
Facile (0 / 0.15) étaient quasi indistincts — Débutant gardait même
LÉGÈREMENT MOINS de tuiles que Facile (6,95 vs 7,25), donc l'ordre était
*inversé* — et Facile perdait contre Intermédiaire à **85 %** (hors cible
60–80 %). Cause : **à perturbation = 0, le taux d'oubli ne pèse presque plus sur
l'issue des parties** (il déplace le taux de victoire, pas les tuiles restantes),
donc pousser l'oubli de Débutant à 0,42 ne l'a pas affaibli comme attendu.

Décision d'Alain : **remonter Facile** (le rendre plus fort). Cela résout les
deux anomalies à la fois — Facile se détache de Débutant par le haut, et l'écart
Facile↔Intermédiaire se réduit. **Débutant, Intermédiaire, Avancé, Expert et
Champion du Monde ne sont PAS touchés.** Voir **CONTEXTE.md §16** (section
« Recalibrage #217 »).

## 1. Réglage retenu — `moteur/niveaux.py`, ligne Facile uniquement

- **Facile : perturbation `0 → 1`, oubli `0.15 → 0.30`.**
  - La **perturbation** est le seul levier qui sépare réellement les niveaux du
    bas (#216) : perturbation 1 autorise de petits **coups de récupération**
    (déplacer au plus 1 tuile du plateau) que l'oubli seul ne permettait pas.
  - L'**oubli** passe de 0,15 à 0,30 pour viser la cible de l'issue (≈ 6,0–6,3
    tuiles restantes en défaite, entre Débutant ≈ 7 et Intermédiaire ≈ 5,4) : le
    smoke pert1/oubli0.15 donnait ≈ 4,0 tuiles — TROP fort (sous Intermédiaire) ;
    0,30 rapproche Facile de la cible.
- **Facile est désormais STRICTEMENT entre Débutant et Intermédiaire sur LES
  DEUX leviers**, ce qui garantit l'ordre *par construction* (et non seulement
  statistiquement) :
  - oubli 0,30 < Débutant 0,42 **et** perturbation 1 > Débutant 0 → Facile plus
    fort que Débutant (l'inversion d'ordre ne peut plus se produire) ;
  - oubli 0,30 > Intermédiaire 0,08 **et** perturbation 1 < Intermédiaire 4 →
    Facile reste clairement plus faible qu'Intermédiaire (aucun dépassement).
- Monotonie préservée : perturbation non décroissante `[0, 1, 4, ∞, ∞, ∞]`,
  oubli non croissant `[0.42, 0.30, 0.08, 0, 0, 0]`.

## 2. Limite computationnelle du calibrage/tournoi (comme #216)

- La mesure fine **en miroir** n'est **pas fiable** pour un niveau à
  perturbation > 0 : deux joueurs égaux pert=1 recyclent le plateau et quasiment
  **toutes les donnes atteignent le garde-fou de tours** (même précaution que
  pour Intermédiaire pert=4 à #216). Le balayage `calibrer_niveaux.py` à
  perturbation 1 n'a donc produit presque aucune manche décidée.
- Le **tournoi de validation au budget de production** est trop coûteux pour
  aboutir dans le temps imparti de #217 : la comparaison de réglages candidats
  (pert1 × oubli 0.20 / 0.30 / 0.42, 2 paires, lancée **en parallèle**) n'a
  décidé que ≈ 2–6 manches par cas (marges ± 30–70 pt → **non significatif**).
- Mesure post-changement au **budget de production** (1,5 s/tour, max_tours 300,
  graine 0, 340 s) : **Débutant vs Facile → Facile 2/12 = 16,7 % ± 21,1 pt**
  (6 donnes). Chiffre **non significatif** (n=12, marge ± 21 pt couvrant
  largement 50 %) et à prendre avec prudence : #216 a établi que le taux de
  victoire est un signal **peu sensible** au bas de l'échelle (Débutant vs Facile
  valait déjà 55 % « non significatif »). Il ne contredit pas la garantie
  structurelle d'ordre (sur les tuiles restantes) ; la fourchette cible 60–75 %
  demande la validation complète ci-dessous pour être tranchée.
- Le réglage s'appuie donc sur la **garantie structurelle** du §1. La validation
  complète est laissée à relancer par Alain, hors contrainte de temps (commande
  ci-dessous).

## 3. Nouvel outil — `scripts/valider_bas_echelle.py`

- Tournoi de validation **ciblé** du bas de l'échelle : joue uniquement
  **Débutant vs Facile** et **Facile vs Intermédiaire**, et mesure les **tuiles
  restantes en défaite** de Débutant / Facile / Intermédiaire. **Résultats
  partiels écrits en continu** dans `--sortie` (après chaque donne), limite de
  temps ferme (`--limite-temps`), `--budget-solveur` réglable, filtre `--paire`,
  et override temporaire d'un réglage candidat de Facile
  (`--facile-perturbation` / `--facile-oubli`) pour comparer sans figer
  `niveaux.py`. Réutilise `comparer()` de `scripts/comparer_niveaux_ia.py`.
- **Commande de validation définitive à relancer par Alain :**

  ```
  python scripts/valider_bas_echelle.py --donnes 40 --seed 0 \
      --budget-solveur 1.5 --max-tours 300 --limite-temps 5400 \
      --donnes-profil 20 --sortie resultats_bas_echelle_217.txt
  ```

## 4. Tests

- `tests/test_niveaux.py::test_oubli_declenche_pioche_coup_non_gagnant` : épingle
  désormais la perturbation de Facile à 0 via `monkeypatch`. Facile valant
  maintenant perturbation 1, le coup riche de la donne de test **vide la main**
  (coup gagnant, jamais oublié) ; on pin la perturbation à 0 pour que le seul
  coup reste l'extension d'une tuile NON gagnante et continuer d'exercer le
  mécanisme d'oubli. Même motif que `test_oubli_100pct_pioche_toujours`.
- `test_bridages_monotones_du_plus_faible_au_plus_fort`, reproductibilité sous
  graine, et toute la suite (#213/#216) **au vert** : 322 passed, 13 skipped.

## 5. Hors périmètre — non touchés

- Solveur, moteur hors `niveaux.py`, interface : **inchangés**.
- Débutant, Intermédiaire, Avancé, Expert, Champion du Monde : **inchangés**.
