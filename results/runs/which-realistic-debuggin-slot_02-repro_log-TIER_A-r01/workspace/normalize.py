def normalize_email(email: str) -> str:
    """
    Normalizes an email address by stripping leading/trailing whitespace
    and converting it to lowercase.
    """
    return email.strip().lower()
