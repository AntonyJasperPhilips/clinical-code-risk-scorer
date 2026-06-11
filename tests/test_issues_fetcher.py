from scorer import issues_fetcher
from scorer.issues_fetcher import extract_issue_numbers, fetch_linked_issues
from tests.conftest import FakeResponse, load_fixture


def test_extract_issue_numbers():
    nums = extract_issue_numbers("Closes #123", "Relates to #456 and #123")
    assert nums == [123, 456]


def test_extract_issue_numbers_empty():
    assert extract_issue_numbers("No refs here", "") == []


def test_fetch_linked_issues_clinical(monkeypatch):
    pr_payload = {
        "title": "Update IV drip limits",
        "body": "Fixes #123",
    }
    issue_payload = load_fixture("sample_issue.json")

    def fake_get(url, *a, **k):
        if "/pulls/" in url:
            return FakeResponse(pr_payload)
        return FakeResponse(issue_payload)

    monkeypatch.setattr(issues_fetcher.requests, "get", fake_get)

    issues, clinical_intent = fetch_linked_issues("tok", "owner/repo", 7)
    assert clinical_intent is True
    assert issues[0].issue_number == 123
    assert "dosage" in issues[0].clinical_keywords_found
    assert "patient" in issues[0].clinical_keywords_found


def test_fetch_linked_issues_none(monkeypatch):
    monkeypatch.setattr(
        issues_fetcher.requests,
        "get",
        lambda *a, **k: FakeResponse({"title": "Fix typo", "body": "no refs"}),
    )
    issues, clinical_intent = fetch_linked_issues("tok", "owner/repo", 7)
    assert issues == []
    assert clinical_intent is False
