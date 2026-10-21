import json

class Store:
    def __init__(self, filename):
        self.filename = filename
        self.rows = []
        self.seen_emails = set()

    def load(self):
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.rows = data.get('rows', [])
                # Ensure seen_emails is populated from loaded rows
                self.seen_emails = set(row['email'] for row in self.rows)
        except FileNotFoundError:
            # If the file doesn't exist, start with empty data
            self.rows = []
            self.seen_emails = set()
        except json.JSONDecodeError:
            # Handle cases where the file is empty or not valid JSON
            self.rows = []
            self.seen_emails = set()

    def add_row(self, name, email):
        self.rows.append({'name': name, 'email': email})

    def save(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump({'rows': self.rows, 'seen': list(self.seen_emails)}, f, indent=4)

