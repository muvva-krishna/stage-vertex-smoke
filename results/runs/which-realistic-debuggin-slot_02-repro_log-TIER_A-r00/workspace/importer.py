import argparse
import csv
import json

from store import Store
from normalize import normalize_email

def main():
    parser = argparse.ArgumentParser(description='Import contacts from a CSV file.')
    parser.add_argument('csv_file', help='Path to the CSV file')
    parser.add_argument('json_store', help='Path to the JSON store file')
    args = parser.parse_args()

    store = Store(args.json_store)
    total_rows = 0
    imported_rows = 0

    with open(args.csv_file, mode='r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            total_rows += 1
            name = row.get('name')
            email = row.get('email')

            if not email:
                continue

            normalized_email = normalize_email(email)

            if store.has_seen(normalized_email):
                continue

            store.add_row({'name': name, 'email': email})
            store.mark_as_seen(normalized_email)
            imported_rows += 1

    store.save()
    print(f'imported {imported_rows} of {total_rows} row(s)')

if __name__ == '__main__':
    main()
