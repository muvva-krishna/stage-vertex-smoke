"""AI-generated reference solution overlay for slot_03 (evaluator-only).

Fix: compare like with like — age in milliseconds against TTL converted
to milliseconds — in both the read path and the prune path.
"""
import json
import os

from timeutil import now_ms


def _load(path):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def _save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def cache_set(path, key, value, ttl_s):
    data = _load(path)
    data[key] = {"value": value, "ts": now_ms(), "ttl": ttl_s}
    _save(path, data)


def _age_ok(entry):
    age_ms = now_ms() - entry["ts"]
    return age_ms <= entry["ttl"] * 1000.0


def cache_get(path, key):
    data = _load(path)
    entry = data.get(key)
    if entry is None:
        return (False, None)
    if not _age_ok(entry):
        return (False, None)
    return (True, entry["value"])


def prune_expired(path):
    """Drop expired entries. Returns the number removed."""
    data = _load(path)
    kept = {k: e for k, e in data.items() if _age_ok(e)}
    _save(path, kept)
    return len(data) - len(kept)
