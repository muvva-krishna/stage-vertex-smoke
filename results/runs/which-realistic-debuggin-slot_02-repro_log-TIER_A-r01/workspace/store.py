import json
import sys
from normalize import normalize_email # Import normalize_email here too for loading existing seen emails

class Store:
    def __init__(self, filename):
        self.filename = filename
        self.data = {"rows": [], "seen": []}
        self._load()

    def _load(self):
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
                # Ensure all emails in the 'seen' list are normalized upon loading
                # This handles cases where a store file might have been created
                # before normalization was implemented or if it contains mixed data.
                self.data["seen"] = [normalize_email(e) for e in self.data["seen"]]
        except FileNotFoundError:
            # File doesn't exist, start with empty data
            pass
        except json.JSONDecodeError:
            # File is empty or malformed, start with empty data
            print(f"Warning: {self.filename} is empty or malformed. Starting with empty store.", file=sys.stderr)
            self.data = {"rows": [], "seen": []}

    def save(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2)

    @property
    def rows(self):
        return self.data["rows"]

    @property
    def seen(self):
        return self.data["seen"]

    # Modified to accept normalized_email for the 'seen' list
    def add_contact(self, name, original_email, normalized_email):
        self.data["rows"].append({"name": name, "email": original_email})
        self.data["seen"].append(normalized_email)
