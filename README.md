# Which Debugging Evidence Helps a Coding Agent? — evaluation pilot harness

> **Variant notice (this branch):** the tasks in `tasks/slot_01–03` are
> AI-authored synthetics (see `docs/autonomous_authoring.md`). This is an
> autonomous-pilot variant for pipeline validation — not a completed
> benchmark, and not human-authored ground truth.

A small, reproducible pilot instrument for a focused question: when an agent
repairs a realistic software failure, **which bounded evidence artifacts**
help it diagnose and fix the problem — and when does extra evidence waste
effort or mislead?

This repo is the **harness + rubric + a completed pilot run**, not a benchmark
claim. It contains three AI-authored synthetic tasks, five evidence-packet
conditions, executable ground truth, trajectory capture, and failure analysis.
The packet conditions vary in size as well as content, so this run does not
isolate evidence type. See `docs/related_work.md` for how it connects to
DDBench, TRAIL, SWT-Bench, ConcurBugBench, and coding-agent-bench — and what
was deliberately *not* copied.

## Completed pilot (2026-10-21)

The 60-cell exploratory matrix used three AI-authored tasks, five packet
conditions, two Gemini model IDs, and two repetitions. The stored results
contain 53 completed cells and seven provider failures after retry; those
failures are reported separately, not scored as model outcomes. There are 71
attempt directories because retries are retained.

- **No complete repairs passed the oracle.** Six runs fixed the functional
  behavior on `slot_02` with `gemini-2.5-flash-lite`, but all regressed the
  pinned CLI `--help` interface. They are incomplete repairs, not task passes.
- Four completed attempts crashed the oracle after breaking imports and are
  marked unscored. They are not successes or scored failures.
- The 10-turn cap was reached in 29 of 53 final attempts. The traces do not
  establish that the cap caused the failures.
- Recorded provider spend was **$0.201**. The run used the explicit
  no-global-spend-cap option; per-attempt limits were configured. The seven
  provider errors retain only their exception type, so their underlying cause
  is unknown.
- Human diagnosis and reporting grades remain pending. Tasks and solutions
  were AI-authored, with provenance recorded in `docs/autonomous_authoring.md`.

Read the [full report](results/REPORT_2026-10-21.md),
[analysis](results/ANALYSIS_2026-10-21.md), and
[run ledger](results/matrix_state.json). This is a pipeline-validation pilot,
not evidence that one packet, model tier, or agent protocol is better.

## Setup

Requirements: Python 3.10+ only (no third-party dependencies).

```bash
git clone <this-repo> && cd debugging-evidence-pilot
export PYTHONPATH=src
python3 -m debev.cli validate fixtures/plumbing_fixture/manifest.json
python3 -m unittest discover -s tests -v
```

## Architecture

See `docs/architecture.md`. In one picture: a versioned task manifest, a
deterministic 5-condition evidence loader, an `AgentRunner` interface, an
isolated per-attempt workspace (evaluator files stay outside it), a
`GROUP PASS|FAIL` oracle protocol, a JSONL trajectory recorder (no
chain-of-thought), a 100-point rubric with explicit human-grade
placeholders, and a report generator. Full module map in the architecture
doc.

## Task provenance and future authoring

The current tasks live in `tasks/slot_01|02|03/` and are AI-authored synthetic
tasks; they are not human-authored benchmark material. Their provenance is
documented in `docs/autonomous_authoring.md` and each task's `PROVENANCE.md`.
For future tasks, follow `docs/task_authoring_spec.md`: use realistic
multi-file instructions, pinned repo snapshots, bounded evidence packets,
evaluator-only ground truth (oracle, reference patch, hidden assertions,
accepted diagnosis), constraints, and provenance.

Any future claim of human-authored tasks requires human authorship and review.
`debev validate` rejects manifests that embed answers.

## Running a replay (dry-run plumbing check, no model involved)

