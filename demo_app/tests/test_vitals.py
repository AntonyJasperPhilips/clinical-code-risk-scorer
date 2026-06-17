import pytest

from demo_app.vitals.alarm_threshold import DEFAULTS, AlarmThreshold, breaches
from demo_app.vitals.heart_rate import classify_bpm, smooth_bpm


def test_smooth_bpm_window():
    assert smooth_bpm([60, 62, 64, 66, 68, 70]) == 66.0  # last 5 only


def test_smooth_bpm_empty():
    with pytest.raises(ValueError):
        smooth_bpm([])


@pytest.mark.parametrize(
    "bpm,age,expected",
    [
        (130, 0, "normal"),
        (90, 0, "brady"),
        (80, 30, "normal"),
        (40, 30, "brady"),
        (140, 30, "tachy"),
    ],
)
def test_classify_bpm(bpm, age, expected):
    assert classify_bpm(bpm, age_years=age) == expected


def test_classify_bpm_invalid():
    with pytest.raises(ValueError):
        classify_bpm(0, age_years=30)


def test_alarm_threshold_validation():
    with pytest.raises(ValueError):
        AlarmThreshold("spo2", low=100, high=90)


def test_breaches():
    t = DEFAULTS["spo2"]
    assert breaches(t, 85.0) is True
    assert breaches(t, 95.0) is False
