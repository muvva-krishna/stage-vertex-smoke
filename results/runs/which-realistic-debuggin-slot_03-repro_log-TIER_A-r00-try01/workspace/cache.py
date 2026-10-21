import json
import os

from timeutil import now_s


class TinyFileCache:
    def __init__(self, cache_file):
        self.cache_file = cache_file
        self.cache = self._load_cache()

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
            json.dump(self.cache, f, indent=2)

    def put(self, key, value, ttl):
        self.cache[key] = {
            'value': value,
            'ts': now_s(),
            'ttl': ttl
        }
        self._save_cache()

    def get(self, key):
        entry = self.cache.get(key)
        if entry:
            # Check if the entry is expired
            if now_s() >= entry['ts'] + entry['ttl']:
                del self.cache[key]
                self._save_cache()
                return None
            return entry['value']
        return None

    def prune(self):
        initial_keys = list(self.cache.keys())
        pruned_count = 0
        current_time = now_s()
        keys_to_delete = []

        for key, entry in self.cache.items():
            if current_time >= entry['ts'] + entry['ttl']:
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self.cache[key]
            pruned_count += 1

        if pruned_count > 0:
            self._save_cache()
        return pruned_count
