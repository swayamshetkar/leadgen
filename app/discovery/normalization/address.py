import re
from typing import Optional
from app.utils.text import clean_text


class AddressNormalizer:
    @staticmethod
    def normalize(address: Optional[str]) -> Optional[str]:
        if not address:
            return None
        cleaned = clean_text(address)
        # Collapse multiple commas
        cleaned = re.sub(r",\s*,+", ", ", cleaned)
        return cleaned if len(cleaned) > 5 else None

    @staticmethod
    def extract_city(address: Optional[str], target_locations: list[str]) -> Optional[str]:
        if not address:
            return None
        addr_lower = address.lower()
        for loc in target_locations:
            if loc.lower() in addr_lower:
                return loc
        return None
