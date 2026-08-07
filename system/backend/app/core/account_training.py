"""Domain policy for governed Chinese account-model training runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum

__all__ = [
    "AccountTrainingFamily",
    "AccountTrainingState",
    "TrainingTriggerContext",
    "TrainingTriggerDecision",
    "AccountTrainingPolicy",
    "default_account_training_policy",
    "DEFAULT_HEARTBEAT_TIMEOUT_SECONDS",
    "evaluate_training_trigger",
    "is_training_heartbeat_stale",
    "recovery_attempt_allowed",
    "require_training_transition",
]


class AccountTrainingFamily(StrEnum):
    """Independently versioned model families in the account-detection loop."""

    CHINESE_SOCIAL_ENCODER = "chinese_social_encoder"
    CHINESE_ACCOUNT_DETECTOR = "chinese_account_detector"


class AccountTrainingState(StrEnum):
    """Durable lifecycle states for an account-model training run."""

    QUEUED = "queued"
    PREPARING = "preparing"
    RUNNING = "running"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


DEFAULT_HEARTBEAT_TIMEOUT_SECONDS = 5 * 60
_TERMINAL_STATES = frozenset(
    {AccountTrainingState.COMPLETED, AccountTrainingState.FAILED, AccountTrainingState.CANCELLED}
)
_TRANSITIONS = {
    AccountTrainingState.QUEUED: {
        AccountTrainingState.PREPARING,
        AccountTrainingState.CANCELLED,
        AccountTrainingState.FAILED,
    },
    AccountTrainingState.PREPARING: {
        AccountTrainingState.RUNNING,
        AccountTrainingState.CANCELLED,
        AccountTrainingState.FAILED,
        AccountTrainingState.INTERRUPTED,
    },
    AccountTrainingState.RUNNING: {
        AccountTrainingState.EVALUATING,
        AccountTrainingState.CANCELLED,
        AccountTrainingState.FAILED,
        AccountTrainingState.INTERRUPTED,
    },
    AccountTrainingState.EVALUATING: {
        AccountTrainingState.COMPLETED,
        AccountTrainingState.CANCELLED,
        AccountTrainingState.FAILED,
        AccountTrainingState.INTERRUPTED,
    },
    AccountTrainingState.INTERRUPTED: {
        AccountTrainingState.QUEUED,
        AccountTrainingState.CANCELLED,
        AccountTrainingState.FAILED,
    },
}


@dataclass(frozen=True, slots=True)
class TrainingTriggerContext:
    family: AccountTrainingFamily
    eligible_item_count: int
    last_dispatched_at: datetime | None
    now: datetime
    manual: bool = False
    input_ready: bool = True


@dataclass(frozen=True, slots=True)
class TrainingTriggerDecision:
    allowed: bool
    reason: str
    threshold: int
    eligible_item_count: int
    quantity_bypassed: bool
    cooldown_seconds_remaining: int


@dataclass(frozen=True, slots=True)
class AccountTrainingPolicy:
    """Deployment policy for governed account-model training."""

    dapt_token_threshold: int = 500_000
    supervised_label_threshold: int = 200
    cooldown_days: int = 7
    heartbeat_timeout_seconds: int = DEFAULT_HEARTBEAT_TIMEOUT_SECONDS
    max_resumes: int = 3

    def threshold_for(self, family: AccountTrainingFamily) -> int:
        return (
            self.dapt_token_threshold
            if family == AccountTrainingFamily.CHINESE_SOCIAL_ENCODER
            else self.supervised_label_threshold
        )


def default_account_training_policy() -> AccountTrainingPolicy:
    """Return the documented defaults for pure-domain callers and tests."""

    return AccountTrainingPolicy()


def evaluate_training_trigger(
    context: TrainingTriggerContext,
    *,
    policy: AccountTrainingPolicy | None = None,
) -> TrainingTriggerDecision:
    """Evaluate quantity, input and cooldown gates without side effects."""

    family = AccountTrainingFamily(context.family)
    active_policy = policy or default_account_training_policy()
    threshold = active_policy.threshold_for(family)
    eligible_count = max(0, int(context.eligible_item_count))
    quantity_bypassed = bool(context.manual and eligible_count < threshold)

    if not context.input_ready:
        return _trigger_decision(
            allowed=False,
            reason="training_input_not_ready",
            threshold=threshold,
            eligible_count=eligible_count,
            quantity_bypassed=quantity_bypassed,
        )

    cooldown_remaining = _cooldown_remaining(
        context.last_dispatched_at,
        context.now,
        cooldown_days=active_policy.cooldown_days,
    )
    if cooldown_remaining > 0:
        return _trigger_decision(
            allowed=False,
            reason="cooldown_active",
            threshold=threshold,
            eligible_count=eligible_count,
            quantity_bypassed=quantity_bypassed,
            cooldown_remaining=cooldown_remaining,
        )

    if eligible_count < threshold and not context.manual:
        return _trigger_decision(
            allowed=False,
            reason="eligible_item_threshold_not_met",
            threshold=threshold,
            eligible_count=eligible_count,
            quantity_bypassed=False,
        )

    return _trigger_decision(
        allowed=True,
        reason="manual_quantity_override" if quantity_bypassed else "trigger_gates_passed",
        threshold=threshold,
        eligible_count=eligible_count,
        quantity_bypassed=quantity_bypassed,
    )


def require_training_transition(
    current: AccountTrainingState | str,
    target: AccountTrainingState | str,
) -> None:
    """Reject lifecycle transitions that skip durable training stages."""

    current_state = AccountTrainingState(current)
    target_state = AccountTrainingState(target)
    if current_state in _TERMINAL_STATES or target_state not in _TRANSITIONS.get(current_state, set()):
        raise ValueError(
            f"Invalid account training transition: {current_state.value} -> {target_state.value}"
        )


def is_training_heartbeat_stale(
    *,
    state: AccountTrainingState | str,
    heartbeat_at: datetime | None,
    now: datetime,
    timeout_seconds: int = DEFAULT_HEARTBEAT_TIMEOUT_SECONDS,
) -> bool:
    """Return whether an active run has exceeded its durable heartbeat lease."""

    current = AccountTrainingState(state)
    if current not in {
        AccountTrainingState.PREPARING,
        AccountTrainingState.RUNNING,
        AccountTrainingState.EVALUATING,
    }:
        return False
    if timeout_seconds <= 0:
        raise ValueError("heartbeat timeout_seconds must be positive")
    if heartbeat_at is None:
        return True
    return _as_utc(now) - _as_utc(heartbeat_at) > timedelta(seconds=timeout_seconds)


def recovery_attempt_allowed(*, attempt: int, max_attempts: int) -> bool:
    """Keep resumption bounded even when a worker repeatedly disappears."""

    try:
        normalized_attempt = int(attempt)
        normalized_max_attempts = int(max_attempts)
    except (TypeError, ValueError):
        return False
    return normalized_attempt >= 1 and normalized_attempt < max(1, normalized_max_attempts)


def _cooldown_remaining(
    last_dispatched_at: datetime | None,
    now: datetime,
    *,
    cooldown_days: int,
) -> int:
    if last_dispatched_at is None:
        return 0
    normalized_now = _as_utc(now)
    elapsed = normalized_now - _as_utc(last_dispatched_at)
    return max(0, int((timedelta(days=cooldown_days) - elapsed).total_seconds()))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _trigger_decision(
    *,
    allowed: bool,
    reason: str,
    threshold: int,
    eligible_count: int,
    quantity_bypassed: bool,
    cooldown_remaining: int = 0,
) -> TrainingTriggerDecision:
    return TrainingTriggerDecision(
        allowed=allowed,
        reason=reason,
        threshold=threshold,
        eligible_item_count=eligible_count,
        quantity_bypassed=quantity_bypassed,
        cooldown_seconds_remaining=cooldown_remaining,
    )
