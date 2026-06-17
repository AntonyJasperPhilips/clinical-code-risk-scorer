#!/usr/bin/env bash
#
# Create the four demo branches + PRs for the Clinical Risk Scorer.
# Each branch applies a real, concrete code change to a module mapped to a
# different clinical risk weight, so the scorer produces LOW / MEDIUM / HIGH /
# CRITICAL verdicts.
#
# Requirements:
#   - git remote 'origin' pointing at your GitHub repo
#   - gh CLI authenticated (`gh auth status`)
#
# Usage:
#   bash demo_app/scripts/make_demo_prs.sh           # create all four PRs
#   bash demo_app/scripts/make_demo_prs.sh low high  # create a subset
#
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

BASE_BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null || echo main)"

require_clean() {
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "ERROR: working tree not clean. Commit or stash changes first." >&2
    exit 1
  fi
}

open_pr() {
  local title="$1" body="$2"
  if command -v gh >/dev/null 2>&1; then
    gh pr create --base "$BASE_BRANCH" --fill --title "$title" --body "$body" || \
      echo "  (gh pr create failed — branch is pushed; open the PR manually)"
  else
    echo "  gh not found — branch pushed. Open a PR for this branch manually."
  fi
}

new_branch() {
  git checkout "$BASE_BRANCH" >/dev/null 2>&1
  git checkout -B "$1" >/dev/null 2>&1
  echo ">> branch $1"
}

push() {
  git push -u origin "$1" --force-with-lease
}

# ---------------------------------------------------------------- LOW
scenario_low() {
  new_branch demo/low-ui-tweak
  python3 - <<'PY'
import re, pathlib
p = pathlib.Path("demo_app/ui/dashboard.py")
src = p.read_text()
src = src.replace('return "Saving…" if is_saving else "Save"',
                  'return "Saving…" if is_saving else "Save changes"')
p.write_text(src)
css = pathlib.Path("demo_app/styles/theme.css")
c = css.read_text().replace("--primary: #0a7cff;", "--primary: #1a8cff;")
css.write_text(c)
PY
  git commit -am "ui: relabel primary button and brighten theme colour"
  push demo/low-ui-tweak
  open_pr "Tweak dashboard button label and theme colour" \
          "Cosmetic only: relabels the save button and brightens the primary colour. Relates to #3"
}

# ------------------------------------------------------------- MEDIUM
scenario_medium() {
  new_branch demo/medium-api-sort
  python3 - <<'PY'
import pathlib
p = pathlib.Path("demo_app/api/endpoints.py")
src = p.read_text()
addition = '''

def sort_patients(patients: List[dict], *, by: str = "name", reverse: bool = False) -> List[dict]:
    """Return patients sorted by the given field (defaults to name)."""
    return sorted(patients, key=lambda x: x.get(by, ""), reverse=reverse)
'''
p.write_text(src.rstrip() + "\n" + addition)
PY
  git commit -am "api: add sort_patients helper to search endpoint"
  push demo/medium-api-sort
  open_pr "Add sort option to patient search API" \
          "Adds server-side sorting to the patient search endpoint. No clinical logic changed."
}

# --------------------------------------------------------------- HIGH
scenario_high() {
  new_branch demo/high-heart-rate
  # Add a NEW uncovered branch to a weight-3 clinical module (no test added).
  python3 - <<'PY'
import pathlib
p = pathlib.Path("demo_app/vitals/heart_rate.py")
src = p.read_text()
addition = '''

def neonatal_alert(bpm: float) -> bool:
    """Flag a neonatal heart-rate alert (uncovered on purpose for the demo)."""
    if bpm <= 0:
        raise ValueError("bpm must be positive")
    if bpm < 90:
        return True
    if bpm > 180:
        return True
    return False
'''
p.write_text(src.rstrip() + "\n" + addition)
PY
  git commit -am "vitals: add neonatal heart-rate alert bounds"
  push demo/high-heart-rate
  open_pr "Adjust paediatric/neonatal heart-rate thresholds" \
          "Adds neonatal heart-rate alerting. Patient-safety relevant. Relates to #1"
}

# ----------------------------------------------------------- CRITICAL
scenario_critical() {
  new_branch demo/critical-patient-data
  python3 - <<'PY'
import pathlib
p = pathlib.Path("demo_app/patient_data/pipeline.py")
src = p.read_text()
addition = '''

def reencrypt(stored: list, old_key: int, new_key: int) -> list:
    """Re-encrypt previously stored records under a new key.

    Uncovered on purpose so the demo shows a coverage gap on a CRITICAL module.
    """
    from demo_app.patient_data.encryption import decrypt, encrypt
    out = []
    for rec in stored:
        plain = decrypt(rec["payload"], old_key)
        out.append({**rec, "payload": encrypt(plain, new_key)})
    return out
'''
p.write_text(src.rstrip() + "\n" + addition)
PY
  git commit -am "patient_data: add re-encryption migration path"
  push demo/critical-patient-data
  open_pr "Migrate patient records to new encryption scheme" \
          "Re-encrypts stored patient records under a rotated key. Clinical / patient data. Risk + hazard review required. Relates to #2"
}

require_clean

declare -A MAP=(
  [low]=scenario_low [medium]=scenario_medium [high]=scenario_high [critical]=scenario_critical
)

if [ "$#" -eq 0 ]; then
  set -- low medium high critical
fi

for name in "$@"; do
  fn="${MAP[$name]:-}"
  if [ -z "$fn" ]; then
    echo "Unknown scenario: $name (expected: low medium high critical)" >&2
    continue
  fi
  "$fn"
done

git checkout "$BASE_BRANCH" >/dev/null 2>&1
echo "Done. Switched back to $BASE_BRANCH."
