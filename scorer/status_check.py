"""Component 7 — set a GitHub commit status check based on the risk level."""

import requests

from scorer.models import RiskLevel

GITHUB_API = "https://api.github.com"
CONTEXT = "Clinical Risk Scorer"

# Risk level -> (state, description)
_STATUS_MAP = {
    RiskLevel.LOW: ("success", "Clinical risk: LOW — standard review"),
    RiskLevel.MEDIUM: ("pending", "Clinical risk: MEDIUM — 1 senior reviewer required"),
    RiskLevel.HIGH: ("failure", "Clinical risk: HIGH — 2 reviewers + QA sign-off required"),
    RiskLevel.CRITICAL: ("error", "Clinical risk: CRITICAL — merge blocked, escalate to clinical lead"),
}


def set_status_check(
    token: str,
    repo: str,
    sha: str,
    risk_level: RiskLevel,
    details_url: str,
) -> None:
    """
    POST /repos/{owner}/{repo}/statuses/{sha}
    Sets state, description, and context='Clinical Risk Scorer'.
    """
    state, description = _STATUS_MAP[risk_level]
    url = f"{GITHUB_API}/repos/{repo}/statuses/{sha}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "state": state,
        "description": description[:140],  # GitHub truncates at 140 chars
        "context": CONTEXT,
        "target_url": details_url,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()


def set_failure_status(token: str, repo: str, sha: str, details_url: str) -> None:
    """Set an error status when the scorer itself fails — forces manual review."""
    url = f"{GITHUB_API}/repos/{repo}/statuses/{sha}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "state": "error",
        "description": "Scorer failed — manual review required",
        "context": CONTEXT,
        "target_url": details_url,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
