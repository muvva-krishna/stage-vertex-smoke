import json
import os
import shutil
import sys

from state import MigrationState

# Migration steps are idempotent functions that take the current config
# and return a modified config.
# They are executed in the order they appear in this list.
# The name of the function is the step name.

def add_version(config):
    """Add a 'version: 2' field to the config."""
    if config.get("version") == 2:
        return config
    config["version"] = 2
    return config

def rename_items_to_entries(config):
    """Rename the 'items' field to 'entries'."""
    if "items" not in config:
        return config
    if "entries" in config:
        # Already renamed, or new config has both.
        # If both, assume 'entries' is canonical.
        del config["items"]
        return config
    config["entries"] = config["items"]
    del config["items"]
    return config

# All migration steps, in order.
MIGRATION_STEPS = [
    add_version,
    rename_items_to_entries,
]

def _read_config(config_path):
    with open(config_path, "r") as f:
        return json.load(f)

def _write_config(config_path, config):
    # Write to a temporary file first, then atomically replace the original.
    # This prevents data loss if the process is killed during write.
    tmp_path = config_path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(config, f, indent=2)
    os.replace(tmp_path, config_path)

def _run_step(config_path, config, step_func, state):
    step_name = step_func.__name__
    if state.is_done(step_name):
        print(f"Skipping step '{step_name}' (already done).")
        return config

    print(f"Running step '{step_name}'...")

    # Apply the step function to get the new config
    new_config = step_func(config)

    # Write the new config to disk
    _write_config(config_path, new_config)

    # Mark the step as done *after* the config has been successfully written
    state.mark_done(step_name)

    # Simulate an interruption if MIGRATE_STOP_AFTER is set
    if os.environ.get("MIGRATE_STOP_AFTER") == step_name:
        print(f"MIGRATE_STOP_AFTER={step_name} set. Simulating interruption.")
        sys.exit(0)

    return new_config

def migrate(config_path):
    state = MigrationState(config_path)
    config = _read_config(config_path)

    # Check if already migrated
    if config.get("version") == 2 and "items" not in config and "entries" in config:
        if state.all_done(MIGRATION_STEPS):
            print("Migration already complete.")
            return

    print(f"Starting migration for {config_path}...")

    for step_func in MIGRATION_STEPS:
        config = _run_step(config_path, config, step_func, state)

    # Final check and cleanup
    if config.get("version") == 2 and "items" not in config and "entries" in config:
        state.clear()
        print("Migration complete.")
    else:
        print("Migration incomplete. Please re-run.")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 migrate.py <config_path>")
        sys.exit(1)
    migrate(sys.argv[1])
