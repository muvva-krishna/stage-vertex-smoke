# Evidence authoring placeholder (slot_01)

TODO (human author): create these agent-visible files:
- `evidence/symptom.md` — observed failure only, no diagnosis, no fix pointer.
- `evidence/repro_log.md` — bounded reproduction log for the `repro_log` and `combined` conditions.
- `evidence/state_snapshot.md` — bounded runtime-state snapshot for `state_snapshot` and `combined`.
- `evidence/code_note.md` — short code-path/investigation note for `code_note` and `combined`. Must not state the fix.

Keep every condition within `max_evidence_tokens`. Record actual token counts;
do not pad shorter conditions. See `docs/task_authoring_spec.md`.
