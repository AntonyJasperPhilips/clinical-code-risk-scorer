"""MediFlow — a tiny simulated infusion-pump / patient-monitor stack.

This package exists purely to demonstrate the Clinical Code Risk Scorer. Its
module paths are deliberately laid out to match the glob patterns in
``config/clinical_modules.json`` (dosage_calculator, vitals/, alarm_threshold,
patient_data/, auth/, api/, ui/, styles/) so that PRs touching different files
produce different clinical risk levels.
"""

__version__ = "0.1.0"
