import re
from typing import Optional


class EmailNormalizer:
    @staticmethod
    def normalize(email: Optional[str]) -> Optional[str]:
        if not email:
            return None
        clean = email.strip().lower()
        if re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", clean):
            return clean
        return None
