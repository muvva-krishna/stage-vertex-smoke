# Accepted root-cause diagnosis — slot_03 (AI-written rubric, evaluator-only)

**Accepted root cause (20/20):** entries are stamped with the millisecond
clock (`now_ms`) but aged with the seconds clock (`now_s`) against a TTL
in seconds — the mixed-unit subtraction is hugely negative, so every entry
looks fresh forever. Must name the stamp side, the check side, and the
unit mismatch (both `cache_get` and `prune_expired` share it).

**Partial credit:**
- 14/20: identifies the s/ms mismatch but only on one path (misses that
  `prune_expired` duplicates the bug).
- 8/20: right files (`cache.py`/`timeutil.py`) but wrong mechanism (e.g.
  blames `FAKE_NOW`, the CLI, or file persistence).
- 0/20: patch passes (e.g. deleting the cache on every read) with a wrong
  stated cause.

Valid alternative repairs accepted (e.g. stamping seconds everywhere,
storing an absolute expiry timestamp) provided both paths compare
consistent units. Grade the explanation, not the patch shape.
