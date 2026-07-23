"""Prepare Review optional model and RAG assets.

Downloads go to durable project asset folders by default:

- HuggingFace models: G:\\CISCN\\hf_models
- Public DISARM RAG files: G:\\CISCN\\dataset\\review_public\\DISARM_RAG

Raw FakeSV videos are not silently downloaded here because the public release
usually requires following the dataset owner's access instructions. The already
prepared C3D features remain the automatic video path.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_HF_MODELS = [
    "FacebookAI/xlm-roberta-base",
    "openai/clip-vit-base-patch32@d15b5f29721ca72dac15f8526b284be910de18be",
]

DISARM_URLS = [
    "https://raw.githubusercontent.com/DISARMFoundation/DISARMframeworks/main/generated_files/DISARM_STIX/DISARM.json",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hf-model-dir", default=r"G:\CISCN\hf_models")
    parser.add_argument(
        "--hf-endpoint",
        default="https://huggingface.co",
        help="HuggingFace endpoint. Override if you need a reachable mirror.",
    )
    parser.add_argument("--models", nargs="*", default=DEFAULT_HF_MODELS)
    parser.add_argument("--skip-hf", action="store_true")
    parser.add_argument("--rag-dir", default=r"G:\CISCN\dataset\review_public\DISARM_RAG")
    parser.add_argument("--skip-disarm", action="store_true")
    args = parser.parse_args()

    summary: dict[str, Any] = {
        "hf_model_dir": args.hf_model_dir,
        "hf_endpoint": args.hf_endpoint,
        "models": {},
        "rag_dir": args.rag_dir,
        "disarm": {},
        "manual_assets": {
            "FakeSV raw videos": {
                "status": "manual_or_dataset-owner-controlled",
                "reason": "current Review pipeline uses public pre-extracted C3D features; raw video files are not bundled in the prepared local data",
                "links": [
                    "https://github.com/ICTMCG/FakeSV",
                    "https://ojs.aaai.org/index.php/AAAI/article/view/26589",
                ],
            }
        },
    }

    os.environ["HF_HOME"] = args.hf_model_dir
    os.environ["TRANSFORMERS_CACHE"] = args.hf_model_dir
    os.environ["HF_ENDPOINT"] = args.hf_endpoint

    if not args.skip_hf:
        summary["models"] = prepare_hf_models(args.models, Path(args.hf_model_dir))
    if not args.skip_disarm:
        summary["disarm"] = prepare_disarm_rag(Path(args.rag_dir))

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def prepare_hf_models(model_names: list[str], model_dir: Path) -> dict[str, Any]:
    model_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for model_name in model_names:
        repo_id, revision = split_model_revision(model_name)
        try:
            if repo_id.startswith("openai/clip"):
                from transformers import CLIPModel, CLIPProcessor

                CLIPProcessor.from_pretrained(repo_id, revision=revision, cache_dir=str(model_dir))
                CLIPModel.from_pretrained(repo_id, revision=revision, cache_dir=str(model_dir), use_safetensors=True)
                results[model_name] = {"status": "downloaded_or_cached", "type": "clip", "cache_dir": str(model_dir)}
            else:
                from huggingface_hub import snapshot_download
                from transformers import AutoModel, AutoTokenizer

                AutoTokenizer.from_pretrained(repo_id, revision=revision, cache_dir=str(model_dir), use_fast=True)
                try:
                    AutoModel.from_pretrained(repo_id, revision=revision, cache_dir=str(model_dir), use_safetensors=True)
                    results[model_name] = {
                        "status": "downloaded_or_cached",
                        "type": "hf-transformer",
                        "cache_dir": str(model_dir),
                    }
                except ValueError as exc:
                    snapshot_path = snapshot_download(repo_id, revision=revision, cache_dir=str(model_dir))
                    weight_files = sorted(str(path.name) for path in Path(snapshot_path).glob("*.bin"))
                    results[model_name] = {
                        "status": "downloaded_but_load_blocked",
                        "type": "hf-transformer",
                        "cache_dir": str(model_dir),
                        "snapshot_path": str(snapshot_path),
                        "weight_files": weight_files,
                        "load_error": f"{type(exc).__name__}: {exc}",
                        "fix": "upgrade torch to >=2.6 or use a safetensors-compatible model variant",
                    }
        except Exception as exc:  # pragma: no cover - network/environment dependent
            cached = inspect_hf_model_cache(repo_id, model_dir)
            if cached["has_config"] and cached["has_weight"]:
                results[model_name] = {
                    "status": "downloaded_but_load_blocked",
                    "type": "clip" if repo_id.startswith("openai/clip") else "hf-transformer",
                    "cache_dir": str(model_dir),
                    "cache": cached,
                    "load_error": f"{type(exc).__name__}: {exc}",
                    "fix": "upgrade torch to >=2.6 for .bin weights, or use a safetensors-compatible snapshot/model",
                }
            else:
                results[model_name] = {
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "cache": cached,
                    "manual_link": f"https://huggingface.co/{repo_id}",
                }
    return results


def split_model_revision(model_name: str) -> tuple[str, str | None]:
    if "@" not in model_name:
        return model_name, None
    repo_id, revision = model_name.rsplit("@", 1)
    return repo_id, revision or None


def inspect_hf_model_cache(model_name: str, model_dir: Path) -> dict[str, Any]:
    model_cache = model_dir / f"models--{model_name.replace('/', '--')}"
    snapshots = []
    has_config = False
    has_weight = False
    incomplete_count = 0
    if model_cache.exists():
        incomplete_count = len(list(model_cache.rglob("*.incomplete")))
        for snapshot in sorted((model_cache / "snapshots").glob("*")):
            if not snapshot.is_dir():
                continue
            files = [path for path in snapshot.rglob("*") if path.is_file()]
            weight_files = [
                str(path.relative_to(snapshot))
                for path in files
                if path.name in {"pytorch_model.bin", "model.safetensors"} or path.name.endswith(".safetensors")
            ]
            config_files = [str(path.relative_to(snapshot)) for path in files if path.name == "config.json"]
            has_config = has_config or bool(config_files)
            has_weight = has_weight or bool(weight_files)
            snapshots.append(
                {
                    "snapshot": snapshot.name,
                    "size_mb": round(sum(path.stat().st_size for path in files) / 1024 / 1024, 1),
                    "weights": weight_files,
                    "configs": config_files,
                }
            )
    return {
        "model_cache": str(model_cache),
        "exists": model_cache.exists(),
        "has_config": has_config,
        "has_weight": has_weight,
        "incomplete_count": incomplete_count,
        "snapshots": snapshots,
    }


def prepare_disarm_rag(rag_dir: Path) -> dict[str, Any]:
    rag_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = rag_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    docs = []
    fetched = {}
    for url in DISARM_URLS:
        target = raw_dir / Path(url).name
        try:
            body = fetch_url(url)
            target.write_bytes(body)
            rows = json.loads(body.decode("utf-8"))
            source_docs = normalize_disarm_rows(rows, source=Path(url).stem)
            docs.extend(source_docs)
            fetched[url] = {"status": "downloaded", "path": str(target), "documents": len(source_docs)}
        except Exception as exc:  # pragma: no cover - network/schema dependent
            fetched[url] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}", "path": str(target)}

    corpus_path = rag_dir / "disarm_corpus.jsonl"
    with corpus_path.open("w", encoding="utf-8") as handle:
        for row in docs:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return {
        "status": "ready" if docs else "empty_or_failed",
        "corpus_path": str(corpus_path),
        "document_count": len(docs),
        "sources": fetched,
    }


def fetch_url(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "CogGuard-Review-asset-prep/1.0"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def normalize_disarm_rows(rows: Any, *, source: str) -> list[dict[str, str]]:
    if isinstance(rows, dict):
        candidates = rows.get("objects") or rows.get("data") or rows.get("items") or list(rows.values())
    else:
        candidates = rows
    docs = []
    for index, item in enumerate(candidates if isinstance(candidates, list) else []):
        if not isinstance(item, dict):
            continue
        doc_id = str(item.get("id") or item.get("attack_id") or item.get("external_id") or f"{source}-{index}")
        title = str(item.get("name") or item.get("title") or item.get("label") or doc_id)
        phases = [
            phase.get("phase_name")
            for phase in item.get("kill_chain_phases") or []
            if isinstance(phase, dict)
        ]
        external_ids = [
            ref.get("external_id")
            for ref in item.get("external_references") or []
            if isinstance(ref, dict) and ref.get("external_id")
        ]
        text = " ".join(
            clean_text(value)
            for value in [
                title,
                item.get("type"),
                item.get("description"),
                item.get("summary"),
                item.get("phase"),
                item.get("tactic"),
                item.get("detects"),
                item.get("response"),
                phases,
                external_ids,
            ]
            if value
        )
        if text.strip():
            docs.append({"doc_id": doc_id, "source": f"DISARM::{source}", "title": title, "text": text.strip()})
    return docs


def clean_text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(clean_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(clean_text(item) for item in value.values())
    return re.sub(r"\s+", " ", str(value)).strip()


if __name__ == "__main__":
    raise SystemExit(main())
