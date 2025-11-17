import re
import string


def sanitize_filename(name: str) -> str:
    """
    Sanitizes a string to be used as a valid filename.
    - Converts to lowercase.
    - Replaces spaces and common separators with hyphens.
    - Removes characters that are not alphanumeric or hyphens.
    - Trims leading/trailing hyphens.
    """
    # Convert to lowercase
    name = name.lower()

    # Replace spaces and other separators with hyphens
    name = re.sub(r'[\s_.]+', '-', name)

    # Allow only alphanumeric characters and hyphens
    allowed_chars = string.ascii_letters + string.digits + '-'
    name = ''.join(c for c in name if c in allowed_chars)

    # Replace multiple hyphens with a single one
    name = re.sub(r'--+', '-', name)

    # Trim leading/trailing hyphens
    name = name.strip('-')

    return name
