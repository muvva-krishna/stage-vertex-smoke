# Task slots (AI-authored pilot variant — NOT human-authored)

On this branch the three slots hold **AI-generated synthetic tasks**
(`cfgmigrate`, `csvimport`, `tinyfilecache`), authored by Muse Spark 1.3
via OpenCode on 2026-10-21. See `docs/autonomous_authoring.md` and each
slot's `PROVENANCE.md`. They must never be presented as human-authored and
do not satisfy human-authorship requirements.

- `slot_01/` — interrupted config-migration resume (marker-before-work +
  end-only persistence). Audited.
- `slot_02/` — CSV dedup with inconsistent key normalization. Audited.
- `slot_03/` — TTL cache with seconds/milliseconds unit mismatch. Audited.

Each slot contains: `manifest.json`, `instructions.md`, `repo/`,
`evidence/` (4 truthful artifacts captured from real runs), `evaluator/`
(`oracle.py`, `reference_solution/`, `partial_fixes/`,
`accepted_diagnosis.md` — all AI-generated), `rubric_weights.json`,
`PROVENANCE.md`.

The synthetic fixture in `fixtures/plumbing_fixture/` is NOT a task slot
and must never be presented as one.
