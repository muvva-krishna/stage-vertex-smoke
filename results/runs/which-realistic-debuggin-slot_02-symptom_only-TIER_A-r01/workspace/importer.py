import argparse
import csv
import json
import sys

from store import Store
from normalize import normalize_email # Import the new normalization function

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description="Import name/email pairs from a CSV into a JSON store."
    )
    parser.add_argument("csv_path", help="Path to the input CSV file")
    parser.add_argument("store_path", help="Path to the JSON store file")
    args = parser.parse_args(argv)

    store = Store()
    store.load(args.store_path)

    total_rows = 0
    kept_rows = 0

    with open(args.csv_path, "r", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            total_rows += 1
            original_email = row["email"]
            normalized_email = normalize_email(original_email)

            if normalized_email not in store.seen:
                # Store the original email, but track the normalized email in the 'seen' set
                store.rows.append({"name": row["name"], "email": original_email})
                store.seen.add(normalized_email)
                kept_rows += 1

    store.save(args.store_path)

    print(f"imported {kept_rows} of {total_rows} row(s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