```bash
export PYTHONPATH=src
rm -rf /tmp/opencode/debev-demo && mkdir -p /tmp/opencode/debev-demo
cp -r fixtures/plumbing_fixture /tmp/opencode/debev-demo/task
python3 -m debev.cli replay \
  --task-dir /tmp/opencode/debev-demo/task \
  --condition combined \
  --runs-root /tmp/opencode/debev-demo/runs \
  --run-id-prefix demo \
  --replay-file fixtures/replay_example.jsonl
python3 -m debev.cli report \
  --runs-root /tmp/opencode/debev-demo/runs \
  --out /tmp/opencode/debev-demo/REPORT.md
cat /tmp/opencode/debev-demo/REPORT.md
```

Output is labeled `replayed: true` end to end — replayed data is **never**
described as a real model run.

## Connecting an agent

`debev run` takes `--runner`:

| `--runner` | What it is |
|---|---|
| `noop` (default) | no agent; verifies harness plumbing only |
| `baseline` | bundled local-only investigation probe (`agents/fixture_agents.py`): really reads evidence/repo files and really executes import checks, but attempts no repair. For verifying tool-action capture — not a model result |
| `scripted-fix` | fixture-specific scripted repair, plumbing-only; refuses non-fixture tasks |
| `path/to/agent.py:Class` or `module:Class` | your agent: subclass `debev.runners.AgentRunner` (or use the `debev.toolkit.Toolkit` callbacks: `read`/`write`/`exec`/`test`/`verify`, which enforce the workspace boundary and record events) |

```bash
export PYTHONPATH=src
python3 -m debev.cli run --task-dir tasks/slot_01 --condition symptom_only \
  --runs-root results/runs --run-id-prefix s01-sym \
  --runner ./my_agent.py:MyAgent --config configs/default.json
```

Policy decisions belong to the agent; the toolkit only binds tools to the
attempt. Record model name/version, temperature, seed, limits, and
environment hash in a run config (`configs/default.json` is the template).
Agent commands run with a scrubbed environment and bwrap confinement when
available — the recorded `isolation` level states what was actually used.

## Scoring

- `debev score --run-dir results/runs/<id>` prints the stored oracle +
  rubric outcome.
- `debev grade --run-dir … --diagnosis-pts 14 --reporting-pts 2.0 --grader "Name" --rationale "…"`
  persists human grades (diagnosis 0–20, reporting-accuracy 0–2.5; machine
  parts untouched). Ungraded components render as PENDING, never as zero.
- `debev audit-task --task-dir tasks/slot_XX` checks the oracle FAILs the
  broken start, PASSes `evaluator/reference_solution/`, and still FAILs each
  `evaluator/partial_fixes/` probe. Admit no task without AUDIT PASSED.
- `debev export-otel --run-dir … --out trace.json` exports the trajectory as
  OTLP JSON (pinned shape, `debev.*` attributes; GenAI conventions
  deliberately not used — see `docs/trajectory_schema.md`).
- Rubric: 100 pts = 50 functional (machine) + 20 diagnosis (**human**,
  placeholder) + 15 compatibility (machine) + 10 constraints (machine) +
  5 verification/reporting (mixed). See `docs/rubric.md` for partial-credit
  rules. Efficiency is reported separately; the full-oracle pass rate
  (functional + compatibility groups green) is primary. Functional-only
  passes are never called task passes.
- Failure taxonomy: `missed_evidence`, `misread_evidence`,
  `wrong_causal_hypothesis`, `incomplete_repair`, `regression`,
  `constraint_violation`, `inadequate_verification`, `inaccurate_final_report`
  — each linked to trajectory event seqs with observed-vs-interpretation
  separation.

## CLI reference

