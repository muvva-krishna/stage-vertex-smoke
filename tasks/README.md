# Task slots

Three task slots are reserved for human-authored portfolio tasks. Each slot
contains a structural `manifest.json`, an `instructions.md` placeholder, and
`evidence/` + `evaluator/` authoring placeholders.

- `slot_01/`, `slot_02/`, `slot_03/` — TODO: author real tasks here.
- Suggested domain for one slot: deterministic Python CLI maintenance problem
  such as safe recovery after an interrupted configuration migration.
- The final task prompt, reference patch, hidden assertions, and accepted
  diagnosis must be human-authored and original. Do not copy benchmark tasks,
  prompts, hidden tests, datasets, or answer keys from the references in
  `docs/related_work.md`.

The synthetic fixture in `fixtures/plumbing_fixture/` is NOT a task slot and
must never be presented as one.
