# Reproduction log

```
$ python -m debev_config migrate settings.json
debev-config: process stopped unexpectedly
$ python -m debev_config migrate settings.json
configuration is at schema version 2
$ python -m debev_config show settings.json
{
  "extensions": {},
  "retry": {"max_attempts": 4},
  "schema_version": 2,
  "service": {"endpoint": "https://collector.example"}
}
```

Before the interruption, the affected installation's preferences contained `{"layout": {"compact": true}}`.
