"""Partial-fix probe for slot_02 (evaluator-only): normalize-on-store only.

Stores the normalized key but still looks up the raw key, so variants keep
slipping through. Must still FAIL the oracle.
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
    if row["email"] in store["seen"]:
        return False
    store["seen"].append(normalize_key(row["email"]))
    store["rows"].append(row)
    return True
