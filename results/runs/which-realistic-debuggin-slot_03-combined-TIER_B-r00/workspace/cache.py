import json
import os
import time


def now_s():
    return int(time.time())

def now_ms():
    return int(time.time() * 1000)


class TinyFileCache:
    def __init__(self, cache_file="tinyfilecache.json"):
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
            json.dump(self.cache, f)

    def put(self, key, value, ttl):
        # Store entry with value, current timestamp, and ttl
        # The timestamp should represent the time the entry was stored.
        # The problem states that expiry lets entries live forever, implying
        # that the expiry logic is not correctly implemented or is missing.
        # The current implementation stores the value, the timestamp of storage,
        # and the ttl. The expiry check needs to compare `now_s()` with
        # `entry['ts'] + entry['ttl']`.
        current_time = now_s()
        self.cache[key] = {
            "value": value,
            "ts": current_time,  # Timestamp when the entry was stored
            "ttl": ttl
        }
        self._save_cache()
        print(f"stored {key} ttl={ttl}s")

    def get(self, key):
        if key in self.cache:
            entry = self.cache[key]
            current_time = now_s()
            # Check if the entry has expired
            # An entry expires if current_time is greater than ts + ttl
            if current_time < entry['ts'] + entry['ttl']:
                print(f"HIT {entry['value']}")
                return entry['value']
            else:
                # Entry has expired, treat as MISS
                # We should also remove expired entries, but prune handles that.
                # For now, just return MISS.
                print("MISS")
                return None
        else:
            print("MISS")
            return None

    def prune(self):
        keys_to_remove = []
        current_time = now_s()
        for key, entry in self.cache.items():
            # An entry is expired if current_time is greater than ts + ttl
            if current_time >= entry['ts'] + entry['ttl']:
                keys_to_remove.append(key)
        
        pruned_count = 0
        for key in keys_to_remove:
            del self.cache[key]
            pruned_count += 1
        
        if pruned_count > 0:
            self._save_cache()
            print(f"pruned {pruned_count}")
        else:
            print("pruned 0")


def main():
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="tinyfilecache")
    subparsers = parser.add_subparsers(dest="command")

    put_parser = subparsers.add_parser("put")
    put_parser.add_argument("key")
    put_parser.add_argument("value")
    put_parser.add_argument("--ttl", type=int, required=True)
    put_parser.add_argument("--cache", default="tinyfilecache.json")

    get_parser = subparsers.add_parser("get")
    get_parser.add_argument("key")
    get_parser.add_argument("--cache", default="tinyfilecache.json")

    prune_parser = subparsers.add_parser("prune")
    prune_parser.add_argument("--cache", default="tinyfilecache.json")

    args = parser.parse_args()

    cache = TinyFileCache(args.cache)

    if args.command == "put":
        cache.put(args.key, args.value, args.ttl)
    elif args.command == "get":
        cache.get(args.key)
    elif args.command == "prune":
        cache.prune()

if __name__ == "__main__":
    # Allow FAKE_NOW to be set for deterministic testing
    if "FAKE_NOW" in os.environ:
        fake_now = int(os.environ["FAKE_NOW"])
        # Monkey patch time functions
        original_time_s = time.time
        original_time_ms = timeutil.now_ms
        time.time = lambda: fake_now
        timeutil.now_ms = lambda: fake_now * 1000

    main()
