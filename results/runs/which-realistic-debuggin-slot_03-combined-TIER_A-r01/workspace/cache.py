import json
import os
import timeutil

class Cache:
    def __init__(self, path):
        self.path = path
        self.data = self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return {}
        with open(self.path, 'r') as f:
            return json.load(f)

    def _save(self):
        with open(self.path, 'w') as f:
            json.dump(self.data, f)

    def put(self, key, value, ttl):
        self.data[key] = {"value": value, "ts": timeutil.now_s(), "ttl": ttl}
        self._save()

    def get(self, key):
        entry = self.data.get(key)
        if entry is None:
            return None
        
        # Check for expiry
        if timeutil.now_s() >= entry["ts"] + entry["ttl"]:
            return None # Entry has expired

        return entry["value"]

    def prune(self):
        now = timeutil.now_s()
        pruned_count = 0
        keys_to_delete = []
        for key, entry in self.data.items():
            if now >= entry["ts"] + entry["ttl"]:
                keys_to_delete.append(key)
                pruned_count += 1
        
        for key in keys_to_delete:
            del self.data[key]
        
        if pruned_count > 0:
            self._save()
        return pruned_count
