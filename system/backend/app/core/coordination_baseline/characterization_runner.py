from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd

from app.core.coordination_baseline.characterization import CharacterizationConfig, characterize_detect_output
from app.core.coordination_baseline.io_reproduction import DEFAULT_RELATIONS, run_dyna_colm_detect


def run_dyna_colm_characterize(
    events: pd.DataFrame,
    *,
    output_dir: Path | None = None,
    relations: Sequence[str] = DEFAULT_RELATIONS,
    seed: int = 42,
    detect_result: Mapping[str, object] | None = None,
    include_risk_report: bool = True,
    observer_lens: str = "network_security",
) -> dict[str, object]:
    detect_summary = (
        dict(detect_result)
        if detect_result is not None
        else run_dyna_colm_detect(
            events,
            output_dir=output_dir,
            relations=relations,
            seed=seed,
        )
    )
    characterization = characterize_detect_output(
        events=events,
        discovery=detect_summary.get("discovery", {}) if isinstance(detect_summary.get("discovery"), Mapping) else {},
        predictions=detect_summary.get("predictions", []),
        config=CharacterizationConfig(
            include_risk_report=include_risk_report,
            include_observer_lens=True,
            observer_lens=observer_lens,
        ),
    )
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "characterization_summary.json").write_text(
            __import__("json").dumps(characterization, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return characterization

