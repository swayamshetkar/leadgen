from typing import Dict, Any, Optional
from bs4 import BeautifulSoup
from app.utils.text import clean_text
from app.utils.urls import normalize_url


class MetadataExtractor:
    """
    Extracts HTML document metadata, OpenGraph tags, and Twitter cards.
    """
    def extract(self, html: str, page_url: str) -> Dict[str, Any]:
        if not html:
            return {}

        soup = BeautifulSoup(html, "lxml")
        
        # Title
        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = clean_text(title_tag.get_text())

        # Meta tags
        meta_desc = self._get_meta(soup, "name", "description")
        og_title = self._get_meta(soup, "property", "og:title")
        og_desc = self._get_meta(soup, "property", "og:description")
        og_site_name = self._get_meta(soup, "property", "og:site_name")
        og_url = self._get_meta(soup, "property", "og:url")
        
        # Canonical URL
        canonical = ""
        canonical_tag = soup.find("link", rel=lambda r: r and "canonical" in r)
        if canonical_tag and canonical_tag.get("href"):
            canonical = normalize_url(canonical_tag["href"])

        return {
            "title": title or og_title or "",
            "description": meta_desc or og_desc or "",
            "site_name": og_site_name or "",
            "og_url": og_url or canonical or page_url,
            "canonical": canonical or page_url
        }

    def _get_meta(self, soup: BeautifulSoup, attr: str, val: str) -> Optional[str]:
        tag = soup.find("meta", {attr: val}) or soup.find("meta", {attr: val.lower()})
        if tag and tag.get("content"):
            return clean_text(tag["content"])
        return None
