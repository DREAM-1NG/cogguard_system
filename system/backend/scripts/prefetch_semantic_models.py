"""Prefetch pinned semantic enrichment models into the CogGuard HF cache.

This script is intentionally fail-closed: any missing model, network error, or
revision mismatch raises and returns a non-zero exit code. The application does
not fabricate semantic artifacts when these weights are unavailable.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

from huggingface_hub import HfApi, snapshot_download

HF_CACHE_DIR = Path(r"G:\CISCN\hf_models")
LOCAL_SNAPSHOT_ROOT = HF_CACHE_DIR / "local_snapshots"

MODELS = (
    ("BAAI/bge-small-zh-v1.5", "7999e1d"),
    ("lxyuan/distilbert-base-multilingual-cased-sentiments-student", "cf99110"),
    ("MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli", "0a71e92"),
    ("shibing624/bert4ner-base-chinese", "5d660ed"),
)

REQUIRED_FILE_NAMES = {
    ".gitattributes",
    "added_tokens.json",
    "config.json",
    "config_sentence_transformers.json",
    "merges.txt",
    "modules.json",
    "sentence_bert_config.json",
    "sentencepiece.bpe.model",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer.model",
    "tokenizer_config.json",
    "vocab.json",
    "vocab.txt",
}
REQUIRED_DIR_PREFIXES = ("1_Pooling/",)
WEIGHT_FILE_PRIORITY = ("model.safetensors", "pytorch_model.bin")


def configure_cache() -> None:
    HF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(HF_CACHE_DIR)
    os.environ["TRANSFORMERS_CACHE"] = str(HF_CACHE_DIR)
    os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(HF_CACHE_DIR)


def local_snapshot_dir(repo_id: str, revision: str) -> Path:
    safe_repo = repo_id.replace("/", "__")
    return LOCAL_SNAPSHOT_ROOT / f"{safe_repo}--{revision}"


def select_required_snapshot_files(files: list[str]) -> list[str]:
    """Keep only files needed by SentenceTransformers/Transformers inference.

    Some model repos ship several export formats (PyTorch, safetensors, ONNX,
    TensorFlow). Pulling all of them is slow and unnecessary for the prototype
    runtime. Prefer safetensors when present; otherwise keep PyTorch weights.
    """

    normalized = sorted({filename.replace("\\", "/") for filename in files})
    selected: set[str] = set()
    for filename in normalized:
        basename = filename.rsplit("/", 1)[-1]
        if filename.startswith(REQUIRED_DIR_PREFIXES) or basename in REQUIRED_FILE_NAMES:
            selected.add(filename)
    for weight_name in WEIGHT_FILE_PRIORITY:
        if weight_name in normalized:
            selected.add(weight_name)
            break
    return sorted(selected)


def direct_download_snapshot(repo_id: str, revision: str, *, endpoint: str) -> Path:
    """Download a repo snapshot by direct resolve URLs.

    `huggingface_hub.snapshot_download` can fail in locked-down environments
    when HEAD metadata omits Content-Length/ETag. Direct GET keeps the same
    pinned revision and writes a standard local directory that Transformers can
    load without consulting the Hub metadata cache.
    """

    target_dir = local_snapshot_dir(repo_id, revision)
    target_dir.mkdir(parents=True, exist_ok=True)
    files = select_required_snapshot_files(HfApi(endpoint=endpoint).list_repo_files(repo_id, revision=revision))
    if not files:
        raise RuntimeError(f"No required inference files found for {repo_id}@{revision}")
    base_url = endpoint.rstrip("/")
    for filename in files:
        encoded = "/".join(quote(part) for part in filename.split("/"))
        url = f"{base_url}/{repo_id}/resolve/{revision}/{encoded}"
        target = target_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(url, timeout=60) as response:
            expected_size = int(response.headers.get("content-length") or 0)
            if target.exists() and expected_size and target.stat().st_size == expected_size:
                print(f"SKIP {repo_id}@{revision}:{filename}")
                continue
            temp_target = target.with_suffix(target.suffix + ".part")
            with temp_target.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
            if expected_size and temp_target.stat().st_size != expected_size:
                raise RuntimeError(
                    f"Incomplete download for {repo_id}@{revision}:{filename}; "
                    f"expected {expected_size}, got {temp_target.stat().st_size}"
                )
            temp_target.replace(target)
            print(f"OK direct {repo_id}@{revision}:{filename} -> {target}")
    return target_dir


def main() -> int:
    configure_cache()
    endpoint = os.environ.get("HF_ENDPOINT") or "https://huggingface.co"
    print(f"Prefetching semantic models into {HF_CACHE_DIR}")
    print(f"Using HuggingFace endpoint: {endpoint}")
    for repo_id, revision in MODELS:
        try:
            local_path = snapshot_download(
                repo_id=repo_id,
                revision=revision,
                cache_dir=str(HF_CACHE_DIR),
                local_files_only=False,
                endpoint=endpoint,
            )
        except Exception as exc:
            print(f"snapshot_download failed for {repo_id}@{revision}: {exc}")
            local_path = str(direct_download_snapshot(repo_id, revision, endpoint=endpoint))
        print(f"OK {repo_id}@{revision} -> {local_path}")
    print("All pinned semantic models are present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
