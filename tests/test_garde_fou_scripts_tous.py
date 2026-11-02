"""Empêche qu'un futur script de mesure oublie le garde-fou « solveur exact
requis » (issue #224, qui étend #223 à tous les scripts qui font jouer l'IA).

Détecte, par une recherche de TEXTE dans ``scripts/*.py`` (même critère que
l'inventaire de l'issue #224, point 1), les scripts qui font jouer l'IA par
un chemin dépendant du solveur exact :
  - appel à ``jouer_ia(``, ``jouer_niveau_bride(`` ou ``jouer_niveau_expert(`` ;
  - appel à ``creer_partie(`` (pilote une partie simulée, donc potentiellement
    tous les niveaux) ;
  - import de ``comparer_niveaux_ia`` (qui, lui, pilote des parties via
    ``jouer_niveau_bride``/``jouer_ia`` — voir son propre module).

Chaque script détecté doit soit importer et appeler
``exiger_solveur_exact_ou_quitter`` (le garde-fou de ``_verif_solveur_exact.py``),
soit figurer dans ``EXCEPTIONS`` ci-dessous avec une justification."""

import re
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"

_RE_APPEL_JEU = re.compile(
    r"\b(jouer_ia|jouer_niveau_bride|jouer_niveau_expert|creer_partie)\s*\(")
_RE_IMPORT_COMPARER = re.compile(
    r"(from\s+comparer_niveaux_ia\s+import|import\s+comparer_niveaux_ia\b)")

_RE_IMPORT_GARDE_FOU = re.compile(r"from\s+_verif_solveur_exact\s+import")
_RE_APPEL_GARDE_FOU = re.compile(r"\bexiger_solveur_exact_ou_quitter\s*\(")

# Scripts qui font jouer l'IA (détectés par les motifs ci-dessus) mais
# n'appellent PAS le garde-fou — chaque entrée DOIT porter une justification.
# Vide aujourd'hui : les 10 scripts détectés appellent tous le garde-fou
# (voir issue #224, point 2).
EXCEPTIONS: dict[str, str] = {}


def _fait_jouer_ia(texte: str) -> bool:
    return bool(_RE_APPEL_JEU.search(texte) or _RE_IMPORT_COMPARER.search(texte))


def _a_le_garde_fou(texte: str) -> bool:
    return bool(_RE_IMPORT_GARDE_FOU.search(texte)
                and _RE_APPEL_GARDE_FOU.search(texte))


def _scripts_qui_font_jouer_ia() -> dict[str, str]:
    return {
        f.name: f.read_text(encoding="utf-8")
        for f in sorted(_SCRIPTS.glob("*.py"))
        if _fait_jouer_ia(f.read_text(encoding="utf-8"))
    }


def test_inventaire_connu():
    """Sanity check de la détection elle-même, sur l'inventaire de l'issue
    #224 (point 1) — si cette liste change, c'est que la détection ou
    l'inventaire a changé : à revérifier consciemment, pas en silence."""
    attendu = {
        "_campagne_186.py",
        "calibrer_niveaux.py",
        "comparer_niveaux_ia.py",
        "echelle_niveaux.py",
        "generer_corpus_positions_222.py",
        "match_solveurs.py",
        "profil_joueur.py",
        "simulation_ia.py",
        "valider_bas_echelle.py",
        "verifier_simplicite_expert.py",
    }
    assert set(_scripts_qui_font_jouer_ia()) == attendu


def test_tout_script_qui_fait_jouer_ia_a_le_garde_fou_ou_une_exception():
    manquants = []
    for nom, texte in _scripts_qui_font_jouer_ia().items():
        if nom in EXCEPTIONS:
            continue
        if not _a_le_garde_fou(texte):
            manquants.append(nom)
    assert not manquants, (
        f"script(s) sans garde-fou solveur exact ni exception justifiée : "
        f"{manquants} — voir _verif_solveur_exact.py (issue #223/#224)")


def test_exceptions_ont_toutes_une_justification_non_vide():
    for nom, justification in EXCEPTIONS.items():
        assert justification.strip(), f"exception {nom} sans justification"
