import json
import os

from timeutil import now_s


class Cache:
    def __init__(self, path):
        self._path = path
        self._cache = {}
        self._load()

    def _load(self):
        if not os.path.exists(self._path):
            return
        with open(self._path, "r") as f:
            self._cache = json.load(f)

    def _save(self):
        with open(self._path, "w") as f:
            json.dump(self._cache, f)

    def _is_expired(self, entry):
        # An entry is expired if the current time is past its creation time + TTL.
        return now_s() >= entry["ts"] + entry["ttl"]

    def get(self, key):
        entry = self._cache.get(key)
        if entry is None:
            return None
        if self._is_expired(entry):
            return None
        return entry["value"]

    def put(self, key, value, ttl):
        self._cache[key] = {"value": value, "ts": now_s(), "ttl": ttl}
        self._save()

    def prune(self):
        keys_to_prune = []
        for key, entry in self._cache.items():
            if self._is_expired(entry):
                keys_to_prune.append(key)

        for key in keys_to_prune:
            del self._cache[key]
        self._save()
        return len(keys_to_prune)
