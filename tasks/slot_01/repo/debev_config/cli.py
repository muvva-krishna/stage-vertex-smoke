"""Command-line entry point for migrating user configuration."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .migration import MigrationError, migrate_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="debev-config")
    sub = parser.add_subparsers(dest="command", required=True)
    migrate = sub.add_parser("migrate", help="upgrade a configuration file")
    migrate.add_argument("path", type=Path)
    show = sub.add_parser("show", help="print a configuration file")
    show.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "migrate":
            result = migrate_file(args.path)
            print(f"configuration is at schema version {result['schema_version']}")
        else:
            print(json.dumps(json.loads(args.path.read_text(encoding="utf-8")), indent=2))
    except (OSError, json.JSONDecodeError, MigrationError) as exc:
        parser.exit(2, f"debev-config: {exc}\n")
    return 0
