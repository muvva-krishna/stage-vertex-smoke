import json

def load_store(store_path):
    """Loads the JSON store. Returns an empty store if file not found or invalid."""
    try:
        with open(store_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"rows": [], "seen": set()}

def save_store(store_path, store):
    """Saves the store to a JSON file."""
    with open(store_path, 'w') as f:
        json.dump(store, f, indent=4)
