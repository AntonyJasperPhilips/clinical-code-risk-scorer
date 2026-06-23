"""Component 5 — AI risk scoring via the GitHub Copilot API, with a
deterministic rule-based fallback."""

import json
from typing import List

import requests

from scorer.models import RiskLevel, RiskScore, RiskSignal

COPILOT_ENDPOINT = "https://api.githubcopilot.com/chat/completions"
COPILOT_MODEL = "gpt-4o"

SYSTEM_PROMPT = """You are a clinical software risk classifier for a medical device company operating
under IEC 62304. Your job is to classify the clinical risk of a pull request based
on three signals: the code diff (which clinical modules changed), test coverage
gaps on clinical code, and the linked GitHub issue context.

Respond ONLY with a valid JSON object. No preamble, no markdown, no explanation
outside the JSON.

RISK LEVELS:
- LOW: No clinical modules touched. UI, docs, styling, or non-patient-facing changes.
- MEDIUM: Peripheral clinical modules touched. API changes, config, non-critical logic.
- HIGH: Core clinical modules touched (dosage, vitals, alarms, auth). Coverage may be insufficient.
- CRITICAL: Patient-critical safety systems touched (dosage pipeline, safety interlocks,
  patient data). Any change here blocks merge until escalated to clinical lead.

EXAMPLES:

Input:
{
  "clinical_modules_touched": ["vitals/heart_rate_calculator.py"],
  "max_risk_weight": 3,
  "coverage_below_threshold": true,
  "lowest_clinical_coverage": 58.0,
  "clinical_intent_confirmed": true,
  "linked_issue_titles": ["Update heart rate alert threshold for paediatric patients"]
}
Output:
{
  "risk_level": "HIGH",
  "score": 8,
  "reasoning": "Changes to heart rate calculation logic in a paediatric context are patient-safety relevant. Combined with 58% test coverage on modified clinical paths, this PR requires 2 reviewers and QA sign-off before merge.",
  "contributing_factors": [
    "Clinical module touched: vitals/heart_rate_calculator.py (risk weight 3)",
    "Test coverage on changed clinical path is 58% — below 80% threshold",
    "Linked issue confirms clinical intent: paediatric alarm threshold change"
  ],
  "recommended_gates": [
    "2 reviewer approvals required",
    "QA sign-off required",
    "Coverage must reach 80% before merge"
  ]
}

Input:
{
  "clinical_modules_touched": [],
  "max_risk_weight": 1,
  "coverage_below_threshold": false,
  "lowest_clinical_coverage": 100.0,
  "clinical_intent_confirmed": false,
  "linked_issue_titles": ["Fix typo in patient dashboard label"]
}
Output:
{
  "risk_level": "LOW",
  "score": 1,
  "reasoning": "No clinical modules are touched. The change is limited to a UI label fix with no patient-safety implications.",
  "contributing_factors": [
    "No clinical modules touched",
    "No coverage gap on clinical paths",
    "Linked issue is non-clinical: UI label fix"
  ],
  "recommended_gates": [
    "Standard review — 1 approval required"
  ]
}"""


def build_scoring_payload(signal: RiskSignal) -> dict:
    return {
        "clinical_modules_touched": [
            f"{m.file_path} (domain: {m.domain}, risk_weight: {m.risk_weight})"
            for m in signal.clinical_modules_touched
        ],
        "max_risk_weight": signal.max_module_risk_weight,
        "coverage_below_threshold": signal.clinical_coverage_below_threshold,
        "lowest_clinical_coverage": signal.lowest_clinical_coverage,
        "clinical_intent_confirmed": signal.clinical_intent_confirmed,
        "linked_issue_titles": [i.title for i in signal.linked_issues],
        "clinical_keywords_found": [
            kw for i in signal.linked_issues for kw in i.clinical_keywords_found
        ],
    }


def _sme_for_level(level: RiskLevel, sme_config: dict):
    assignment = sme_config.get("sme_assignments", {}).get(level.value, {})
    return assignment.get("reviewers", []), assignment.get("teams", [])


def _validate_and_build(content: str, level_default: RiskLevel) -> dict:
    """Parse the model's JSON content and validate required fields.

    Raises ValueError on malformed output.
    """
    data = json.loads(content)
    required = ["risk_level", "score", "reasoning", "contributing_factors", "recommended_gates"]
    for key in required:
        if key not in data:
            raise ValueError(f"Copilot response missing required key: {key}")
    if data["risk_level"] not in {l.value for l in RiskLevel}:
        raise ValueError(f"Invalid risk_level: {data['risk_level']}")
    return data


