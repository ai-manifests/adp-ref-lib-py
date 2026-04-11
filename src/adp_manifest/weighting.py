from __future__ import annotations
import math
from datetime import timedelta
from .types import CalibrationScore, StakeMagnitude

DEFAULT_HALF_LIVES: dict[str, timedelta] = {
    "code.correctness": timedelta(days=180),
    "security.policy": timedelta(days=90),
    "api.compatibility": timedelta(days=30),
    "code.style": timedelta(days=365),
}

FALLBACK_HALF_LIFE = timedelta(days=90)

STAKE_FACTORS: dict[StakeMagnitude, float] = {
    StakeMagnitude.HIGH: 1.00,
    StakeMagnitude.MEDIUM: 0.85,
    StakeMagnitude.LOW: 0.50,
}


def compute_weight(
    authority: float,
    calibration: CalibrationScore,
    decision_class: str,
    magnitude: StakeMagnitude,
    half_life_overrides: dict[str, timedelta] | None = None,
) -> float:
    effective_cal = apply_sample_size_discount(calibration.value, calibration.sample_size)
    decay = compute_decay(calibration.staleness, decision_class, half_life_overrides)
    sf = stake_factor(magnitude)
    return authority * effective_cal * decay * sf


def compute_decay(
    staleness: timedelta,
    decision_class: str,
    half_life_overrides: dict[str, timedelta] | None = None,
) -> float:
    hl = _get_half_life(decision_class, half_life_overrides)
    if hl.total_seconds() <= 0:
        return 1.0
    return math.pow(2.0, -staleness.days / (hl.total_seconds() / 86400))


def apply_sample_size_discount(value: float, sample_size: int) -> float:
    return value * (1.0 - 1.0 / (1.0 + sample_size))


def stake_factor(magnitude: StakeMagnitude) -> float:
    return STAKE_FACTORS.get(magnitude, 0.50)


def _get_half_life(
    decision_class: str,
    overrides: dict[str, timedelta] | None,
) -> timedelta:
    if overrides and decision_class in overrides:
        return overrides[decision_class]
    return DEFAULT_HALF_LIVES.get(decision_class, FALLBACK_HALF_LIFE)
