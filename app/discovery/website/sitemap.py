import gzip
import io
import re
import urllib.parse
from typing import List, Optional, Set
import xml.etree.ElementTree as ET
import httpx
from app.core.config import settings
from app.core.logging import get_logger
from app.utils.urls import normalize_url, is_valid_http_url

logger = get_logger("website.sitemap")


class SitemapParser:
    """
    Retrieves and parses XML sitemaps and sitemap indexes.
    Filters URLs to prioritize high-value business, contact, about, and service pages.
    """
    PRIORITY_KEYWORDS = [
        "contact", "about", "service", "team", "doctor",
        "clinic", "location", "branch", "pricing", "staff", "meet-the-team"
    ]

    async def discover_sitemap_urls(
        self,
        base_url: str,
        declared_sitemaps: Optional[List[str]] = None,
        client: Optional[httpx.AsyncClient] = None
    ) -> List[str]:
        parsed_base = urllib.parse.urlparse(base_url)
        root_url = f"{parsed_base.scheme}://{parsed_base.netloc}"

        candidate_sitemaps: List[str] = []
        if declared_sitemaps:
            candidate_sitemaps.extend(declared_sitemaps)

        # Standard sitemap locations
        default_sitemaps = [
            f"{root_url}/sitemap.xml",
            f"{root_url}/sitemap_index.xml",
            f"{root_url}/wp-sitemap.xml",
        ]
        for s in default_sitemaps:
            if s not in candidate_sitemaps:
                candidate_sitemaps.append(s)

        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=10.0, verify=False)
            close_client = True

        all_page_urls: Set[str] = set()

        try:
            for sitemap_url in candidate_sitemaps[:3]:
                try:
                    resp = await client.get(sitemap_url)
                    if resp.status_code == 200:
                        content = resp.content
                        # Handle gzipped sitemap if needed
                        if sitemap_url.endswith(".gz") or resp.headers.get("content-encoding") == "gzip":
                            try:
                                content = gzip.decompress(content)
                            except Exception:
                                pass
                        
                        extracted = self._parse_xml_content(content)
                        for u in extracted:
                            all_page_urls.add(u)
                            
                        if all_page_urls:
                            break
                except Exception as e:
                    logger.debug(f"Failed to fetch sitemap {sitemap_url}: {e}")
                    continue

        finally:
            if close_client:
                await client.aclose()

        # Prioritize and return top relevant URLs
        return self._score_and_filter_urls(list(all_page_urls), max_urls=15)

    def _parse_xml_content(self, xml_bytes: bytes) -> List[str]:
        urls = []
        try:
            # Remove namespace prefixes to ease parsing
            xml_text = xml_bytes.decode("utf-8", errors="ignore")
            xml_text = re.sub(r'xmlns(:\w+)?="[^"]+"', '', xml_text)
            root = ET.fromstring(xml_text)

            # Check if this is a sitemapindex
            for sitemap in root.findall(".//sitemap/loc"):
                loc = sitemap.text.strip() if sitemap.text else None
                if loc and is_valid_http_url(loc):
                    # In deep crawls we can recurse; here we note the URL
                    pass

            # Standard urlset
            for url_elem in root.findall(".//url/loc"):
                loc = url_elem.text.strip() if url_elem.text else None
                if loc and is_valid_http_url(loc):
                    urls.append(normalize_url(loc))

        except Exception as e:
            logger.debug(f"XML parse error: {e}")
        return urls

    def _score_and_filter_urls(self, urls: List[str], max_urls: int = 15) -> List[str]:
        scored: List[tuple[int, str]] = []
        for url in urls:
            url_lower = url.lower()
            score = 0
            for kw in self.PRIORITY_KEYWORDS:
                if kw in url_lower:
                    score += 10
            # Penalize blogs, tags, feeds, pagination
            if any(bad in url_lower for bad in ["/blog/", "/tag/", "/category/", "/page/", "/author/", "/wp-content/"]):
                score -= 15
            if score > 0:
                scored.append((score, url))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [u for _, u in scored[:max_urls]]
