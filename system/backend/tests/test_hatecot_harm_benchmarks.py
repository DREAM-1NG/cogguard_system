from __future__ import annotations

import csv
import json

from app.core.review.hatecot_harm_benchmarks import (
    HATECOT_BENCHMARKS,
    build_benchmark_target_manifest,
    load_hatecheck_cases,
    load_hatexplain_cases,
    load_latent_hate_cases,
    map_hatecot_source_cases,
    select_benchmark_target_cases,
)


def _source_case(case_id: str, label: str, domain: str = "source") -> dict[str, object]:
    return {
        "case_id": case_id,
        "text": f"{label} source text",
        "labels": {"interpersonal_harm": label},
        "metadata": {"category": domain},
    }


def test_hatecheck_source_mapping_collapses_only_for_its_explicit_binary_protocol():
    mapped = map_hatecot_source_cases(
        [
            _source_case("normal", "non_harmful"),
            _source_case("offensive", "offensive"),
            _source_case("hate", "hate"),
        ],
        benchmark=HATECOT_BENCHMARKS["HateCheck"],
    )

    assert [item["labels"]["benchmark_label"] for item in mapped] == [
        "non_hateful",
        "hateful",
        "hateful",
    ]
    assert HATECOT_BENCHMARKS["HateCheck"].source_mapping_is_proxy is False


def test_latent_hate_source_mapping_is_explicitly_marked_as_a_proxy():
    benchmark = HATECOT_BENCHMARKS["Latent_Hate"]
    mapped = map_hatecot_source_cases(
        [
            _source_case("normal", "non_harmful"),
            _source_case("offensive", "offensive"),
            _source_case("hate", "hate"),
        ],
        benchmark=benchmark,
    )

    assert [item["labels"]["benchmark_label"] for item in mapped] == [
        "not_hate",
        "implicit_hate",
        "implicit_hate",
    ]
    assert benchmark.source_mapping_is_proxy is True


def test_hatecheck_loader_keeps_gold_label_outside_agent_visible_label_key(tmp_path):
    path = tmp_path / "test_suite_cases.csv"
    path.write_text(
        "case_id,test_case,label_gold,functionality\n"
        "1,Targeted attack,hateful,derogation\n"
        "2,Protected group mention,non-hateful,neutral\n",
        encoding="utf-8",
    )

    cases, manifest = load_hatecheck_cases(path)

    assert [case["labels"]["benchmark_label"] for case in cases] == ["hateful", "non_hateful"]
    assert manifest["target_labels_sent_to_agent"] is False
    assert all("gold_label" not in case for case in cases)


def test_hatexplain_loader_uses_majority_label_and_official_test_split(tmp_path):
    data_dir = tmp_path / "Data"
    data_dir.mkdir()
    (data_dir / "dataset.json").write_text(
        json.dumps(
            {
                "test-1": {
                    "post_id": "test-1",
                    "post_tokens": ["targeted", "abuse"],
                    "annotators": [
                        {"label": "offensive"},
                        {"label": "offensive"},
                        {"label": "hatespeech"},
                    ],
                },
                "train-1": {
                    "post_id": "train-1",
                    "post_tokens": ["normal"],
                    "annotators": [{"label": "normal"}] * 3,
                },
            }
        ),
        encoding="utf-8",
    )
    (data_dir / "post_id_divisions.json").write_text(
        json.dumps({"train": ["train-1"], "test": ["test-1"]}),
        encoding="utf-8",
    )

    cases, manifest = load_hatexplain_cases(tmp_path)

    assert len(cases) == 1
    assert cases[0]["case_id"] == "hatexplain::test-1"
    assert cases[0]["labels"]["benchmark_label"] == "offensive"
    assert manifest["split"] == "test"


def test_latent_hate_loader_uses_declared_binary_stage_one_labels(tmp_path):
    path = tmp_path / "implicit_hate_v1_stg1_posts.tsv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["post", "class"], delimiter="\t")
        writer.writeheader()
        writer.writerows([
            {"post": "implicit attack", "class": "implicit_hate"},
            {"post": "neutral text", "class": "not_hate"},
        ])

    cases, manifest = load_latent_hate_cases(path)

    assert [case["labels"]["benchmark_label"] for case in cases] == ["implicit_hate", "not_hate"]
    assert manifest["label_semantics"] == "stage_one_binary_hate_presence"


def test_target_sampling_is_stratified_and_manifest_marks_rows_evaluation_only():
    benchmark = HATECOT_BENCHMARKS["HateXplain"]
    cases = [
        {
            "case_id": f"{label}-{index}",
            "text": f"{label} target text {index}",
            "labels": {"benchmark_label": label},
            "metadata": {"category": "HateXplain"},
        }
        for label in benchmark.label_space
        for index in range(3)
    ]

    selected = select_benchmark_target_cases(cases, benchmark=benchmark, cases_per_label=2, random_state=42)
    manifest = build_benchmark_target_manifest(
        benchmark=benchmark,
        target_cases=selected,
        random_state=42,
        cases_per_label=2,
    )

    assert len(selected) == 6
    assert manifest["evaluation_only"] is True
    assert manifest["target_labels_sent_to_agent"] is False
    assert set(manifest["label_counts"]) == set(benchmark.label_space)
