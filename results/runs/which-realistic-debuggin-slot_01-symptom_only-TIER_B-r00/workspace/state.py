import json
import os


class MigrationState:
    def __init__(self, marker_path):
        self.marker_path = marker_path
        self.done_steps = []
        self._load()

    def _load(self):
        if os.path.exists(self.marker_path):
            try:
                with open(self.marker_path, 'r') as f:
                    state = json.load(f)
                    self.done_steps = state.get("done", [])
            except (json.JSONDecodeError, FileNotFoundError):
                # If marker file is corrupted or missing, start fresh
                self.done_steps = []

    def save(self):
        with open(self.marker_path, 'w') as f:
            json.dump({"done": self.done_steps}, f)

    def add_step(self, step_name):
        if step_name not in self.done_steps:
            self.done_steps.append(step_name)
            self.save()

    def is_done(self, step_name):
        return step_name in self.done_steps

    def reset(self):
        self.done_steps = []
        if os.path.exists(self.marker_path):
            os.remove(self.marker_path)

    def is_fully_migrated(self, total_steps):
        return len(self.done_steps) == total_steps


def get_migration_state(output_path):
    marker_path = f"{output_path}.migration.json"
    return MigrationState(marker_path)


# Example usage (for testing purposes, not part of the core logic)
if __name__ == "__main__":
    # This part is for demonstration and testing, not for the actual tool execution
    # In a real scenario, cli.py would handle argument parsing and calling migrate
    pass
