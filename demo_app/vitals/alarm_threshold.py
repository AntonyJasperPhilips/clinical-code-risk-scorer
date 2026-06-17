"""Alarm threshold configuration — safety interlock (risk weight 4).

Matches glob ``**/alarm_threshold*``.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AlarmThreshold:
    metric: str
    low: float
    high: float

    def __post_init__(self):
        if self.low >= self.high:
            raise ValueError(f"low ({self.low}) must be < high ({self.high})")


# Default interlocks. Changing these is a CRITICAL-adjacent action.
DEFAULTS = {
    "spo2": AlarmThreshold("spo2", low=90.0, high=100.0),
    "heart_rate": AlarmThreshold("heart_rate", low=50.0, high=120.0),
}


def breaches(threshold: AlarmThreshold, value: float) -> bool:
    """True if a measured value should trigger an alarm."""
    return value < threshold.low or value > threshold.high
