"""Heart-rate processing and alerting."""

from statistics import mean
from typing import List


def smooth_bpm(samples: List[float]) -> float:
    """Return a simple moving average of the last 5 BPM samples."""
    if not samples:
        raise ValueError("no samples provided")
    window = samples[-5:]
    return round(mean(window), 1)


def classify_bpm(bpm: float, *, age_years: int) -> str:
    """Classify a heart rate as 'brady', 'normal', or 'tachy'.

    Uses age-adjusted bounds (paediatric patients run faster).
    """
    if bpm <= 0:
        raise ValueError("bpm must be positive")

    if age_years < 1:
        low, high = 100, 160
    elif age_years < 12:
        low, high = 70, 120
    else:
        low, high = 60, 100

    if bpm < low:
        return "brady"
    if bpm > high:
        return "tachy"
    return "normal"
