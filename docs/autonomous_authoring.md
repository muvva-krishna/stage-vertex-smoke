# Autonomous authoring record (AI-authored pilot variant)

**Disclosure: the three tasks in `tasks/slot_01–03` were authored by an AI
model (Muse Spark 1.3 via OpenCode), NOT by a human.** This branch is an
autonomous-pilot variant of the harness prototype. It does **not** satisfy
any requirement for human-authored tasks, and nothing here may be presented
as human-authored ground truth. The original human-authored protocol
(`docs/task_authoring_spec.md`, `docs/evaluation_protocol.md`) is unchanged;
this document records where this variant deliberately departs from it
(AI-generated task content) and where it still complies (audit gates,
isolation, no fabricated results).

- Authoring model: Muse Spark 1.3 Contributor (Meta MSL), via OpenCode.
- Date: 2026-10-21. Seed: n/a (interactive session, no fixed seed).
- Generation brief hash: recorded in each task's PROVENANCE.md (sha256 of
  the brief below).
- No independent critic model was available; review was deterministic only
  (validate + audit-task ×2, evidence captured from actual runs). The lack
  of independent review is a validity limitation, stated in the final report.
- Task-authoring, evaluated-agent, and grader roles are currently
  unseparated (no models configured). Any future runs must label
  self-evaluation explicitly.

## Generation brief (hashed for provenance)

Three original synthetic debugging tasks, disjoint root-cause mechanisms,
each a small multi-file Python repo (stdlib only):

1. `cfgmigrate` (slot_01): stepwise JSON config migration with a marker
   file. Bug class: crash-recovery — step marked done before its effect is
   persisted + config saved only at end, so interrupted-then-resumed runs
   converge to a half-migrated config. Deterministic crash hook:
   MIGRATE_STOP_AFTER env var.
2. `csvimport` (slot_02): CSV→JSON importer with email dedup. Bug class:
   inconsistent normalization — membership tested on the normalized key,
   `seen` records the raw key, so spelling variants slip through.
3. `tinyfilecache` (slot_03): file-backed TTL cache with dual clocks.
   Bug class: unit mismatch across a module boundary — millisecond stamp
   aged with a seconds clock against a seconds TTL, so entries never
   expire. Deterministic clock: FAKE_NOW env var.

Per task: 3-file repo, truthful evidence captured from actual buggy runs
(symptom/repro/state/code-note), GROUP-protocol oracle (behavior checks +
compat groups), reference solution overlay, one failing partial-fix probe,
rubric weights, accepted-diagnosis rubric, manifest, instructions.
Mechanisms, names, code, and numbers are original to this session; no
benchmark tasks, patches, or tests were copied (related-work sources were
used for harness patterns only, per docs/related_work.md).
