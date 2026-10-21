# Live provider smoke — 2026-10-21 (plumbing-only, NOT a benchmark result)

Target: `tasks/slot_01` (audited draft task), symptom_only.
Model: `gemini-2.5-flash` (publisher alias, frozen 2026-10-21) via Vertex AI
ADC, project `gen-lang-client-0430700811`, location `global`.
Command:
`debev run-matrix --plan configs/plan.vertex.60.json --mode smoke --live
--smoke-task tasks/slot_01 --runs-root <tmp> --state <tmp>`
(smoke cap gate: 1-cell worst $0.074 ≤ $1.00 smoke cap)

## What was verified (provider integration: YES)

- ADC mint → generateContent → parsed JSON actions → toolkit dispatch.
- Provider usage reporting (`usageMetadata` → input/output tokens in
  `run_meta.json → provider_usage`).
- Sandboxed execution (`bwrap-sandbox` on every command), workspace-only
  writes, evaluator isolation, oracle scoring, spend/cap gates.
- Three earlier live attempts surfaced real harness gaps, all fixed and
  tested: evidence paths now `evidence/<file>`; file-action OSErrors are
  graceful rejections (not runner crashes); provider usage survives the
  error path; model replies are recorded (`model_reply` events).

## Model behavior (agent performance: NO conclusion — smoke only)

- Attempt 1: read wrong path (`symptom.md` unprefixed) → crashed runner
  (pre-fix behavior).
- Attempt 2: looped `ls -F`, never edited/tested in 5 turns.
- Attempt 3: transient provider error on turn 3 (provider healthy on
  direct retest) — validates the matrix retry design.
- Attempt 4 (8 turns): read the real repo files, correctly diagnosed the
  marker-before-work bug in its note — then rewrote `migrate.py` against
  an imagined API (`MigrationState`, `--init`), verified nothing with a
  `test` op, and finished with confabulated details. Oracle: FAIL (all
  functional groups), total 37.5. Smoke criteria (genuine read + edit +
  executed test) NOT met.

## Actual cost

Attempt 4: 17,975 in / 2,368 out ≈ $0.0057. All live attempts combined
≈ $0.017 (≈2¢). No matrix cells run. Matrix (60 attempts, worst ≈ $6.75)
remains blocked on an explicit user spend cap above the worst case plus
`--authorize-spend`.

## Validity notes

- Tasks are AI-authored synthetics (see `docs/autonomous_authoring.md`);
  this smoke says nothing about real-world repair ability.
- Prompt affordances were improved during smoke (grounded file listing,
  workflow/grounding rules, turn budget hints). Further prompt tuning
  risks overfitting to one model and was stopped here.
- Raw trajectories retained under /tmp for this session; rerun the smoke
  command to reproduce (costs a few cents).
