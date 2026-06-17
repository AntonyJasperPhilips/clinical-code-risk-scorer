# Clinical Code Risk Scorer

A **GitHub Actions-native** service that automatically scores the clinical risk of every
pull request and enforces proportionate quality gates before any code is merged.

Built for medical device software teams working under **IEC 62304**, where changes touching
patient-safety-critical modules must undergo risk-proportionate review — automatically.

## How it works

On every PR (`opened`, `synchronize`, `reopened`) the scorer combines three signals:

1. **Diff** — which files changed, tagged against `config/clinical_modules.json` (glob → clinical domain + risk weight 1–4).
2. **Coverage** — parses `coverage.xml` (pytest-cov) and flags clinical files below the coverage threshold.
3. **Issues** — fetches linked GitHub issues and scans for clinical keywords / labels.

These feed a **GitHub Copilot** scoring engine (temperature 0, JSON-only) that returns a
`LOW | MEDIUM | HIGH | CRITICAL` classification with reasoning and recommended gates. If Copilot
is unavailable, a deterministic **rule-based fallback** takes over.

The result is posted as a PR comment (edited in place on re-runs) and written to a commit
**status check** that blocks or allows merge:

| Risk | Status | Effect |
|---|---|---|
| LOW | `success` | Standard review |
| MEDIUM | `pending` | 1 senior reviewer |
| HIGH | `failure` | 2 reviewers + QA sign-off |
| CRITICAL | `error` | Merge blocked — clinical lead escalation |

## Layout

```
scorer/                          # the scorer service
  diff_analyzer.py               # Signal 1 — PR diff + module tagging
  coverage_analyzer.py           # Signal 2 — coverage delta on clinical paths
  issues_fetcher.py              # Signal 3 — linked GitHub issue context
  copilot_scorer.py              # AI scoring + rule-based fallback
  report_formatter.py            # PR comment (post or update in place)
  status_check.py                # GitHub commit status
  main.py                        # orchestrator / entry point
  models.py                      # dataclasses
config/
  clinical_modules.json          # file-path glob → clinical domain + risk weight
  sme_registry.json              # risk level → approvals, reviewers, teams
tests/                           # unit tests + fixtures for the scorer
demo_app/                        # MediFlow — a runnable demo project (see below)
.github/workflows/clinical-risk-scorer.yml
```

## Configuration

- **`config/clinical_modules.json`** — file-path glob → clinical domain + risk weight. Editable
  without code changes; highest matching weight wins, unmatched files get `default_risk_weight`.
- **`config/sme_registry.json`** — risk level → required approvals, reviewer handles, teams.

## Secrets

| Secret | Notes |
|---|---|
| `GITHUB_TOKEN` | Auto-provided by GitHub Actions. |
| `COPILOT_API_TOKEN` | Org-licensed Copilot token. Without it, the rule-based fallback is used. |

## Local development

```bash
pip install -r requirements.txt
pytest                      # run the unit tests
pytest --cov=scorer         # with coverage
```

The scorer entry point is `python -m scorer.main`, driven entirely by environment variables
(`GITHUB_TOKEN`, `COPILOT_TOKEN`, `REPO`, `PR_NUMBER`, `HEAD_SHA`, `BASE_SHA`, `COVERAGE_THRESHOLD`).

---

## Demo project — MediFlow (`demo_app/`)

`demo_app/` is a small but genuinely functional simulated infusion-pump / patient-monitor stack.
Its module paths are laid out to match every glob pattern in `config/clinical_modules.json`, so PRs
touching different files produce different clinical risk verdicts — ideal for demonstrating the scorer.

### Module → risk-weight map

