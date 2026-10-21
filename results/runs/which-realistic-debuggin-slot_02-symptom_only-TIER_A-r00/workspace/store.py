import json
from normalize import normalize_email

class Store:
    def __init__(self, path):
        self.path = path
        self.rows = []
        self.seen = set()
        self._load()

    def _load(self):
        try:
            with open(self.path, 'r') as f:
                data = json.load(f)
                self.rows = data.get('rows', [])
                # When loading, normalize existing emails for the 'seen' set
                self.seen = {normalize_email(row['email']) for row in self.rows}
        except FileNotFoundError:
            pass # New store

    def add(self, row):
        email = row['email']
        normalized_email = normalize_email(email)
        if normalized_email not in self.seen:
            self.rows.append(row)
            self.seen.add(normalized_email)
            return True
        return False

    def has_seen(self, email):
        normalized_email = normalize_email(email)
        return normalized_email in self.seen

    def save(self):
        with open(self.path, 'w') as f:
            json.dump({'rows': self.rows, 'seen': list(self.seen)}, f, indent=2)
