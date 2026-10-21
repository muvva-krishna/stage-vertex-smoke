import argparse
import csv
import json
import sys
from store import Store
from normalize import normalize_email # Import the new function

def main():
    parser = argparse.ArgumentParser(description="Import contacts from a CSV file.")
    parser.add_argument("csv_file", help="Path to the CSV file.")
    parser.add_argument("store_file", help="Path to the JSON store file.")
    args = parser.parse_args()

    store = Store(args.store_file)
    total_rows = 0
    imported_rows = 0

    try:
        with open(args.csv_file, mode='r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                total_rows += 1
                name = row.get('name')
                email = row.get('email')

                if not name or not email:
                    print(f"Skipping row {total_rows}: missing name or email.", file=sys.stderr)
                    continue

                normalized_email = normalize_email(email) # Normalize the email

                # Check against the normalized seen list
                if normalized_email not in store.seen:
                    # Add original email to rows, normalized email to seen
                    store.add_contact(name, email, normalized_email)
                    imported_rows += 1
                else:
                    print(f"Skipping duplicate email: {email} (normalized to {normalized_email})", file=sys.stderr)

        store.save()
        print(f"imported {imported_rows} of {total_rows} row(s)")

    except FileNotFoundError:
        print(f"Error: File not found - {args.csv_file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
