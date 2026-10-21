import json
from normalize import normalize_email

class Store:
    def __init__(self, path):
        self.path = path
        self.rows = []
        self.seen = set() # Stores normalized emails
        self._load()

    def _load(self):
        try:
            with open(self.path, 'r') as f:
                data = json.load(f)
                self.rows = data.get('rows', [])
                # Normalize existing 'seen' entries upon loading
                self.seen = set(normalize_email(email) for email in data.get('seen', []))
        except FileNotFoundError:
            pass # Will be created on first save
        except json.JSONDecodeError:
            # Handle corrupted JSON or empty file by starting fresh
            self.rows = []
            self.seen = set()

    def add(self, row):
        email = row.get('email')
        if not email:
            return False # Skip rows without an email

        normalized_email = normalize_email(email)

        if normalized_email in self.seen:
            return False # Already seen this email (normalized)

        self.seen.add(normalized_email)
        self.rows.append(row) # Store the original row
        return True

    def save(self):
        with open(self.path, 'w') as f:
            # When saving, convert the set of normalized emails back to a list
            json.dump({'rows': self.rows, 'seen': list(self.seen)}, f, indent=2)

    def count(self):
        return len(self.rows)
