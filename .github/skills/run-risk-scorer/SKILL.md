---
name: run-risk-scorer
description: 'Run the Clinical Code Risk Scorer against a pull request or diff to produce a LOW/MEDIUM/HIGH/CRITICAL clinical risk verdict. Use when asked to score a PR, assess clinical risk of changes, reproduce the scorer locally, debug the scorer output/status check/PR comment, or generate coverage.xml for scoring. Covers required env vars (GITHUB_TOKEN, COPILOT_TOKEN, REPO, PR_NUMBER, HEAD_SHA, BASE_SHA, COVERAGE_THRESHOLD), the three signals (diff, coverage, issues), and interpreting the result.'
---

# Run the Clinical Code Risk Scorer

Reproduce and interpret the risk assessment that the `Clinical Risk Scorer` GitHub
Action produces for a pull request. The entry point is `python -m scorer.main`, driven
entirely by environment variables.

## When to Use

- "Score this PR" / "what's the clinical risk of these changes?"
- Reproduce the CI scorer locally against a specific PR or base/head SHA.
- Debug a wrong verdict, a missing PR comment, or an unexpected commit status check.
- Generate the `coverage.xml` the scorer needs.

## How It Works (3 signals → 1 verdict)

1. **Diff** — changed files tagged against [config/clinical_modules.json](../../../config/clinical_modules.json) (glob → clinical domain + risk weight 1–4; highest match wins).
2. **Coverage** — parses `coverage.xml` (pytest-cov) and flags clinical files below `COVERAGE_THRESHOLD`.
3. **Issues** — fetches linked GitHub issues and scans for clinical keywords/labels.

These feed the Copilot scoring engine (temperature 0, JSON-only). If `COPILOT_TOKEN`
is absent or the call fails, a deterministic **rule-based fallback** runs instead.
Output is posted as a PR comment (edited in place on re-runs) and written to a commit
status check.

| Risk | Status | Effect |
|---|---|---|
| LOW | `success` | Standard review |
| MEDIUM | `pending` | 1 senior reviewer |
| HIGH | `failure` | 2 reviewers + QA sign-off |
| CRITICAL | `error` | Merge blocked |

## Procedure

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Generate coverage.xml
The scorer reads `coverage.xml` from the repo root. Match the CI command:
```bash
pytest --cov=. --cov-report=xml:coverage.xml || true
```
> A missing or empty `coverage.xml` means Signal 2 cannot flag coverage gaps — generate it first.

### 3. Identify the PR's base and head SHAs
```bash
gh pr view <PR_NUMBER> --json number,headRefOid,baseRefOid,headRepository
# or, for a local diff:
git rev-parse origin/main   # BASE_SHA
git rev-parse HEAD          # HEAD_SHA
```

### 4. Set environment variables and run
```bash
export GITHUB_TOKEN=...        # repo-scoped token; needed for diff, issues, comment, status
export COPILOT_TOKEN=...        # optional — omit to exercise the rule-based fallback
export REPO=owner/repo
export PR_NUMBER=123
export HEAD_SHA=<head sha>
export BASE_SHA=<base sha>
export COVERAGE_THRESHOLD=80    # optional, defaults to 80.0

python -m scorer.main
```
Success prints: `Risk assessment complete: <LEVEL> (score <n>/10)`.

> **Side effects:** a successful run posts/updates a PR comment and writes a commit
> status check on `HEAD_SHA`. To inspect logic without touching the live PR, use a test
> PR number or read the orchestration in [scorer/main.py](../../../scorer/main.py) and call the
> component functions directly.

### 5. Interpret the result
- The PR comment and `print` line carry the level, score, reasoning, and recommended gates.
- The level maps to the status check in the table above.
- Required config: [config/clinical_modules.json](../../../config/clinical_modules.json) and [config/sme_registry.json](../../../config/sme_registry.json) — a `FileNotFoundError` here is a hard failure (not caught).

## Component Map (for debugging)

| Concern | File |
|---|---|
| Orchestration / env vars | [scorer/main.py](../../../scorer/main.py) |
| Signal 1 — diff + module tagging | [scorer/diff_analyzer.py](../../../scorer/diff_analyzer.py) |
| Signal 2 — coverage delta | [scorer/coverage_analyzer.py](../../../scorer/coverage_analyzer.py) |
| Signal 3 — linked issues | [scorer/issues_fetcher.py](../../../scorer/issues_fetcher.py) |
| AI scoring + fallback | [scorer/copilot_scorer.py](../../../scorer/copilot_scorer.py) |
| PR comment (post/update) | [scorer/report_formatter.py](../../../scorer/report_formatter.py) |
| Commit status check | [scorer/status_check.py](../../../scorer/status_check.py) |
| Dataclasses | [scorer/models.py](../../../scorer/models.py) |
| CI workflow | [.github/workflows/clinical-risk-scorer.yml](../../../.github/workflows/clinical-risk-scorer.yml) |

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `KeyError: 'GITHUB_TOKEN'` (or REPO/PR_NUMBER/HEAD_SHA/BASE_SHA) | A required env var is unset — all of these are mandatory. |
| Verdict ignores coverage | `coverage.xml` missing/stale — re-run step 2. |
| Comment shows "fallback" note | `COPILOT_TOKEN` absent or Copilot call failed — rule-based path ran (this is expected without the token). |
| `FileNotFoundError` | A `config/*.json` file is missing — hard failure, fix the config path. |
| Verdict lower/higher than expected | Check the glob→weight mapping in [config/clinical_modules.json](../../../config/clinical_modules.json); highest matching weight wins, unmatched files get `default_risk_weight`. |
| Process exits 1 with `[main] Scorer failed:` | A non-config exception occurred; a failure status is set on `HEAD_SHA`. Read stderr for the cause. |

## Demo Shortcut

To produce real LOW→CRITICAL PRs against the bundled `demo_app/` (MediFlow):
```bash
bash demo_app/scripts/make_demo_prs.sh           # all four PRs
bash demo_app/scripts/make_demo_prs.sh low high  # a subset
```
Requires `git remote origin` set and `gh` authenticated.
