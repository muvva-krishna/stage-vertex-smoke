# Code-path note

Dedup happens in `add` in `store.py`, which consults `normalize_key` from
`normalize.py` and the `seen` list persisted in the store. Trace what form
of the key goes into the membership test versus what form gets recorded —
and what the second spelling of an address therefore finds waiting for it.
(This note narrows the search region; it does not state the fix.)
