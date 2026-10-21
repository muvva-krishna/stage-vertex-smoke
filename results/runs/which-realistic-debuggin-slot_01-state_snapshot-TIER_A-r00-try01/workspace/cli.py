import argparse
from pathlib import Path
import sys

# Assuming migrate.py is in the same directory or importable
import migrate

def main():
    parser = argparse.ArgumentParser(description="Migrate configuration files.")
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to the configuration file to migrate.",
    )
    parser.add_argument(
        "--marker",
        type=Path,
        help="Path to the migration marker file (default: <config>.migration.json).",
    )
    parser.add_argument(
        "--steps",
        action="store_true",
        help="List all available migration steps and exit.",
    )

    args = parser.parse_args()

    if args.steps:
        for step_name in migrate.get_step_names():
            print(step_name)
        sys.exit(0)

    config_path = args.config
    if not config_path.exists():
        print(f"Error: Config file not found at {config_path}", file=sys.stderr)
        sys.exit(1)

    marker_path = args.marker
    if marker_path is None:
        marker_path = config_path.with_suffix(config_path.suffix + ".migration.json")

    try:
        migrate.run_migration(config_path, marker_path)
    except Exception as e:
        print(f"Migration failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
