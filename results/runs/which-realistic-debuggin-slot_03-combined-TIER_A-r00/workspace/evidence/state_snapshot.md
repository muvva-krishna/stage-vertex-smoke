# State snapshot (cache.json after the run above)

```json
{
  "session": {"value": "abc123", "ts": 1000000.0, "ttl": 100.0}
}
```

Observation: the entry was stamped at `ts: 1000000.0` while the clock that
wrote it read `FAKE_NOW=1000`. Compare the magnitude of the stamp against
the clock reading and the TTL before deciding where the comparison goes
wrong.
