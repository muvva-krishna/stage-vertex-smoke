import re

def normalize_email(email):
    """Normalize email address by lowercasing and stripping whitespace."""
    if email is None:
        return None
    return email.strip().lower()

def normalize_name(name):
    """Normalize name by stripping whitespace."""
    if name is None:
        return None
    return name.strip()
