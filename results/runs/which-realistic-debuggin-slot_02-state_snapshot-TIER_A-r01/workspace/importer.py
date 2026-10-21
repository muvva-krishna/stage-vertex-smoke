import argparse
import csv
import json
from store import Store
from normalize import normalize_email

def main():
    parser = argparse.ArgumentParser(description="Import contacts from a CSV file into a JSON store.")
    parser.add_argument("csv_file", help="Path to the CSV file")
    parser.add_argument("json_store", help="Path to the JSON store file")
    args = parser.parse_args()

    store = Store(args.json_store)
    total_rows = 0
    imported_rows = 0

    with open(args.csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            email = row.get("email")
            if email:
                normalized_email = normalize_email(email)
                if normalized_email not in store.seen:
                    store.add_row(row)
                    store.seen.add(normalized_email)
                    imported_rows += 1

    store.save()
    print(f"imported {imported_rows} of {total_rows} row(s)")

if __name__ == "__main__":
    main()
