from scorer import labeler
from scorer.labeler import sync_risk_label
from scorer.models import RiskLevel


class _Recorder:
    """Records GitHub API calls and returns canned responses."""

    def __init__(self, post_status=201, delete_status=200):
        self.post_calls = []
        self.delete_calls = []
        self._post_status = post_status
        self._delete_status = delete_status

    def post(self, url, headers=None, json=None, timeout=None):
        self.post_calls.append((url, json))
        # The repo-label create endpoint returns 422 when the label already exists;
        # treat label-create as success here.
        return _Resp(self._post_status)

    def delete(self, url, headers=None, timeout=None):
        self.delete_calls.append(url)
        return _Resp(self._delete_status)


class _Resp:
    def __init__(self, status_code):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"status {self.status_code}")


def _added_labels(rec):
    return [j.get("labels") for _, j in rec.post_calls if j and "labels" in j]


def test_critical_adds_critical_label(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(labeler, "requests", rec)
    sync_risk_label("tok", "owner/repo", 1, RiskLevel.CRITICAL)
    assert ["clinical-risk:CRITICAL"] in _added_labels(rec)
    # The HIGH label must be removed so a downgraded re-run is accurate.
    assert any("clinical-risk%3AHIGH" in u for u in rec.delete_calls)


def test_high_adds_high_label(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(labeler, "requests", rec)
    sync_risk_label("tok", "owner/repo", 2, RiskLevel.HIGH)
    assert ["clinical-risk:HIGH"] in _added_labels(rec)
    assert any("clinical-risk%3ACRITICAL" in u for u in rec.delete_calls)


def test_low_adds_no_label_and_clears_managed(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(labeler, "requests", rec)
    sync_risk_label("tok", "owner/repo", 3, RiskLevel.LOW)
    assert _added_labels(rec) == []
    # Both managed labels are removed on a LOW verdict.
    assert len(rec.delete_calls) == 2


def test_medium_adds_no_label(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(labeler, "requests", rec)
    sync_risk_label("tok", "owner/repo", 4, RiskLevel.MEDIUM)
    assert _added_labels(rec) == []
