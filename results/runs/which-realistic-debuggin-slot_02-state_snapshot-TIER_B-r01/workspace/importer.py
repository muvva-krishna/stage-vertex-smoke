import csv
import json
import sys

from normalize import normalize_email, normalize_name
from store import Store

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 importer.py <csv_file> <store_file>")
        sys.exit(1)

    csv_file = sys.argv[1]
    store_file = sys.argv[2]

    store = Store(store_file)
    store.load()

    imported_count = 0
    total_rows = 0

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            name = normalize_name(row.get('name'))
            email = normalize_email(row.get('email'))

            if not name or not email:
                print(f"Skipping row with missing name or email: {row}")
                continue

            if email not in store.seen_emails:
                store.add_row(name, email)
                store.seen_emails.add(email)
                imported_count += 1
            else:
                # If email is already seen, update name if the current name is not empty
                # and the stored name for this email is empty or different.
                # This part is not strictly required by the prompt but is a good practice.
                # For this task, we only care about deduplication based on email.
                pass

    store.save()
    print(f"imported {imported_count} of {total_rows} row(s)")

if __name__ == "__main__":
    main()
