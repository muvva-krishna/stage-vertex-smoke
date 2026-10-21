import argparse
import csv
import json
import sys

from normalize import normalize_email


def main():
    parser = argparse.ArgumentParser(
        description="Import contacts from a CSV file into a JSON store."
    )
    parser.add_argument(
        "csv_file", help="Path to the CSV file containing contacts."
    )
    parser.add_argument(
        "json_store", help="Path to the JSON file for storing contacts."
    )
    args = parser.parse_args()

    try:
        with open(args.json_store, "r+", encoding="utf-8") as f:
            store = json.load(f)
    except FileNotFoundError:
        store = {"rows": [], "seen": []}
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {args.json_store}", file=sys.stderr)
        sys.exit(1)

    initial_rows_count = len(store["rows"])
    initial_seen_count = len(store["seen"])

    # Normalize existing 'seen' emails for comparison
    # This handles cases where 'seen' might contain original emails from previous runs
    # or if it already contains normalized emails.
    normalized_seen = {normalize_email(email) for email in store["seen"]}

    imported_count = 0
    total_rows_in_csv = 0

    try:
        with open(args.csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_rows_in_csv += 1
                email = row.get("email")
                name = row.get("name")

                if not email or not name:
                    print(
                        f"Skipping row due to missing name or email: {row}",
                        file=sys.stderr,
                    )
                    continue

                normalized_email = normalize_email(email)

                if normalized_email not in normalized_seen:
                    store["rows"].append({"name": name, "email": email})
                    store["seen"].append(normalized_email) # Store normalized email in 'seen' list
                    normalized_seen.add(normalized_email) # Add normalized to the set for checks
                    imported_count += 1

    except FileNotFoundError:
        print(f"Error: CSV file not found at {args.csv_file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred during CSV processing: {e}", file=sys.stderr)
        sys.exit(1)

    if imported_count > 0:
        with open(args.json_store, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2)

    print(f"imported {imported_count} of {total_rows_in_csv} row(s)")


if __name__ == "__main__":
    main()
