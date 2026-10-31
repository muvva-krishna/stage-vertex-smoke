# Scoring rubric (v1.0.0) — 100 points

Component scores are always reported separately **and** as a total.
Efficiency is reported separately and never affects the total.

| Component | Pts | Graded by | Source |
|---|---|---|---|
| Functional correctness | 50 | machine | evaluator test groups for required behavior + invariants |
| Root-cause diagnosis | 20 | **human** | human-authored rubric per task (placeholder until authored) |
| Backward compatibility / regression | 15 | machine | evaluator-only `compat:` checks on existing interfaces |
| Constraint compliance | 10 | machine | task constraints (evaluator files untouched, no prohibited deps, CLI preserved) |
| Verification & reporting accuracy | 5 | mixed | machine (2.5: relevant verification ran) + human (2.5: summary accuracy) |

## How each component is scored

- **Functional correctness (50, machine).** Oracle groups map to required
  behaviors. With per-group weights `w`: `50 × Σw(passed) / Σw(all)`;
  unweighted: `50 × passed / total`. Scored on behavior, never on textual
  similarity to a reference patch. Correctness pass = all functional groups
  PASS (this is also the primary pilot outcome).
- **Root-cause diagnosis (20, human).** Graded after the human authors the
  task rubric. Must allow valid alternative explanations/fixes. Until then
  the harness records `0.0` with `PENDING HUMAN GRADE` — never an invented
  score. Partial-credit example: 14/20 for identifying the faulty migration
  step but misattributing the trigger; 8/20 for the right file but wrong
  mechanism; 0/20 for a patch that passes by accident with a wrong stated
  cause.
- **Compatibility/regression (15, machine).** `compat:` oracle groups over
  existing interfaces. Same proportional rule as functional.
- **Constraint compliance (10, machine).** All-or-nothing over the
  constraint checklist: 10 if every check passes, else 0. Partial-credit
  example: none at the machine level by design (a violated constraint fails
  the cell); the report should still name which check failed.
- **Verification/reporting (5, mixed).** 2.5 machine (a `test_run` or
  `command` event exists in the trajectory) + 2.5 human (final summary
  accurately describes the observed result). Partial-credit example: 2.5/5
  for running the right suite but overstating the result ("all green" when a
  group failed).

## Machine vs human summary

- Machine-graded: functional (50), compatibility (15), constraint (10),
  verification-ran half (2.5 — structured `verification`/`test_run` events
  only; bare commands and the evaluator's oracle run never count).
  Implemented in `src/debev/rubric.py`.
- Human-graded: diagnosis (20), reporting-accuracy half (2.5). Until graded,
  components read `0.0` with a `PENDING HUMAN GRADE` marker — reports render
  this as **"PENDING (not a zero)"**, so an ungraded run is never confused
  with a genuinely zero-scored one.

## Human-grading workflow

```bash
export PYTHONPATH=src
python3 -m debev.cli grade --run-dir results/runs/<id> \
  --diagnosis-pts 14 --reporting-pts 2.0 \
  --grader "Your Name" --rationale "right file, wrong trigger"
```

- `--diagnosis-pts` (0–20) and `--reporting-pts` (0–2.5) are independent;
  omit either to leave it pending. `--grader` is required whenever points
  are set. Machine components are never modified by grading.
- The grade (points + grader + rationale) is persisted in `score.json` and
  mirrored into `run_meta.json → human_grade`; the total is recomputed.
- Grade against the task's accepted-diagnosis rubric after it is authored;
  allow valid alternative explanations/fixes (see partial-credit examples
  above).

## Task-specific placeholders (fill per task)

- `rubric_weights.json → functional`: per-group weights for the 50 pts.
- Accepted-diagnosis rubric: what counts as correct root cause (20 pts).
- `compat:` group list and weights (15 pts).
- Constraint checklist entries (10 pts).
