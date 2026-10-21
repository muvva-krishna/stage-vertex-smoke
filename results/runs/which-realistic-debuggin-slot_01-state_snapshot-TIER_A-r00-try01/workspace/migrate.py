import os
import json
from pathlib import Path
import sys
from typing import Callable, List, Tuple
import tempfile


# --- Logging --- #
def _log(message: str):
    print(f"[migrate] {message}")


# --- Config File Operations ---
def _load_config(config_path: Path) -> dict:
    with open(config_path, "r") as f:
        return json.load(f)


def _save_config(config_path: Path, config: dict):
    # Write to a temporary file first, then atomically replace the original
    temp_file_path = None
    try:
        # Create a temporary file in the same directory as the target config file
        # This is crucial for os.replace to be atomic across filesystems
        with tempfile.NamedTemporaryFile(mode="w", delete=False, dir=config_path.parent, encoding="utf-8") as tmp_f:
            json.dump(config, tmp_f, indent=2)
            tmp_f.flush()  # Ensure all buffered data is written to the OS
            os.fsync(tmp_f.fileno()) # Ensure OS buffers are flushed to disk
        
        temp_file_path = Path(tmp_f.name)
        
        # Atomically replace the original file with the temporary file
        os.replace(temp_file_path, config_path)
    except Exception as e:
        _log(f"Error saving config atomically: {e}")
        raise # Re-raise to ensure the process doesn't continue with a failed save
    finally:
        # Clean up the temporary file if it still exists (e.g., if os.replace failed)
        if temp_file_path and temp_file_path.exists():
            temp_file_path.unlink()


# --- Migration Steps ---
def add_version(config: dict):
    config["version"] = 2

def rename_items_to_entries(config: dict):
    if "items" in config:
        config["entries"] = config.pop("items")

def remove_items(config: dict):
    # This step is mostly for idempotency, ensuring 'items' is gone
    # even if rename_items_to_entries was interrupted.
    if "items" in config:
        del config["items"]


# --- Verification Functions ---
def verify_add_version(config: dict) -> bool:
    return config.get("version") == 2

def verify_rename_items_to_entries(config: dict) -> bool:
    return "entries" in config and "items" not in config

def verify_remove_items(config: dict) -> bool:
    return "items" not in config


STEPS: List[Tuple[str, Callable[[dict], None], Callable[[dict], bool]]] = [
    ("add_version", add_version, verify_add_version),
    ("rename_items_to_entries", rename_items_to_entries, verify_rename_items_to_entries),
    ("remove_items", remove_items, verify_remove_items),
]


# --- Migration State Management ---
# (Assumed to be in state.py, but included here for context if needed)
# from state import MigrationState


# --- Main Migration Logic ---
def _run_step(config_path: Path, state, step_name: str, step_fn: Callable[[dict], None], verify_fn: Callable[[dict], bool]):
    # Load config *before* checking state, to use for verification if step is marked done
    current_config_on_disk = _load_config(config_path)

    if state.is_done(step_name):
        if verify_fn(current_config_on_disk):
            _log(f"Step '{step_name}' already done and verified in config.")
            return
        else:
            _log(f"WARNING: Step '{step_name}' marked done in state, but config does not reflect changes. Re-running step.")
            # Fall through to run the step again

    _log(f"Running step '{step_name}'...")
    # Reload config to ensure we're working with the absolute latest state
    config_to_modify = _load_config(config_path)
    step_fn(config_to_modify)
    
    _save_config(config_path, config_to_modify)

    # After saving, verify the change *before* marking as done in state
    config_after_save = _load_config(config_path) # Reload to ensure we read what's on disk
    if not verify_fn(config_after_save):
        _log(f"ERROR: Step '{step_name}' applied and saved, but verification failed. "
             f"Config file at '{config_path}' does not reflect the change. "
             f"This step will be re-attempted on next run.")
        # Do not mark as done. Raise an error to stop current migration,
        # so it can be re-run and re-attempt this step.
        raise RuntimeError(f"Verification failed for step '{step_name}' after save to '{config_path}'.")

    state.mark_done(step_name)
    state.save_state()
    _log(f"Step '{step_name}' done and verified.")

    if os.environ.get("MIGRATE_STOP_AFTER") == step_name:
        _log(f"MIGRATE_STOP_AFTER={step_name} set. Exiting.")
        sys.exit(0)


def _resume_migration(config_path: Path, marker_path: Path):
    from state import MigrationState # Import here to avoid circular dependency if state.py imports migrate.py
    state = MigrationState(marker_path)
    _log(f"Resuming migration for {config_path}...")

    # Check if already fully migrated by verifying all steps
    config = _load_config(config_path)
    all_steps_verified = all(verify_fn(config) for _, _, verify_fn in STEPS)
    if all_steps_verified:
        _log("Config already fully migrated. Exiting.")
        return

    for step_name, step_fn, verify_fn in STEPS:
        _run_step(config_path, state, step_name, step_fn, verify_fn)

    _log("Migration complete.")


# For cli.py to access steps
def get_step_names():
    return [name for name, _, _ in STEPS]


# For cli.py to run migration
def run_migration(config_path: Path, marker_path: Path):
    _resume_migration(config_path, marker_path)
