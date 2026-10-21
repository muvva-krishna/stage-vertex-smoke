import json
import os


def load_state(path):
    """Load migration state from a marker file."""
    marker_path = f"{path}.migration.json"
    if os.path.exists(marker_path):
        with open(marker_path, 'r') as f:
            return json.load(f)
    return {"done": []}


def save_state(path, state):
    """Save migration state to a marker file."""
    marker_path = f"{path}.migration.json"
    with open(marker_path, 'w') as f:
        json.dump(state, f, indent=2)


def is_done(path, step):
    """Check if a step is already done."""
    state = load_state(path)
    return step in state.get("done", [])


def mark_done(path, step):
    """Mark a step as done."""
    state = load_state(path)
    if step not in state.get("done", []):
        state.setdefault("done", []).append(step)
        save_state(path, state)


def reset_state(path):
    """Reset migration state."""
    save_state(path, {"done": []})
