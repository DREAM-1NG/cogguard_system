from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List


PRIMARY_BASELINES = ("MINDS", "FOREST", "CasFT")


def template_rows(dataset: str, config_id: str) -> List[Dict]:
    rows = []
    for model in PRIMARY_BASELINES:
        task = "scale" if model == "CasFT" else "multi_scale"
        rows.append(
            {
                "model": model,
                "dataset": dataset,
                "task": task,
                "status": "failed",
                "reproduction_level": "frontier_reproduction_full_run",
                "config_id": config_id,
                "seed": None,
                "num_runs": 0,
                "same_protocol": True,
                "notes": "Fill this row only after running the original public code under the KT2 full-run protocol.",
                "msle": None,
                "mae": None,
                "rmse": None,
                "direction_accuracy": None,
                "candidate_recall_full": None,
                "hits@100": None,
                "map@100": None,
                "mrr": None,
                "macro_micro_consistency": None,
            }
        )
    return rows


def write_template(path: Path, dataset: str, config_id: str) -> Dict:
    rows = template_rows(dataset, config_id)
    payload = {
        "schema": "cogguard.kt2.same_protocol_full_run_baselines.template.v1",
        "status": "template_not_evidence",
        "dataset": dataset,
        "config_id": config_id,
        "rows": rows,
        "note": "This file is a checklist/template. Copy completed ok rows into same_protocol_full_run_baselines.json after real runs.",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="douban")
    parser.add_argument("--config_id", default="full-run-preflight")
    parser.add_argument("--out", default=str(Path("benchmark") / "same_protocol_full_run_baselines.template.json"))
    args = parser.parse_args()
    payload = write_template(Path(args.out), args.dataset, args.config_id)
    print(json.dumps({"status": payload["status"], "rows": len(payload["rows"]), "out": args.out}))


if __name__ == "__main__":
    main()
