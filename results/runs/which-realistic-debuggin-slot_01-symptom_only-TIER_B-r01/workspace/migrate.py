import json
import os


def migrate(input_path, output_path, stop_after=None):
    """Migrates a v1 config to v2, with optional interruption."""
    try:
        with open(input_path, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file '{input_path}' not found.")
        return

    # State management for resumability
    marker_path = f"{output_path}.migration.json"
    done_steps = []
    if os.path.exists(marker_path):
        try:
            with open(marker_path, 'r') as f:
                state = json.load(f)
                done_steps = state.get("done", [])
        except json.JSONDecodeError:
            print(f"Warning: Corrupted marker file '{marker_path}'. Starting fresh.")
            done_steps = []

    # Define migration steps
    migration_steps = [
        ("add_version", add_version_step),
        ("rename_items", rename_items_step),
    ]

    # Filter steps based on done_steps
    steps_to_run = [step for step in migration_steps if step[0] not in done_steps]

    for step_name, step_func in steps_to_run:
        print(f"Running step: {step_name}")
        try:
            config = step_func(config)
            done_steps.append(step_name)
            # Update marker file after each successful step
            with open(marker_path, 'w') as f:
                json.dump({"done": done_steps}, f)

            if stop_after == step_name:
                print(f"Stopped after step: {step_name}")
                return
        except Exception as e:
            print(f"Error during step '{step_name}': {e}")
            # In a real scenario, you might want more sophisticated error handling
            return

    # If all steps are done or were already done
    if len(done_steps) == len(migration_steps):
        print("migration complete")
    else:
        print("migration complete (already done or interrupted)")

    # Write the final migrated config
    try:
        with open(output_path, 'w') as f:
            json.dump(config, f, indent=2)
        # Clean up marker file on successful completion of all steps
        if len(done_steps) == len(migration_steps) and os.path.exists(marker_path):
            os.remove(marker_path)
    except IOError as e:
        print(f"Error writing output file '{output_path}': {e}")


def add_version_step(config):
    """Adds version 2 to the config."""
    if "version" not in config:
        config["version"] = 2
    return config

def rename_items_step(config):
    """Renames 'items' to 'entries' in the config."""
    if "items" in config:
        config["entries"] = config.pop("items")
    return config


# Example usage (for testing purposes, not part of the core logic)
if __name__ == "__main__":
    # This part is for demonstration and testing, not for the actual tool execution
    # In a real scenario, cli.py would handle argument parsing and calling migrate
    pass
