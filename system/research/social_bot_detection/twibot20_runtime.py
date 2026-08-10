"""Hash-verified runtime for the fixed-graph NLPCC TwiBot-20 checkpoint."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Iterable, Mapping

import torch

__all__ = [
    "TWIBOT20_DEPLOYMENT_SCOPE",
    "TwiBot20ResearchRuntime",
    "build_twibot20_research_bundle",
]

_BUNDLE_SCHEMA = "cogguard.nlpcc.twibot20.transductive.v1"
TWIBOT20_DEPLOYMENT_SCOPE = "twibot20_transductive_research"
_MANIFEST_NAME = "manifest.json"
_MANIFEST_HASH_NAME = "manifest.sha256"
_CHECKPOINT_NAME = "checkpoint.pt"
_PREDICTIONS_NAME = "predictions.pt"
_NODE_IDS_NAME = "node_ids.json"
_SOURCE_MANIFEST_NAME = "source_manifest.json"
_SELECTION_METRICS_NAME = "selection_metrics.json"
_REQUIRED_FILES = (
    _CHECKPOINT_NAME,
    _PREDICTIONS_NAME,
    _NODE_IDS_NAME,
    _SOURCE_MANIFEST_NAME,
    _SELECTION_METRICS_NAME,
)


def build_twibot20_research_bundle(
    output_dir: str | Path,
    *,
    checkpoint_path: str | Path,
    outputs_path: str | Path,
    node_ids_path: str | Path,
    source_manifest_path: str | Path,
    selection_metrics_path: str | Path,
) -> dict[str, Any]:
    """Build a self-contained research bundle from one selected fixed-graph run."""

    bundle_dir = Path(output_dir).resolve()
    bundle_dir.mkdir(parents=True, exist_ok=True)
    if any(bundle_dir.iterdir()):
        raise ValueError("TwiBot-20 bundle output directory must be empty")

    checkpoint_source = _require_file(checkpoint_path, "checkpoint")
    outputs_source = _require_file(outputs_path, "outputs")
    node_ids_source = _require_file(node_ids_path, "node ids")
    source_manifest_source = _require_file(source_manifest_path, "source manifest")
    selection_metrics_source = _require_file(selection_metrics_path, "selection metrics")

    checkpoint = _load_mapping(checkpoint_source, "checkpoint")
    _validate_checkpoint(checkpoint)
    outputs = _load_mapping(outputs_source, "outputs")
    predictions = _validated_predictions(outputs)
    node_ids = _read_node_ids(node_ids_source)
    if len(node_ids) != int(predictions["pred"].shape[0]):
        raise ValueError("TwiBot-20 node id count does not match prediction count")
    if "labels" in predictions:
        _validate_node_labels(node_ids_source, predictions["labels"])

    source_manifest = _read_json_object(source_manifest_source, "source manifest")
    selection_metrics = _read_json_object(selection_metrics_source, "selection metrics")
    expected_nodes = int((source_manifest.get("node_id_manifest") or {}).get("num_nodes") or len(node_ids))
    if expected_nodes != len(node_ids):
        raise ValueError("TwiBot-20 source manifest node count does not match node ids")
    checkpoint_selection = source_manifest.get("checkpoint_selection") or {}
    if checkpoint_selection.get("primary") != "validation_accuracy":
        raise ValueError("TwiBot-20 checkpoint was not selected by validation accuracy")

    shutil.copy2(checkpoint_source, bundle_dir / _CHECKPOINT_NAME)
    torch.save(predictions, bundle_dir / _PREDICTIONS_NAME)
    _write_json(bundle_dir / _NODE_IDS_NAME, node_ids)
    _write_json(bundle_dir / _SOURCE_MANIFEST_NAME, source_manifest)
    _write_json(bundle_dir / _SELECTION_METRICS_NAME, selection_metrics)

    files = {
        name: {
            "sha256": _sha256(bundle_dir / name),
            "size_bytes": (bundle_dir / name).stat().st_size,
        }
        for name in _REQUIRED_FILES
    }
    manifest = {
        "schema": _BUNDLE_SCHEMA,
        "dataset": "TwiBot-20",
        "deployment_scope": TWIBOT20_DEPLOYMENT_SCOPE,
        "online_account_activation_allowed": False,
        "inference_contract": "fixed_graph_node_lookup",
        "node_count": len(node_ids),
        "model": {
            "backbone": source_manifest.get("backbone"),
            "checkpoint_schema": "nlpcc_rgcn_hyperscan_fixed_graph",
        },
        "selection": {
            "policy": "highest_validation_accuracy_across_completed_seeds",
            "seed": source_manifest.get("seed"),
            "metrics": selection_metrics,
        },
        "files": files,
    }
    _write_json(bundle_dir / _MANIFEST_NAME, manifest)
    (bundle_dir / _MANIFEST_HASH_NAME).write_text(
        f"{_sha256(bundle_dir / _MANIFEST_NAME)}  {_MANIFEST_NAME}\n",
        encoding="ascii",
    )
    return manifest


class TwiBot20ResearchRuntime:
    """Serve predictions for nodes already present in the deployed TwiBot-20 graph."""

    def __init__(self, bundle_dir: str | Path) -> None:
        self.bundle_dir = Path(bundle_dir).resolve()
        self.manifest = _load_and_verify_manifest(self.bundle_dir)
        checkpoint = _load_mapping(self.bundle_dir / _CHECKPOINT_NAME, "checkpoint")
        _validate_checkpoint(checkpoint)
        predictions = _load_mapping(self.bundle_dir / _PREDICTIONS_NAME, "predictions")
        self._predictions = _validated_predictions(predictions)
        self._node_ids = _read_node_ids(self.bundle_dir / _NODE_IDS_NAME)
        if len(self._node_ids) != int(self._predictions["pred"].shape[0]):
            raise ValueError("TwiBot-20 bundle node and prediction counts differ")
        self._node_index = {node_id: index for index, node_id in enumerate(self._node_ids)}

    def model_info(self) -> dict[str, Any]:
        return {
            "schema": self.manifest["schema"],
            "dataset": self.manifest["dataset"],
            "deployment_scope": self.manifest["deployment_scope"],
            "online_account_activation_allowed": False,
            "node_count": self.manifest["node_count"],
            "model": self.manifest["model"],
            "selection": self.manifest["selection"],
        }

    def predict_nodes(self, node_ids: Iterable[str]) -> dict[str, Any]:
        accounts: list[dict[str, Any]] = []
        probabilities = self._predictions["prob"]
        predictions = self._predictions["pred"]
        labels = self._predictions.get("labels")
        for raw_node_id in node_ids:
            node_id = str(raw_node_id).strip()
            if node_id not in self._node_index:
                raise KeyError(f"{node_id!r} is not part of the deployed TwiBot-20 graph")
            index = self._node_index[node_id]
            prediction = int(predictions[index].item())
            row = {
                "node_id": node_id,
                "node_index": index,
                "prediction": "bot" if prediction == 1 else "human",
                "bot_probability": float(probabilities[index, 1].item()),
            }
            if labels is not None:
                label = _label_index(labels[index])
                row["label"] = "bot" if label == 1 else "human"
            accounts.append(row)
        return {
            "method": "NLPCC RGCN-HyperScan",
            "dataset": "TwiBot-20",
            "deployment_scope": TWIBOT20_DEPLOYMENT_SCOPE,
            "accounts": accounts,
            "model_info": self.model_info(),
        }


def _load_and_verify_manifest(bundle_dir: Path) -> dict[str, Any]:
    manifest = _read_json_object(bundle_dir / _MANIFEST_NAME, "bundle manifest")
    if manifest.get("schema") != _BUNDLE_SCHEMA:
        raise ValueError("unsupported TwiBot-20 research bundle schema")
    if manifest.get("deployment_scope") != TWIBOT20_DEPLOYMENT_SCOPE:
        raise ValueError("invalid TwiBot-20 deployment scope")
    if manifest.get("online_account_activation_allowed") is not False:
        raise ValueError("TwiBot-20 research bundle cannot allow online account activation")
    expected_manifest_hash = _read_hash_file(bundle_dir / _MANIFEST_HASH_NAME)
    if _sha256(bundle_dir / _MANIFEST_NAME) != expected_manifest_hash:
        raise ValueError("TwiBot-20 bundle manifest hash verification failed")
    files = manifest.get("files")
    if not isinstance(files, Mapping) or set(files) != set(_REQUIRED_FILES):
        raise ValueError("TwiBot-20 bundle file manifest is incomplete")
    for name in _REQUIRED_FILES:
        path = bundle_dir / name
        metadata = files[name]
        if not path.is_file() or not isinstance(metadata, Mapping):
            raise ValueError(f"TwiBot-20 bundle file is missing: {name}")
        if _sha256(path) != str(metadata.get("sha256") or ""):
            raise ValueError(f"TwiBot-20 bundle hash verification failed: {name}")
        if path.stat().st_size != int(metadata.get("size_bytes") or -1):
            raise ValueError(f"TwiBot-20 bundle size verification failed: {name}")
    return manifest


def _validated_predictions(outputs: Mapping[str, Any]) -> dict[str, torch.Tensor]:
    probability = outputs.get("prob")
    prediction = outputs.get("pred")
    labels = outputs.get("labels")
    if not isinstance(probability, torch.Tensor) or probability.ndim != 2 or probability.shape[1] != 2:
        raise ValueError("TwiBot-20 outputs require a [node, 2] probability tensor")
    if not isinstance(prediction, torch.Tensor) or prediction.ndim != 1 or prediction.shape[0] != probability.shape[0]:
        raise ValueError("TwiBot-20 outputs require one prediction per node")
    if not torch.isfinite(probability).all() or (probability < 0).any() or (probability > 1).any():
        raise ValueError("TwiBot-20 output probabilities are invalid")
    compact = {"prob": probability.detach().cpu(), "pred": prediction.detach().cpu().long()}
    if isinstance(labels, torch.Tensor):
        if labels.shape[0] != probability.shape[0]:
            raise ValueError("TwiBot-20 output labels do not match node count")
        compact["labels"] = labels.detach().cpu()
    return compact


def _validate_checkpoint(checkpoint: Mapping[str, Any]) -> None:
    model = checkpoint.get("model")
    model_config = checkpoint.get("model_config")
    if not isinstance(model, Mapping) or not model:
        raise ValueError("TwiBot-20 checkpoint has no model state")
    if not isinstance(model_config, Mapping):
        raise ValueError("TwiBot-20 checkpoint has no model configuration")
    if model_config.get("GNN_model") != "rgcn_hyperscan_dhg_nodeinput":
        raise ValueError("TwiBot-20 checkpoint backbone is incompatible")


def _validate_node_labels(node_ids_path: Path, labels: torch.Tensor) -> None:
    if node_ids_path.name != "label_new.json":
        return
    payload = _read_json_object(node_ids_path, "node labels")
    expected = [value for key, value in payload.items() if key != "id"]
    actual = [_label_index(row) for row in labels]
    encoded = [1 if str(value).strip().lower() == "bot" else 0 for value in expected]
    if encoded != actual:
        raise ValueError("TwiBot-20 node order does not match output labels")


def _read_node_ids(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        values = payload
    elif isinstance(payload, dict):
        values = [key for key in payload if key != "id"]
    else:
        raise ValueError("TwiBot-20 node ids must be a list or object")
    node_ids = [str(value).strip() for value in values]
    if any(not value for value in node_ids) or len(node_ids) != len(set(node_ids)):
        raise ValueError("TwiBot-20 node ids must be non-empty and unique")
    return node_ids


def _label_index(value: torch.Tensor) -> int:
    if value.ndim == 0:
        return int(value.item())
    return int(torch.argmax(value).item())


def _load_mapping(path: Path, label: str) -> Mapping[str, Any]:
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(payload, Mapping):
        raise ValueError(f"TwiBot-20 {label} must be a mapping")
    return payload


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"TwiBot-20 {label} is unreadable") from error
    if not isinstance(payload, dict):
        raise ValueError(f"TwiBot-20 {label} must be an object")
    return payload


def _read_hash_file(path: Path) -> str:
    try:
        value = path.read_text(encoding="ascii").strip().split()[0]
    except (OSError, IndexError) as error:
        raise ValueError("TwiBot-20 bundle manifest hash is missing") from error
    if len(value) != 64:
        raise ValueError("TwiBot-20 bundle manifest hash is invalid")
    return value


def _require_file(value: str | Path, label: str) -> Path:
    path = Path(value).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"TwiBot-20 {label} not found: {path}")
    return path


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
