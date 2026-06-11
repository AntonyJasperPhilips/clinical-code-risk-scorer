from scorer.coverage_analyzer import compute_coverage_deltas, parse_coverage_xml
from scorer.models import ChangedModule
from tests.conftest import FIXTURES


def _module(path):
    return ChangedModule(path, "Clinical Measurement", 4, 10, 0)


def test_parse_coverage_xml():
    cov = parse_coverage_xml(str(FIXTURES / "sample_coverage.xml"))
    assert cov["vitals/dosage_calculator.py"] == 61.0
    assert cov["patient_data/pipeline.py"] == 45.0


def test_parse_coverage_xml_missing():
    assert parse_coverage_xml("nope.xml") == {}


def test_compute_deltas_below_threshold():
    cov = parse_coverage_xml(str(FIXTURES / "sample_coverage.xml"))
    deltas, below, lowest = compute_coverage_deltas(
        cov, [_module("vitals/dosage_calculator.py")], threshold=80.0
    )
    assert below is True
    assert lowest == 61.0
    assert len(deltas) == 1


def test_compute_deltas_above_threshold():
    cov = parse_coverage_xml(str(FIXTURES / "sample_coverage.xml"))
    deltas, below, lowest = compute_coverage_deltas(
        cov, [_module("api/endpoints/patient_search.py")], threshold=80.0
    )
    assert below is False
    assert lowest == 85.0


def test_compute_deltas_no_clinical_files():
    deltas, below, lowest = compute_coverage_deltas({}, [], threshold=80.0)
    assert deltas == []
    assert below is False
    assert lowest == 100.0
