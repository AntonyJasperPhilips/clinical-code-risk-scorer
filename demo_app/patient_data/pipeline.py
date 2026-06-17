"""Patient record ingest pipeline."""

from dataclasses import dataclass
from typing import Dict, List

from demo_app.patient_data.encryption import encrypt


@dataclass
class PatientRecord:
    mrn: str          # medical record number
    name: str
    payload: str      # free-text clinical note


def validate_record(record: PatientRecord) -> None:
    """Raise ValueError if a record is missing mandatory identifiers."""
    if not record.mrn:
        raise ValueError("record missing MRN")
    if not record.name:
        raise ValueError("record missing patient name")


def ingest(records: List[PatientRecord], key: int) -> List[Dict[str, str]]:
    """Validate, then store records with the note field encrypted at rest."""
    stored = []
    for record in records:
        validate_record(record)
        stored.append(
            {
                "mrn": record.mrn,
                "name": record.name,
                "payload": encrypt(record.payload, key),
            }
        )
    return stored
