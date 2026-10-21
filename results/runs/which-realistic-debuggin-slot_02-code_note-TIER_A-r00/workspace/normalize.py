def normalize_email(email):
    """Normalizes an email address for comparison (case-insensitive, whitespace-stripped)."""
    return email.strip().lower()
