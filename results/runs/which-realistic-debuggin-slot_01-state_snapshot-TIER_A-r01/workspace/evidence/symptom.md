# Symptom

After `cfgmigrate` was killed mid-migration and re-run to completion, the
config file is missing the `"version"` field even though the tool reports
`migration complete`:

```json
{
  "name": "demo",
  "entries": ["a", "bb"]
}
```

Expected: a fully migrated config carries `"version": 2` and `"entries"`
with no `"items"` key. A downstream check (`version == 2`) fails on the
resumed result. A fresh uninterrupted migration on the same input works.
