"""Component 10 — request PR reviewers/teams based on the clinical risk level.

The reviewer and team handles come from ``config/sme_registry.json`` (resolved
into the RiskScore by the scorer). This module turns that recommendation into an
actual GitHub *review request* on the PR, escalating with criticality.

Best-effort by design: an invalid handle, the PR author appearing in the list, or
a personal (org-less) repo must NOT fail the core risk assessment — failures are
logged and swallowed.
"""

import sys

import requests

from scorer.models import RiskScore

GITHUB_API = "https://api.github.com"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def request_reviewers(token: str, repo: str, pr_number: int, score: RiskScore) -> None:
    """Request the reviewers/teams assigned to this PR's risk level.

    - reviewers  -> individual GitHub usernames
    - teams      -> org team slugs (ignored by GitHub on personal repos)
    Does nothing when neither is configured (e.g. LOW). Never raises.
    """
    reviewers = list(score.assigned_reviewers or [])
    team_reviewers = list(score.assigned_teams or [])

    if not reviewers and not team_reviewers:
        print(f"[reviewer_assigner] No reviewers configured for {score.level.value} — skipping.")
        return

    url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/requested_reviewers"
    payload = {"reviewers": reviewers, "team_reviewers": team_reviewers}

    try:
        resp = requests.post(url, headers=_headers(token), json=payload, timeout=30)
        if resp.status_code >= 400:
            # 422 commonly means a handle is unknown, not a collaborator, or is the
            # PR author. Treat as non-fatal so the assessment still completes.
            print(
                f"[reviewer_assigner] Could not request reviewers "
                f"({resp.status_code}): {resp.text[:200]}",
                file=sys.stderr,
            )
            return
        print(
            f"[reviewer_assigner] Requested {len(reviewers)} reviewer(s) and "
            f"{len(team_reviewers)} team(s) for {score.level.value}."
        )
    except requests.RequestException as exc:
        print(f"[reviewer_assigner] Review request failed: {exc}", file=sys.stderr)
