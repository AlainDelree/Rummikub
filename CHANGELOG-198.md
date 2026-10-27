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
