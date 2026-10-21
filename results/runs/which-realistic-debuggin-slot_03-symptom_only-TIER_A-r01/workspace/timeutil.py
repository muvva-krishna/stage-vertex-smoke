"""Clock helpers with a deterministic override for tests.

Set FAKE_NOW=<unix seconds> to freeze/advance time deterministically.
"""
import os
import time


def now_s():
    fake = os.environ.get("FAKE_NOW")
    if fake is not None:
        return float(fake)
    return time.time()


def now_ms():
    fake = os.environ.get("FAKE_NOW")
    if fake is not None:
        return float(fake) * 1000.0
    return time.time() * 1000.0
