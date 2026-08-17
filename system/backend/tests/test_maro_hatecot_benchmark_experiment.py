from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_runner():
    path = Path(__file__).resolve().parents[1] / "scripts" / "run_maro_hatecot_benchmark_experiment.py"
    spec = importlib.util.spec_from_file_location("maro_hatecot_benchmark_runner", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_label_plan_uses_maro_binary_layout_only_for_binary_benchmarks():
    runner = _load_runner()

    assert runner.demonstration_label_plan(("non_hateful", "hateful")) == (
        "hateful",
        "hateful",
        "non_hateful",
        "non_hateful",
    )
    assert runner.demonstration_label_plan(("normal", "offensive", "hate")) == (
        "normal",
        "offensive",
        "hate",
    )


def test_benchmark_target_task_excludes_target_label_from_agent_input():
    runner = _load_runner()
    case = {
        "case_id": "hatexplain::test-1",
        "text": "Target post.",
        "labels": {"benchmark_label": "hate"},
        "metadata": {"category": "hatexplain"},
    }

    task = runner.benchmark_target_task(case, "HateXplain")

    assert task.query_case_id == "hatexplain::test-1"
    assert not hasattr(task, "query_label")
    assert "hate" not in task.__dict__.values()
