# Evaluator authoring placeholder (slot_01)

TODO (human author): create `evaluator/oracle.py` following the GROUP protocol
(see `docs/trajectory_schema.md` and the plumbing fixture oracle). Keep this
directory OUT of the agent workspace. Include:
- required-behavior test groups (functional correctness, 50 pts),
- existing-interface checks prefixed `compat:` (15 pts),
- any hidden assertions here — never in `instructions.md` or `evidence/`.

Also TODO: `reference_patch/` (human-authored, evaluator-only) and
`rubric_weights.json` (functional group weights) plus the accepted
root-cause diagnosis rubric (20 pts, human-graded).

## Ground-truth layout (enforced by `debev audit-task`)

- `evaluator/oracle.py` — GROUP-protocol checks (see plumbing fixture oracle).
- `evaluator/reference_solution/` — human-authored fixed files as an overlay
  (same relative paths as the repo). Proves the oracle PASSes a correct fix.
- `evaluator/partial_fixes/<name>/` — at least one plausible-but-incomplete
  fix overlay that must still FAIL (guards against overfit oracles).
- None of the above is ever staged into agent workspaces or runs.
