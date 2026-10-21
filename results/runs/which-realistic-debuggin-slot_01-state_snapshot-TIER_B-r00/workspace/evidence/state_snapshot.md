# State snapshot (captured after the interrupted + resumed runs above)

`cfg.json`:
```json
{
  "name": "demo",
  "entries": ["a", "bb"]
}
```

`cfg.json.migration.json` (marker):
```json
{
  "done": ["add_version", "rename_items"]
}
```

Observation: the marker claims `add_version` is done, but the persisted
config has no `"version"` field. The marker and the config disagree about
what was actually persisted.
