# Task authoring spec (human-authored tasks)

Every portfolio task must satisfy this checklist before it is admitted.
Placeholders live in `tasks/slot_*/`; the fixture in `fixtures/` must never
be presented as a task.

## 1. Realistic instructions
- [ ] Problem statement reads like a real maintenance ticket (observed
      behavior, expected behavior, affected CLI/commands).
- [ ] Requires multi-file reasoning (at least two source files must be read
      to diagnose correctly).
- [ ] States constraints explicitly: files that must not be edited
      (evaluator files), prohibited dependencies, required CLI behavior to
      preserve.
- [ ] Gives verification guidance (how to run relevant checks) without
      revealing the diagnosis.

## 2. Repository snapshot
- [ ] Pinned reference: repo URL + commit + license recorded in
      `manifest.json → repo_snapshot` with provenance.
- [ ] Snapshot builds deterministically from the recorded reference.
- [ ] Starting state reproduces the failure (oracle FAILs before the fix).

## 3. Evidence artifacts (five conditions)
- [ ] `evidence/symptom.md`: observed failure only. No logs, no state, no
      code pointers, no fix hints.
- [ ] `evidence/repro_log.md`: bounded reproduction log. Faithful to what a
      logging harness would emit; must not name the fix.
- [ ] `evidence/state_snapshot.md`: bounded runtime-state snapshot (config
      files, migration markers, partial state). Must not name the fix.
- [ ] `evidence/code_note.md`: short code-path/investigation note of the kind
      a static analyzer or prior investigation could produce. Narrows the
      search region; must not state the fix or the exact edit.
- [ ] Combined condition = all four files. Total tokens ≤
      `max_evidence_tokens`. Record actual token counts per condition; **do
      not pad** shorter conditions.

## 4. Ground truth (evaluator-only, never agent-visible)
- [ ] `evaluator/oracle.py` implements the `GROUP <name> PASS|FAIL` protocol:
      required-behavior groups + `compat:`-prefixed regression groups.
- [ ] Oracle FAILs on the starting snapshot and PASSes on the reference fix.
- [ ] Oracle accepts any behaviorally correct patch, not just the reference
      text (no substring/regex matching of the fix).
- [ ] `evaluator/reference_solution/` holds the human-authored fixed files as
      an overlay (same relative paths as the repo). Used by `audit-task`;
      never staged into agent workspaces or runs.
- [ ] `evaluator/partial_fixes/<name>/` holds at least one plausible-but-
      incomplete fix overlay that must still FAIL the oracle (guards against
      overfit/insensitive oracles).
- [ ] `debev audit-task --task-dir tasks/slot_XX` prints AUDIT PASSED.
- [ ] `rubric_weights.json` assigns functional-group weights (task-specific).
- [ ] Accepted root-cause diagnosis rubric written (20 pts, human-graded);
      allows valid alternative explanations/fixes.

## 5. Constraints and compatibility
- [ ] Constraint checks enumerated (evaluator files untouched, no prohibited
      deps, CLI behavior preserved).
- [ ] Backward-compatibility checks cover existing interfaces the fix must
      not break.

## 6. Provenance and originality
- [ ] Author, date, and source recorded in `manifest.json → provenance`.
- [ ] Task is original and human-authored. Confirm no copying of benchmark
      tasks, prompts, hidden tests, datasets, or answer keys from
      `docs/related_work.md` sources.
- [ ] `debev validate <manifest>` passes with zero errors.

## Suggested domain (one slot)

Deterministic Python CLI maintenance problem, e.g. **safe recovery after an
interrupted configuration migration**: a CLI migrates a config file in steps,
crashes mid-migration, and must resume/repair idempotently without losing
user settings. This exercises multi-file reasoning (CLI layer, migration
logic, state markers) with fully deterministic oracles — no concurrency
mining required.
