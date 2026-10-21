import re

def normalize_email(email):
    """Normalize email address by lowercasing and stripping whitespace."""
    return re.sub(r'^\s+|\s+$', '', email).lower()
