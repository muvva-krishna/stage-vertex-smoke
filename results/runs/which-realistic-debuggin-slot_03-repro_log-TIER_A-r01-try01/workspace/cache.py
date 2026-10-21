import json
import os
import timeutil

class Cache:
    def __init__(self, cache_file):
        self.cache_file = cache_file
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        return {}

    def _save(self):
        with open(self.cache_file, 'w') as f:
            json.dump(self.data, f)

    def put(self, key, value, ttl):
        self.data[key] = {"value": value, "ts": timeutil.now_s(), "ttl": ttl}
        self._save()

    def get(self, key):
        entry = self.data.get(key)
        if entry:
            # Check for expiry
            expiry_time = entry["ts"] + entry["ttl"]
            current_time = timeutil.now_s()

            if current_time > expiry_time:
                # Entry has expired
                del self.data[key]
                self._save()
                return None
            else:
                # Entry is still valid
                return entry["value"]
        return None

    def prune(self):
        pruned_count = 0
        keys_to_prune = []
        for key, entry in self.data.items():
            if timeutil.now_s() > entry["ts"] + entry["ttl"]:
                keys_to_prune.append(key)
        for key in keys_to_prune:
            del self.data[key]
            pruned_count += 1
        if pruned_count > 0:
            self._save()
        return pruned_count
