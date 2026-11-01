from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_full_alembic_chain_renders_offline_sql():
    backend = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=backend,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert "CREATE TABLE risk_assessments" in result.stdout
    assert "b9e4d2a7c610" in result.stdout
