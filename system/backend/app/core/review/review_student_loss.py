"""Task-Masked Joint Loss and Latent Distillation for Review Student."""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict

class ReviewStudentJointLoss(nn.Module):
    def __init__(self, lambda_soft: float = 0.5, lambda_latent: float = 1.0, stance_weight: float = 0.2):
        super().__init__()
        self.bce = nn.BCEWithLogitsLoss(reduction="none")
        self.ce = nn.CrossEntropyLoss(reduction="none")
        self.cosine_embedding_loss = nn.CosineEmbeddingLoss(reduction="none")
        
        self.lambda_soft = lambda_soft
        self.lambda_latent = lambda_latent
        self.stance_weight = stance_weight
        
    def _masked_weighted_mean(self, losses: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        """Computes the mean of losses where the mask is active."""
        weighted_mask = mask.float()
        total = weighted_mask.sum().clamp_min(1.0)
        return (losses * weighted_mask).sum() / total

    def forward(
        self, 
        outputs: Dict[str, torch.Tensor], 
        targets: Dict[str, torch.Tensor]
    ) -> Dict[str, torch.Tensor]:
        """
        Calculates joint masked loss for gold labels and distillation targets.
        
        Expected targets:
        - attack_gold, misinfo_gold, stance_gold (and their masks)
        - attack_soft, misinfo_soft, stance_soft (and their masks from teacher)
        - rationale_sbert (the teacher's rationale vector), rationale_mask
        """
        # 1. Gold Label Losses (Masked)
        attack_gold_loss = self._masked_weighted_mean(
            self.bce(outputs["attack_hate_offense"], targets["attack_gold"]), 
            targets["attack_mask"]
        )
        misinfo_gold_loss = self._masked_weighted_mean(
            self.bce(outputs["misinfo_claim_risk"], targets["misinfo_gold"]), 
            targets["misinfo_mask"]
        )
        stance_gold_loss = self._masked_weighted_mean(
            self.ce(outputs["stance"], targets["stance_gold"]), 
            targets["stance_mask"]
        )
        
        gold_loss = attack_gold_loss + misinfo_gold_loss + self.stance_weight * stance_gold_loss
        
        # 2. Teacher Silver Soft-Label Distillation (KL/BCE)
        attack_soft_loss = self._masked_weighted_mean(
            self.bce(outputs["attack_hate_offense"], targets["attack_soft"]), 
            targets["attack_soft_mask"]
        )
        misinfo_soft_loss = self._masked_weighted_mean(
            self.bce(outputs["misinfo_claim_risk"], targets["misinfo_soft"]), 
            targets["misinfo_soft_mask"]
        )
        stance_soft_loss = self._masked_weighted_mean(
            self.ce(outputs["stance"], targets["stance_soft"]), 
            targets["stance_soft_mask"]
        )
        
        soft_loss = attack_soft_loss + misinfo_soft_loss + self.stance_weight * stance_soft_loss
        
        # 3. Latent Rationale Distillation
        # Use CosineEmbeddingLoss to align student CLS proj with teacher SBERT embedding.
        # target=1 means they should be similar.
        target_similarity = torch.ones(outputs["rationale_proj"].shape[0], device=outputs["rationale_proj"].device)
        latent_distill = self.cosine_embedding_loss(
            outputs["rationale_proj"], 
            targets["rationale_sbert"], 
            target_similarity
        )
        latent_loss = self._masked_weighted_mean(latent_distill, targets["rationale_mask"])
        
        # Total Joint Loss
        total_loss = gold_loss + self.lambda_soft * soft_loss + self.lambda_latent * latent_loss
        
        return {
            "total_loss": total_loss,
            "gold_loss": gold_loss,
            "soft_loss": soft_loss,
            "latent_loss": latent_loss
        }
