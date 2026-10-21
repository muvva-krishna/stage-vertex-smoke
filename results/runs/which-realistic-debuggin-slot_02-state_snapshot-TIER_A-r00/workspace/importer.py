"""csvimport CLI: import contacts from CSV into a dedup JSON store."""
import argparse
import csv
import sys

from store import add, load_store, save_store


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="csvimport",
        description="Import name,email rows from CSV, skipping duplicates.")
    p.add_argument("csv_file", help="input CSV with name,email columns")
    p.add_argument("store_file", help="output JSON store (created/extended)")
    args = p.parse_args(argv)
    store = load_store(args.store_file)
    kept, total = 0, 0
    with open(args.csv_file, newline="") as f:
        for row in csv.DictReader(f):
            total += 1
            if add(store, {"name": row["name"], "email": row["email"]}):
                kept += 1
    save_store(args.store_file, store)
    print(f"imported {kept} of {total} row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
