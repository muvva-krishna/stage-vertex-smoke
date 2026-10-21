import json
import os

# Migration steps

def add_version(config):
    """Add version 2 to the config."""
    config["version"] = 2
    return config

def rename_items_to_entries(config):
    """Rename the 'items' key to 'entries'."""
    if "items" in config:
        config["entries"] = config.pop("items")
    return config

# Migration task definitions

MIGRATION_TASKS = [
    ("add_version", add_version),
    ("rename_items_to_entries", rename_items_to_entries),
]

# State management

MARKER_SUFFIX = ".migration.json"

def get_marker_path(config_path):
    return config_path + MARKER_SUFFIX

def load_marker(config_path):
    marker_path = get_marker_path(config_path)
    if os.path.exists(marker_path):
        with open(marker_path, 'r') as f:
            return json.load(f)
    return {"done": []}

def save_marker(config_path, marker):
    marker_path = get_marker_path(config_path)
    with open(marker_path, 'w') as f:
        json.dump(marker, f, indent=2)

# Migration execution

def migrate(config_path, stop_after=None):
    """Migrate a config file, with optional stop point for testing."""
    config = json.load(open(config_path))
    marker = load_marker(config_path)
    
    # Determine which tasks to run
    tasks_to_run = []
    for name, func in MIGRATION_TASKS:
        if name not in marker["done"]:
            tasks_to_run.append((name, func))
        if name == stop_after:
            break

    if not tasks_to_run:
        print("migration complete")
        return

    for name, func in tasks_to_run:
        config = func(config)
        marker["done"].append(name)
        save_marker(config_path, marker)
        print(f"Completed step: {name}")
        if name == stop_after:
            print(f"Stopped after step: {name}")
            return

    # Finalize migration
    # Remove marker file if migration is fully complete
    if len(marker["done"]) == len(MIGRATION_TASKS):
        os.remove(get_marker_path(config_path))
        print("migration complete")
    else:
        # This case should ideally not be reached if stop_after is handled correctly
        # but as a safeguard, we ensure the marker is saved.
        save_marker(config_path, marker)
        print("migration interrupted, resuming next time")


def check_migration_status(config_path):
    """Check if migration is complete."""
    marker = load_marker(config_path)
    if len(marker["done"]) == len(MIGRATION_TASKS):
        return "complete"
    else:
        return "in-progress"

def is_fully_migrated(config):
    """Check if a config is fully migrated."""
    return config.get("version") == 2 and "entries" in config and "items" not in config

