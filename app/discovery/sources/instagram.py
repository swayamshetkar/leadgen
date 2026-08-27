import re
import urllib.parse
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup

from app.discovery.sources.base import BaseDiscoverySource
from app.schemas.discovery_request import DiscoveryRequest
from app.models.candidate import CandidateBusiness, EmailRecord, PhoneRecord
from app.core.config import settings
from app.core.rate_limit import AsyncRateLimiter
from app.utils.urls import normalize_url, extract_domain
from app.utils.text import clean_text


class InstagramDiscoverySource(BaseDiscoverySource):
    """
    Public Instagram business profile discovery.
    Uses public search engine indexing and public profile snippets to discover
    active business profiles, public bios, and linked websites without requiring logins
    or bypassing anti-bot systems. Gracefully fails if automated access is restricted.
    """
    def __init__(self):
        super().__init__(name="instagram")
        self.rate_limiter = AsyncRateLimiter(min_delay=0.5, max_delay=1.0)

    async def discover(self, request: DiscoveryRequest) -> List[CandidateBusiness]:
        candidates: List[CandidateBusiness] = []
        target = request.target
        industry = target.industry
        locations = request.locations

        headers = {
            "User-Agent": settings.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        async with httpx.AsyncClient(headers=headers, timeout=settings.SEARCH_REQUEST_TIMEOUT, follow_redirects=True) as client:
            for loc in locations:
                # One combined query per location avoids duplicate provider calls.
                terms = [industry]
                if target.keywords:
                    terms[0] = f"{industry} {target.keywords[0]}"
                for term in terms:
                    query = f'site:instagram.com "{term}" "{loc}"'
                    try:
                        await self.rate_limiter.acquire()
                        results = await self._search_instagram_profiles(client, query)
                        
                        for res in results:
                            raw_url = res.get("url", "")
                            profile_url, handle = self._extract_instagram_handle(raw_url)
                            if not profile_url or not handle:
                                continue

                            title = res.get("title", "")
                            snippet = res.get("snippet", "")
                            
                            # Extract display name from title: "Dr. Smith Dental Clinic (@drsmithdental) • Instagram photos"
                            name = self._parse_name_from_title(title, handle)
                            
                            cand = CandidateBusiness(
                                name=name or f"@{handle}",
                                industry=industry,
                                description=snippet,
                                social_profiles={"instagram": profile_url},
                                locations=[loc]
                            )
                            
                            # Check if snippet contains a phone or email
                            self._extract_contacts_from_snippet(cand, snippet, profile_url)
                            
                            cand.add_evidence(
                                field_name="social_profiles.instagram",
                                value=profile_url,
                                source_type="instagram",
                                source_url=profile_url,
                                confidence=0.90,
                                context_snippet=snippet
                            )
                            
                            if name:
                                cand.add_evidence(
                                    field_name="name",
                                    value=name,
                                    source_type="instagram",
                                    source_url=profile_url,
                                    confidence=0.80,
                                    context_snippet=title
                                )

                            candidates.append(cand)

                    except Exception as e:
                        self.logger.warning(f"Graceful degradation: Instagram discovery failed for '{query}': {e}")
                        continue

        self.logger.info(f"Instagram source discovered {len(candidates)} public profile candidates")
        return candidates

    async def _search_instagram_profiles(self, client: httpx.AsyncClient, query: str) -> List[dict]:
        results = []
        try:
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "b": ""},
                headers={"Referer": "https://html.duckduckgo.com/"}
            )
            if resp.status_code != 200 or not resp.text.strip():
                resp = await client.post(
                    "https://lite.duckduckgo.com/lite/",
                    data={"q": query},
                )
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                result_blocks = soup.select(".result__body, .result")
                for body in result_blocks:
                    title_elem = body.select_one(".result__title a, .result__a, h2 a, h3 a")
                    snippet_elem = body.select_one(".result__snippet, .result-snippet")
                    if title_elem:
                        raw_href = title_elem.get("href", "")
                        target_url = self._unwrap_url(raw_href)
                        if target_url and "instagram.com/" in target_url.lower():
                            results.append({
                                "title": clean_text(title_elem.get_text()),
                                "url": target_url,
                                "snippet": clean_text(snippet_elem.get_text()) if snippet_elem else ""
                            })
                if not result_blocks:
                    for link in soup.select("a.result-link, a.result__a"):
                        target_url = self._unwrap_url(link.get("href", ""))
                        if target_url and "instagram.com/" in target_url.lower():
                            results.append({
                                "title": clean_text(link.get_text()),
                                "url": target_url,
                                "snippet": "",
                            })
            else:
                self.logger.debug("Instagram search provider returned HTTP %s", resp.status_code)
            if not results:
                results = await self._search_bing_profiles(client, query)
        except Exception as e:
            self.logger.debug(f"Instagram search parse error: {e}")
        return results

    async def _search_bing_profiles(self, client: httpx.AsyncClient, query: str) -> List[dict]:
        """Fallback to Bing's public result page when DuckDuckGo is unavailable."""
        results: List[dict] = []
        try:
            resp = await client.get("https://www.bing.com/search", params={"q": query})
            if resp.status_code != 200:
                return results
            soup = BeautifulSoup(resp.text, "lxml")
            for item in soup.select("li.b_algo"):
                link = item.select_one("h2 a")
                if not link:
                    continue
                target_url = self._unwrap_url(link.get("href", ""))
                if target_url and "instagram.com/" in target_url.lower():
                    snippet = item.select_one(".b_caption p")
                    results.append({
                        "title": clean_text(link.get_text()),
                        "url": target_url,
                        "snippet": clean_text(snippet.get_text()) if snippet else "",
                    })
        except Exception as e:
            self.logger.debug(f"Bing Instagram fallback failed: {e}")
        return results

    def _unwrap_url(self, raw_href: str) -> Optional[str]:
        if not raw_href:
            return None
        if "uddg=" in raw_href:
            parsed = urllib.parse.urlparse(raw_href)
            params = urllib.parse.parse_qs(parsed.query)
            uddg = params.get("uddg")
            if uddg:
                return uddg[0]
        return raw_href if raw_href.startswith("http") else None

    def _extract_instagram_handle(self, url: str) -> tuple[Optional[str], Optional[str]]:
        """
        Extracts clean username handle and canonical profile URL.
        Ignores tags, reels, posts, explore, p/, stories.
        """
        match = re.search(r"instagram\.com/([a-zA-Z0-9_.]+)", url)
        if not match:
            return None, None
        handle = match.group(1).lower()
        # Exclude reserved paths
        if handle in ("p", "reel", "reels", "stories", "explore", "tv", "accounts", "tags", "direct"):
            return None, None
        canonical_url = f"https://www.instagram.com/{handle}/"
        return canonical_url, handle

    def _parse_name_from_title(self, title: str, handle: str) -> Optional[str]:
        if not title:
            return None
        # Format often: "ABC Clinic (@abc_clinic) • Instagram photos and videos"
        title = re.sub(r"•\s*Instagram.*$", "", title, flags=re.IGNORECASE).strip()
        title = re.sub(r"\(@[a-zA-Z0-9_.]+\)", "", title).strip()
        title = re.sub(r"on Instagram:.*$", "", title, flags=re.IGNORECASE).strip()
        title = clean_text(title)
        return title if len(title) > 2 else None

    def _extract_contacts_from_snippet(self, cand: CandidateBusiness, snippet: str, profile_url: str):
        if not snippet:
            return
        # Simple phone regex in bio snippet
        phone_match = re.search(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", snippet)
        if phone_match:
            phone_val = phone_match.group(0).strip()
            cand.phone_numbers.append(PhoneRecord(value=phone_val, source_type="instagram", source_url=profile_url))
            cand.add_evidence(
                field_name="phone",
                value=phone_val,
                source_type="instagram",
                source_url=profile_url,
                confidence=0.75,
                context_snippet=snippet
            )
        # Simple email in bio snippet
        email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", snippet)
        if email_match:
            email_val = email_match.group(0).lower()
            cand.emails.append(EmailRecord(value=email_val, verified=False, source_type="instagram", source_url=profile_url))
            cand.add_evidence(
                field_name="email",
                value=email_val,
                source_type="instagram",
                source_url=profile_url,
                confidence=0.75,
                context_snippet=snippet
            )
