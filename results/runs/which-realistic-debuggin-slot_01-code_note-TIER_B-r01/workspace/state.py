import json
import os

# This file is part of cfgmigrate.
# It is intended to be run as a module, e.g.
#   python -m cfgmigrate

# Configuration
CONFIG_FILE = "config.json"
MARKER_FILE_SUFFIX = ".migration.json"

# Migration steps
# Each step is a function that takes the config dict and returns the modified dict.
# The steps are applied in order.
# If a step raises an exception, the migration is considered interrupted.

def add_version(config):
    """Adds version: 2 to the config."""
    if "version" in config:
        return config
    config["version"] = 2
    return config

def rename_items_to_entries(config):
    """Renames "items" to "entries" in the config."""
    if "items" in config:
        config["entries"] = config.pop("items")
    return config

def remove_old_fields(config):
    """Removes any old fields that are no longer needed."""
    # In this simple example, we don't have any old fields to remove.
    # In a real migration, you might remove deprecated fields here.
    return config


# The list of migration steps. This list is used to determine the order of operations
# and to track progress in the marker file.
# The order is important and must be maintained.
MIGRATION_STEPS = [
    add_version,
    rename_items_to_entries,
    remove_old_fields,
]

def get_marker_file_path(config_path):
    """Returns the path to the marker file for a given config file."""
    return config_path + MARKER_FILE_SUFFIX

def load_marker_file(marker_path):
    """Loads the marker file. Returns a dict with a "done" key, which is a list of completed steps.
    If the marker file does not exist, returns an empty dict.
    """
    if not os.path.exists(marker_path):
        return {"done": []}
    with open(marker_path, "r") as f:
        return json.load(f)

def save_marker_file(marker_path, marker_data):
    """Saves the marker file."""
    with open(marker_path, "w") as f:
        json.dump(marker_data, f)

def load_config(config_path):
    """Loads the config file."""
    with open(config_path, "r") as f:
        return json.load(f)

def save_config(config_path, config_data):
    """Saves the config file."""
    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=4) # Use indent for readability

def migrate(config_path):
    """Migrates the config file to the latest version."""
    marker_path = get_marker_file_path(config_path)
    marker_data = load_marker_file(marker_path)
    config = load_config(config_path)

    # Determine which steps have already been completed
    completed_steps = marker_data.get("done", [])
    steps_to_run = []
    for step in MIGRATION_STEPS:
        if step.__name__ not in completed_steps:
            steps_to_run.append(step)

    if not steps_to_run:
        print("already-complete")
        return

    print(f"Starting migration. Steps to run: {[step.__name__ for step in steps_to_run]}")

    for step in steps_to_run:
        try:
            print(f"Running step: {step.__name__}")
            config = step(config)
            completed_steps.append(step.__name__)
            marker_data["done"] = completed_steps
            save_marker_file(marker_path, marker_data)
            save_config(config_path, config)
            # Simulate interruption after a step if MIGRATE_STOP_AFTER is set
            stop_after = os.environ.get("MIGRATE_STOP_AFTER")
            if stop_after and step.__name__ == stop_after:
                print(f"Stopped after step: {step.__name__}")
                return
        except Exception as e:
            print(f"Error during step {step.__name__}: {e}")
            # In a real-world scenario, you might want to implement rollback here.
            return

    print("migration complete")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="cfgmigrate: safe resume after an interrupted migration.")
    parser.add_argument("--steps", action="store_true", help="List all migration steps and exit.")
    args = parser.parse_args()

    if args.steps:
        for step in MIGRATION_STEPS:
            print(step.__name__)
        exit(0)

    # Default behavior: migrate the config file
    migrate(CONFIG_FILE)

if __name__ == "__main__":
    main()
