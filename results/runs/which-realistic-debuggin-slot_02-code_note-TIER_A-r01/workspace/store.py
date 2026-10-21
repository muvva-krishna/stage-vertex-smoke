import json
from normalize import normalize_email

class Store:
    def __init__(self, filename):
        self.filename = filename
        self.data = {"rows": [], "seen": []}
        self._load()

    def _load(self):
        try:
            with open(self.filename, 'r') as f:
                self.data = json.load(f)
            # Normalize existing 'seen' emails on load to handle legacy data
            self.data["seen"] = [normalize_email(e) for e in self.data["seen"]]
        except FileNotFoundError:
            pass # File will be created on first save

    def _save(self):
        with open(self.filename, 'w') as f:
            json.dump(self.data, f, indent=2)

    def add_row(self, row):
        email = row.get('email')
        if email:
            normalized_email = normalize_email(email)
            if normalized_email not in self.data["seen"]:
                self.data["rows"].append(row) # Store original row
                self.data["seen"].append(normalized_email)
                self._save()
                return True
        return False
