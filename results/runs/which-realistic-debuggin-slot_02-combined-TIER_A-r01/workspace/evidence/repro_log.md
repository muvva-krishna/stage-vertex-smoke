# Reproduction log (captured from actual runs)

```
$ printf 'name,email\nAnn,A@x.com\nAnn2, a@x.com\nAnn3,A@X.COM \n' > in.csv
$ python3 importer.py in.csv store.json
imported 3 of 3 row(s)
rc=0
```

All three spellings of the address were stored. Re-running the import over
the same store keeps all three rows; no error is reported.
