from __future__ import annotations

import asyncio
import inspect
from pathlib import Path

from app.config import PROJECT_ROOT
from app.services import kt2_prediction_service


def test_kt2_cached_prediction_uses_internal_research_artifact():
    result = asyncio.run(
        kt2_prediction_service.predict_kt2_macro_micro(
            dataset="twitter",
            seed=42,
            run_live=False,
        )
    )

    artifact = Path(result["artifact"])
    assert result["status"] == "ok"
    assert artifact.is_relative_to(PROJECT_ROOT / "research" / "kt2")


def test_kt2_prediction_service_has_no_external_cogguard_dev_path_or_sys_path_patch():
    source = inspect.getsource(kt2_prediction_service)

    assert "subsystems" not in source
    assert "cogguard_dev" not in source.lower()
    assert "sys.path.insert" not in source
