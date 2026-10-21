# Symptom

A cache entry stored with `--ttl 100` is still served 200 seconds later:

```
$ FAKE_NOW=1000 python3 app.py put session abc123 --ttl 100
stored session ttl=100.0s
$ FAKE_NOW=1200 python3 app.py get session
HIT abc123
```

Expected `MISS`: 200 s have passed, twice the 100 s TTL. (`FAKE_NOW`
freezes the clock at the given unix time so the timing is deterministic.)
Fresh reads inside the TTL behave normally, so expiry — not storage or
lookup — is where the entry survives past its time.
