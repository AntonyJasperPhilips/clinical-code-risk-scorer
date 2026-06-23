import json

from scorer import copilot_scorer
from scorer.copilot_scorer import call_copilot_scorer, rule_based_fallback
from scorer.models import ChangedModule, LinkedIssue, RiskLevel, RiskSignal


def make_signal(weight, below=False, lowest=100.0, modules=None, issues=None):
    return RiskSignal(
        changed_files=["x.py"],
        clinical_modules_touched=modules or [],
        max_module_risk_weight=weight,
        coverage_deltas=[],
        clinical_coverage_below_threshold=below,
        lowest_clinical_coverage=lowest,
        linked_issues=issues or [],
        clinical_intent_confirmed=bool(issues),
    )


# ---- rule-based fallback ----

def test_fallback_low(sme_config):
    score = rule_based_fallback(make_signal(1), sme_config)
    assert score.level == RiskLevel.LOW
    assert score.fallback_used is True


def test_fallback_medium(sme_config):
    score = rule_based_fallback(make_signal(2), sme_config)
    assert score.level == RiskLevel.MEDIUM


def test_fallback_high(sme_config):
    mod = ChangedModule("vitals/x.py", "Clinical Measurement", 3, 5, 0)
    score = rule_based_fallback(make_signal(3, modules=[mod]), sme_config)
    assert score.level == RiskLevel.HIGH
    assert score.assigned_reviewers  # HIGH has reviewers in sme_registry


def test_fallback_critical(sme_config):
    mod = ChangedModule("patient_data/pipeline.py", "Patient Data", 4, 5, 0)
    score = rule_based_fallback(make_signal(4, below=True, lowest=45.0, modules=[mod]), sme_config)
    assert score.level == RiskLevel.CRITICAL
    assert score.score == 10


def test_fallback_medium_escalates_on_coverage_gap(sme_config):
    score = rule_based_fallback(make_signal(2, below=True, lowest=50.0), sme_config)
    assert score.level == RiskLevel.HIGH


# ---- copilot path ----

def test_call_copilot_no_token_uses_fallback(sme_config):
    score = call_copilot_scorer("", make_signal(4), sme_config)
    assert score.fallback_used is True
    assert score.level == RiskLevel.CRITICAL


def test_call_copilot_success(monkeypatch, sme_config):
    api_json = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "risk_level": "HIGH",
                            "score": 8,
                            "reasoning": "clinical change",
                            "contributing_factors": ["dosage module"],
                            "recommended_gates": ["2 approvals"],
                        }
                    )
                }
            }
        ]
    }

    class Resp:
        status_code = 200

        def json(self):
            return api_json

        def raise_for_status(self):
            pass

    monkeypatch.setattr(copilot_scorer, "_exchange_copilot_token", lambda tok: "copilot-bearer")
    monkeypatch.setattr(copilot_scorer.requests, "post", lambda *a, **k: Resp())

    score = call_copilot_scorer("tok", make_signal(3), sme_config)
    assert score.level == RiskLevel.HIGH
    assert score.score == 8
    assert score.fallback_used is False
    assert score.assigned_reviewers  # filled from sme_config for HIGH


def test_call_copilot_invalid_json_falls_back(monkeypatch, sme_config):
    class Resp:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "not json"}}]}

        def raise_for_status(self):
            pass

    monkeypatch.setattr(copilot_scorer, "_exchange_copilot_token", lambda tok: "copilot-bearer")
    monkeypatch.setattr(copilot_scorer.requests, "post", lambda *a, **k: Resp())

    score = call_copilot_scorer("tok", make_signal(4), sme_config)
    assert score.fallback_used is True
    assert score.level == RiskLevel.CRITICAL


def test_token_exchange_failure_falls_back(monkeypatch, sme_config):
    """If the Copilot token exchange fails, we fall back without calling the model."""
    import requests as _requests

    def boom(_tok):
        raise _requests.RequestException("exchange down")

    def fail_post(*a, **k):
        raise AssertionError("model should not be called when exchange fails")

    monkeypatch.setattr(copilot_scorer, "_exchange_copilot_token", boom)
    monkeypatch.setattr(copilot_scorer.requests, "post", fail_post)

    score = call_copilot_scorer("oauth-tok", make_signal(4), sme_config)
    assert score.fallback_used is True
    assert score.level == RiskLevel.CRITICAL


def test_models_endpoint_skips_token_exchange(monkeypatch, sme_config):
    """A non-Copilot endpoint (GitHub Models/gateway) uses the token as-is."""
    api_json = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "risk_level": "MEDIUM",
                            "score": 4,
                            "reasoning": "peripheral change",
                            "contributing_factors": ["api module"],
                            "recommended_gates": ["1 approval"],
                        }
                    )
                }
            }
        ]
    }

    class Resp:
        status_code = 200

        def json(self):
            return api_json

        def raise_for_status(self):
            pass

    def no_exchange(_tok):
        raise AssertionError("token exchange must not run for non-Copilot endpoints")

    monkeypatch.setattr(copilot_scorer, "COPILOT_ENDPOINT", "https://models.github.ai/inference/chat/completions")
    monkeypatch.setattr(copilot_scorer, "_exchange_copilot_token", no_exchange)
    monkeypatch.setattr(copilot_scorer.requests, "post", lambda *a, **k: Resp())

    score = call_copilot_scorer("pat", make_signal(2), sme_config)
    assert score.fallback_used is False
    assert score.level == RiskLevel.MEDIUM
