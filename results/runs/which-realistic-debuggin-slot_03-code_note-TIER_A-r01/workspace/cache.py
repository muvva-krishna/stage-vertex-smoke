import json
import os
from typing import Dict, Any

from timeutil import now_s


class TinyFileCache:
    def __init__(self, cache_file: str = "./.tinyfilecache.json"):
        self.cache_file = cache_file
        self._cache: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                try:
                    self._cache = json.load(f)
                except json.JSONDecodeError:
                    self._cache = {}
        else:
            self._cache = {}

    def _save(self):
        with open(self.cache_file, 'w') as f:
            json.dump(self._cache, f, indent=2)

    def put(self, key: str, value: str, ttl: int):
        self._cache[key] = {"value": value, "ts": now_s(), "ttl": ttl}
        self._save()

    def get(self, key: str) -> str | None:
        entry = self._cache.get(key)
        if entry and not self._is_expired(entry):
            return entry["value"]
        return None

    def prune(self) -> int:
        initial_size = len(self._cache)
        keys_to_prune = [key for key, entry in self._cache.items() if self._is_expired(entry)]
        for key in keys_to_prune:
            del self._cache[key]
        self._save()
        return initial_size - len(self._cache)

    def _is_expired(self, entry: dict) -> bool:
        # Fix: An entry is expired if the current time minus its stored timestamp
        # is greater than its time-to-live.
        return now_s() - entry['ts'] > entry['ttl']

    def clear(self):
        self._cache = {}
        self._save()
