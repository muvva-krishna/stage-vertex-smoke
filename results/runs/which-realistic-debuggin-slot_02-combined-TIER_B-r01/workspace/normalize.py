import re

def normalize_email(email):
    """Normalize email address by lowercasing and stripping whitespace."""
    return re.sub(r'^\s+|\s+$', '', email).lower()

def normalize_name(name):
    """Normalize name by stripping whitespace."""
    return re.sub(r'^\s+|\s+$', '', name)
