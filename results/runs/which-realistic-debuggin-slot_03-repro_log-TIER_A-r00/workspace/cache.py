"""Small file-backed TTL cache."""
import json
import os

from timeutil import now_ms, now_s


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
    age = now_s() - entry["ts"]
    return age <= entry["ttl"]


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
    kept = {k: e for k, e in data.items() if now_s() - e["ts"] <= e["ttl"]}
    _save(path, kept)
    return len(data) - len(kept)
