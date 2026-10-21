"""Key normalization shared by the importer pipeline."""
def normalize_key(s):
    return s.strip().lower()
