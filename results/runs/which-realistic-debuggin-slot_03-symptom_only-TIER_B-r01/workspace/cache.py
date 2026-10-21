import json
import os
import time

from timeutil import now_s, now_ms


class Cache:
    def __init__(self, cache_file="cache.db"):
        self.cache_file = cache_file
        self.cache = self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "r") as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}

    def _save_cache(self):
        with open(self.cache_file, "w") as f:
            json.dump(self.cache, f)

    def put(self, key, value, ttl):
        expiry = now_s() + ttl
        self.cache[key] = {"value": value, "ts": now_ms(), "ttl": expiry}
        self._save_cache()
        return f"stored {key} ttl={ttl}s"

    def get(self, key):
        if key not in self.cache:
            return "MISS"
        entry = self.cache[key]
        if now_s() > entry["ttl"]:
            # Entry has expired, remove it
            del self.cache[key]
            self._save_cache()
            return "MISS"
        return f"HIT {entry['value']}"

    def prune(self):
        pruned_count = 0
        current_time = now_s()
        keys_to_delete = []
        for key, entry in self.cache.items():
            if current_time > entry["ttl"]:
                keys_to_delete.append(key)
        for key in keys_to_delete:
            del self.cache[key]
            pruned_count += 1
        if pruned_count > 0:
            self._save_cache()
        return f"pruned {pruned_count}"
