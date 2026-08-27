import re
import urllib.parse
from typing import Dict, Optional, List
from bs4 import BeautifulSoup
from app.utils.urls import normalize_url


class SocialExtractor:
    """
    Extracts, validates, and normalizes social profile links (Instagram, Facebook, LinkedIn, Twitter/X, YouTube).
    Ignores share intent widgets and generic social root URLs.
    """
    SOCIAL_PATTERNS = {
        "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/([a-zA-Z0-9_.]+)/?", re.IGNORECASE),
        "facebook": re.compile(r"https?://(?:www\.)?facebook\.com/([a-zA-Z0-9_.-]+)/?", re.IGNORECASE),
        "linkedin": re.compile(r"https?://(?:www\.)?linkedin\.com/(?:company|in)/([a-zA-Z0-9_.-]+)/?", re.IGNORECASE),
        "twitter": re.compile(r"https?://(?:www\.)?(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)/?", re.IGNORECASE),
        "youtube": re.compile(r"https?://(?:www\.)?youtube\.com/(?:@|c/|channel/)?([a-zA-Z0-9_.-]+)/?", re.IGNORECASE),
    }

    IGNORED_HANDLES = {
        "share", "sharer", "intent", "sharer.php", "home", "search",
        "login", "privacy", "terms", "policies", "help", "about", "pages"
    }

    def extract_socials(self, html: str, same_as_urls: Optional[List[str]] = None) -> Dict[str, str]:
        socials: Dict[str, str] = {}
        all_candidate_urls = []

        if same_as_urls:
            all_candidate_urls.extend(same_as_urls)

        if html:
            soup = BeautifulSoup(html, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if href and ("instagram.com" in href or "facebook.com" in href or "linkedin.com" in href or "twitter.com" in href or "x.com" in href or "youtube.com" in href):
                    all_candidate_urls.append(href)

        for raw_url in all_candidate_urls:
            for platform, pattern in self.SOCIAL_PATTERNS.items():
                if platform in socials:
                    continue  # already found best link
                match = pattern.search(raw_url)
                if match:
                    handle = match.group(1).lower()
                    if handle not in self.IGNORED_HANDLES and len(handle) > 1:
                        # Clean canonical profile URL
                        clean_url = match.group(0)
                        socials[platform] = normalize_url(clean_url)

        return socials
