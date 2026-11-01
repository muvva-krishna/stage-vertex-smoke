# Pilot results — Muse Spark 1.3 Contributor

> Exploratory one-task smoke pilot. Five real model runs; no population-level
> or statistical conclusions are supported by this sample.

- **Date:** 2026-11-01
- **Harness:** `debev-0.1.0`, commit `1b5fc09` (working tree was dirty)
- **Model:** `opencode-go/muse-spark-1.3-contributor` (OpenCode `2.2.5`)
- **Task:** `slot_01` / `migration-resume`; slots 02–03 are still placeholders.
- **Repetitions:** 1 per condition; randomized order with CLI order seed `0`
  (execution order: state snapshot, repro log, symptom only, combined, code
  note). Model temperature and model sampling seed were not set (`null`).
- **Run artifacts:** [`REPORT.md`](REPORT.md), [`REPORT.json`](REPORT.json),
  and `runs/muse-spark-1-3-contributor-slot-01-*/`.

## Outcomes by task x condition

| task | condition | attempts | passes | pass_rate | recorded total* | evidence tokens | replayed |
|---|---|---:|---:|---:|---:|---:|---|
| migration-resume | code_note | 1 | 1 | 1.0 | 77.5 | 79 | no |
| migration-resume | combined | 1 | 1 | 1.0 | 77.5 | 190 | no |
| migration-resume | repro_log | 1 | 1 | 1.0 | 77.5 | 88 | no |
| migration-resume | state_snapshot | 1 | 0 | 0.0 | 62.5 | 87 | no |
| migration-resume | symptom_only | 1 | 1 | 1.0 | 77.5 | 32 | no |

\* Recorded scores are provisional: root-cause diagnosis (20 points) and the
human reporting-accuracy portion (2.5 points) remain pending. Do not interpret
these as final human-graded totals. Evidence token counts are whitespace-based
approximations. Packet sizes differ, so this comparison is about realistic
packets—not evidence-type attribution.

## Per-run notes

All five public `unittest` suites passed. The hidden behavioral oracle passed
all groups for four runs. The `state_snapshot` run passed fresh migration,
committed-target recovery, idempotence, and CLI compatibility, but failed
`resume_partial_target`: it did not recover an unreadable/truncated target
from the backup. This is the only oracle failure. Human diagnosis and final
report-accuracy grades have not been assigned.

| condition | evidence opened | oracle | changed file | public tests |
|---|---|---|---|---|
| symptom_only | `symptom.md` | pass | `debev_config/migration.py` | pass |
| repro_log | `symptom.md`, `repro_log.md` | pass | `debev_config/migration.py` | pass |
| state_snapshot | `symptom.md`, `state_snapshot.md` | fail: `resume_partial_target` | `debev_config/migration.py` | pass |
| code_note | `symptom.md`, `code_note.md` | pass | `debev_config/migration.py` | pass |
| combined | all four evidence files | pass | `debev_config/migration.py` | pass |

## Efficiency (separate from correctness)

| condition | tool calls | tests | evidence tokens | model tokens | wall clock | retries |
|---|---:|---:|---:|---|---:|---:|
| symptom_only | 4 | 1 | 32 | unavailable | 47.10 s | 0 |
| repro_log | 4 | 1 | 88 | unavailable | 99.00 s | 0 |
| state_snapshot | 4 | 1 | 87 | unavailable | 48.30 s | 0 |
| code_note | 4 | 1 | 79 | unavailable | 60.99 s | 0 |
| combined | 4 | 1 | 190 | unavailable | 42.18 s | 0 |

## Limitations and interpretation

- One task and one attempt per condition are only enough to validate the
  harness and surface a case for follow-up. `symptom_only` also passed, so
  these outcomes do not establish that extra evidence improves performance.
- Slot 01's manifest attributes the task to OpenAI Codex, while the project
  authoring spec calls for human-authored tasks. Treat this as exploratory
  until a human reviews and accepts the task; slots 02–03 still need tasks.
- The harness and oracle used `bwrap-sandbox`. Model token counts were not
  available; the model sampling seed and temperature were unset.
- Scores keep human-graded components pending. The generated report preserves
  the raw per-run outcomes and trajectories.
