"""Role-based access control for clinical actions."""

# action -> roles permitted to perform it
_PERMISSIONS = {
    "view_vitals": {"nurse", "physician", "admin"},
    "order_dosage": {"physician", "admin"},
    "edit_thresholds": {"physician", "biomed", "admin"},
    "export_patient_data": {"admin"},
}


def can(role: str, action: str) -> bool:
    """Return True if ``role`` is permitted to perform ``action``."""
    allowed = _PERMISSIONS.get(action)
    if allowed is None:
        raise ValueError(f"unknown action: {action}")
    return role in allowed


def require(role: str, action: str) -> None:
    """Raise PermissionError if the role may not perform the action."""
    if not can(role, action):
        raise PermissionError(f"role '{role}' may not '{action}'")
