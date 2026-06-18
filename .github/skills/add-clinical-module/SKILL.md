---
name: add-clinical-module
description: 'Register a new clinical module so the Clinical Code Risk Scorer tags and scores it. Use when asked to add/extend a clinical module, map a file path or glob to a clinical domain and risk weight, add a new entry to config/clinical_modules.json, add a matching module under demo_app/, define SME reviewers for a risk level in config/sme_registry.json, or write tests for module tagging. Covers the glob→weight matching rules (highest weight wins, default_risk_weight), the weight→risk-level mapping (1=LOW, 2=MEDIUM, 3=HIGH, 4=CRITICAL), and the test conventions.'
---

# Add a Clinical Module

Extend what the scorer assesses by mapping a file-path glob to a clinical **domain**
and **risk weight**. The scorer's Signal 1 (diff analysis) tags every changed file
against [config/clinical_modules.json](../../../config/clinical_modules.json); the highest
matching weight drives the PR's risk level.

## When to Use

- "Add a new clinical module for `<path>`"
- Map a glob/path to a clinical domain + risk weight.
- Introduce a new SME reviewer set for a risk level.
- Add a runnable module under `demo_app/` that exercises a new mapping.

## Key Rules (read before editing)

- **Matching:** `fnmatch` glob via [scorer/diff_analyzer.py](../../../scorer/diff_analyzer.py) (`tag_file` / `_glob_match`). A `**/` prefix also matches zero leading directories (so `**/vitals/**` matches `vitals/x.py`).
- **Highest weight wins.** A file matching multiple patterns takes the largest `risk_weight`. (e.g. `patient_data/notes.md` matches `**/*.md`=1 and `**/patient_data/**`=4 → 4.)
- **Unmatched files** get `domain="Unclassified"` and the top-level `default_risk_weight` (currently 2); they influence `max_weight` but are not listed as "clinical modules touched".
- **Weight → risk level** (rule-based fallback in [scorer/copilot_scorer.py](../../../scorer/copilot_scorer.py)):

  | risk_weight | level | base score |
  |:-:|---|:-:|
  | 4 | CRITICAL | 9 |
  | 3 | HIGH | 7 |
  | 2 | MEDIUM | 4 |
  | 1 | LOW | 1 |

  A clinical coverage gap escalates one level. Pick the weight by the level you want a touch to produce.

## Procedure

### 1. Add the module entry
Append an object to the `modules` array in [config/clinical_modules.json](../../../config/clinical_modules.json):
```json
{
  "pattern": "**/infusion_pump/**",
  "domain": "Infusion Delivery",
  "risk_weight": 4,
  "description": "Infusion pump rate control — patient safety critical"
}
```
- `pattern` — `fnmatch` glob; prefer `**/<dir>/**` or `**/<name>*` to match regardless of nesting.
- `domain` — human-readable clinical domain (shown in the report).
- `risk_weight` — `1`–`4`, chosen from the weight→level table above.
- `description` — one line of rationale.

> **Ordering doesn't matter** — matching is by highest weight, not list order. Avoid a broad low-weight glob unintentionally being the *only* match for files you intended to score higher; add the specific high-weight pattern too.

### 2. (If introducing a new risk level's reviewers) update the SME registry
Only `LOW/MEDIUM/HIGH/CRITICAL` keys exist in [config/sme_registry.json](../../../config/sme_registry.json). If your weight maps to a level whose reviewers/teams need to change, edit that level's `required_approvals`, `reviewers`, and `teams`. No new keys are needed for a new module — the level is derived from weight.

### 3. (Demo only — optional) Add a runnable module under `demo_app/`
`demo_app/` exists **solely for demonstration** — it is not production code and is not
required when registering a real mapping. Add a module here **only** if you want a PR
that visibly exercises the new mapping in a demo. If so, create a file at a path your
glob matches, e.g. `demo_app/infusion_pump/rate_controller.py`, with a small functional
unit and an `__init__.py` in any new package directory, consistent with neighbouring demo
modules. For a production mapping, skip this step.

### 4. Add tests for the mapping
Follow the conventions in [tests/test_diff_analyzer.py](../../../tests/test_diff_analyzer.py). Use the
`modules_config` fixture from [tests/conftest.py](../../../tests/conftest.py) (it loads the real config):
```python
def test_tag_file_infusion_pump(modules_config):
    domain, weight = tag_file("infusion_pump/rate_controller.py", modules_config)
    assert weight == 4
    assert domain == "Infusion Delivery"
```
Add a "highest weight wins" case if your path can also match a lower-weight glob.
If you added a `demo_app/` module with logic, add unit tests under
[demo_app/tests/](../../../demo_app/tests/) matching that package's style.

### 5. Verify
```bash
pytest tests/test_diff_analyzer.py    # mapping tests
pytest                                # full suite stays green
```
Confirm: the glob matches the intended path, the expected `risk_weight`/`domain`
come back, and "highest weight wins" holds for any overlap.

## Quality Checklist

- [ ] `pattern` matches the intended path (and only what you intend) via `fnmatch`.
- [ ] `risk_weight` (1–4) corresponds to the desired risk level.
- [ ] `domain` and `description` are clear and clinical.
- [ ] Overlapping globs resolve to the correct (highest) weight.
- [ ] Tests added for the new mapping; full `pytest` suite passes.
- [ ] SME registry reviewed if the level's reviewers/teams need to change.

## Common Pitfalls

- **`risk_weight` out of range** — only `1`–`4` map cleanly to levels; anything ≥4 is treated as CRITICAL.
- **Forgetting `__init__.py`** when adding a new `demo_app/` package directory.
- **Editing the config but not adding a test** — mapping regressions go unnoticed.
- **Assuming list order matters** — it doesn't; highest weight always wins.
