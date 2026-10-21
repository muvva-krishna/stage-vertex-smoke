"""cfgmigrate CLI: migrate a v1 JSON config file to v2, resumably."""
import argparse
import sys

from migrate import STEPS, run_migration


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="cfgmigrate",
        description="Migrate a v1 JSON config to v2 (resumable across interruptions).")
    p.add_argument("config", help="path to JSON config file")
    p.add_argument("--state", default=None,
                   help="marker file (default: <config>.migration.json)")
    p.add_argument("--steps", action="store_true",
                   help="list migration steps and exit")
    args = p.parse_args(argv)
    if args.steps:
        print("\n".join(STEPS))
        return 0
    state_path = args.state or (args.config + ".migration.json")
    status = run_migration(args.config, state_path)
    print(f"migration {status}")
    return 0 if status in ("complete", "already-complete") else 1


if __name__ == "__main__":
    raise SystemExit(main())
