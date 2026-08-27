import re
from typing import Optional
from app.utils.text import clean_text


class BusinessNormalizer:
    # Common corporate, legal, and clinic suffixes to strip for canonical matching
    LEGAL_SUFFIXES = [
        r"\bpvt\.?\s*ltd\.?\b",
        r"\bprivate\s+limited\b",
        r"\bltd\.?\b",
        r"\bllc\.?\b",
        r"\binc\.?\b",
        r"\bcorporation\b",
        r"\bcorp\.?\b",
        r"\bco\.?\b",
        r"\bllp\.?\b",
        r"\bplc\.?\b",
    ]

    GENERIC_SUFFIXES = [
        r"\bclinic\b",
        r"\bcenter\b",
        r"\bcentre\b",
        r"\bhospital\b",
        r"\bcare\b",
        r"\bservices\b",
        r"\bgroup\b",
        r"\bsolutions\b",
        r"\bconsultancy\b",
    ]

    @classmethod
    def normalize_name(cls, name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        cleaned = clean_text(name)
        # Strip legal suffixes
        for pattern in cls.LEGAL_SUFFIXES:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
        # Clean trailing commas or dashes
        cleaned = re.sub(r"[-–—,]+$", "", cleaned).strip()
        return cleaned if cleaned else None

    @classmethod
    def match_key(cls, name: Optional[str]) -> Optional[str]:
        """
        Aggressive normalization key for fuzzy deduplication:
        Strips punctuation, whitespace, legal and generic suffixes.
        """
        norm = cls.normalize_name(name)
        if not norm:
            return None
        key = norm.lower()
        for pattern in cls.GENERIC_SUFFIXES:
            key = re.sub(pattern, "", key, flags=re.IGNORECASE)
        # Keep only alphanumeric characters
        key = re.sub(r"[^a-z0-9]", "", key)
        return key if len(key) >= 3 else None
