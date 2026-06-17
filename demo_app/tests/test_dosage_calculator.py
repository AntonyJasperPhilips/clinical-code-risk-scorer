import pytest

from demo_app.dosage_calculator import (
    DosageError,
    DosageOrder,
    calculate_dose_mg,
    is_within_safe_range,
)


def test_normal_dose():
    order = DosageOrder("paracetamol", mg_per_kg=10, patient_weight_kg=70)
    assert calculate_dose_mg(order) == 700.0


def test_dose_clamped_to_ceiling():
    order = DosageOrder("morphine", mg_per_kg=1.0, patient_weight_kg=80)
    # raw would be 80mg, ceiling is 10mg
    assert calculate_dose_mg(order) == 10.0


def test_unknown_drug():
    with pytest.raises(DosageError):
        calculate_dose_mg(DosageOrder("aspirin", 5, 60))


def test_non_positive_weight():
    with pytest.raises(DosageError):
        calculate_dose_mg(DosageOrder("heparin", 50, 0))


def test_negative_rate():
    with pytest.raises(DosageError):
        calculate_dose_mg(DosageOrder("heparin", -1, 60))


def test_is_within_safe_range():
    assert is_within_safe_range(DosageOrder("paracetamol", 10, 70)) is True
    assert is_within_safe_range(DosageOrder("morphine", 1.0, 80)) is False
    assert is_within_safe_range(DosageOrder("aspirin", 1, 80)) is False
