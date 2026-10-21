# Architecture plan

Small, adapter-friendly harness (stdlib-only Python). No web UI, no training
system, no generic agent framework.

```
task dir (authored)          run (per attempt)               analysis
───────────────────          ─────────────────               ────────
manifest.json ──validate──┐
repo/ ──────────copy──────┼─► runs/<id>/workspace/ (agent) ─► trajectory.jsonl
evidence/*.md ──loader────┘   runs/<id>/evaluator/ (oracle) ─► score.json
evaluator/oracle.py ──────────► oracle runs OUTSIDE workspace   (rubric.py)
instructions.md ──────────► workspace/TASK_INSTRUCTIONS.md  ─► REPORT.md/.json
                               runs/<id>/diff.patch, run_meta.json
```

## Modules (`src/debev/`)

- `manifest.py` — schema v1.0.0 + validation (incl. refusal to store
  reference patches / hidden tests / diagnoses in the manifest).
- `conditions.py` — deterministic 5-condition loader; whitespace-token
  counting; budget enforcement; no padding.
- `runners.py` — `AgentRunner` interface (connect a local/hosted agent
  later without touching evaluation logic), `ReplayRunner` (plumbing-only
  replays, always labeled), `NoopRunner` (default when no agent
  connected); isolated run directories; diff/snapshot helpers.
- `trajectory.py` — observable-event recorder → JSONL; rejects private
  reasoning fields.
- `oracle.py` — `GROUP <name> PASS|FAIL` script protocol, executed with the
  workspace path as argv, living in `evaluator/`.
- `rubric.py` — 100-pt machine portion + explicit human-grade placeholders.
- `report.py` — per task × condition outcomes, trajectory summaries,
  seq-linked failure labels, pilot warnings.
- `config.py` — model/harness/temperature/seed/limits/dependency versions +
  secret-free environment hash.
- `cli.py` — `validate | run | replay | score | report`.

## Data flow guarantees

1. Evaluator files never enter `workspace/` (copy-time separation +
   post-run constraint check).
2. Only the selected condition's artifacts are materialized
   (`workspace/evidence/`), each logged as `evidence_access`.
3. Oracle executes outside the workspace; its groups feed the rubric.
4. Replays are structurally identical runs with `replayed: true` end to end.
