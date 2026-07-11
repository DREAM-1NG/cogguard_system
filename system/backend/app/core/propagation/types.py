from __future__ import annotations

from typing import Any

import networkx as nx
import pandas as pd

SharedObjects = dict[str, list[dict[str, Any]]]
BetweennessScores = dict[str, float]
PropagationGraph = nx.MultiDiGraph
PropagationFrame = pd.DataFrame
