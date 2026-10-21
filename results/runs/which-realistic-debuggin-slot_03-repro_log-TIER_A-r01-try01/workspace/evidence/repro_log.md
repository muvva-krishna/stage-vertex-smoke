# Reproduction log (captured from actual runs)

```
$ FAKE_NOW=1000 python3 app.py put session abc123 --ttl 100
stored session ttl=100.0s
$ FAKE_NOW=1200 python3 app.py get session
HIT abc123
rc=0
```

The get at t=1200 — 200 s after the put with a 100 s TTL — still hits.
`FAKE_NOW=<unix seconds>` pins the clock in `timeutil.py`, so this
transcript is deterministic.
