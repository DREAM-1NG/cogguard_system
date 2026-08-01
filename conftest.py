from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent

for extra_path in (ROOT / "system" / "backend", ROOT / "system"):
    path_str = str(extra_path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
