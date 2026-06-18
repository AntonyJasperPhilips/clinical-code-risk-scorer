"""Component 9 — apply a clinical-risk label to the PR for HIGH/CRITICAL verdicts.

Labels make high-risk PRs filterable in the GitHub UI. The label set is
"managed" by the scorer: on every run the label that does not match the current
verdict is removed, so re-runs (e.g. after a fix lowers the risk) stay accurate.
"""

from urllib.parse import quote

import requests

from scorer.models import RiskLevel

GITHUB_API = "https://api.github.com"

# Risk level -> (label name, hex colour, description). Only HIGH/CRITICAL are labelled.
_LABEL_DEFS = {
    RiskLevel.HIGH: ("clinical-risk:HIGH", "D93F0B", "Clinical Risk Scorer: HIGH risk change"),
    RiskLevel.CRITICAL: ("clinical-risk:CRITICAL", "B60205", "Clinical Risk Scorer: CRITICAL risk change"),
}

MANAGED_LABELS = {name for name, _, _ in _LABEL_DEFS.values()}


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _ensure_label_exists(token: str, repo: str, name: str, color: str, description: str) -> None:
    """Create the repo label if it does not already exist (422 = already present)."""
    url = f"{GITHUB_API}/repos/{repo}/labels"
    resp = requests.post(
        url,
        headers=_headers(token),
        json={"name": name, "color": color, "description": description},
        timeout=30,
    )
    if resp.status_code == 422:  # already exists — fine
        return
    resp.raise_for_status()


def sync_risk_label(token: str, repo: str, pr_number: int, risk_level: RiskLevel) -> None:
    """Ensure the PR carries the correct clinical-risk label.

    - HIGH/CRITICAL  -> add the matching label (creating it in the repo if needed).
    - LOW/MEDIUM     -> add nothing.
    Any *other* managed risk label left over from a previous run is removed, so a
    PR that drops from CRITICAL to LOW does not keep a stale CRITICAL tag.
    """
    desired = _LABEL_DEFS.get(risk_level, (None, None, None))[0]

    # Remove any managed label that is not the desired one.
    for name in MANAGED_LABELS:
        if name == desired:
            continue
        url = f"{GITHUB_API}/repos/{repo}/issues/{pr_number}/labels/{quote(name, safe='')}"
        resp = requests.delete(url, headers=_headers(token), timeout=30)
        if resp.status_code not in (200, 404):  # 404 = label not on PR, ignore
            resp.raise_for_status()

    if desired is None:
        return

    _, color, description = _LABEL_DEFS[risk_level]
    _ensure_label_exists(token, repo, desired, color, description)

    url = f"{GITHUB_API}/repos/{repo}/issues/{pr_number}/labels"
    resp = requests.post(url, headers=_headers(token), json={"labels": [desired]}, timeout=30)
    resp.raise_for_status()
