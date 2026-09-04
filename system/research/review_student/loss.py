"""Task-masked classification and latent rationale distillation losses."""

from __future__ import annotations

from collections.abc import Mapping

import torch
from torch import nn


class ReviewStudentJointLoss(nn.Module):
    def __init__(self, *, lambda_soft: float = 0.5, lambda_latent: float = 1.0, stance_weight: float = 0.2) -> None:
        super().__init__()
        self._binary = nn.BCEWithLogitsLoss(reduction="none")
        self._categorical = nn.CrossEntropyLoss(reduction="none")
        self._cosine = nn.CosineEmbeddingLoss(reduction="none")
        self.lambda_soft = float(lambda_soft)
        self.lambda_latent = float(lambda_latent)
        self.stance_weight = float(stance_weight)

    @staticmethod
    def _masked_mean(losses: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        weights = mask.to(dtype=losses.dtype)
        total = weights.sum()
        if total.item() == 0:
            return losses.sum() * 0.0
        return (losses * weights).sum() / total

    def forward(
        self,
        outputs: Mapping[str, torch.Tensor],
        targets: Mapping[str, torch.Tensor],
    ) -> dict[str, torch.Tensor]:
        attack_gold = self._masked_mean(
            self._binary(outputs["attack_hate_offense"], targets["attack_gold"]),
            targets["attack_mask"],
        )
        misinfo_gold = self._masked_mean(
            self._binary(outputs["misinfo_claim_risk"], targets["misinfo_gold"]),
            targets["misinfo_mask"],
        )
        stance_gold = self._masked_mean(
            self._categorical(outputs["stance"], targets["stance_gold"]),
            targets["stance_mask"],
        )
        gold_loss = attack_gold + misinfo_gold + self.stance_weight * stance_gold

        attack_soft = self._masked_mean(
            self._binary(outputs["attack_hate_offense"], targets["attack_soft"]),
            targets["attack_soft_mask"],
        )
        misinfo_soft = self._masked_mean(
            self._binary(outputs["misinfo_claim_risk"], targets["misinfo_soft"]),
            targets["misinfo_soft_mask"],
        )
        stance_soft = self._masked_mean(
            self._categorical(outputs["stance"], targets["stance_soft"]),
            targets["stance_soft_mask"],
        )
        soft_loss = attack_soft + misinfo_soft + self.stance_weight * stance_soft

        similarity_target = torch.ones(
            outputs["rationale_proj"].shape[0],
            device=outputs["rationale_proj"].device,
        )
        latent_loss = self._masked_mean(
            self._cosine(
                outputs["rationale_proj"],
                targets["rationale_target"],
                similarity_target,
            ),
            targets["rationale_mask"],
        )
        total_loss = gold_loss + self.lambda_soft * soft_loss + self.lambda_latent * latent_loss
        return {
            "total_loss": total_loss,
            "gold_loss": gold_loss,
            "soft_loss": soft_loss,
            "latent_loss": latent_loss,
        }


__all__ = ["ReviewStudentJointLoss"]