| Path in `demo_app/`            | Clinical domain      | Weight | Drives level |
|--------------------------------|----------------------|:------:|--------------|
| `dosage_calculator.py`         | Medication Safety    | 4      | CRITICAL     |
| `vitals/alarm_threshold.py`    | Patient Monitoring   | 4      | CRITICAL     |
| `patient_data/**`              | Patient Data         | 4      | CRITICAL     |
| `vitals/heart_rate.py`         | Clinical Measurement | 3      | HIGH         |
| `auth/access_control.py`       | Access Control       | 3      | HIGH         |
| `api/endpoints.py`             | Integration          | 2      | MEDIUM       |
| `ui/dashboard.py`              | User Interface       | 1      | LOW          |
| `styles/theme.css`             | Styling              | 1      | LOW          |

> The test suite intentionally leaves `patient_data/encryption.py` at **~60%** coverage —
> below the 80% threshold — so any PR touching `patient_data/` shows a real clinical coverage gap.

```bash
pytest                          # runs scorer + demo tests (49 passing)
pytest --cov=demo_app           # see the demo coverage profile
```

### Prerequisites for a live demo

1. Push this repo to GitHub.
2. Add the `COPILOT_API_TOKEN` secret (Settings → Secrets → Actions). **Optional** — without it the
   rule-based fallback runs and the comment shows the fallback note (this *is* Scenario E).
3. Make `Clinical Risk Scorer` a **required status check** on the default branch
   (Settings → Branches → branch protection) so HIGH/CRITICAL actually block merge.
4. (Optional) Create the demo issues below and reference them in PR bodies to strengthen Signal 3.

### Fastest path — generate all demo PRs

With `git remote origin` set and `gh` authenticated:

```bash
bash demo_app/scripts/make_demo_prs.sh              # create all four PRs (LOW→CRITICAL)
bash demo_app/scripts/make_demo_prs.sh low high     # or a subset
```

The script creates a branch per scenario, applies a real code change to the relevant module
(HIGH/CRITICAL branches add deliberately untested code to open a coverage gap), pushes, and opens a PR.

### Scenarios

| # | Branch | Files touched | Expected verdict | Status |
|---|--------|---------------|------------------|--------|
| A | `demo/low-ui-tweak` | `ui/dashboard.py`, `styles/theme.css` | LOW, score 1–2 | `success` |
| B | `demo/medium-api-sort` | `api/endpoints.py` | MEDIUM, score 3–5 | `pending` |
| C | `demo/high-heart-rate` | `vitals/heart_rate.py` (untested) | HIGH, score 7–8 | `failure` |
| D | `demo/critical-patient-data` | `patient_data/pipeline.py` | CRITICAL, score 9–10 | `error` |
| E | any of the above with `COPILOT_API_TOKEN` unset | rule-based fallback, same level + ⚠ note | — |

**Manual recipe (Scenario C example):**

```bash
git checkout main && git checkout -b demo/high-heart-rate
# edit demo_app/vitals/heart_rate.py — add a new uncovered branch/function, add NO test
git commit -am "vitals: adjust paediatric heart-rate bounds"
git push -u origin demo/high-heart-rate
gh pr create --fill --title "Adjust paediatric heart-rate thresholds" \
  --body "Updates heart rate alert bounds for paediatric patients. Relates to #1"
```

### Demo issues (optional)

- **#1** — *"Adjust paediatric heart-rate alert thresholds"*, label `clinical` —
  "Paediatric patients need age-adjusted heart-rate bounds. Patient safety / IEC 62304."
- **#2** — *"Migrate patient records to new encryption scheme"*, label `clinical` —
  "Re-encrypt patient data at rest. Risk + hazard review required."
- **#3** — *"Update primary dashboard button colour"* (no clinical label/keywords) — for Scenario A.

### Showing comment-update-in-place

Push a second commit to any open demo PR. The scorer **edits its existing comment** rather than
posting a new one — point this out during the demo.

See [`demo_app/DEMO_GUIDE.md`](demo_app/DEMO_GUIDE.md) for the full walkthrough.

---
*Philips SWE Hackathon 2 — Clinical Code Risk Scorer*
*Team: Antony Jasper (pipeline & signals) · Gaurav Kumar (AI scoring & output)*
