"""Signal 2 — parse coverage.xml (pytest-cov) and compute coverage on the
clinical files changed in the PR."""

import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple

from scorer.models import ChangedModule, CoverageDelta


def parse_coverage_xml(xml_path: str) -> Dict[str, float]:
    """
    Parse coverage.xml and return {file_path: coverage_percentage} mapping.
    Returns empty dict if file is missing or malformed.
    """
    if not os.path.exists(xml_path):
        print(f"[coverage_analyzer] WARNING: coverage report '{xml_path}' not found.")
        return {}

    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as exc:
        print(f"[coverage_analyzer] WARNING: failed to parse '{xml_path}': {exc}")
        return {}

    root = tree.getroot()
    coverage_map: Dict[str, float] = {}

    # Cobertura format: <coverage><packages><package><classes><class filename=... line-rate=...>
    for cls in root.iter("class"):
        filename = cls.get("filename")
        line_rate = cls.get("line-rate")
        if filename is None or line_rate is None:
            continue
        try:
            pct = float(line_rate) * 100.0
        except ValueError:
            continue
        # If multiple class entries map to the same file, keep the lowest (most
        # conservative) coverage.
        if filename in coverage_map:
            coverage_map[filename] = min(coverage_map[filename], pct)
        else:
            coverage_map[filename] = pct

    return coverage_map


def _lookup_coverage(coverage_map: Dict[str, float], file_path: str) -> float:
    """Find coverage for a changed file, tolerating path-prefix differences
    between the diff (repo-relative) and the coverage report."""
    if file_path in coverage_map:
        return coverage_map[file_path]
    # Match by suffix — coverage filenames may be relative to a source root.
    for cov_path, pct in coverage_map.items():
        if cov_path.endswith(file_path) or file_path.endswith(cov_path):
            return pct
        if os.path.basename(cov_path) == os.path.basename(file_path):
            return pct
    return -1.0  # sentinel: not found in report


def compute_coverage_deltas(
    coverage_map: Dict[str, float],
    clinical_modules: List[ChangedModule],
    threshold: float,
) -> Tuple[List[CoverageDelta], bool, float]:
    """
    Returns:
        deltas: coverage info for each clinical file
        any_below_threshold: True if any clinical file is below threshold
        lowest_coverage: the lowest coverage percentage found (100.0 if none)
    """
    deltas: List[CoverageDelta] = []
    any_below = False
    lowest = 100.0

    for module in clinical_modules:
        pct = _lookup_coverage(coverage_map, module.file_path)
        if pct < 0:
            # File not in coverage report — skip but note it could not be measured.
            continue
        deltas.append(
            CoverageDelta(
                file_path=module.file_path,
                coverage_before=pct,   # no historical baseline available; report current
                coverage_after=pct,
                delta=0.0,
                is_clinical=True,
            )
        )
        lowest = min(lowest, pct)
        if pct < threshold:
            any_below = True

    return deltas, any_below, lowest
