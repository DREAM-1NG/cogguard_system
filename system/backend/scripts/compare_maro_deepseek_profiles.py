"""Compare two completed MARO DeepSeek profiles without re-running an LLM."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.review.maro_experiment_evaluation import compare_maro_profiles  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixed-dir", required=True)
    parser.add_argument("--routed-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    comparison = compare_maro_profiles(
        _load_profile_rows(Path(args.fixed_dir)),
        _load_profile_rows(Path(args.routed_dir)),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: comparison[key] for key in ("shared_case_count", "fixed", "routed")}, ensure_ascii=False, indent=2))
    return 0


def _load_profile_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/agent_predictions.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
