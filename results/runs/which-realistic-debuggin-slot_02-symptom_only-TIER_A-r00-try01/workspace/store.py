"""Deduplicating JSON row store, keyed by email."""
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
    key = row["email"]
    if normalize_key(key) in store["seen"]:
        return False
    store["seen"].append(key)
    store["rows"].append(row)
    return True
