# Evaluation protocol

## Matched conditions

The same task, repository snapshot, agent instructions, model, tool access,
and resource limits are used across all five conditions. **Only the evidence
packet changes** (see `src/debev/conditions.py`):

1. `symptom_only` — `symptom.md` only.
2. `repro_log` — symptom + reproduction log.
3. `state_snapshot` — symptom + state snapshot.
4. `code_note` — symptom + code-path/investigation note.
5. `combined` — symptom + all three evidence artifacts.

## Matrix execution (frozen plan → resumable runs)

- `run-matrix --mode dry-run`: expands the matrix, assigns deterministic
  run IDs/paths, simulates resume against existing state, prints the cost
  preflight. Zero provider calls.
- `run-matrix --mode smoke`: audits the plumbing fixture, runs one
  plumbing-only attempt through the real `ModelAgentRunner` loop with a
  labeled loopback transport, and verifies toolkit mediation
  (reads/writes/tests observed, fixture labeling present). Zero provider
  calls; output is never a model result.
- `run-matrix --mode execute --authorize-spend`: runs each planned cell
  once (plus bounded retries on transient provider failures only), skipping
  cells already `done` in `results/matrix_state.json`. Fail-closed
  preflight: invalid manifests, failing audits, missing credentials,
  missing/uncovering spend cap, or a changed plan hash all abort before any
  paid call. Spend is ledgered per model from provider-reported usage;
  execution stops before the cap would be exceeded. Both tiers use the same
  `ModelAgentRunner` loop and toolkit — model settings are frozen per plan
  cell and substitution is refused.
- Aggregation (`report`) groups by task × condition × model; human
  diagnosis/reporting fields stay PENDING unless graded with `debev grade`.
  Never invent human grades or present unlabelled model grades as ground
  truth.

## What the design can and cannot claim

Conditions differ in **size as well as content**: `combined` carries roughly
the sum of the single-artifact packets. A shared maximum budget plus recorded
actual token counts keeps the comparison honest, but it does **not** isolate
evidence *type* from evidence *amount*. The supported claim is therefore:

> **"Which realistic evidence packet works best"** — with packet size
> (`evidence_tokens`, per artifact and per condition) reported alongside
> every outcome.

Do not attribute a `combined`-vs-single difference to a specific evidence
type. If type-level attribution is wanted later, author a length-matched
control (e.g. symptom + a size-matched distractor note with no diagnostic
value) and pre-register it as an explicit sixth condition — do not
retro-fit it onto this five-condition pilot.

## Evidence budget

- One `max_evidence_tokens` value applies to every condition of a task.
- The condition loader records the **actual** token count per artifact and
  per condition (`token_counts`, `evidence_tokens` in `run_meta.json`).
- Conditions exceeding the budget fail at load time (task-authoring error).
- Shorter conditions are **never padded**.

## Run order, repetition, limits

- `--repetitions N` repeats every task × condition cell N times.
- Order is randomized with `--seed S` (default seed 0); use `--no-randomize`
  only for debugging and record the choice.
- Resource limits (`max_tool_calls`, `max_wall_seconds`,
  `max_evidence_tokens`) come from the manifest; model/harness/temperature/
  seed from the run config. Every run stores its config + environment hash
  in `run_meta.json`.
- Agent tool access is fixed per task (`allowed_tools`); the oracle,
  evaluator directory, and answer data are never agent-accessible.

## Analysis plan (prewritten before any model runs)

- **Primary outcome:** full-oracle repair pass rate (functional AND
  compatibility groups green), tabulated by
  task × condition × model (per-task tables; raw attempt counts shown).
  Functional-only passes are reported separately and are never called
  task passes.
- **Paired comparisons:** each evidence condition compared against
  `symptom_only` *within the same task and model* (paired by repetition
  order where applicable). Report raw differences only.
- **Secondary outcomes:** diagnosis rubric points, compatibility/regression
  points, constraint adherence, verification accuracy (human), plus tool
  calls, tokens where available, and wall time — each reported separately.
- **Model × evidence-condition comparison:** descriptive only (e.g. whether
  the weaker tier gains pass rate while the stronger tier gains efficiency,
  as DDBench observed). No causal attribution beyond the observed cells.
