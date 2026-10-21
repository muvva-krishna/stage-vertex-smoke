# tinyfilecache — entries never expire

`tinyfilecache` is a small file-backed TTL cache:

```
python3 app.py put KEY VALUE --ttl SECONDS [--cache FILE]
python3 app.py get KEY [--cache FILE]      # prints HIT <value> or MISS
python3 app.py prune [--cache FILE]        # drops expired entries
```

`timeutil.py` offers `now_s()` / `now_ms()` clocks; setting
`FAKE_NOW=<unix seconds>` pins both deterministically for testing.

## Failure report

An entry stored with `--ttl 100` is still a `HIT` 200 seconds later (see
evidence; times pinned with `FAKE_NOW`). Fresh reads inside the TTL work,
so storage and lookup are fine — expiry lets entries live forever.

## Requirements

1. A `get` after more than TTL seconds have passed prints exactly `MISS`.
2. A `get` inside the TTL prints `HIT <value>`.
3. `prune` removes only expired entries and reports `pruned <n>`.
4. Entry schema stays `{"value", "ts", "ttl"}`; `put` still prints
   `stored <key> ttl=<ttl>s`.
5. Do not add dependencies (standard library only), and do not touch
   anything outside `tasks/slot_03/repo/`.

## Verification guidance

Pin the clock with `FAKE_NOW`: store with one timestamp, read before and
after the TTL with another, and run `prune` over a mix of fresh and stale
entries checking which keys survive.
