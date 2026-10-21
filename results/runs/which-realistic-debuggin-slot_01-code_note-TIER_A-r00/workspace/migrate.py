import json
import os
import sys
from pathlib import Path

from state import MigrationState


class Migration:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.state = MigrationState(config_path)
        self.config = self._load_config()

    def _load_config(self):
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Config file {self.config_path} is corrupted. Starting with empty config.", file=sys.stderr)
            return {}

    def _save_config(self):
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)

    def add_version(self):
        if self.config.get("version") == 2:
            return
        self.config["version"] = 2

    def rename_items_to_entries(self):
        if "items" not in self.config:
            return
        self.config["entries"] = self.config["items"]

    def remove_old_items_key(self):
        if "items" not in self.config:
            return
        del self.config["items"]

    def run(self):
        steps = [
            ("add_version", self.add_version),
            ("rename_items_to_entries", self.rename_items_to_entries),
            ("remove_old_items_key", self.remove_old_items_key),
        ]
        stop_after_step = os.environ.get("MIGRATE_STOP_AFTER")

        for step_name, step_func in steps:
            if self.state.is_done(step_name):
                print(f"Skipping {step_name} (already done)")
                # Removed the early exit for MIGRATE_STOP_AFTER when step is already done.
                # This allows the tool to proceed and potentially fix the config if the state
                # file is ahead of the config file due to a prior interruption.
                continue

            print(f"Running {step_name}...")
            step_func()  # Modifies self.config in memory

            # Ensure config is saved successfully before marking the step as done.
            # If saving fails, the step is not marked done, allowing re-run on resume.
            try:
                self._save_config()
            except Exception as e:
                print(f"Error saving config after {step_name}: {e}", file=sys.stderr)
                sys.exit(1)  # Exit with error if config save fails

            self.state.mark_done(step_name)  # This saves the state.

            if stop_after_step == step_name:
                print(f"Interrupted after {step_name}. Exiting.")
                sys.exit(0)

        if self.state.all_done(len(steps)):
            print("Migration complete.")
        else:
            print("Migration partially complete. Re-run to finish.")

