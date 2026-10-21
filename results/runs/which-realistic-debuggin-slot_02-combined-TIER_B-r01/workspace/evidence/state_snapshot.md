# State snapshot (store.json after the run above)

```json
{
  "rows": [
    {"name": "Ann", "email": "A@x.com"},
    {"name": "Ann2", "email": " a@x.com"},
    {"name": "Ann3", "email": "A@X.COM "}
  ],
  "seen": ["A@x.com", " a@x.com", "A@X.COM "]
}
```

Observation: the `seen` list holds three entries for what is plausibly one
address — each recorded exactly as spelled in its row.
