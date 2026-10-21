# Pilot results (TEMPLATE — no findings yet)

> Small pilot. This file contains **no invented findings**. Fill it from
> `debev report` output after human-authored tasks land and real (or replay)
> runs complete. Replayed rows must stay labeled as replays.

- Date run:
- Commit / harness version:
- Model(s) + versions (or `replayed fixture`):
- Tasks: slot_01 / slot_02 / slot_03 (see `tasks/README.md`)
- Repetitions per cell / seed / run order:

## Outcomes by task x condition x model

| task | condition | model | attempts | passes | pass_rate | totals | evid_tokens | replayed |
|---|---|---|---|---|---|---|---|---|
| (fill from report JSON `cells`; evid_tokens shows packet size per attempt — report it alongside pass rates, never as an afterthought) | | | | | | | |

## Per-run notes (trajectory summaries + failure labels)

(Fill from `debev report` Markdown: evidence opened, commands/tests, diff
summary, failure label → event seqs, observed vs interpretation.)

## Efficiency (separate from correctness)

(Fill: tool calls, tests run, tokens where available, wall-clock, retries —
per run. Do not fold into scores.)

## Limitations observed

(Fill: isolation level used, budget notes, anything that constrains
interpretation. Keep the pilot warning: no population-level conclusions or
significance claims from this sample.)
