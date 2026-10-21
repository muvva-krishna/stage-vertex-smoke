"""Migration marker persistence (which steps are recorded done)."""
import json
import os


def load_marker(path):
    if not os.path.exists(path):
        return {"done": []}
    with open(path) as f:
        data = json.load(f)
    return {"done": list(data.get("done", []))}


def save_marker(path, marker):
    with open(path, "w") as f:
        json.dump({"done": marker["done"]}, f, indent=2)


def mark_done(path, step):
    marker = load_marker(path)
    if step not in marker["done"]:
        marker["done"].append(step)
    save_marker(path, marker)
