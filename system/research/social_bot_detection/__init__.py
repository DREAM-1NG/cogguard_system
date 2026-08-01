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
from .dataset import load_botection_dataset, load_social_dataset, split_samples
from .datasets import load_cresci_2015_dataset, load_cresci_2017_dataset, load_midterm_2018_dataset
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
    "BotRHGInference",
    "DatasetManifest",
    "EvaluationReport",
    "ModelConfig",
    "StrictAccountRecord",
    "StrictCorpus",
    "StrictFeatureSchema",
    "StrictGraph",
    "StrictRelationEdge",
    "TrainingConfig",
    "build_support_hyperedges",
    "build_reference_hyperedges",
    "compute_correction_risk",
    "evaluate_predictions",
    "load_botection_dataset",
    "load_cresci_2015_dataset",
    "load_cresci_2017_dataset",
    "load_midterm_2018_dataset",
    "load_strict_cresci_2015_corpus",
    "load_strict_cresci_2017_corpus",
    "load_strict_midterm_2018_corpus",
    "load_strict_social_corpus",
    "load_social_dataset",
    "select_routed_accounts",
    "split_samples",
    "train_strict_botrhg",
    "train_botrhg",
]
