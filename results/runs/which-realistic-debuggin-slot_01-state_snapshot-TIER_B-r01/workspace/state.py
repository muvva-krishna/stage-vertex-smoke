import json
import os

from typing import Any, Dict, List


class State:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.marker_path = f"{config_path}.migration.json"
        self.state: Dict[str, Any] = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if os.path.exists(self.marker_path):
            with open(self.marker_path, "r") as f:
                return json.load(f)
        return {"done": []}

    def save_state(self) -> None:
        with open(self.marker_path, "w") as f:
            json.dump(self.state, f, indent=2)

    def is_done(self, step: str) -> bool:
        return step in self.state.get("done", [])

    def mark_done(self, step: str) -> None:
        if step not in self.state["done"]:
            self.state["done"].append(step)
            self.save_state()

    def reset(self) -> None:
        self.state = {"done": []}
        self.save_state()


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)

def save_config(path: str, config: Dict[str, Any]) -> None:
    with open(path, "w") as f:
        json.dump(config, f, indent=2)

def migrate_v1_to_v2(config: Dict[str, Any]) -> Dict[str, Any]:
    if "items" not in config:
        return config
    new_config = {
        "version": 2,
        "entries": config["items"],
    }
    return new_config

def migrate_v2_to_v3(config: Dict[str, Any]) -> Dict[str, Any]:
    # No changes needed for v2 to v3 migration in this example.
    # This function is a placeholder for future migrations.
    return config

def migrate_config(config: Dict[str, Any], steps: List[str]) -> Dict[str, Any]:
    current_version = config.get("version", 1)

    if current_version == 1:
        config = migrate_v1_to_v2(config)
        current_version = 2

    if current_version == 2:
        config = migrate_v2_to_v3(config)
        current_version = 3

    # Add more migration steps here as needed

    return config


def migrate(config_path: str, stop_after: str | None = None) -> None:
    state = State(config_path)
    config = load_config(config_path)

    steps = ["add_version", "rename_items_to_entries"]

    if state.is_done("add_version") and state.is_done("rename_items_to_entries"):
        print("already-complete")
        return

    if not state.is_done("add_version"):
        if stop_after == "add_version":
            print("migration complete")
            return
        config = migrate_v1_to_v2(config)
        state.mark_done("add_version")

    if not state.is_done("rename_items_to_entries"):
        if stop_after == "rename_items_to_entries":
            print("migration complete")
            return
        config = migrate_v2_to_v3(config) # This should be migrate_v2_to_v3, but it's not used in the current logic
        state.mark_done("rename_items_to_entries")

    save_config(config_path, config)
    print("migration complete")


def get_migration_steps() -> List[str]:
    return ["add_version", "rename_items_to_entries"]


