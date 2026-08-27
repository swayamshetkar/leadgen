import re
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from app.utils.text import clean_text


class BusinessExtractor:
    """
    Synthesizes core business properties: clean name, services offered, and overview description.
    """
    def extract_business_info(
        self,
        html: str,
        meta: Dict[str, Any],
        jsonld_items: List[Dict[str, Any]],
        target_services: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml") if html else None

        # 1. Business Name Resolution
        # Priority: JSON-LD name -> og:site_name -> <H1> -> Title tag
        name = None
        if jsonld_items and jsonld_items[0].get("name"):
            name = jsonld_items[0]["name"]
        elif meta.get("site_name"):
            name = meta["site_name"]
        elif soup and soup.find("h1"):
            h1_text = clean_text(soup.find("h1").get_text())
            if len(h1_text) >= 3 and len(h1_text) <= 70:
                name = h1_text
        if not name and meta.get("title"):
            # Split title on common delimiters
            parts = re.split(r"[-|–—:•]", meta["title"])
            if parts:
                name = clean_text(parts[0])

        # 2. Description Resolution
        description = None
        if jsonld_items and jsonld_items[0].get("description"):
            description = jsonld_items[0]["description"]
        elif meta.get("description"):
            description = meta["description"]
        elif soup:
            p_tags = soup.find_all("p")
            for p in p_tags:
                p_text = clean_text(p.get_text())
                if len(p_text) > 40:
                    description = p_text
                    break

        # 3. Services Detection
        discovered_services: List[str] = []
        page_text = soup.get_text(separator=" ").lower() if soup else ""

        if target_services:
            for s in target_services:
                if s.lower() in page_text and s not in discovered_services:
                    discovered_services.append(s)

        # Look for list items under service sections
        if soup:
            service_sections = soup.find_all(
                ["section", "div", "ul"],
                class_=lambda c: c and "service" in str(c).lower()
            )
            for sec in service_sections:
                for li in sec.find_all("li"):
                    li_text = clean_text(li.get_text())
                    if len(li_text) >= 3 and len(li_text) <= 50 and li_text not in discovered_services:
                        discovered_services.append(li_text)

        return {
            "name": name,
            "description": description,
            "services": discovered_services[:15]
        }
