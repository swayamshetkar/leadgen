"""
Directory Extractor — extracts individual business entities from aggregator/directory pages.

When a search result points to a directory page (Practo, JustDial, etc.), instead of
treating the directory as the business, we attempt to extract the individual businesses
listed on that page.

Each extracted entity is isolated — phones and emails are strictly scoped to each business
card, preventing cross-contamination between different businesses.
"""
import re
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup, Tag
from app.models.candidate import CandidateBusiness, PhoneRecord, EmailRecord
from app.discovery.normalization.phone import PhoneNormalizer
from app.discovery.normalization.email import EmailNormalizer
from app.core.logging import get_logger

logger = get_logger("extractors.directory")

# Phone pattern
PHONE_RE = re.compile(
    r'(?:\+?91[-.\s]?)?(?:\(?0?[6-9]\d{9}\)?|(?:\d{2,4}[-.\s]?\d{6,8}))',
    re.UNICODE
)
# Email pattern
EMAIL_RE = re.compile(
    r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'
)


class DirectoryExtractor:
    """
    Extracts individual business entities from directory/listing pages.
    Each business is strictly isolated — no cross-contamination of contact data.
    """

    def extract_businesses(
        self,
        html: str,
        source_url: str,
        target_industry: str,
        target_location: str,
    ) -> List[CandidateBusiness]:
        """
        Parse a directory page and extract individual businesses.

        Returns a list of CandidateBusiness — each with only data
        visibly associated with that specific business card.
        """
        if not html:
            return []

        candidates: List[CandidateBusiness] = []

        try:
            soup = BeautifulSoup(html, "lxml")

            # Strategy 1: JSON-LD ItemList
            candidates.extend(self._extract_from_jsonld_itemlist(soup, source_url, target_industry, target_location))

            # Strategy 2: Structured card elements (common directory patterns)
            if not candidates:
                candidates.extend(self._extract_from_cards(soup, source_url, target_industry, target_location))

            # Strategy 3: Generic list items with names
            if not candidates:
                candidates.extend(self._extract_from_list_items(soup, source_url, target_industry, target_location))

        except Exception as e:
            logger.debug(f"Directory extraction failed for {source_url}: {e}")

        logger.info(f"Directory extractor found {len(candidates)} businesses from {source_url}")
        return candidates

    def _extract_from_jsonld_itemlist(
        self, soup: BeautifulSoup, source_url: str, industry: str, location: str
    ) -> List[CandidateBusiness]:
        """Extract from JSON-LD ItemList / ListItem structures."""
        import json
        candidates = []

        scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
        for script in scripts:
            try:
                data = json.loads(script.string or "{}")
                # Handle both single object and array
                if isinstance(data, list):
                    items = data
                else:
                    items = [data]

                for item in items:
                    item_type = item.get("@type", "")
                    # Direct business entity
                    if item_type in ("LocalBusiness", "MedicalBusiness", "Dentist",
                                     "Physician", "Restaurant", "Store", "Organization"):
                        cand = self._jsonld_item_to_candidate(item, source_url, industry, location)
                        if cand:
                            candidates.append(cand)
                    # ItemList containing businesses
                    elif item_type in ("ItemList", "BreadcrumbList"):
                        for list_item in item.get("itemListElement", []):
                            sub_item = list_item.get("item", list_item)
                            sub_type = sub_item.get("@type", "")
                            if sub_type not in ("ListItem", "BreadcrumbList", ""):
                                cand = self._jsonld_item_to_candidate(sub_item, source_url, industry, location)
                                if cand:
                                    candidates.append(cand)

            except (json.JSONDecodeError, Exception):
                continue

        return candidates

    def _jsonld_item_to_candidate(
        self, item: Dict[str, Any], source_url: str, industry: str, location: str
    ) -> Optional[CandidateBusiness]:
        """Convert a JSON-LD item to a CandidateBusiness."""
        name = item.get("name", "").strip()
        if not name or len(name) < 2:
            return None

        # Extract URL (the business's own website, not the directory page)
        url = item.get("url", "")
        if url and (source_url and source_url.split("/")[2] in url):
            # This URL is on the same directory domain — it's a directory listing URL, not a website
            url = ""

        phone_raw = item.get("telephone", "")
        email_raw = item.get("email", "")

        address_obj = item.get("address", {})
        address_str = ""
        if isinstance(address_obj, str):
            address_str = address_obj
        elif isinstance(address_obj, dict):
            parts = [
                address_obj.get("streetAddress", ""),
                address_obj.get("addressLocality", ""),
                address_obj.get("addressRegion", ""),
            ]
            address_str = ", ".join(p for p in parts if p)

        cand = CandidateBusiness(
            name=name,
            website=url or None,
            industry=industry,
            address=address_str or None,
            locations=[location] if location else [],
            sources=["directory_jsonld"],
            is_directory=False,
        )

        if phone_raw:
            norm_phone = PhoneNormalizer.normalize_e164(phone_raw)
            cand.phone_numbers.append(
                PhoneRecord(value=norm_phone or phone_raw, source_url=source_url, source_type="directory_jsonld")
            )

        if email_raw:
            norm_email = EmailNormalizer.normalize(email_raw)
            if norm_email:
                cand.emails.append(
                    EmailRecord(value=norm_email, verified=False, source_url=source_url, source_type="directory_jsonld")
                )

        cand.add_evidence("name", name, "directory_jsonld", source_url, confidence=0.90)
        return cand

    def _extract_from_cards(
        self, soup: BeautifulSoup, source_url: str, industry: str, location: str
    ) -> List[CandidateBusiness]:
        """Extract from common card-style directory patterns."""
        candidates = []

        # Common card selectors used by Practo, JustDial, etc.
        card_selectors = [
            "div[data-qa-id]",             # Practo-style
            "li.result",                    # Generic
            "div.listing-item",
            "div.business-card",
            "div.card",
            "article",
            "li[itemscope]",               # Microdata
            "div[itemscope]",
        ]

        for selector in card_selectors:
            cards = soup.select(selector)
            if len(cards) >= 3:  # Only use if we found multiple cards (genuine listing)
                for card in cards[:50]:  # Limit to 50 per page
                    cand = self._card_to_candidate(card, source_url, industry, location)
                    if cand:
                        candidates.append(cand)
                if candidates:
                    break  # Found a working pattern

        return candidates

    def _card_to_candidate(
        self, card: Tag, source_url: str, industry: str, location: str
    ) -> Optional[CandidateBusiness]:
        """Extract a single business from a card element."""
        try:
            # Find name — look for heading elements or itemprop="name"
            name_elem = (
                card.find(attrs={"itemprop": "name"}) or
                card.find(["h1", "h2", "h3", "h4"]) or
                card.find(class_=re.compile(r"name|title|business-name", re.I))
            )
            name = name_elem.get_text(strip=True) if name_elem else None

            if not name or len(name.strip()) < 2:
                return None

            # Extract phone — strictly from this card only
            card_text = card.get_text()
            phone_matches = PHONE_RE.findall(card_text)
            phone_elem = card.find(attrs={"itemprop": "telephone"})
            if phone_elem:
                phone_matches = [phone_elem.get_text(strip=True)] + phone_matches

            # Extract email — strictly from this card only
            email_matches = EMAIL_RE.findall(card_text)
            email_elem = card.find(attrs={"itemprop": "email"})
            if email_elem:
                email_matches = [email_elem.get_text(strip=True)] + email_matches

            # Filter out directory/noise emails
            noise_domains = {"magicpin", "practo", "justdial", "sulekha", "lybrate"}
            filtered_emails = [
                e for e in email_matches
                if not any(nd in e.lower() for nd in noise_domains)
            ]

            # Extract address
            addr_elem = (
                card.find(attrs={"itemprop": "address"}) or
                card.find(class_=re.compile(r"address|location|locality", re.I))
            )
            address = addr_elem.get_text(strip=True) if addr_elem else None

            # Extract website link (must be external, not the directory itself)
            dir_domain = source_url.split("/")[2] if "/" in source_url else ""
            links = card.find_all("a", href=True)
            website = None
            for link in links:
                href = link.get("href", "")
                if href.startswith("http") and dir_domain not in href:
                    website = href
                    break

            cand = CandidateBusiness(
                name=name.strip(),
                website=website,
                industry=industry,
                address=address,
                locations=[location] if location else [],
                sources=["directory_card"],
                is_directory=False,
            )

            # Add phones — only the ones found in THIS card
            seen_phones = set()
            for ph in phone_matches[:3]:  # max 3 phones per business
                norm = PhoneNormalizer.normalize_e164(ph)
                val = norm or ph.strip()
                if val and val not in seen_phones:
                    seen_phones.add(val)
                    cand.phone_numbers.append(
                        PhoneRecord(value=val, source_url=source_url, source_type="directory_card")
                    )

            # Add emails — only from this card
            seen_emails = set()
            for em in filtered_emails[:2]:
                norm = EmailNormalizer.normalize(em)
                val = norm or em.strip().lower()
                if val and val not in seen_emails:
                    seen_emails.add(val)
                    cand.emails.append(
                        EmailRecord(value=val, verified=False, source_url=source_url, source_type="directory_card")
                    )

            cand.add_evidence("name", name, "directory_card", source_url, confidence=0.85)
            return cand

        except Exception as e:
            logger.debug(f"Card extraction error: {e}")
            return None

    def _extract_from_list_items(
        self, soup: BeautifulSoup, source_url: str, industry: str, location: str
    ) -> List[CandidateBusiness]:
        """Last resort: extract from generic list items with business-like names."""
        candidates = []

        lists = soup.find_all(["ul", "ol"])
        for lst in lists:
            items = lst.find_all("li", recursive=False)
            if len(items) < 3:  # Need at least 3 to look like a listing
                continue

            for item in items[:20]:
                link = item.find("a")
                if link:
                    name = link.get_text(strip=True)
                    href = link.get("href", "")
                    if name and len(name) >= 3 and len(name) <= 80:
                        # Check if this looks like a business name (not navigation/footer)
                        if not any(kw in name.lower() for kw in ["home", "about", "contact", "login", "sign"]):
                            cand = CandidateBusiness(
                                name=name,
                                industry=industry,
                                locations=[location] if location else [],
                                sources=["directory_list"],
                                is_directory=False,
                            )
                            cand.add_evidence("name", name, "directory_list", source_url, confidence=0.60)
                            candidates.append(cand)

        return candidates
