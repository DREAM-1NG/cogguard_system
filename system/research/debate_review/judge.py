from typing import List, Dict, Any
from .interfaces import DecodableEvidence, DebateAgent

class JudgeAgent:
    """
    The main Teacher core. It listens to the debate between the Red and Blue agents
    and renders a final Review Verdict.
    """
    def __init__(self, red_agent: DebateAgent, blue_agent: DebateAgent, max_rounds: int = 3):
        self.red_agent = red_agent
        self.blue_agent = blue_agent
        self.max_rounds = max_rounds
        
    def conduct_debate(self, evidence: DecodableEvidence) -> List[str]:
        """
        Orchestrates the debate rounds between Red and Blue agents.
        """
        transcript = []
        for round_num in range(self.max_rounds):
            # Blue argues for organic/harmless
            blue_arg = self.blue_agent.generate_argument(evidence, transcript)
            transcript.append(f"Blue: {blue_arg}")
            
            # Red argues for coordinated/harmful
            red_arg = self.red_agent.generate_argument(evidence, transcript)
            transcript.append(f"Red: {red_arg}")
            
        return transcript
        
    def render_verdict(self, evidence: DecodableEvidence, transcript: List[str]) -> Dict[str, Any]:
        """
        Judge synthesizes the evidence and the debate transcript into a final verdict.
        """
        # Placeholder for LLM Judge prompt execution
        return {
            "verdict": "harmful",
            "confidence": 0.85,
            "core_narrative": "Identified coordinated attempt to spread X using method Y.",
            "evidence_used": ["behavioral.burstiness", "semantic.template_match"],
            "debate_summary": "Red agent successfully proved coordination; Blue agent's defense of organic spread lacked contextual backing."
        }
