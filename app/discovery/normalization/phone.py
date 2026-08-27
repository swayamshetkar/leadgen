import re
from typing import Optional
import phonenumbers


class PhoneNormalizer:
    @staticmethod
    def normalize_e164(phone: Optional[str], default_region: str = "IN") -> Optional[str]:
        if not phone:
            return None
        raw = phone.strip()
        try:
            parsed = phonenumbers.parse(raw, default_region)
            if phonenumbers.is_possible_number(parsed) or phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except Exception:
            pass

        # Try US / GB
        for r in ("US", "GB", None):
            try:
                parsed = phonenumbers.parse(raw, r)
                if phonenumbers.is_possible_number(parsed):
                    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            except Exception:
                continue

        # Fallback: digits only
        digits = re.sub(r"\D", "", raw)
        return f"+{digits}" if len(digits) >= 10 else raw

    @staticmethod
    def digits_key(phone: Optional[str]) -> Optional[str]:
        if not phone:
            return None
        digits = re.sub(r"\D", "", phone)
        # Return last 10 digits to match local vs country-coded numbers
        return digits[-10:] if len(digits) >= 10 else digits if len(digits) >= 7 else None
