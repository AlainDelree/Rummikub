from __future__ import annotations
import os, sys

# Linux : WM_CLASS affiché dans la barre des tâches
os.environ.setdefault("GDK_PROGRAM_CLASS", "Rummikub")

# Windows : AppUserModelID affiché dans la barre des tâches
if sys.platform == "win32":
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Rummikub")

import json
import subprocess
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def _lancer_actualise_ui_si_flag():
    """Si Actualise a déposé un flag de mise à jour dans le dossier
    d'installation, lance ActualiseUI.exe avant l'ouverture de la fenêtre.
    Ne doit JAMAIS bloquer le démarrage de Rummikub."""
    _flag = Path(sys.executable).parent / "actualise_update.flag"
    if _flag.exists():
        try:
            _data = json.loads(_flag.read_text(encoding="utf-8"))
            subprocess.Popen([
                _data["actualise_ui"],
                "--bat", _data["bat"],
                "--flag", str(_flag),
                "--relancer", sys.executable,
            ])
        except Exception:
            pass  # ne jamais bloquer le démarrage de Rummikub


from rummikub.ui.application import main

if __name__ == "__main__":
    _lancer_actualise_ui_si_flag()
    raise SystemExit(main())
