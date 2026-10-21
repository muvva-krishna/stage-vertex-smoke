import re

def normalize_email(email):
    """Normalize email address by lowercasing and stripping whitespace."""
    return email.strip().lower()

def normalize_row(row):
    """Normalize email in a row dictionary."""
    if 'email' in row:
        row['email'] = normalize_email(row['email'])
    return row
