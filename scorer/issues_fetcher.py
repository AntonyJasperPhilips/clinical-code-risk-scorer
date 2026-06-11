"""Signal 3 — extract issue references from the PR and fetch their context
from the GitHub Issues API."""

import re
from typing import List, Tuple

import requests

from scorer.models import LinkedIssue

GITHUB_API = "https://api.github.com"

CLINICAL_KEYWORDS = [
    "dosage", "medication", "patient", "clinical", "safety",
    "alarm", "threshold", "vital", "diagnostic", "treatment",
    "iec 62304", "risk", "hazard", "adverse event", "fmea",
]

# Clinical-intent labels (lowercased) that confirm intent on their own.
_CLINICAL_LABEL_HINTS = {"clinical", "patient-safety", "safety", "hazard", "iec-62304"}

_ISSUE_REF = re.compile(r"#(\d+)")


def extract_issue_numbers(pr_title: str, pr_body: str) -> List[int]:
    """Extract all issue numbers referenced in the PR title and body.

    Captures bare `#123` as well as `closes #123`, `fixes #123`, etc.
    Returns a de-duplicated, order-preserving list.
    """
    text = f"{pr_title or ''}\n{pr_body or ''}"
    seen = []
    for match in _ISSUE_REF.finditer(text):
        num = int(match.group(1))
        if num not in seen:
            seen.append(num)
    return seen


def _scan_keywords(text: str) -> List[str]:
    lowered = (text or "").lower()
    return [kw for kw in CLINICAL_KEYWORDS if kw in lowered]


def fetch_issue(token: str, repo: str, issue_number: int) -> LinkedIssue:
    """Fetch a single issue and return a LinkedIssue dataclass."""
    url = f"{GITHUB_API}/repos/{repo}/issues/{issue_number}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    labels = [lbl["name"] for lbl in data.get("labels", [])]
    haystack = f"{data.get('title', '')}\n{data.get('body', '')}\n{' '.join(labels)}"
    keywords = _scan_keywords(haystack)

    return LinkedIssue(
        issue_number=issue_number,
        title=data.get("title", ""),
        labels=labels,
        clinical_keywords_found=keywords,
    )


def _issue_signals_clinical(issue: LinkedIssue) -> bool:
    if issue.clinical_keywords_found:
        return True
    for lbl in issue.labels:
        if lbl.lower() in _CLINICAL_LABEL_HINTS:
            return True
    return False


def fetch_linked_issues(
    token: str,
    repo: str,
    pr_number: int,
) -> Tuple[List[LinkedIssue], bool]:
    """
    Returns:
        linked_issues: list of fetched LinkedIssue objects
        clinical_intent_confirmed: True if any issue signals clinical intent
    """
    pr_url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = requests.get(pr_url, headers=headers, timeout=30)
    resp.raise_for_status()
    pr = resp.json()

    issue_numbers = extract_issue_numbers(pr.get("title", ""), pr.get("body", ""))

    linked_issues: List[LinkedIssue] = []
    clinical_intent = False
    for num in issue_numbers:
        try:
            issue = fetch_issue(token, repo, num)
        except requests.HTTPError as exc:
            print(f"[issues_fetcher] WARNING: could not fetch issue #{num}: {exc}")
            continue
        linked_issues.append(issue)
        if _issue_signals_clinical(issue):
            clinical_intent = True

    return linked_issues, clinical_intent
