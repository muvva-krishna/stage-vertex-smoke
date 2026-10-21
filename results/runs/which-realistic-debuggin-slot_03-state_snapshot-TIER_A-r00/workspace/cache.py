import json
import os
from timeutil import now_s

class TinyFileCache:
    def __init__(self, cache_file):
        self.cache_file = cache_file
        self.data = self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}

    def _save_cache(self):
        with open(self.cache_file, 'w') as f:
            json.dump(self.data, f)

    def put(self, key, value, ttl):
        self.data[key] = {
            "value": value,
            "ts": now_s(),
            "ttl": ttl
        }
        self._save_cache()

    def get(self, key):
        entry = self.data.get(key)
        if entry:
            # Check if the entry has expired
            if now_s() - entry["ts"] < entry["ttl"]:
                return entry["value"]
            else:
                # Entry expired, remove it from cache
                del self.data[key]
                self._save_cache()
        return None

    def prune(self):
        initial_keys = list(self.data.keys())
        pruned_count = 0
        current_time = now_s()

        keys_to_delete = []
        for key, entry in self.data.items():
            if current_time - entry["ts"] >= entry["ttl"]:
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self.data[key]
            pruned_count += 1

        if pruned_count > 0:
            self._save_cache()
        return pruned_count
