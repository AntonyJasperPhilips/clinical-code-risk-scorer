"""Medication dosage calculation — patient-safety critical (risk weight 4).

Matches glob ``**/dosage_calculator*`` in clinical_modules.json.
"""

from dataclasses import dataclass


# Hard safety ceilings (mg) per drug — never exceed regardless of weight.
MAX_ABSOLUTE_DOSE_MG = {
    "paracetamol": 1000.0,
    "morphine": 10.0,
    "heparin": 5000.0,
    "ibuprofen": 800.0,
}


@dataclass
class DosageOrder:
    drug: str
    mg_per_kg: float
    patient_weight_kg: float


class DosageError(ValueError):
    """Raised when a dosage request is clinically unsafe or malformed."""


def calculate_dose_mg(order: DosageOrder) -> float:
    """Compute a single dose in mg, clamped to the drug's absolute ceiling.

    Raises DosageError for non-positive weight or unknown drugs.
    """
    if order.patient_weight_kg <= 0:
        raise DosageError("patient weight must be positive")
    if order.mg_per_kg < 0:
        raise DosageError("mg_per_kg cannot be negative")

    drug = order.drug.lower()
    if drug not in MAX_ABSOLUTE_DOSE_MG:
        raise DosageError(f"unknown drug: {order.drug}")

    raw = order.mg_per_kg * order.patient_weight_kg
    ceiling = MAX_ABSOLUTE_DOSE_MG[drug]
    return min(raw, ceiling)


def is_within_safe_range(order: DosageOrder) -> bool:
    """True if the requested dose does not need to be clamped to the ceiling."""
    drug = order.drug.lower()
    if drug not in MAX_ABSOLUTE_DOSE_MG:
        return False
    raw = order.mg_per_kg * order.patient_weight_kg
    return raw <= MAX_ABSOLUTE_DOSE_MG[drug]
