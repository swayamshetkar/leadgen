import re
import html
import unicodedata
from difflib import SequenceMatcher


def clean_text(text: str) -> str:
    """
    Cleans raw HTML text, decodes entities, normalizes unicode and collapses whitespace.
    """
    if not text:
        return ""
    # Decode HTML entities
    text = html.unescape(text)
    # Normalize unicode
    text = unicodedata.normalize("NFKC", text)
    # Remove control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", " ", text)
    # Collapse multiple whitespaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


def similarity_ratio(a: str, b: str) -> float:
    """
    Calculates normalized string similarity ratio between 0.0 and 1.0.
    """
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def extract_keywords(text: str) -> list[str]:
    """
    Extracts alphanumeric keyword tokens from text.
    """
    if not text:
        return []
    words = re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", text.lower())
    return list(dict.fromkeys(words))
