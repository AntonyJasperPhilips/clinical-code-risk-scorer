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


class _Resp:
    def __init__(self, status_code, author=""):
        self.status_code = status_code
        self.text = "error body"
        self._author = author

    def json(self):
        return {"user": {"login": self._author}}


class _Recorder:
    """Fake `requests` module: records POST payloads, returns canned responses."""

    def __init__(self, post_status=201, author=""):
        self.posts = []
        self.gets = []
        self._post_status = post_status
        self._author = author
        self.RequestException = Exception

    def get(self, url, headers=None, timeout=None):
        self.gets.append(url)
        return _Resp(200, author=self._author)

    def post(self, url, headers=None, json=None, timeout=None):
        self.posts.append(json)
        return _Resp(self._post_status)


def test_critical_requests_reviewers_and_teams_separately(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(reviewer_assigner, "requests", rec)
    score = _score(RiskLevel.CRITICAL, ["a", "b", "c"], ["clinical-qa", "patient-safety"])
    request_reviewers("tok", "owner/repo", 1, score)
    # Reviewers and teams go in separate calls.
    assert {"reviewers": ["a", "b", "c"]} in rec.posts
    assert {"team_reviewers": ["clinical-qa", "patient-safety"]} in rec.posts


def test_pr_author_removed_from_reviewers(monkeypatch):
    rec = _Recorder(author="a")
    monkeypatch.setattr(reviewer_assigner, "requests", rec)
    score = _score(RiskLevel.HIGH, ["a", "b"], [])
    request_reviewers("tok", "owner/repo", 2, score)
    assert {"reviewers": ["b"]} in rec.posts
    assert {"reviewers": ["a", "b"]} not in rec.posts


def test_low_with_no_reviewers_makes_no_request(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(reviewer_assigner, "requests", rec)
    score = _score(RiskLevel.LOW, [], [])
    request_reviewers("tok", "owner/repo", 3, score)
    assert rec.posts == []
    assert rec.gets == []  # no author lookup when nothing to assign


def test_batch_failure_retries_individually(monkeypatch):
    # Batch of >1 fails; individual requests (len 1) succeed.
    class _SizeAwareRecorder(_Recorder):
        def post(self, url, headers=None, json=None, timeout=None):
            self.posts.append(json)
            values = next(iter(json.values()))
            return _Resp(422 if len(values) > 1 else 201)

    rec = _SizeAwareRecorder()
    monkeypatch.setattr(reviewer_assigner, "requests", rec)
    score = _score(RiskLevel.CRITICAL, ["a", "b"], [])
    request_reviewers("tok", "owner/repo", 4, score)
    assert {"reviewers": ["a", "b"]} in rec.posts
    assert {"reviewers": ["a"]} in rec.posts
    assert {"reviewers": ["b"]} in rec.posts


def test_422_is_swallowed(monkeypatch):
    rec = _Recorder(post_status=422)
    monkeypatch.setattr(reviewer_assigner, "requests", rec)
    score = _score(RiskLevel.HIGH, ["unknown-handle"], [])
    request_reviewers("tok", "owner/repo", 5, score)  # must not raise


def test_network_error_is_swallowed(monkeypatch):
    import requests as real_requests

    class _Boom:
        RequestException = real_requests.RequestException

        def get(self, *a, **k):
            raise real_requests.RequestException("boom")

        def post(self, *a, **k):
            raise real_requests.RequestException("boom")

    monkeypatch.setattr(reviewer_assigner, "requests", _Boom())
    score = _score(RiskLevel.CRITICAL, ["a"], ["t"])
    request_reviewers("tok", "owner/repo", 6, score)  # must not raise
