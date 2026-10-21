import csv
import json
import sys

from normalize import normalize_email

def import_contacts(csv_path, store_path):
    """Reads contacts from CSV and stores them, deduplicating by email."""
    try:
        with open(store_path, 'r') as f:
            store = json.load(f)
    except FileNotFoundError:
        store = {"rows": [], "seen": set()}
    except json.JSONDecodeError:
        store = {"rows": [], "seen": set()}

    seen_emails = set(store.get("seen", []))
    rows = store.get("rows", [])
    
    imported_count = 0
    total_count = 0

    with open(csv_path, 'r', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            total_count += 1
            name = row.get('name')
            email = row.get('email')

            if not name or not email:
                continue

            normalized_email = normalize_email(email)

            if normalized_email not in seen_emails:
                seen_emails.add(normalized_email)
                rows.append({"name": name, "email": email}) # Store original email
                imported_count += 1

    with open(store_path, 'w') as f:
        json.dump({"rows": rows, "seen": list(seen_emails)}, f, indent=4)

    print(f"imported {imported_count} of {total_count} row(s)")

def main():
    if len(sys.argv) != 3:
        print("Usage: python importer.py <csv_path> <store_path>")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    store_path = sys.argv[2]
    import_contacts(csv_path, store_path)

if __name__ == "__main__":
    main()
