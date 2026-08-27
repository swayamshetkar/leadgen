from typing import Optional
from app.utils.urls import extract_domain, normalize_url


class DomainNormalizer:
    @staticmethod
    def normalize(url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        domain = extract_domain(url)
        return domain if domain else None

    @staticmethod
    def canonical_url(url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        return normalize_url(url)
