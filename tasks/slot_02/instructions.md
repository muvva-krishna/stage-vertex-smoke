# csvimport — duplicates with different spelling slip through dedup

`csvimport` reads `name,email` rows from a CSV file into a JSON store,
skipping addresses it has already seen:

```
python3 importer.py contacts.csv store.json
```

## Failure report

A mailing list exported from two systems spells the same address
differently (`A@x.com` vs ` a@x.com` vs `A@X.COM `). Importing all three
stores three rows and reports `imported 3 of 3 row(s)` instead of
collapsing them to one. Distinct addresses import fine.

## Requirements

1. Spelling variants of one address (case and surrounding whitespace)
   collapse to a single stored row — the first spelling seen wins.
2. Genuinely distinct addresses are all kept.
3. Re-importing overlapping data adds no duplicates (repeat imports stable).
4. `store.json` stays `{"rows": [...], "seen": [...]}` JSON; each row stays
   `{"name": ..., "email": ...}`.
5. `importer.py --help` works, exit 0. The printed summary stays
   `imported <kept> of <total> row(s)`.
6. Do not add dependencies (standard library only), and do not touch
   anything outside `tasks/slot_02/repo/`.

## Verification guidance

Import a CSV mixing case/space variants with distinct addresses, inspect
the stored rows, then re-import overlapping data and confirm nothing is
added twice.
