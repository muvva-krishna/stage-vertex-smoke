import argparse
import csv
import json

from normalize import normalize_email
import store

def process_csv(csv_filepath, store_filepath):
    kept_rows = 0
    total_rows = 0

    with open(csv_filepath, 'r', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        rows_to_add = []
        for row in reader:
            total_rows += 1
            normalized_email = normalize_email(row["email"])
            if normalized_email not in store.seen:
                store.seen.add(normalized_email)
                rows_to_add.append(row)
                kept_rows += 1

    # Append new rows to the store
    store.rows.extend(rows_to_add)

    # Save the updated store
    with open(store_filepath, 'w') as f:
        json.dump({"rows": store.rows, "seen": list(store.seen)}, f, indent=2)

    print(f"imported {kept_rows} of {total_rows} row(s)")

def main():
    parser = argparse.ArgumentParser(description='Import contacts from a CSV file.')
    parser.add_argument('csv_filepath', help='Path to the CSV file')
    parser.add_argument('store_filepath', help='Path to the JSON store file')
    args = parser.parse_args()

    store.load(args.store_filepath)
    process_csv(args.csv_filepath, args.store_filepath)

if __name__ == '__main__':
    main()
