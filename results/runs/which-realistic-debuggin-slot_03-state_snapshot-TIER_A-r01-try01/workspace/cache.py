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
        
        current_time = timeutil.now_s()
        if current_time > entry["ts"] + entry["ttl"]:
            # Entry has expired
            del self.data[key] # Remove expired entry on get
            self._save() # Save changes if an entry was removed
            return None
        
        return entry["value"]

    def prune(self):
        initial_count = len(self.data)
        keys_to_delete = []
        current_time = timeutil.now_s()
        for key, entry in self.data.items():
            if current_time > entry["ts"] + entry["ttl"]:
                keys_to_delete.append(key)
        for key in keys_to_delete:
            del self.data[key]
        self._save()
        return initial_count - len(self.data)
