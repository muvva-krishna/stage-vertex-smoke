# Code-path note

Expiry is decided in `cache.py` (`cache_get` and `prune_expired`) from a
stored stamp and the two clocks in `timeutil.py` (`now_s`, `now_ms`). Check
which clock stamps the entry at write time, which clock is read at check
time, and what units the TTL is expressed in — then follow the arithmetic.
(This note narrows the search region; it does not state the fix.)
