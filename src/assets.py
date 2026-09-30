# Locates files under the repo's assets/ folder, from source or from a PyInstaller build.

import sys
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def assetPath(name):
    return str(ROOT / "assets" / name)