def call_copilot_scorer(
    copilot_token: str,
    signal: RiskSignal,
    sme_config: dict,
) -> RiskScore:
    """
    Calls the Copilot API and returns a RiskScore dataclass.
    Falls back to rule-based scoring if the API call fails or the token is missing.
    Retries once on invalid JSON before falling back.
    """
    if not copilot_token:
        print("[copilot_scorer] No Copilot token provided — using rule-based fallback.")
        return rule_based_fallback(signal, sme_config)

    payload = build_scoring_payload(signal)
    body = {
        "model": COPILOT_MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload)},
        ],
    }
    headers = {
        "Authorization": f"Bearer {copilot_token}",
        "Content-Type": "application/json",
        # The Copilot backend rejects requests without an integration id (400).
        "Copilot-Integration-Id": "vscode-chat",
        "Editor-Version": "vscode/1.90.0",
        "Editor-Plugin-Version": "copilot-chat/0.16.0",
    }

    last_error = None
    for attempt in range(2):
        try:
            resp = requests.post(COPILOT_ENDPOINT, headers=headers, json=body, timeout=60)
            if resp.status_code >= 400:
                # Surface the API error body — vital for diagnosing 400/403 from the gateway.
                print(
                    f"[copilot_scorer] HTTP {resp.status_code} from Copilot: {resp.text[:300]}"
                )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            data = _validate_and_build(content, RiskLevel.MEDIUM)
            level = RiskLevel(data["risk_level"])
            reviewers, teams = _sme_for_level(level, sme_config)
            return RiskScore(
                level=level,
                score=int(data["score"]),
                reasoning=data["reasoning"],
                contributing_factors=list(data["contributing_factors"]),
                recommended_gates=list(data["recommended_gates"]),
                assigned_reviewers=reviewers,
                assigned_teams=teams,
                fallback_used=False,
            )
        except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            print(f"[copilot_scorer] attempt {attempt + 1} failed: {exc}")

    print(f"[copilot_scorer] Copilot unavailable ({last_error}) — using rule-based fallback.")
    return rule_based_fallback(signal, sme_config)


def rule_based_fallback(signal: RiskSignal, sme_config: dict) -> RiskScore:
    """
    Deterministic fallback scorer used when Copilot API is unavailable.
    Uses max_risk_weight + coverage threshold to determine level.
        Weight 4 (or critical coverage gap) -> CRITICAL
        Weight 3 (or coverage < threshold)   -> HIGH
        Weight 2                             -> MEDIUM
        Weight 1                             -> LOW
    """
    weight = signal.max_module_risk_weight
    below = signal.clinical_coverage_below_threshold
    lowest = signal.lowest_clinical_coverage

    if weight >= 4:
        level, score = RiskLevel.CRITICAL, 9
    elif weight == 3:
        level, score = RiskLevel.HIGH, 7
    elif weight == 2:
        level, score = RiskLevel.MEDIUM, 4
    else:
        level, score = RiskLevel.LOW, 1

    # Escalate one level if there is a clinical coverage gap.
    if below:
        if level == RiskLevel.MEDIUM:
            level, score = RiskLevel.HIGH, 7
        elif level == RiskLevel.HIGH:
            score = 8
        elif level == RiskLevel.CRITICAL:
            score = 10

    factors: List[str] = []
    if signal.clinical_modules_touched:
        for m in signal.clinical_modules_touched:
            factors.append(
                f"Clinical module touched: {m.file_path} "
                f"(domain {m.domain}, risk weight {m.risk_weight})"
            )
    else:
        factors.append("No clinical modules touched")

    if below:
        factors.append(
            f"Test coverage on a changed clinical path is {lowest:.0f}% — below threshold"
        )
    elif signal.coverage_deltas:
        factors.append(f"Clinical coverage OK (lowest {lowest:.0f}%)")

    if signal.clinical_intent_confirmed:
        factors.append("Linked issue confirms clinical intent")

    gates_by_level = {
        RiskLevel.LOW: ["Standard review — 1 approval required"],
        RiskLevel.MEDIUM: ["1 senior reviewer approval required"],
        RiskLevel.HIGH: [
            "2 reviewer approvals required",
            "QA sign-off required",
            "Coverage must reach threshold before merge",
        ],
        RiskLevel.CRITICAL: [
            "Merge blocked — clinical lead escalation required",
            "3 reviewer approvals required",
            "QA + patient-safety sign-off required",
        ],
    }

    reviewers, teams = _sme_for_level(level, sme_config)
    return RiskScore(
        level=level,
        score=score,
        reasoning=(
            f"Rule-based fallback assessment: highest clinical risk weight among "
            f"changed files is {weight}"
            + (", with a clinical coverage gap" if below else "")
            + f". Classified as {level.value}."
        ),
        contributing_factors=factors,
        recommended_gates=gates_by_level[level],
        assigned_reviewers=reviewers,
        assigned_teams=teams,
        fallback_used=True,
    )
