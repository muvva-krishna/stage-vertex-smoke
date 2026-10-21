# Accepted root-cause diagnosis — slot_02 (AI-written rubric, evaluator-only)

**Accepted root cause (20/20):** `store.add` tests membership with the
*normalized* key but records the *raw* key in `seen` — so the second
spelling of an address looks up a normalized form that was never stored,
misses, and is appended as a duplicate.

**Partial credit:**
- 14/20: identifies the normalized-vs-raw inconsistency but attributes it
  to the wrong side (e.g. claims lookup is raw and storage normalized).
- 8/20: right file/function (`store.add`) but wrong mechanism (e.g. blames
  CSV parsing, the importer loop, or `normalize_key` itself).
- 0/20: patch passes (e.g. normalizing rows at import) with a wrong stated
  cause, or claims dedup is entirely missing.

Valid alternative repairs accepted (e.g. normalizing at the importer
boundary and keeping raw storage, using a dict keyed by normalized form)
provided lookups and records use one consistent form. Grade the
explanation, not the patch shape.
