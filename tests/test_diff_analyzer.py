import pytest

from scorer import diff_analyzer
from scorer.diff_analyzer import analyze_diff, load_clinical_modules, tag_file
from tests.conftest import FakeResponse, load_fixture


def test_load_clinical_modules_missing():
    with pytest.raises(FileNotFoundError):
        load_clinical_modules("config/does_not_exist.json")


def test_tag_file_critical(modules_config):
    domain, weight = tag_file("vitals/dosage_calculator.py", modules_config)
    assert weight == 4
    assert domain == "Medication Safety"


def test_tag_file_low(modules_config):
    domain, weight = tag_file("styles/theme.css", modules_config)
    assert weight == 1
    assert domain == "Styling"


def test_tag_file_unclassified_uses_default(modules_config):
    domain, weight = tag_file("random/thing.py", modules_config)
    assert domain == "Unclassified"
    assert weight == modules_config["default_risk_weight"]


def test_tag_file_highest_weight_wins(modules_config):
    # A markdown file under patient_data would match both **/*.md (1) and
    # **/patient_data/** (4) — highest must win.
    domain, weight = tag_file("patient_data/notes.md", modules_config)
    assert weight == 4


def test_analyze_diff_high_risk(monkeypatch, modules_config):
    monkeypatch.setattr(
        diff_analyzer.requests,
        "get",
        lambda *a, **k: FakeResponse(load_fixture("sample_diff_high_risk.json")),
    )
    changed, clinical, max_weight = analyze_diff(
        "tok", "owner/repo", "base", "head", modules_config
    )
    assert "vitals/dosage_calculator.py" in changed
    assert max_weight == 4
    assert any(m.file_path == "vitals/dosage_calculator.py" for m in clinical)


def test_analyze_diff_low_risk(monkeypatch, modules_config):
    monkeypatch.setattr(
        diff_analyzer.requests,
        "get",
        lambda *a, **k: FakeResponse(load_fixture("sample_diff_low_risk.json")),
    )
    changed, clinical, max_weight = analyze_diff(
        "tok", "owner/repo", "base", "head", modules_config
    )
    assert max_weight == 1
    assert len(clinical) == 2
