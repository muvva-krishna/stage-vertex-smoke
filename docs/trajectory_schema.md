# Trajectory schema (v1)

All runs emit **JSONL**: one JSON object per line in `trajectory.jsonl`.
Field order is not significant. Times are wall-clock seconds since `run_start`.

## Event envelope

| Field | Type | Meaning |
|---|---|---|
| `seq` | int | 1-based sequence number, strictly increasing |
| `t_wall_s` | float | seconds since run start |
| `type` | string | one of the types below |
| `run_id` | string | attempt identifier |
| `task_id` | string | task identifier |
| `condition` | string | one of the five evidence conditions |
| `data` | object | type-specific payload (observable facts only) |

## Event types and `data` payloads

- `run_start`: `{model, model_version, harness, seed, temperature, condition,
  evidence_files[], evidence_tokens, token_counts{}, budget, replayed: bool,
  environment_hash}`
- `evidence_access`: `{file, tokens}` — one per supplied artifact materialized
  for the agent. Absence of an event means the file was **not supplied** in
  this condition (not merely unopened).
- `file_read`: `{path}` — agent read of a workspace file.
- `file_write`: `{path}` (+ optional `bytes`) — agent write in the workspace.
- `command`: `{cmd, rc, output?}` — shell command executed by/for the agent.
- `test_run`: `{name, result, via?, ...}` — `result` in {`PASS`, `FAIL`,
  `ERROR`, `INCONCLUSIVE`}. A test the agent (or its harness) actually
  executed. Only `test_run` events executed through the toolkit
  (`via: "toolkit"`, not replayed) earn **machine** verification credit.
- `verification`: `{name, result, detail}` — the agent's explicit final
  claim (`result` in {`PASS`, `FAIL`, `ERROR`, `INCONCLUSIVE`}).
  Free-form/self-reported: recorded for **human** grading of reporting
  accuracy, but NEVER earns machine verification credit on its own.
- `timeout`: `{kind, ...}` — `kind` in {`command`, `test`, `attempt`}: a
  per-command timeout (`TIMEOUT`, mapped to `INCONCLUSIVE` for tests) or
  the attempt wall-clock watchdog firing.
- `limit_exceeded`: `{kind, op}` — `kind` in {`tool_calls`, `wall_clock`}:
  the per-attempt budget stopped further tool calls.
- `agent_note`: `{kind, text}` — `kind` in {`diagnosis`, `verification`}.
  Short user-visible summaries only. **Private chain-of-thought, hidden
  reasoning, and system prompts are never collected**; the recorder rejects
  fields named `chain_of_thought`, `cot`, `hidden_reasoning`, `system_prompt`.
- `diff`: `{summary}` — compact workspace diff summary at end of run.
- `run_end`: `{wall_s, replayed}`.

## Worked example (replayed plumbing fixture)

```json
{"seq": 1, "t_wall_s": 0.0, "type": "run_start", "run_id": "replay-001",
 "task_id": "fixture-plumbing", "condition": "combined",
 "data": {"model": "not-configured", "evidence_files": ["code_note.md", "repro_log.md", "state_snapshot.md", "symptom.md"], "evidence_tokens": 87, "replayed": true, "environment_hash": "sha256:…"}}
{"seq": 2, "t_wall_s": 0.01, "type": "evidence_access", "run_id": "replay-001",
 "task_id": "fixture-plumbing", "condition": "combined",
 "data": {"file": "symptom.md", "tokens": 20, "replayed": true}}
```

## Failure labels (stored in `run_meta.json`, not in the trajectory)

Each label links to observable event seqs and separates observation from
interpretation:

```json
{"label": "missed_evidence", "event_seqs": [2, 5],
 "observed": "repro_log.md supplied (seq 2) but no file_read/command references it by seq 5",
 "interpretation": "evaluator hypothesis: agent ignored the reproduction log"}
```

Valid labels: `missed_evidence`, `misread_evidence`,
`wrong_causal_hypothesis`, `incomplete_repair`, `regression`,
`constraint_violation`, `inadequate_verification`, `inaccurate_final_report`.
See `docs/rubric.md` for definitions. Never claim a trace category *caused*
an outcome unless the matched-condition experiment supports it.

## OTLP export

`debev export-otel --run-dir … --out trace.json` converts a trajectory to
OTLP JSON (`resourceSpans`, opentelemetry-proto v1 shape, pinned in
`src/debev/otel_export.py`) with spans named `debev.<event-type>`. The
adapter deliberately avoids OpenTelemetry's GenAI/agent conventions (marked
development-status upstream) and uses plain `debev.*` attribute keys. It is
an export adapter for trajectory interop (e.g. TRAIL-style tooling), not a
claim of conformance.
