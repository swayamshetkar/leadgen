import json
import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from app.utils.text import clean_text
from app.utils.urls import normalize_url


class JSONLDExtractor:
    """
    Extracts Schema.org structured data from JSON-LD script blocks.
    Supports LocalBusiness, Dentist, MedicalBusiness, Store, Organization, etc.
    """
    TARGET_TYPES = {
        "localbusiness", "organization", "dentist", "medicalbusiness",
        "physician", "store", "professionalservice", "healthandbeautybusiness",
        "dentistry", "medicalclinic", "hospital", "corporation"
    }

    def extract(self, html: str, page_url: str) -> List[Dict[str, Any]]:
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        scripts = soup.find_all("script", type="application/ld+json")
        results = []

        for script in scripts:
            content = script.string or script.get_text()
            if not content:
                continue

            try:
                # Clean stray comments or CDATA
                cleaned = re.sub(r"^\s*<!--|-->\s*$", "", content.strip())
                data = json.loads(cleaned)
                
                # Extract items whether single object, list, or @graph
                items = self._flatten_items(data)
                for item in items:
                    parsed = self._parse_schema_item(item, page_url)
                    if parsed:
                        results.append(parsed)

            except Exception:
                continue

        return results

    def _flatten_items(self, data: Any) -> List[Dict[str, Any]]:
        items = []
        if isinstance(data, list):
            for sub in data:
                items.extend(self._flatten_items(sub))
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                for sub in data["@graph"]:
                    items.extend(self._flatten_items(sub))
            else:
                items.append(data)
        return items

    def _parse_schema_item(self, item: Dict[str, Any], page_url: str) -> Optional[Dict[str, Any]]:
        schema_type = item.get("@type", "")
        if isinstance(schema_type, list):
            schema_type_str = " ".join(str(t) for t in schema_type).lower()
        else:
            schema_type_str = str(schema_type).lower()

        # Check if type matches any business/org target
        is_target_type = any(t in schema_type_str for t in self.TARGET_TYPES)
        if not is_target_type and not ("name" in item and ("telephone" in item or "address" in item)):
            return None

        name = item.get("name") or item.get("legalName")
        if not name or not isinstance(name, str):
            return None

        # Parse Address
        address_raw = item.get("address")
        address_str = self._format_address(address_raw)

        # Parse Phone
        phone = item.get("telephone")
        if isinstance(phone, list) and phone:
            phone = str(phone[0])
        elif phone:
            phone = str(phone)

        # Parse Email
        email = item.get("email")
        if isinstance(email, list) and email:
            email = str(email[0])
        elif email:
            email = str(email)

        # Parse sameAs (social profiles / external links)
        same_as = item.get("sameAs", [])
        if isinstance(same_as, str):
            same_as = [same_as]
        elif not isinstance(same_as, list):
            same_as = []

        url = item.get("url") or page_url
        description = item.get("description")

        return {
            "type": schema_type,
            "name": clean_text(name),
            "telephone": phone.strip() if phone else None,
            "email": email.strip().lower() if email else None,
            "address": address_str,
            "url": normalize_url(str(url)) if url else None,
            "description": clean_text(str(description)) if description else None,
            "sameAs": [normalize_url(str(s)) for s in same_as if isinstance(s, str)],
            "source_url": page_url
        }

    def _format_address(self, addr: Any) -> Optional[str]:
        if not addr:
            return None
        if isinstance(addr, str):
            return clean_text(addr)
        if isinstance(addr, dict):
            parts = [
                addr.get("streetAddress"),
                addr.get("addressLocality"),
                addr.get("addressRegion"),
                addr.get("postalCode"),
                addr.get("addressCountry")
            ]
            valid_parts = [clean_text(str(p)) for p in parts if p]
            return ", ".join(valid_parts) if valid_parts else None
        return None
