import json
import os
import time

from timeutil import now_s, now_ms


class Cache:
    def __init__(self, cache_path="cache.db"):
        self.cache_path = cache_path
        self.cache = self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_path):
            with open(self.cache_path, "r") as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    # If the cache file is corrupted, start with an empty cache
                    return {}
        else:
            return {}

    def _save_cache(self):
        with open(self.cache_path, "w") as f:
            json.dump(self.cache, f)

    def put(self, key, value, ttl):
        expiry_time = now_s() + ttl
        self.cache[key] = {"value": value, "ts": now_ms(), "ttl": expiry_time}
        self._save_cache()
        return f"stored {key} ttl={ttl}s"

    def get(self, key):
        if key not in self.cache:
            return "MISS"

        entry = self.cache[key]
        current_time = now_s()

        # The problem is here: entry["ttl"] is the expiry timestamp, not the TTL duration.
        # It should be compared against current_time.
        if entry["ttl"] < current_time:
            del self.cache[key]
            self._save_cache()
            return "MISS"
        else:
            return f"HIT {entry['value']}"

    def prune(self):
        keys_to_delete = []
        current_time = now_s()
        for key, entry in self.cache.items():
            if entry["ttl"] < current_time:
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self.cache[key]

        self._save_cache()
        return f"pruned {len(keys_to_delete)}"
