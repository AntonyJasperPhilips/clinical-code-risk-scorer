"""Tiny render helpers for the patient dashboard (non-clinical presentation)."""


def format_patient_row(name: str, bpm: float, status: str) -> str:
    """Render a single dashboard row as plain text."""
    return f"{name:<20} {bpm:>5.0f} bpm   [{status}]"


def primary_button_label(is_saving: bool) -> str:
    return "Saving…" if is_saving else "Save"
