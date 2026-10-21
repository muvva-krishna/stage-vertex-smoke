import argparse
import csv
import os
from store import Store

def main():
    parser = argparse.ArgumentParser(description='Import contacts from a CSV file.')
    parser.add_argument('csv_file', help='Path to the CSV file')
    parser.add_argument('store_file', help='Path to the JSON store file')
    args = parser.parse_args()

    contacts_to_import = []
    try:
        with open(args.csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                contacts_to_import.append(row)
    except FileNotFoundError:
        print(f"Error: CSV file '{args.csv_file}' not found.")
        return

    store = Store(args.store_file)

    initial_row_count = store.count()
    imported_count = 0
    for contact in contacts_to_import:
        if store.add(contact):
            imported_count += 1

    store.save()

    print(f"imported {imported_count} of {len(contacts_to_import)} row(s)")

if __name__ == '__main__':
    main()
