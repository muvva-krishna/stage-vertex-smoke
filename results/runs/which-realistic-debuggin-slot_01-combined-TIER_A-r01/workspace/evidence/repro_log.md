# Reproduction log (captured from actual runs)

Starting from `{"name": "demo", "items": ["a", "bb"]}`:

```
$ MIGRATE_STOP_AFTER=add_version python3 cli.py cfg.json
migration interrupted
rc=1

$ python3 cli.py cfg.json
migration complete
rc=0
```

Resulting `cfg.json`:

```json
{
  "name": "demo",
  "entries": ["a", "bb"]
}
```

`MIGRATE_STOP_AFTER=<step>` stops right after that step to reproduce the
reported kill deterministically. Note the resume exits 0 and still leaves
the config without `"version"`.
