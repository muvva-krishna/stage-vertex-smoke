"""tinyfilecache CLI: put/get keys with a TTL, plus prune."""
import argparse
import sys

from cache import cache_get, cache_set, prune_expired


def main(argv=None):
    p = argparse.ArgumentParser(prog="tinyfilecache",
                                description="File-backed TTL cache.")
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("put", help="store a key")
    pp.add_argument("key")
    pp.add_argument("value")
    pp.add_argument("--ttl", type=float, default=300, help="TTL in seconds")
    pp.add_argument("--cache", default="cache.json")
    gp = sub.add_parser("get", help="fetch a key")
    gp.add_argument("key")
    gp.add_argument("--cache", default="cache.json")
    rp = sub.add_parser("prune", help="drop expired entries")
    rp.add_argument("--cache", default="cache.json")
    args = p.parse_args(argv)
    if args.cmd == "put":
        cache_set(args.cache, args.key, args.value, args.ttl)
        print(f"stored {args.key} ttl={args.ttl}s")
        return 0
    if args.cmd == "get":
        hit, value = cache_get(args.cache, args.key)
        print(f"HIT {value}" if hit else "MISS")
        return 0
    removed = prune_expired(args.cache)
    print(f"pruned {removed} entr(y/ies)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
