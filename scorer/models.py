from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class ChangedModule:
    file_path: str
    domain: str
    risk_weight: int
    lines_added: int
    lines_removed: int


@dataclass
class CoverageDelta:
    file_path: str
    coverage_before: float        # percentage 0–100
    coverage_after: float         # percentage 0–100
    delta: float                  # coverage_after - coverage_before
    is_clinical: bool             # True if file is in a clinical module


@dataclass
class LinkedIssue:
    issue_number: int
    title: str
    labels: List[str]
    clinical_keywords_found: List[str]


@dataclass
class RiskSignal:
    # Signal 1: diff
    changed_files: List[str]
    clinical_modules_touched: List[ChangedModule]
    max_module_risk_weight: int

    # Signal 2: coverage
    coverage_deltas: List[CoverageDelta]
    clinical_coverage_below_threshold: bool
    lowest_clinical_coverage: float

    # Signal 3: issues
    linked_issues: List[LinkedIssue]
    clinical_intent_confirmed: bool


@dataclass
class RiskScore:
    level: RiskLevel
    score: int                    # 1–10 numeric score
    reasoning: str                # AI-generated rationale
    contributing_factors: List[str]
    recommended_gates: List[str]
    assigned_reviewers: List[str] = field(default_factory=list)
    assigned_teams: List[str] = field(default_factory=list)
    fallback_used: bool = False   # True if rule-based fallback produced this score


@dataclass
class RiskReport:
    pr_number: int
    repo: str
    sha: str
    signal: RiskSignal
    score: RiskScore
    coverage_threshold: float = 80.0
