"""Focused fixtures implementation for coordination reproduction."""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import os
import pickle
import re
import shlex
import shutil
import subprocess
import time
import urllib.request
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence
import networkx as nx
import numpy as np
import pandas as pd
from networkx.algorithms.community import greedy_modularity_communities, louvain_communities
from networkx.algorithms.community.quality import modularity
from app.core.coordination_baseline.characterization import CharacterizationConfig, characterize_detect_output
from app.core.coordination_baseline.deep_graph import (
    DEPRECATED_DISCOVER_ENCODERS,
    DeepGraphDiscoverConfig,
    DeepGraphDiscoverResult,
    STABLE_DISCOVER_ENCODER,
    run_deep_graph_discover,
)


def make_sample_events() -> pd.DataFrame:
    rows = [
        ("u1", "url_share", "https://a.example/story", 1, "p1", "same story alpha", 1),
        ("u2", "url_share", "https://a.example/story", 2, "p2", "same story alpha", 1),
        ("u3", "url_share", "https://b.example/organic", 3, "p3", "organic comment beta", 0),
        ("u1", "hashtag_share", "topic-a", 4, "p4", "topic alpha", 1),
        ("u2", "hashtag_share", "topic-a", 5, "p5", "topic alpha", 1),
        ("u4", "hashtag_share", "topic-b", 6, "p6", "organic beta", 0),
        ("u1", "retweet_target", "tweet:root-1", 7, "p7", "amplify root", 1),
        ("u2", "retweet_target", "tweet:root-1", 8, "p8", "amplify root", 1),
        ("u3", "mention_target", "u4", 9, "p9", "talk to friend", 0),
        ("u4", "mention_target", "u3", 10, "p10", "reply to friend", 0),
    ]
    return pd.DataFrame(
        rows,
        columns=["account_id", "relation", "object_id", "timestamp", "content_id", "content", "label"],
    )


def write_sample_events(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    make_sample_events().to_csv(path, index=False, quoting=csv.QUOTE_MINIMAL)

__all__ = [
    "make_sample_events",
    "write_sample_events",
]
