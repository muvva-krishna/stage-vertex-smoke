import csv
import json
import sys

from normalize import normalize_email

def import_contacts(csv_path, store_path):
    """Reads contacts from CSV and stores them, deduplicating by normalized email."""
    try:
        with open(store_path, 'r') as f:
            store = json.load(f)
    except FileNotFoundError:
        store = {"rows": [], "seen": set()}
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {store_path}. Starting with empty store.")
        store = {"rows": [], "seen": set()}

    seen_emails = set(store.get("seen", []))
    rows = store.get("rows", [])
    imported_count = 0
    total_rows = 0

    with open(csv_path, 'r', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            total_rows += 1
            name = row.get('name')
            email = row.get('email')

            if not name or not email:
                print(f"Skipping row with missing name or email: {row}")
                continue

            normalized = normalize_email(email)

            if normalized not in seen_emails:
                seen_emails.add(normalized)
                rows.append({"name": name, "email": email}) # Store original email
                imported_count += 1

    store["rows"] = rows
    store["seen"] = list(seen_emails) # Convert set back to list for JSON serialization

    with open(store_path, 'w') as f:
        json.dump(store, f, indent=4)

    print(f"imported {imported_count} of {total_rows} row(s)")

def main():
    if len(sys.argv) != 3:
        print("Usage: python importer.py <csv_path> <store_path>")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    store_path = sys.argv[2]
    import_contacts(csv_path, store_path)

if __name__ == "__main__":
    main()
