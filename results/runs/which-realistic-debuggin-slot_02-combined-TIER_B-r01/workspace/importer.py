import csv
import json
import sys

from normalize import normalize_email, normalize_name

def import_csv(csv_path, store_path):
    """Imports contacts from a CSV file into a JSON store.

    Args:
        csv_path: Path to the input CSV file.
        store_path: Path to the JSON store file.
    """
    try:
        with open(store_path, 'r') as f:
            store = json.load(f)
    except FileNotFoundError:
        store = {"rows": [], "seen": set()}
    except json.JSONDecodeError:
        store = {"rows": [], "seen": set()}

    seen_emails = set(store.get("seen", []))
    rows_to_add = []
    total_rows = 0

    with open(csv_path, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            name = row.get('name')
            email = row.get('email')

            if not name or not email:
                print(f"Skipping row with missing name or email: {row}", file=sys.stderr)
                continue

            normalized_email = normalize_email(email)

            if normalized_email not in seen_emails:
                seen_emails.add(normalized_email)
                rows_to_add.append({
                    "name": normalize_name(name),
                    "email": normalized_email
                })

    store["rows"].extend(rows_to_add)
    store["seen"] = list(seen_emails)

    with open(store_path, 'w') as f:
        json.dump(store, f, indent=4)

    print(f"imported {len(rows_to_add)} of {total_rows} row(s)")

def main():
    if len(sys.argv) != 3:
        print("Usage: python importer.py <csv_path> <store_path>")
        sys.exit(1)

    csv_path = sys.argv[1]
    store_path = sys.argv[2]
    import_csv(csv_path, store_path)

if __name__ == "__main__":
    main()
