import urllib.parse
from typing import List, Set
from bs4 import BeautifulSoup
from app.utils.urls import normalize_url, is_same_domain, is_valid_http_url


class URLDiscovery:
    """
    Extracts, filters, and prioritizes internal links from HTML pages.
    """
    PRIORITY_KEYWORDS = [
        "contact", "about", "service", "team", "doctor",
        "dentist", "clinic", "location", "reach-us", "find-us",
        "our-story", "about-us", "contact-us"
    ]
    IGNORE_EXTENSIONS = (
        ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg",
        ".mp4", ".zip", ".css", ".js", ".xml", ".ico"
    )

    def extract_internal_links(self, html: str, current_url: str, max_links: int = 10) -> List[str]:
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        discovered: Set[str] = set()
        scored_links: List[tuple[int, str]] = []

        for a_tag in soup.find_all("a", href=True):
            raw_href = a_tag["href"].strip()
            if not raw_href or raw_href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue

            # Resolve absolute URL
            abs_url = urllib.parse.urljoin(current_url, raw_href)
            if not is_valid_http_url(abs_url) or not is_same_domain(current_url, abs_url):
                continue

            # Strip fragments and query
            norm_url = normalize_url(abs_url)
            if not norm_url or norm_url in discovered:
                continue

            # Skip asset extensions
            parsed_path = urllib.parse.urlparse(norm_url).path.lower()
            if any(parsed_path.endswith(ext) for ext in self.IGNORE_EXTENSIONS):
                continue

            discovered.add(norm_url)
            
            # Score link by path and anchor text
            anchor_text = a_tag.get_text().lower().strip()
            score = 0
            for kw in self.PRIORITY_KEYWORDS:
                if kw in parsed_path:
                    score += 10
                if kw in anchor_text:
                    score += 8

            if score > 0:
                scored_links.append((score, norm_url))

        scored_links.sort(key=lambda x: x[0], reverse=True)
        return [url for _, url in scored_links[:max_links]]
