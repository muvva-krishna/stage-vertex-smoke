# State snapshot after the interruption

- `settings.json` parses successfully and has `schema_version: 2`.
- `settings.json.migration.json` contains `{"status": "in_progress"}`.
- `settings.json.migration.bak` is present and contains the pre-migration version 1 configuration, including the user's `preferences` object.
- The current version 2 file has the correct service endpoint and retry limit, but its `extensions` object is empty.
