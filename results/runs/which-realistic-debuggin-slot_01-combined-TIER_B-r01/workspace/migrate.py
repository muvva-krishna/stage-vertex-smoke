import json
import os
import sys

from state import load_state, save_state, is_done, mark_done, reset_state


def migrate_v1_to_v2(path):
    """Migrate a v1 JSON config to v2."""
    # Check if already migrated
    try:
        with open(path, 'r') as f:
            config = json.load(f)
        if config.get("version") == 2 and "entries" in config:
            print("already-complete")
            return
    except FileNotFoundError:
        # If the file doesn't exist, it's not migrated yet.
        pass
    except json.JSONDecodeError:
        # If the file is not valid JSON, we can't proceed.
        print(f"Error: Config file {path} is not valid JSON.")
        sys.exit(1)

    # Load the config if it exists, otherwise start with an empty dict
    if os.path.exists(path):
        with open(path, 'r') as f:
            config = json.load(f)
    else:
        config = {}

    # Define migration steps
    steps = [
        ("add_version", add_version),
        ("rename_items_to_entries", rename_items_to_entries),
    ]

    # Execute migration steps
    for step_name, step_func in steps:
        if not is_done(path, step_name):
            print(f"Running step: {step_name}")
            step_func(config)
            mark_done(path, step_name)
            # Simulate interruption for testing
            if os.environ.get("MIGRATE_STOP_AFTER") == step_name:
                print(f"Stopped after {step_name} as requested.")
                # Save the current state before exiting
                # The state should reflect the steps completed *before* the interrupted one.
                # So, if MIGRATE_STOP_AFTER is 'add_version', we should mark 'add_version' as done.
                # The current logic in mark_done already handles this.
                sys.exit(0)
        else:
            print(f"Step {step_name} already done.")

    # Save the migrated config
    with open(path, 'w') as f:
        json.dump(config, f, indent=2)

    # Reset state for next run if fully migrated
    reset_state(path)
    print("migration complete")


def add_version(config):
    """Add version field to the config."""
    if "version" not in config:
        config["version"] = 2

def rename_items_to_entries(config):
    """Rename 'items' to 'entries' in the config."""
    if "items" in config:
        config["entries"] = config.pop("items")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python migrate.py <config_path>")
        sys.exit(1)

    config_path = sys.argv[1]
    migrate_v1_to_v2(config_path)
