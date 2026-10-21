# Symptom

Importing a CSV where the same address appears with different case or
surrounding spaces stores one row per spelling instead of deduplicating:

```
name,email
Ann,A@x.com
Ann2, a@x.com
Ann3,A@X.COM 
```

```
$ python3 importer.py in.csv store.json
imported 3 of 3 row(s)
```

Expected: `imported 1 of 3 row(s)` with a single stored row. Distinct
addresses import normally, so the dedup path — not the CSV parsing — is
where the variants escape.
