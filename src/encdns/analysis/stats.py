"""Statistical primitives shared by every supported analysis."""
from __future__ import annotations
import math

def wilson_interval(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    if trials <= 0:
        return (float("nan"), float("nan"))
    proportion = successes / trials
    denominator = 1 + z * z / trials
    centre = proportion + z * z / (2 * trials)
    half_width = z * math.sqrt(proportion * (1 - proportion) / trials + z * z / (4 * trials * trials))
    return ((centre - half_width) / denominator, (centre + half_width) / denominator)

def empirical_p_value(observed: float, null_scores: list[float]) -> float:
    if not null_scores:
        return float("nan")
    return (1 + sum(score >= observed for score in null_scores)) / (1 + len(null_scores))
