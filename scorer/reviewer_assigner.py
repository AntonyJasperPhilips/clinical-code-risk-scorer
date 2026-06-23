"""Component 10 — request PR reviewers/teams based on the clinical risk level.

The reviewer and team handles come from ``config/sme_registry.json`` (resolved
into the RiskScore by the scorer). This module turns that recommendation into an
actual GitHub *review request* on the PR, escalating with criticality.

Best-effort by design: an invalid handle, the PR author appearing in the list, or
a personal (org-less) repo must NOT fail the core risk assessment — failures are
logged and swallowed.

Robustness notes:
- Reviewers and teams are requested in *separate* calls, so a bad team slug does
  not block valid individual reviewers (and vice versa).
- If a batch request fails (e.g. one invalid entry), each entry is retried
  individually so the valid ones still get assigned.
- The PR author is removed from the reviewer list (GitHub rejects self-requests).
"""

import sys
from typing import List

import requests

from scorer.models import RiskScore

GITHUB_API = "https://api.github.com"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _pr_author(token: str, repo: str, pr_number: int) -> str:
    """Return the PR author's login, or "" if it cannot be determined."""
    url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}"
    try:
        resp = requests.get(url, headers=_headers(token), timeout=30)
        if resp.status_code >= 400:
            return ""
        return (resp.json().get("user") or {}).get("login", "") or ""
    except requests.RequestException:
        return ""


def _post_review_request(token: str, repo: str, pr_number: int, payload: dict) -> bool:
    """POST a requested_reviewers payload. Returns True on success, False on any error."""
    url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/requested_reviewers"
    try:
        resp = requests.post(url, headers=_headers(token), json=payload, timeout=30)
        if resp.status_code >= 400:
            print(
                f"[reviewer_assigner] request rejected ({resp.status_code}) for "
                f"{payload}: {resp.text[:200]}",
                file=sys.stderr,
            )
            return False
        return True
    except requests.RequestException as exc:
        print(f"[reviewer_assigner] request failed for {payload}: {exc}", file=sys.stderr)
        return False


def _request_batch(token: str, repo: str, pr_number: int, key: str, values: List[str]) -> None:
    """Request a list of reviewers (key='reviewers') or teams (key='team_reviewers').

    Tries a single batch first; if that fails, retries each value individually so
    one invalid entry does not block the rest.
    """
    if not values:
        return
    if _post_review_request(token, repo, pr_number, {key: values}):
        print(f"[reviewer_assigner] Requested {len(values)} {key}: {values}")
        return
    # Batch failed — fall back to one-at-a-time so valid entries still apply.
    for value in values:
        if _post_review_request(token, repo, pr_number, {key: [value]}):
            print(f"[reviewer_assigner] Requested {key}: {value}")
        else:
            print(f"[reviewer_assigner] Skipped invalid {key}: {value}", file=sys.stderr)


def request_reviewers(token: str, repo: str, pr_number: int, score: RiskScore) -> None:
    """Request the reviewers/teams assigned to this PR's risk level.

    - reviewers  -> individual GitHub usernames (PR author removed automatically)
    - teams      -> org team slugs (ignored by GitHub on personal repos)
    Does nothing when neither is configured (e.g. LOW). Never raises.
    """
    reviewers = list(score.assigned_reviewers or [])
    team_reviewers = list(score.assigned_teams or [])

    if not reviewers and not team_reviewers:
        print(f"[reviewer_assigner] No reviewers configured for {score.level.value} — skipping.")
        return

    # GitHub rejects a review request that includes the PR author.
    if reviewers:
        author = _pr_author(token, repo, pr_number)
        if author and author in reviewers:
            reviewers = [r for r in reviewers if r != author]
            print(f"[reviewer_assigner] Removed PR author '{author}' from reviewer request.")

    # Separate calls so a bad team slug does not block valid individual reviewers.
    _request_batch(token, repo, pr_number, "reviewers", reviewers)
    _request_batch(token, repo, pr_number, "team_reviewers", team_reviewers)
