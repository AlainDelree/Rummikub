# Issue #269 — Documentation de #267 : chiffres réels d'Avancé contre Expert, ménage dans la doc et CHANGELOG-267.md

## Contexte

#267 (application des réglages calibrés dans `niveaux.py`) a été interrompue
trois fois par le délai de 1800 s, terminée à la main (commit `bf4cbb0`),
sans rapport de clôture ni changelog. Sa documentation dans
`docs/contexte/niveaux_ia_calibrage.md` était restée approximative (chiffres
venus d'autres campagnes, renvoi vers un « rapport de clôture de #267 » qui
n'existe pas). Issue purement documentaire : aucun code touché.

Mesure de contrôle faite sur le PC fixe : campagne « Avancé 6/0,04 contre
Expert », 100 donnes (graine 31, miroir, 200 manches), règle de fin de
manche réelle (blocage, #255), budget solveur 1,5 s (production, contre
4,0 s en calibration). Résultat : Expert gagne 127/200 = 63,5 % ± 6,7
(+96 Elo) — **identique** au résultat obtenu à 4,0 s.

## 1. `docs/contexte/niveaux_ia_calibrage.md`, section « Échelle calibrée »

- Remplacé la phrase sur le temps par tour d'Avancé (chiffres venus des
  campagnes de Débutant/Facile, renvoi vers un rapport de clôture
  inexistant) par les chiffres réels du contrôle à 1,5 s : 160 ms en
  moyenne, 4 594 ms au maximum (Expert : 151 ms / 1 953 ms), manches de
  64,4 tours en moyenne toutes terminées par chevalet vide. Précisé que le
  maximum d'Avancé dépasse le budget et que la cause probable (appels
  multiples au solveur par tour, chacun borné individuellement) n'est pas
  vérifiée.
- Complété le résultat du duel Avancé/Expert (auparavant seulement « validé
  dans la cible ») par le détail chiffré ci-dessus, en indiquant les deux
  budgets (4,0 s en calibration, 1,5 s en contrôle #269) et l'identité des
  deux résultats. Les autres duels (Facile/Débutant, Facile/Intermédiaire,
  Intermédiaire/Avancé) laissés tels quels.

## 2. Ménage dans le même fichier

- §16 : la note « Expert et Avancé sont de nouveau STRICTEMENT IDENTIQUES …
  jusqu'à la calibration de #267 ci-dessous, qui y met fin » remplacée par
  une ligne d'historique courte (de #236 à #267, Avancé et Expert étaient
  identiques ; ce n'est plus vrai depuis #267, voir « Échelle calibrée »),
  sans conserver le raisonnement détaillé d'avant.
- Ligne vide manquante insérée avant le paragraphe commençant par
  `test_reglages_calibres_267` (collé au paragraphe précédent).
- Rien d'autre changé dans l'historique des sections plus anciennes.

## 3. `CHANGELOG-267.md` créé à la racine

Changelog rétroactif de #267 (jamais écrit à l'époque), même format que les
autres `CHANGELOG-<N>.md` : réglages appliqués, fichiers modifiés
(`niveaux.py`, `ia.py`, `scripts/calibrer_echelle.py`,
`scripts/echelle_niveaux.py`, `tests/test_niveaux.py`,
`docs/contexte/niveaux_ia_calibrage.md`), résultats des duels, le contrôle à
1,5 s de #269, et un point de vigilance sur les trois interruptions, le
commit manuel `bf4cbb0`, et la suite de tests cassée par la dépendance de
`test_export_trace.py` à l'ancien Débutant rapide (corrigée par #268).

## Vérifications

- Suite complète (`timeout 900 python -m pytest tests -q`, sortie dans
  `/tmp/pytest_issue269.log`) : **547 passed, 13 skipped en 138 s**, aucune
  régression.
- Aucun fichier de code modifié (`niveaux.py`, tests, `CONTEXTE.md`) : seuls
  `docs/contexte/niveaux_ia_calibrage.md`, `CHANGELOG-267.md` et
  `CHANGELOG-269.md` touchés.
- `CONTEXTE.md` : non modifié, et son index ne nécessite aucune mise à jour
  (le fichier de domaine cité, `niveaux_ia_calibrage.md`, y figure déjà).

py_compile : N/A (aucun fichier Python modifié).
