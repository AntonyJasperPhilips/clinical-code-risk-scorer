"""Component 8 — orchestrator / entry point."""

import json
import os
import sys

from scorer.coverage_analyzer import compute_coverage_deltas, parse_coverage_xml
from scorer.copilot_scorer import call_copilot_scorer
from scorer.diff_analyzer import analyze_diff, load_clinical_modules
from scorer.issues_fetcher import fetch_linked_issues
from scorer.labeler import sync_risk_label
from scorer.models import RiskReport, RiskSignal
from scorer.report_formatter import format_report, post_or_update_comment
from scorer.reviewer_assigner import request_reviewers
from scorer.status_check import set_failure_status, set_status_check


def main():
    # 1. Load env vars
    token = os.environ["GITHUB_TOKEN"]
    copilot_token = os.environ.get("COPILOT_TOKEN", "")
    repo = os.environ["REPO"]
    pr_number = int(os.environ["PR_NUMBER"])
    head_sha = os.environ["HEAD_SHA"]
    base_sha = os.environ["BASE_SHA"]
    threshold = float(os.environ.get("COVERAGE_THRESHOLD", "80.0"))

    pr_url = f"https://github.com/{repo}/pull/{pr_number}"

    try:
        # 2. Load config
        modules_config = load_clinical_modules("config/clinical_modules.json")
        with open("config/sme_registry.json") as f:
            sme_config = json.load(f)

        # 3. Signal 1 — diff analysis
        changed_files, clinical_modules, max_weight = analyze_diff(
            token, repo, base_sha, head_sha, modules_config
        )

        # 4. Signal 2 — coverage delta
        coverage_map = parse_coverage_xml("coverage.xml")
        deltas, below_threshold, lowest_cov = compute_coverage_deltas(
            coverage_map, clinical_modules, threshold
        )

        # 5. Signal 3 — GitHub Issues
        linked_issues, clinical_intent = fetch_linked_issues(token, repo, pr_number)

        # 6. Assemble signal
        signal = RiskSignal(
            changed_files=changed_files,
            clinical_modules_touched=clinical_modules,
            max_module_risk_weight=max_weight,
            coverage_deltas=deltas,
            clinical_coverage_below_threshold=below_threshold,
            lowest_clinical_coverage=lowest_cov,
            linked_issues=linked_issues,
            clinical_intent_confirmed=clinical_intent,
        )

        # 7. AI scoring (falls back to rule-based internally)
        risk_score = call_copilot_scorer(copilot_token, signal, sme_config)

        # 8. Assemble report
        report = RiskReport(
            pr_number=pr_number,
            repo=repo,
            sha=head_sha,
            signal=signal,
            score=risk_score,
            coverage_threshold=threshold,
        )

        # 9. Post PR comment
        comment_body = format_report(report)
        post_or_update_comment(token, repo, pr_number, comment_body)

        # 10. Set commit status check
        set_status_check(token, repo, head_sha, risk_score.level, pr_url)

        # 11. Tag the PR with a clinical-risk label for HIGH/CRITICAL verdicts
        sync_risk_label(token, repo, pr_number, risk_score.level)

        # 12. Request reviewers/teams proportionate to the risk level (best-effort)
        request_reviewers(token, repo, pr_number, risk_score)

        print(f"Risk assessment complete: {risk_score.level.value} (score {risk_score.score}/10)")

    except FileNotFoundError:
        # Required config missing — this is a hard failure.
        raise
    except Exception as exc:  # noqa: BLE001 — top-level guard
        print(f"[main] Scorer failed: {exc}", file=sys.stderr)
        try:
            set_failure_status(token, repo, head_sha, pr_url)
        except Exception as status_exc:  # noqa: BLE001
            print(f"[main] Could not set failure status: {status_exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
