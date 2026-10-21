import json
from normalize import normalize_email

class Store:
    def __init__(self, json_path):
        self.json_path = json_path
        self.rows = []
        self.seen = set()
        self._load()

    def _load(self):
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.rows = data.get("rows", [])
                # Normalize emails when loading into the seen set
                self.seen = {normalize_email(email) for email in data.get("seen", [])}
        except FileNotFoundError:
            pass # Store will be created on first save

    def add_row(self, row):
        self.rows.append(row)

    def save(self):
        data = {"rows": self.rows, "seen": list(self.seen)}
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
