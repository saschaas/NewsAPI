import hashlib
from typing import Union


def generate_content_hash(content: Union[str, bytes]) -> str:
    """
    Generate SHA-256 hash of content for duplicate detection

    Args:
        content: Text or bytes to hash

    Returns:
        Hexadecimal hash string
    """
    if isinstance(content, str):
        content = content.encode('utf-8')

    return hashlib.sha256(content).hexdigest()


def normalize_content(content: str) -> str:
    """
    Normalize content before hashing to improve duplicate detection

    Args:
        content: Raw content text

    Returns:
        Normalized content
    """
    # Remove extra whitespace
    normalized = ' '.join(content.split())

    # Convert to lowercase for consistent hashing
    normalized = normalized.lower()

    # Remove common noise characters
    noise_chars = ['\r', '\n', '\t']
    for char in noise_chars:
        normalized = normalized.replace(char, ' ')

    return normalized.strip()
