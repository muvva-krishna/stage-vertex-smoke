# Accepted root-cause diagnosis — slot_01 (AI-written rubric, evaluator-only)

**Accepted root cause (20/20):** the resume loop records each step as done
*before* its effect is persisted, and the config file is only written at
the very end — so an interruption leaves the marker claiming a step whose
work never reached disk, and the resume skips it. Must name both halves:
(1) premature completion marking, (2) end-only persistence.

**Partial credit:**
- 14/20: identifies the marker/config disagreement and the premature
  marking, but misses that persistence happens only at the end (or vice
  versa).
- 8/20: right files (`migrate.py` loop / `state.py` marker) but wrong
  mechanism (e.g. blames the step functions or the crash hook).
- 0/20: patch passes by luck (e.g. always re-running all steps without
  understanding) with a wrong stated cause.

Valid alternative repairs accepted (e.g. write-ahead redo log, atomic
per-step checkpoint files, revalidating persisted state instead of trusting
the marker) provided the diagnosis explains the observed marker/config
disagreement. Grade the explanation, not the patch shape.
