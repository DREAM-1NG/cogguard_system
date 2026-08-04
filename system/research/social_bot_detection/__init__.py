"""Trainable BotRHG transfer implementation for account-level social-bot detection.

This package is intentionally independent from the external NLPCC research
directory. It implements the paper's two-stage structure locally and records
the missing-data adaptations required by each supported public corpus.

Supported corpora are Botection, Cresci-2015, Cresci-2017, and Midterm-2018.
The public-corpus loaders retain source labels and provenance but pass only
normalized account text to the model.
"""

from .contracts import (
    AccountSample,
    DatasetManifest,
    EvaluationReport,
    ModelConfig,
    TrainingConfig,
)
from .active_learning import (
    AccountAcquisitionCandidate,
    AccountAcquisitionItem,
    AccountAcquisitionResult,
    AccountAcquisitionWeights,
    AcquisitionInputError,
    badge_select,
    calibrated_uncertainty,
    compute_alps_embeddings,
    core_set_select,
    select_account_labeling_batch,
    select_heuristic_labeling_batch,
)
from .chinese_corpus import ApprovedAccountLabel, ChineseAccountCorpusManifest, export_approved_account_corpus
from .dataset import load_botection_dataset, load_social_dataset, split_samples
from .datasets import (
    load_approved_account_corpus,
    load_cresci_2015_dataset,
    load_cresci_2017_dataset,
    load_midterm_2018_dataset,
)
from .evaluate_active_round import (
    ActiveRoundEvaluationGate,
    build_frozen_holdout_manifest,
    compare_active_learning_efficiency,
    evaluate_active_round_gates,
)
from .evaluation import evaluate_predictions
from .hypergraph import build_reference_hyperedges, build_support_hyperedges
from .inference import BotRHGInference
from .reliability import compute_correction_risk, select_routed_accounts
from .strict_contracts import StrictAccountRecord, StrictCorpus, StrictFeatureSchema, StrictGraph, StrictRelationEdge
from .strict_datasets import (
    load_strict_cresci_2015_corpus,
    load_strict_cresci_2017_corpus,
    load_strict_midterm_2018_corpus,
    load_strict_social_corpus,
)
from .strict_training import train_strict_botrhg
from .training import train_botrhg

__all__ = [
    "AccountSample",
    "AccountAcquisitionCandidate",
    "AccountAcquisitionItem",
    "AccountAcquisitionResult",
    "AccountAcquisitionWeights",
    "AcquisitionInputError",
    "ActiveRoundEvaluationGate",
    "ApprovedAccountLabel",
    "BotRHGInference",
    "ChineseAccountCorpusManifest",
    "DatasetManifest",
    "EvaluationReport",
    "ModelConfig",
    "StrictAccountRecord",
    "StrictCorpus",
    "StrictFeatureSchema",
    "StrictGraph",
    "StrictRelationEdge",
    "TrainingConfig",
    "evaluate_active_round_gates",
    "build_support_hyperedges",
    "build_reference_hyperedges",
    "compute_correction_risk",
    "build_frozen_holdout_manifest",
    "compare_active_learning_efficiency",
    "badge_select",
    "calibrated_uncertainty",
    "compute_alps_embeddings",
    "core_set_select",
    "evaluate_predictions",
    "export_approved_account_corpus",
    "load_approved_account_corpus",
    "load_botection_dataset",
    "load_cresci_2015_dataset",
    "load_cresci_2017_dataset",
    "load_midterm_2018_dataset",
    "load_strict_cresci_2015_corpus",
    "load_strict_cresci_2017_corpus",
    "load_strict_midterm_2018_corpus",
    "load_strict_social_corpus",
    "load_social_dataset",
    "select_account_labeling_batch",
    "select_heuristic_labeling_batch",
    "select_routed_accounts",
    "split_samples",
    "train_strict_botrhg",
    "train_botrhg",
]
