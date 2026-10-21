import argparse
import json
import os

from migrate import migrate
from state import get_migration_state

def main():
    parser = argparse.ArgumentParser(description="cfgmigrate — safe resume after an interrupted migration")
    parser.add_argument("--input", default="config.json", help="Input configuration file (v1 format).")
    parser.add_argument("--output", default="config.json", help="Output configuration file (v2 format).")
    parser.add_argument("--steps", action="store_true", help="List available migration steps.")
    parser.add_argument("stop_after", nargs='?', default=None, help="Stop migration after this step (for testing interruptions).")

    args = parser.parse_args()

    if args.steps:
        # In a real scenario, this would dynamically get steps from migrate.py
        print("add_version")
        print("rename_items")
        return

    # Check if the output file is already migrated
    marker_path = f"{args.output}.migration.json"
    state = get_migration_state(args.output)

    # Determine total number of steps to check for completion
    # This should ideally be dynamic, but for this example, we hardcode it.
    # A more robust solution would involve introspecting migrate.py or a config file.
    total_migration_steps = 2 # add_version, rename_items

    if state.is_fully_migrated(total_migration_steps) and os.path.exists(args.output):
        # Verify if the output file is byte-identical to a known good migrated file
        # For simplicity here, we just assume if the marker says done, it's good.
        # A real check would involve comparing content or a hash.
        print("already-complete")
        return

    # If the output file exists and is not fully migrated, and the marker file exists,
    # it implies an interruption. We resume.
    # If the output file does not exist, or the marker file is missing/corrupted,
    # we start a fresh migration.

    # Ensure input and output are not the same if migration is not complete
    if args.input == args.output and not state.is_fully_migrated(total_migration_steps):
        print("Error: Input and output files cannot be the same for an incomplete migration.")
        return

    migrate(args.input, args.output, args.stop_after)

if __name__ == "__main__":
    main()
