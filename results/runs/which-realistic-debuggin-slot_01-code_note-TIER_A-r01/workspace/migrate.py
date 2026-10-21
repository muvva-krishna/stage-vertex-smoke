import json
from pathlib import Path
import os

import state as state_mod

def add_version(cfg: dict) -> dict:
    cfg["version"] = 2
    return cfg

def rename_items_to_entries(cfg: dict) -> dict:
    if "items" in cfg:
        cfg["entries"] = cfg["items"]
        del cfg["items"]
    return cfg

def remove_items(cfg: dict) -> dict:
    if "items" in cfg:
        del cfg["items"]
    return cfg


STEPS = [
    ("add_version", add_version),
    ("rename_items_to_entries", rename_items_to_entries),
    ("remove_items", remove_items),
]

def migrate(cfg_path: Path, stop_after_step: str | None = None) -> None:
    state_path = cfg_path.with_suffix(".migration.json")

    # Load config
    with open(cfg_path, "r") as f:
        cfg = json.load(f)

    state = state_mod.load_state(state_path)

    # Check if already complete
    if state_mod.is_complete(state, [s[0] for s in STEPS]):
        print("Migration already complete. No changes made.")
        return

    # Apply steps
    config_changed_in_this_run = False
    for step_name, step_func in STEPS:
        if state_mod.is_done(state, step_name):
            print(f"Step '{step_name}' already done. Skipping.")
            continue

        print(f"Running step '{step_name}'...")
        
        cfg_before_step_dump = json.dumps(cfg, indent=2)
        
        cfg = step_func(cfg)

        cfg_after_step_dump = json.dumps(cfg, indent=2)

        # Always save the config to disk after a step has been executed,
        # before marking the step as done in the state file.
        # This ensures that the config on disk reflects the in-memory state
        # after the step, even if the step was idempotent and didn't change
        # the config from its *previous* state (e.g., if version:2 was already there).
        with open(cfg_path, "w") as f:
            f.write(cfg_after_step_dump)
        
        if cfg_before_step_dump != cfg_after_step_dump:
            config_changed_in_this_run = True
            print(f"Config updated after step '{step_name}'.")
        else:
            print(f"Config unchanged after step '{step_name}'. (Still saved to disk for consistency)")

        state_mod.mark_done(state, step_name)
        state_mod.save_state(state, state_path)

        if stop_after_step == step_name:
            print(f"Stopped after step '{step_name}' as requested.")
            return

    # Final message based on whether any changes were made during this run
    if config_changed_in_this_run:
        print("Migration complete. Config updated.")
    else:
        print("Migration complete. Config unchanged.")
