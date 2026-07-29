from __future__ import annotations
import os, sys

# Linux : WM_CLASS affiché dans la barre des tâches
os.environ.setdefault("GDK_PROGRAM_CLASS", "Rummikub")

# Windows : AppUserModelID affiché dans la barre des tâches
if sys.platform == "win32":
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Rummikub")

from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from rummikub.ui.application import main

if __name__ == "__main__":
    raise SystemExit(main())
