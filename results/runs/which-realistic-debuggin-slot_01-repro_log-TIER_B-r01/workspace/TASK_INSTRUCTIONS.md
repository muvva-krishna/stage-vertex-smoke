# cfgmigrate — safe resume after an interrupted migration

`cfgmigrate` migrates a v1 JSON config (`{"name": ..., "items": [...]}`)
to v2 (`"version": 2`, `"items"` renamed to `"entries"`). It is resumable:
if the process is killed mid-migration, re-running the same command must
converge to a fully migrated config.

## Failure report

An operator killed a migration after the first step and re-ran the tool.
The second run printed `migration complete` and exited 0, but the config
is missing `"version": 2`. A downstream version check fails. A fresh
uninterrupted migration of the same input works.

To reproduce the interruption deterministically, set
`MIGRATE_STOP_AFTER=<step>` (e.g. `add_version`); the tool stops right
after that step as if killed.

## Requirements

1. After any interruption point (`MIGRATE_STOP_AFTER` set to any listed
   step, or no interruption), a follow-up run with no interruption must
   leave a fully migrated config: `"version" == 2`, `"entries"` present
   with the original items, `"items"` absent.
2. A fresh uninterrupted migration must fully migrate.
3. Re-running on an already-migrated config must report `already-complete`
   and leave the file byte-identical.
4. `cli.py --steps` must list the migration steps, one per line, exit 0.
5. The marker file (`<config>.migration.json`) must remain JSON of the
   form `{"done": [...]}` listing completed steps.
6. Do not add dependencies (standard library only), do not change the CLI
   argument names, and do not touch anything outside `tasks/slot_01/repo/`
   (evaluator files are off limits and not visible to you).

## Verification guidance

Exercise the tool end to end: fresh run, interrupted run + resume for each
step, and a rerun on the migrated result. Compare the final config against
requirement 1 field by field.
