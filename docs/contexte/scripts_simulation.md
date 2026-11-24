# Scripts de simulation IA vs IA

## 9. Scripts de simulation IA vs IA (`scripts/`)

- `scripts/simulation_ia.py` : fait jouer 2 à 4 IA sur un match de `--manches`
  N manches (défaut 1), journalise les anomalies (coup invalide, blocage) et
  affiche, pour plusieurs manches, le résultat par manche et le vainqueur du
  match (plus haut score cumulé — issue #203). Utile pour un test de fumée
  ponctuel.
- `scripts/comparer_niveaux_ia.py` (#184, `--manches` N depuis #203) : compare
  deux niveaux d'IA sur un grand nombre de **matchs** de N manches à 2
  joueurs, pour savoir si l'un est réellement plus fort que l'autre. Avec
  plusieurs manches, le vainqueur d'un match est le joueur au plus haut score
  cumulé ; le rapport donne les résultats par match (victoires, score cumulé
  moyen) ET par manche (fins, durée, pénalités). Chaque donne (même
  distribution de tuiles) est jouée deux fois en miroir (places échangées),
  pour annuler l'effet du
  tirage ; avec la même graine, la campagne est reproductible à l'identique.
  Toujours via le moteur Python seul, jamais pywebview (§7). Usage :

  ```
  python scripts/comparer_niveaux_ia.py --niveau-a Avancé --niveau-b Expert
  python scripts/comparer_niveaux_ia.py --niveau-a Avancé --niveau-b Expert \
      --donnes 200 --seed 7 --max-tours 500
  # Depuis #211 : comparer deux réglages d'ÉVALUATION DE LA MAIN d'Expert,
  # en miroir dans une même campagne (le reste identique) :
  python scripts/comparer_niveaux_ia.py --niveau-a Expert --niveau-b Expert \
      --eval-a off --eval-b complet --manches 3 --donnes 30
  ```

  **Depuis #211**, `--eval-a`/`--eval-b` appliquent un preset d'évaluation de la
  main restante (`moteur/evaluation_main.depuis_preset` : `off`, `complet`,
  `doublons`, `bords`, `points`, `points-nul|faible|moyen|fort`, suffixe
  `-avant`/`-apres` pour la position vs la simplicité) à l'Expert de chaque camp
  — voir §13 pour les résultats chiffrés de la campagne #211.

  Affiche : victoires/taux/marge d'erreur (IC 95 %) par niveau, nombre
  moyen de tuiles/points de pénalité du perdant, durée moyenne en tours,
  répartition des fins de partie (chevalet vidé / manche bloquée — vraie
  règle du blocage, issue #255, pioche vide ET tous passés — / arrêtée
  par le garde-fou anti-blocage), temps de calcul moyen/maximal d'un
  tour de décision par niveau (repérage d'un emballement de la recherche de
  libération de joker), et, **depuis #187**, le nombre d'anomalies de
  conservation des tuiles : à chaque coup, les 106 tuiles de référence
  doivent être présentes exactement une fois (mains + plateau + pioche,
  voir `_anomalies_conservation`) ; un coup refusé par le garde-fou
  anti-disparition de `jouer_tour` (§4) est compté à part et clairement
  signalé dans le rapport (ne doit normalement jamais arriver, puisque
  l'IA revalide ses propres coups avant de les proposer). **Depuis #190**,
  le rapport affiche aussi le nombre de tours où Expert s'est replié sur la
  recherche arborescente (`jouer_un_tour` appelle `ia.jouer_niveau_bride(...,
  on_repli=..., on_aucun=...)` — le MÊME chemin de production que `jouer_ia`,
  voir #223 ci-dessous — pour compter ces replis sans dupliquer la logique
  de décision), **en distinguant, depuis #223, TROIS causes** (voir aussi
  §13) : (1) budget de temps réellement dépassé sans rien trouvé
  (`BudgetExactDepasse` — un problème de vitesse, la seule cause que
  l'accélération de #190 peut réduire) ; (2) solveur exact indisponible
  (`solveur_exact.DISPONIBLE` faux au moment de l'appel — dépendances
  absentes) ; (3) toute autre anomalie (résultat non valide, exception —
  ne devrait normalement jamais survenir puisque le script refuse de
  démarrer sans solveur exact, voir §13). **Avant #223, les causes (2) et
  (3) étaient confondues sous un seul bucket, étiqueté « coup légitimement
  impossible, aucun rapport avec la vitesse »** — une étiquette FAUSSE
  quand la cause réelle était (2), ce qui a fait perdre une campagne entière
  (incident documenté en §13). Le cas réellement légitime, « aucun coup
  possible » (le solveur exact PROUVE qu'il n'y a rien à jouer, via
  `on_aucun`), n'est PAS un repli : compté séparément depuis #223. Les deux
  premières versions du compteur de repli (avant #190) ne distinguaient
  RIEN, ce qui rendait la mesure peu interprétable : le taux de repli
  « toute cause » restait élevé et quasi inchangé avant/après #190 (la
  plupart des replis étaient déjà, avant tout correctif, de cause
  NON liée au budget de temps) — voir CHANGELOG-190 pour les chiffres
  corrigés de l'époque (établis avec l'ancienne distinction à deux causes,
  depuis affinée par #223 ci-dessus). Première
  campagne (#184, Avancé vs Expert avant le solveur de réarrangement
  global, 50 donnes) : écart non significatif à 95 % (53 % / 47 % sur
  100 parties). **#186** (Expert = solveur de réarrangement global,
  §8bis), à budget de production (1.5s/tour), 40 parties (2 lots) : écart
  significatif, Expert 80.0 % ± 12.4 pt, part de parties bloquées (pioche
  épuisée) 10 % (contre 29 % en #184) — mesure **invalidée a posteriori**
  par #187 (bug de disparition de tuiles non détecté à l'époque, faute du
  contrôle de conservation ci-dessus). **#187** (mêmes paramètres, rejoués
  après correctif) : Expert 72.5 % ± 13.8 pt (29/40, IC qui recouvre
  largement celui de #186 — écart non démontrable comme un effet du
  correctif avec cet échantillon), 0 anomalie de conservation des tuiles
  sur l'ensemble de la campagne — voir CHANGELOG-187 pour le détail
  complet. **#190** (solveur rendu progressif, mêmes paramètres) : voir
  CHANGELOG-190 pour les chiffres avant/après (taux de victoire, parties
  bloquées, replis d'Expert sur Avancé, temps par tour).

**Réglage de mesure `--fin-manche-pioche-vide-test`** (issue #256,
désactivé par défaut, disponible sur `simulation_ia.py`,
`comparer_niveaux_ia.py` et `calibrer_echelle.py`) : depuis la vraie règle
de blocage (#255), une manche Intermédiaire/Intermédiaire peut dépasser
300 s sans se décider (plus de pioche pour borner la durée) — à n'utiliser
QUE pour accélérer une campagne de calibration (`calibrer_echelle.py`,
§16), jamais pour une mesure destinée à juger le jeu réel : les résultats
obtenus avec cette option NE REMPLACENT PAS une vérification finale avec
la vraie règle. Dans `calibrer_echelle.py`, le réglage fait partie des
paramètres de la série (`reglages.json`) : reprendre un dossier existant
avec l'autre règle est refusé, comme pour la graine/max_tours/budget/cible.
Détail (fonctionnement moteur, rapport, mesure chiffrée) :
`docs/contexte/ia_anti_don_joker.md` §10.

