# Clinical Risk Scorer — Demo Guide

This guide walks you through demonstrating the scorer end-to-end using the
**MediFlow** simulator in `demo_app/`. Each scenario is a branch + PR that
touches files mapped to different clinical risk weights in
`config/clinical_modules.json`, so the scorer produces a different verdict.

## Module → risk-weight map (for reference)

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

> The current test suite leaves `patient_data/encryption.py` at **~60%** coverage —
> below the 80% threshold — so any PR touching `patient_data/` shows a real coverage gap.

---

## Prerequisites

1. Push this repo to GitHub.
2. Add the `COPILOT_API_TOKEN` secret (Settings → Secrets → Actions). **Optional** —
   without it the rule-based fallback runs and the comment shows the fallback note
   (this *is* Scenario E).
3. Make `Clinical Risk Scorer` a **required status check** on the default branch
   (Settings → Branches → branch protection) so HIGH/CRITICAL actually block merge.
4. (Optional) Create demo issues — see "Demo issues" below — and reference them in PR bodies.

The fastest path: run `bash demo_app/scripts/make_demo_prs.sh` (needs `gh` authenticated).
Or create each branch manually using the recipes below.

---

## Scenario A — LOW (auto-pass) 🟢

Touch only presentation files.

```bash
git checkout main && git checkout -b demo/low-ui-tweak
# edit demo_app/ui/dashboard.py and demo_app/styles/theme.css (e.g. change button label / colour)
git commit -am "UI: tweak primary button label and theme colour"
git push -u origin demo/low-ui-tweak
gh pr create --fill --title "Tweak dashboard button + theme colour"
```
**Expected:** LOW, score 1–2, status `success`, standard 1-approval gate.

## Scenario B — MEDIUM 🟡

Touch the API layer only.

```bash
git checkout main && git checkout -b demo/medium-api-pagination
# edit demo_app/api/endpoints.py (e.g. add a sort param to search_patients)
git commit -am "api: add sort option to patient search"
git push -u origin demo/medium-api-pagination
gh pr create --fill --title "Add sort to patient search API"
```
**Expected:** MEDIUM, score 3–5, status `pending`, 1 senior reviewer.

## Scenario C — HIGH (primary demo) 🔴

Change clinical calculation logic **and** leave it under-tested.

```bash
git checkout main && git checkout -b demo/high-heart-rate
# edit demo_app/vitals/heart_rate.py — add a new uncovered branch/function
# do NOT add tests for the new code, so coverage on this clinical path drops
git commit -am "vitals: adjust paediatric heart-rate bounds"
git push -u origin demo/high-heart-rate
gh pr create --fill --title "Adjust paediatric heart-rate thresholds" \
  --body "Updates heart rate alert bounds for paediatric patients. Relates to #1"
```
**Expected:** HIGH, score 7–8, status `failure`, 2 reviewers + QA sign-off + coverage gate.

## Scenario D — CRITICAL (merge blocked) 🚨

Touch the patient-data pipeline (weight 4) — encryption.py already sits below the
coverage threshold.

```bash
git checkout main && git checkout -b demo/critical-patient-data
# edit demo_app/patient_data/pipeline.py and/or encryption.py
git commit -am "patient_data: migrate records to new encryption scheme"
git push -u origin demo/critical-patient-data
gh pr create --fill --title "Migrate patient records to new encryption scheme" \
  --body "Re-encrypts stored patient records. Clinical change. Relates to #2"
```
**Expected:** CRITICAL, score 9–10, status `error`, merge blocked — clinical lead escalation.

## Scenario E — Copilot unavailable (fallback) ⚠

Run **any** of the above with `COPILOT_API_TOKEN` unset (or invalid). The scorer
still produces a correct level via the rule-based fallback, and the PR comment
includes: *"⚠ AI scorer unavailable — rule-based fallback used"*.

To re-run a PR after toggling the secret, push an empty commit:
```bash
git commit --allow-empty -m "retrigger scorer" && git push
```

---

## Demo issues (optional, strengthens Signal 3)

Create these so PR bodies can link real clinical context:

- **#1** — *"Adjust paediatric heart-rate alert thresholds"*, label `clinical`
  Body: "Paediatric patients need age-adjusted heart-rate bounds. Patient safety / IEC 62304."
- **#2** — *"Migrate patient records to new encryption scheme"*, label `clinical`
  Body: "Re-encrypt patient data at rest. Risk + hazard review required."
- **#3** — *"Update primary dashboard button colour"* (no clinical label/keywords) — for Scenario A.

---

## Showing comment-update-in-place

Push a second commit to any open demo PR. The scorer **edits its existing comment**
rather than posting a new one — point this out during the demo.
