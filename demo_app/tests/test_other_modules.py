"""Coverage for auth, api, ui, and patient_data modules.

Note: patient_data is deliberately only *partially* covered (encryption.decrypt
and some pipeline branches are untested) so the demo can show a clinical
coverage gap on a high-risk module.
"""

import pytest

from demo_app.api.endpoints import paginate, search_patients
from demo_app.auth.access_control import can, require
from demo_app.patient_data.encryption import encrypt
from demo_app.patient_data.pipeline import PatientRecord, ingest, validate_record
from demo_app.ui.dashboard import format_patient_row, primary_button_label


# ---- auth ----

def test_can_and_require():
    assert can("physician", "order_dosage") is True
    assert can("nurse", "order_dosage") is False
    require("admin", "export_patient_data")
    with pytest.raises(PermissionError):
        require("nurse", "export_patient_data")


def test_unknown_action():
    with pytest.raises(ValueError):
        can("admin", "launch_rocket")


# ---- api ----

def test_paginate():
    items = [{"id": i} for i in range(45)]
    page = paginate(items, page=2, page_size=20)
    assert page["total"] == 45
    assert page["total_pages"] == 3
    assert page["results"][0]["id"] == 20


def test_paginate_invalid():
    with pytest.raises(ValueError):
        paginate([], page=0)


def test_search_patients():
    patients = [{"name": "Ada Lovelace"}, {"name": "Alan Turing"}]
    assert len(search_patients(patients, "ada")) == 1
    assert len(search_patients(patients, "")) == 2


# ---- ui ----

def test_ui_helpers():
    assert "bpm" in format_patient_row("Ada", 72, "normal")
    assert primary_button_label(True) == "Saving…"


# ---- patient_data (intentionally partial) ----

def test_ingest_happy_path():
    records = [PatientRecord("MRN1", "Ada", "stable")]
    stored = ingest(records, key=42)
    assert stored[0]["mrn"] == "MRN1"
    assert stored[0]["payload"] != "stable"  # encrypted


def test_validate_missing_mrn():
    with pytest.raises(ValueError):
        validate_record(PatientRecord("", "Ada", "note"))


def test_encrypt_roundtrip_partial():
    # Only encrypt is exercised here — decrypt is intentionally left uncovered.
    assert encrypt("hello", key=7) != "hello"
