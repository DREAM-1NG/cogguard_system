from abc import ABC, abstractmethod
from typing import Dict, Any, List

class DecodableEvidence:
    """
    Standardized evidence extracted by the Investigator Agents.
    Maps to the four Evidence Dimensions.
    """
    def __init__(self, semantic: Dict, multimodal: Dict, behavioral: Dict, contextual: Dict):
        self.semantic = semantic          # e.g., narrative templates, sentiment
        self.multimodal = multimodal      # e.g., OCR, visual-text conflicts
        self.behavioral = behavioral      # e.g., burstiness, topology
        self.contextual = contextual      # e.g., fact-checking KB matches

class InvestigatorAgent(ABC):
    @abstractmethod
    def extract_evidence(self, event_snapshot: Dict[str, Any]) -> DecodableEvidence:
        pass

class DebateAgent(ABC):
    """
    Base class for Red (Attack/Harm) and Blue (Defense/Organic) Analyst Agents.
    """
    def __init__(self, stance: str):
        self.stance = stance  # "organic/harmless" or "coordinated/harmful"
        
    @abstractmethod
    def generate_argument(self, evidence: DecodableEvidence, previous_arguments: List[str]) -> str:
        """
        Generates an argument supporting its stance based on the evidence and rebutting previous arguments.
        """
        pass
