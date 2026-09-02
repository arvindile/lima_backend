from dataclasses import dataclass
from typing import Optional

# Same constants as the Kotlin ScoringEngine — keep these two in sync if you
# tune the formula, since the Android app shows a preview calculation before
# the match ends, and this is the source of truth that actually applies it.
BASE_WIN = 30
BASE_LOSS = 10
SCALING_FACTOR = 200.0
MIN_MULTIPLIER = 0.5
MAX_MULTIPLIER = 2.0

MIN_TOTAL_SECONDS = 15 * 60
MIN_PER_SET_SECONDS = 5 * 60

TIERS = ["BEGINNER", "INTERMEDIATE", "ADVANCED", "PRO"]
TIER_THRESHOLDS = [0, 200, 600, 1200]


@dataclass
class ScoringResult:
    points_to_winner: int
    points_to_loser: int


def calculate_points(winner_points: int, loser_points: int) -> ScoringResult:
    gap = loser_points - winner_points  # positive if the winner was the underdog

    win_multiplier = _clamp(1 + gap / SCALING_FACTOR, MIN_MULTIPLIER, MAX_MULTIPLIER)
    loss_multiplier = _clamp(1 - gap / SCALING_FACTOR, MIN_MULTIPLIER, MAX_MULTIPLIER)

    return ScoringResult(
        points_to_winner=round(BASE_WIN * win_multiplier),
        points_to_loser=round(BASE_LOSS * loss_multiplier),
    )


def get_tier(points: int) -> str:
    tier = TIERS[0]
    for name, threshold in zip(TIERS, TIER_THRESHOLDS):
        if points >= threshold:
            tier = name
    return tier


def tier_mismatch_warning(player1_points: int, player2_points: int) -> Optional[str]:
    t1, t2 = get_tier(player1_points), get_tier(player2_points)
    gap = abs(TIERS.index(t1) - TIERS.index(t2))
    if gap >= 2:
        return f"This is a {t1.lower()} vs {t2.lower()} matchup — big skill gap."
    return None


def is_recordable(total_time_seconds: int, time_per_set_seconds: int) -> bool:
    return total_time_seconds >= MIN_TOTAL_SECONDS and time_per_set_seconds >= MIN_PER_SET_SECONDS


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