| Command | Purpose |
|---|---|
| `debev validate <manifest>` | schema + authorship-guardrail check |
| `debev run --task-dir … --condition … [--conditions a,b --repetitions N --seed S] [--runner …] [--replay-from f]` | run attempt(s); randomized order by default |
| `debev replay --task-dir … --replay-file …` | replay fixture events (labeled, not a model run) |
| `debev score --run-dir …` | print stored score |
| `debev grade --run-dir … --diagnosis-pts … --reporting-pts … --grader …` | persist a human grade |
| `debev audit-task --task-dir …` | oracle soundness check (broken FAIL / reference PASS / partials FAIL) |
| `debev plan-matrix --plan … [--write …]` | validate + print the experiment matrix (no agents, no APIs); optional `planned:true` artifact |
| `debev run-matrix --plan … --mode dry-run` | offline: expansion, run IDs/paths, resume simulation, cost preflight. No provider calls, no cost |
| `debev run-matrix --plan … --mode smoke` | one plumbing-only loopback attempt through the real model loop. No provider calls, no cost |
| `debev run-matrix --plan … --mode execute --authorize-spend` | **paid provider calls.** Refuses without the flag, a covering spend cap, passing audits, and set credentials |
| `debev run-matrix --plan … --mode execute --authorize-spend --no-spend-cap` | same, but the user explicitly waives the total cap (per-attempt token/turn/retry caps still bound worst case; spend ledgered per cell) |
| `debev export-otel --run-dir … --out …` | OTLP JSON trace export |
| `debev report --runs-root … --out …` | pilot report (Markdown + JSON sidecar) |

## Experiment design and completed matrix

The completed exploratory matrix was **3 tasks × 5 conditions × 2 Gemini
model IDs × 2 reps = 60 planned cells**. Both models used the same
`ModelAgentRunner` loop and toolkit, but the run does not support a tier
comparison: seven provider failures affected `gemini-2.5-flash`, the sample
has only three AI-authored tasks, and no full repair passed. The 90-attempt
template remains a planning option, not a completed experiment. See
`configs/experiment_plan.template.json` and `docs/model_selection.md` for
the reusable planning and cost-estimation workflow:

```bash
export PYTHONPATH=src
python3 -m debev.cli plan-matrix --plan configs/experiment_plan.template.json
```

Only `run-matrix --mode execute` can incur API cost, and it refuses without
all three: `--authorize-spend`, a `spend_cap` covering the printed worst
case, and credential env vars set (names from the plan; values never enter
the repo, logs, or run metadata). `dry-run` and `smoke` make zero provider
calls. Cost bounds use your per-1k input/output prices × per-attempt token
caps × max turns × (1 + retries); see `docs/model_selection.md`.

## Resource limits (enforced, not just recorded)

- `max_tool_calls` per attempt: hard — further toolkit calls raise
  `ToolBudgetExceeded` after a `limit_exceeded` event is recorded.
- `max_wall_seconds` per attempt: watchdog thread + cooperative toolkit
  checks; `timeout`/`limit_exceeded` events and `runner_orphaned` flag on
  expiry. In-process runners stuck in pure computation cannot be forcibly
  killed (documented boundary — hard kills need an out-of-process runner).
- `per_command_timeout`: hard subprocess timeout; tests map it to
  `INCONCLUSIVE`, never to a pass.
- `run_meta.json → limits` records budgets and whether each was reached.

## What the experiment claims

Conditions differ in size as well as content (`combined` carries more).
The supported claim is **"which realistic evidence packet works best"**,
with packet token counts reported alongside every outcome — not
evidence-type attribution. See `docs/evaluation_protocol.md`.

## Limitations

- Three-task pilot: no population-level conclusions, no significance claims.
- Isolation is bwrap confinement when the host provides a working `bwrap`,
  otherwise filesystem separation only (recorded per run; reports must state
  the recorded level). Use a `bwrap`-capable host or container for untrusted
  agent code.
- Evidence-token counting is a documented whitespace approximation, not a
  model tokenizer.
- Machine verification credit requires an executed `test_run` through the
  toolkit; self-reported `verification` events, bare shell commands, and the
  evaluator's oracle run earn nothing (self-reports are kept for human
  grading of reporting accuracy).
- Offline `dry-run`, `smoke`, and fixture replay make no provider calls. The
  completed pilot did use paid Gemini APIs; its recorded spend and run details
  are in the results above. A future `execute` run can incur cost and is
  guarded by explicit authorization and the configured spend policy.
- DDBench's official code/data URL could not be verified (see
  `docs/related_work.md`); nothing was reused from it.
