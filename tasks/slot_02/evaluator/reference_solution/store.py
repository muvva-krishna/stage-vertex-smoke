"""AI-generated reference solution overlay for slot_02 (evaluator-only).

Fix: record the NORMALIZED key in `seen`, matching the normalized lookup,
so every spelling of an address maps to one entry.
"""
import json
import os

from normalize import normalize_key


def empty_store():
    return {"rows": [], "seen": []}


def load_store(path):
    if not os.path.exists(path):
        return empty_store()
    with open(path) as f:
        data = json.load(f)
    return {"rows": list(data.get("rows", [])), "seen": list(data.get("seen", []))}


def save_store(path, store):
    with open(path, "w") as f:
        json.dump(store, f, indent=2)


def add(store, row):
    """Add row unless its email was seen. Returns True if stored."""
    key = normalize_key(row["email"])
    if key in store["seen"]:
        return False
    store["seen"].append(key)
    store["rows"].append(row)
    return True
