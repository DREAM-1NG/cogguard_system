from __future__ import annotations

import argparse
import re
from pathlib import Path

from benchmark import (
    kt2_minds_comparison,
    propagation_fair_learned_matrix_20260810,
    propagation_training_adequacy_20260810,
    run_benchmark,
    same_protocol_full_run_baselines,
)


BENCHMARK_DIR = Path(__file__).resolve().parents[1] / "benchmark"


def _parser_defaults(parser: argparse.ArgumentParser) -> dict[str, object]:
    return vars(parser.parse_args([]))


def test_trainable_propagation_entrypoints_default_to_200_epochs() -> None:
    adequacy_defaults = _parser_defaults(propagation_training_adequacy_20260810.build_arg_parser())
    fair_defaults = _parser_defaults(propagation_fair_learned_matrix_20260810.build_arg_parser())
    kt2_minds_defaults = _parser_defaults(kt2_minds_comparison.build_arg_parser())
    public_baseline_defaults = _parser_defaults(same_protocol_full_run_baselines.build_arg_parser())
    suite_defaults = _parser_defaults(run_benchmark.build_arg_parser())

    assert adequacy_defaults["epoch_grid"] == "200"
    assert fair_defaults["epochs"] == 200
    assert kt2_minds_defaults["minds_epochs"] == 200
    assert kt2_minds_defaults["kt2_epochs"] == 200
    assert public_baseline_defaults["minds_epochs"] == 200
    assert public_baseline_defaults["forest_epochs"] == 200
    assert public_baseline_defaults["forest_rl_epochs"] == 200
    assert public_baseline_defaults["casft_max_epoch"] == 200
    assert suite_defaults["epochs"] == 200
    assert suite_defaults["hyperidp_adv_epochs"] == 200
    assert suite_defaults["kt2_joint_epochs"] == 200
    assert suite_defaults["frontier_epochs"] == 200


def test_propagation_powershell_queues_do_not_launch_short_epoch_runs() -> None:
    launchers = [
        BENCHMARK_DIR / "run_propagation_training_sufficiency_full_20260811.ps1",
        BENCHMARK_DIR / "run_propagation_sota_full_20260810.ps1",
        BENCHMARK_DIR / "run_propagation_sota_stable_20260810.ps1",
    ]
    short_epoch_pairs = re.compile(
        r'"--(?:epoch_grid|minds_epochs|kt2_epochs|forest_epochs|forest_rl_epochs|casft_max_epoch|frontier_epochs)"'
        r'\s*,\s*"(?:1|5|10|20|30|50)"'
    )

    for launcher in launchers:
        text = launcher.read_text(encoding="utf-8")
        assert not short_epoch_pairs.search(text), launcher


def test_legacy_propagation_experiment_entrypoints_do_not_default_to_short_epochs() -> None:
    legacy_entrypoints = [
        BENCHMARK_DIR / "kt2_original_fusion_experiment.py",
        BENCHMARK_DIR / "kt2_original_fusion_ablation.py",
    ]
    short_epoch_default = re.compile(r'parser\.add_argument\("--epochs",\s*type=int,\s*default=(?:1|5|10|20|30|50)\)')

    for entrypoint in legacy_entrypoints:
        text = entrypoint.read_text(encoding="utf-8")
        assert not short_epoch_default.search(text), entrypoint


def test_propagation_adapter_entrypoints_default_to_200_epochs() -> None:
    checks = [
        ("minds_runner.py", "--epochs"),
        ("forest_runner.py", "--epochs"),
        ("forest_runner.py", "--rl_epochs"),
        ("casft_runner.py", "--max_epoch"),
        ("temporal_graph_runner.py", "--epochs"),
        ("hyperidp_adversarial_proxy.py", "--epochs"),
        ("kt2_sequence_joint_model.py", "--epochs"),
        ("kt2_joint_model.py", "--epochs"),
    ]
    for filename, argument in checks:
        text = (BENCHMARK_DIR / "adapters" / filename).read_text(encoding="utf-8")
        assert re.search(
            rf'add_argument\("{re.escape(argument)}"[^)]*default=200\)',
            text,
            flags=re.DOTALL,
        ), f"{filename} {argument}"

    sequence_text = (BENCHMARK_DIR / "adapters" / "kt2_sequence_joint_model.py").read_text(encoding="utf-8")
    joint_text = (BENCHMARK_DIR / "adapters" / "kt2_joint_model.py").read_text(encoding="utf-8")
    assert 'kwargs.get("epochs", 200)' in sequence_text
    assert 'kwargs.get("epochs", 200)' in joint_text
