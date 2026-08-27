import re
import urllib.parse
from typing import List, Dict, Any, Optional, Set
from bs4 import BeautifulSoup
import phonenumbers
from app.utils.text import clean_text
from app.models.candidate import EmailRecord, PhoneRecord


class ContactExtractor:
    """
    High-accuracy contact information extractor.
    Extracts emails, phone numbers, and physical addresses from HTML structure,
    text nodes, links (mailto:, tel:), and de-obfuscates masked contact signatures.
    """
    EMAIL_REGEX = re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    )
    OBFUSCATED_EMAIL_REGEX = re.compile(
        r"\b([A-Za-z0-9._%+-]+)\s*(?:\[at\]|\(at\)|\bat\b)\s*([A-Za-z0-9.-]+)\s*(?:\[dot\]|\(dot\)|\bdot\b)\s*([A-Za-z]{2,})\b",
        re.IGNORECASE
    )
    # Common dummy, template or asset placeholder emails
    IGNORED_EMAIL_DOMAINS = {
        "example.com", "domain.com", "email.com", "yourdomain.com",
        "mysite.com", "sentry.io", "wixpress.com", "wix.com", "wordpress.org"
    }
    IGNORED_EMAIL_PREFIXES = {
        "user@", "test@", "info@yourdomain.com", "name@", "username@"
    }

    PHONE_REGEX = re.compile(
        r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,5}"
    )

    def extract_contacts(self, html: str, page_url: str) -> Dict[str, Any]:
        if not html:
            return {"emails": [], "phone_numbers": [], "address": None}

        soup = BeautifulSoup(html, "lxml")
        
        # Remove noisy tags
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()

        emails = self._extract_emails(soup, page_url)
        phones = self._extract_phones(soup, page_url)
        address = self._extract_address(soup)

        return {
            "emails": emails,
            "phone_numbers": phones,
            "address": address
        }

    def _extract_emails(self, soup: BeautifulSoup, page_url: str) -> List[EmailRecord]:
        seen_emails: Set[str] = set()
        email_records: List[EmailRecord] = []

        # 1. mailto: links
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.lower().startswith("mailto:"):
                raw_mail = href[7:].split("?")[0].strip()
                self._add_email(raw_mail, seen_emails, email_records, page_url, "mailto")

        # 2. Text body matching
        text = soup.get_text(separator=" ")
        for match in self.EMAIL_REGEX.findall(text):
            self._add_email(match, seen_emails, email_records, page_url, "html_text")

        # 3. De-obfuscate emails
        for user, domain, tld in self.OBFUSCATED_EMAIL_REGEX.findall(text):
            reconstructed = f"{user}@{domain}.{tld}".strip()
            self._add_email(reconstructed, seen_emails, email_records, page_url, "deobfuscated")

        return email_records

    def _add_email(
        self,
        email_str: str,
        seen: Set[str],
        records: List[EmailRecord],
        page_url: str,
        source_type: str
    ):
        email_clean = email_str.strip().lower()
        if not email_clean or email_clean in seen:
            return

        # Exclude asset files accidentally matched as extensions
        if any(email_clean.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js"]):
            return

        domain = email_clean.split("@")[-1] if "@" in email_clean else ""
        if domain in self.IGNORED_EMAIL_DOMAINS:
            return

        if any(email_clean.startswith(p) for p in self.IGNORED_EMAIL_PREFIXES):
            return

        seen.add(email_clean)
        records.append(EmailRecord(
            value=email_clean,
            verified=False,
            source_url=page_url,
            source_type=source_type
        ))

    def _extract_phones(self, soup: BeautifulSoup, page_url: str) -> List[PhoneRecord]:
        seen_phones: Set[str] = set()
        phone_records: List[PhoneRecord] = []

        # 1. tel: links
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.lower().startswith("tel:"):
                raw_tel = href[4:].split("?")[0].strip()
                self._add_phone(raw_tel, seen_phones, phone_records, page_url, "tel_link")

        # 2. Text matching across entire document body
        full_text = soup.get_text(separator=" ")
        for match in self.PHONE_REGEX.findall(full_text):
            self._add_phone(match, seen_phones, phone_records, page_url, "html_text")

        return phone_records

    def _add_phone(
        self,
        phone_str: str,
        seen: Set[str],
        records: List[PhoneRecord],
        page_url: str,
        source_type: str
    ):
        raw_clean = clean_text(phone_str)
        # Strip trailing punctuation
        raw_clean = re.sub(r"[^\d+]+$", "", raw_clean).strip()
        
        # Check digit count (must have at least 7 digits to be a phone number)
        digits = re.sub(r"\D", "", raw_clean)
        if len(digits) < 7 or len(digits) > 15:
            return

        # Attempt standard E.164 parsing with phonenumbers
        formatted = None
        for default_region in ("IN", "US", "GB", None):
            try:
                parsed = phonenumbers.parse(raw_clean, default_region)
                if phonenumbers.is_possible_number(parsed) or phonenumbers.is_valid_number(parsed):
                    formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                    break
            except Exception:
                continue

        final_val = formatted if formatted else raw_clean
        if final_val in seen:
            return

        seen.add(final_val)
        records.append(PhoneRecord(
            value=final_val,
            raw_value=raw_clean,
            source_url=page_url,
            source_type=source_type
        ))

    def _extract_address(self, soup: BeautifulSoup) -> Optional[str]:
        # 1. <address> tag
        addr_tag = soup.find("address")
        if addr_tag:
            addr_text = clean_text(addr_tag.get_text())
            if len(addr_text) > 10:
                return addr_text

        # 2. Elements with address class/itemprop
        addr_elem = soup.find(attrs={"itemprop": "address"}) or soup.find(
            class_=lambda c: c and ("address" in str(c).lower() or "location" in str(c).lower())
        )
        if addr_elem:
            text = clean_text(addr_elem.get_text())
            if len(text) > 15 and len(text) < 300:
                return text

        return None
