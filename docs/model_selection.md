# Model selection (placeholders — human decision, no recommendations here)

Fill `configs/experiment_plan.template.json → models` before any paid calls.
Do not hard-code provider names or model picks in the harness.

## Checklist

- [ ] Choose **one stronger coding model** (TIER_A) and **one smaller/cheaper
      or local model** (TIER_B). Two tiers run through the *same* agent
      harness and tool interface, so the model — not the harness — is the
      variable.
- [ ] Freeze **exact model IDs and versions** (snapshot dates, build hashes)
      in the plan. A bare family name ("GPT-X", "Claude-X") is not a version.
- [ ] Set per-model temperature and generation settings explicitly
      (deterministic settings preferred; record whatever is used).
- [ ] Estimate cost from **user-supplied prices only**: fill
      `plan.budgeting.prices` (`input_per_1k`, `output_per_1k`, `currency`,
      `source: "user-supplied"`) plus separate
      `assumed_max_input_tokens_per_attempt` /
      `assumed_max_output_tokens_per_attempt`, `max_model_turns_per_attempt`,
      and `max_retries_per_cell`, then run `debev plan-matrix --plan …` for
      the worst-case bound (caps × turns × (1 + retries) × cells). Never
      guess current prices. Run the full matrix only when the estimate is
      accepted.
- [ ] Set an explicit `spend_cap` (`currency` + `amount`) at or above the
      worst case. Execution refuses to start below it and stops before
      exceeding it. Credentials go in the named environment variables only —
      never in the plan, repo, logs, or metadata.
- [ ] Lower-cost option: 3 tasks × 5 conditions × 2 models × **2 reps = 60
      attempts** (docs: fewer repetitions increase uncertainty). Full plan:
      3 × 5 × 2 × **3 = 90 attempts**.
- [ ] If only one model is available, say so in every report and limit
      conclusions to that model. Do not compare harnesses and attribute the
      difference to models.

## Blind grading

Human grading of diagnosis/report summaries should hide model and condition
where practical (grade from the trajectory summary + final diff + agent
notes with identifiers stripped). Record the grader, the blinding used,
and any unblinded exceptions in the grade rationale.
