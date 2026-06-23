from scorer import reviewer_assigner
from scorer.reviewer_assigner import request_reviewers
from scorer.models import RiskLevel, RiskScore


def _score(level, reviewers, teams):
    return RiskScore(
        level=level,
        score=9,
        reasoning="x",
        contributing_factors=[],
        recommended_gates=[],
        assigned_reviewers=reviewers,
        assigned_teams=teams,
    )


class _Recorder:
    def __init__(self, status_code=201):
        self.calls = []
        self._status = status_code

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append((url, json))
        return _Resp(self._status)


class _Resp:
    def __init__(self, status_code):
        self.status_code = status_code
        self.text = "error body"


def test_critical_requests_reviewers_and_teams(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(reviewer_assigner, "requests", rec)
    score = _score(RiskLevel.CRITICAL, ["a", "b", "c"], ["clinical-qa", "patient-safety"])
    request_reviewers("tok", "owner/repo", 1, score)
    assert len(rec.calls) == 1
    url, payload = rec.calls[0]
    assert url.endswith("/pulls/1/requested_reviewers")
    assert payload == {"reviewers": ["a", "b", "c"], "team_reviewers": ["clinical-qa", "patient-safety"]}


def test_low_with_no_reviewers_makes_no_request(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(reviewer_assigner, "requests", rec)
    score = _score(RiskLevel.LOW, [], [])
    request_reviewers("tok", "owner/repo", 2, score)
    assert rec.calls == []


def test_422_is_swallowed(monkeypatch):
    rec = _Recorder(status_code=422)
    monkeypatch.setattr(reviewer_assigner, "requests", rec)
    score = _score(RiskLevel.HIGH, ["unknown-handle"], [])
    # Must not raise even though GitHub rejects the handle.
    request_reviewers("tok", "owner/repo", 3, score)
    assert len(rec.calls) == 1


def test_network_error_is_swallowed(monkeypatch):
    import requests as real_requests

    class _Boom:
        RequestException = real_requests.RequestException

        def post(self, *a, **k):
            raise real_requests.RequestException("boom")

    monkeypatch.setattr(reviewer_assigner, "requests", _Boom())
    score = _score(RiskLevel.CRITICAL, ["a"], [])
    request_reviewers("tok", "owner/repo", 4, score)  # should not raise