- **Scale warning (repeat in every report):** three tasks are too few for
  population-level claims about coding agents, regardless of how many
  repeated attempts run. Repetitions show within-cell stability, not breadth.
- **Packet-size statement:** the five conditions compare realistic packets
  of different sizes; they do not isolate evidence content from evidence
  quantity. Length-matched or neutral-context controls are a possible
  *later study*, never a retrofitted claim on this matrix.
- **No significance claims or confidence intervals** unless a method
  appropriate to three tasks is chosen and fully explained. Default: none.
- **Blind human grading** of diagnosis/report summaries (model and condition
  hidden where practical); record grader, blinding, and exceptions.
- **Stop rule:** do not run the model matrix until (a) all three tasks pass
  `audit-task`, and (b) an agent/tooling smoke check reproduces real tool
  actions in a trajectory on a fixture or draft task.

## Reporting rules (existing, retained)

- Correctness pass rate is the primary outcome. Efficiency (tool calls,
  tests run, tokens where available, wall-clock, retries) is reported
  separately and never folded into scores.
- Report per-task outcomes, raw attempt counts, and totals. A three-task
  evaluation is labeled a **small pilot** in every report; no
  population-level conclusions, no significance claims from tiny samples.
- Replayed runs are labeled `replayed: true` everywhere and described as
  fixture/replay data — never as model results.
- Failure labels must link to observable trajectory event seqs and keep
  `observed` (facts) separate from `interpretation` (evaluator hypothesis).
- Do not call paid model APIs, use existing credentials, or incur external
  costs without explicit instruction. Do not fabricate outputs, scores,
  confidence intervals, or results.
- Avoid logging secrets or environment variables. Environment hashes cover
  interpreter/platform info only.

## Isolation

- Each attempt gets an isolated `workspace/` copy; evaluator checks run in
  `evaluator/` outside it. Agent commands and oracle runs execute with a
  scrubbed environment (small allowlist — credentials are never inherited
  by task commands) via `src/debev/sandbox.py`.
- If `bwrap` (bubblewrap) is installed *and* passes a live usability probe,
  subprocesses are confined so only the working directory is visible
  read-write (interpreter libraries read-only). Otherwise the setup is
  **filesystem separation only**, which keeps honest agents out of
  evaluator files but does not stop a process that reaches for parent paths.
- The actual level (`bwrap-sandbox` vs `fs-separation`) is probed per run
  and recorded in `run_meta.json` (`oracle_isolation`,
  `sandbox_available`). Reports must state the recorded level — never claim
  a container boundary that was not used. For untrusted agent code, run on
  a host with `bwrap` (or a real container) and record that in the config.

## Runner trust and sandbox scope (read before connecting an agent)

- **Trusted:** custom `AgentRunner` code (loaded from `--runner`) runs
  in-process with full harness privileges — treat it like harness code, not
  like model output. Review it before use.
- **Confined:** actions mediated by `debev.toolkit` — file reads/writes are
  path-checked to the run workspace; spawned commands get a scrubbed
  environment (no credentials) and the recorded sandbox. A custom runner
  that shells out on its own bypasses all of this; runners must use the
  toolkit for confinement.
- **Evaluator files** are never mounted in the agent's sandbox (bwrap binds
  only the workspace plus read-only interpreter libraries). The oracle
  mounts the workspace read-only, so under bwrap it can read but not modify
  agent files.
- **Fallback is not a boundary:** `fs-separation` keeps honest agents out of
  evaluator files; it does not stop a process that reaches for parent paths
  and must never be presented as a security boundary.
- **Limits:** per-attempt tool-call budgets are hard (further toolkit calls
  raise after recording `limit_exceeded`); per-command timeouts are hard
  (subprocess); the attempt wall clock is enforced cooperatively (toolkit
  checks) plus a watchdog that marks `timeout`/`limit_exceeded` and records
  `runner_orphaned` if the thread survives. An in-process runner stuck in
  pure computation without tool calls cannot be forcibly terminated — a hard
  kill requires an out-of-process runner boundary. `run_meta.json → limits`
  records the configured budgets and whether each was reached: do not report
  a limit as enforced unless the metadata shows the mechanism above.
