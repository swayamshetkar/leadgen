import re
import urllib.parse
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup

from app.discovery.sources.base import BaseDiscoverySource
from app.schemas.discovery_request import DiscoveryRequest
from app.models.candidate import CandidateBusiness
from app.core.config import settings
from app.core.rate_limit import AsyncRateLimiter
from app.utils.urls import normalize_url, extract_domain, is_valid_http_url
from app.utils.text import clean_text
from app.discovery.query_generator import QueryGenerator
from app.discovery.validation.business_validator import DIRECTORY_DOMAINS


class DorkingDiscoverySource(BaseDiscoverySource):
    """
    Search-Operator / Dork Discovery Strategy.
    Generates and executes safe, public search queries with advanced operators
    (inurl, exact phrase, contact signatures) to uncover high-intent business sites.
    """
    def __init__(self):
        super().__init__(name="dorking")
        self.rate_limiter = AsyncRateLimiter(min_delay=1.2, max_delay=2.5)
        self.query_gen = QueryGenerator()
        self.domain_blocklist = DIRECTORY_DOMAINS | {
            "duckduckgo.com", "google.com", "bing.com", "yahoo.com",
            "wikipedia.org", "youtube.com", "facebook.com", "instagram.com",
            "linkedin.com", "twitter.com", "x.com", "reddit.com", "pinterest.com",
            "practo.com", "magicpin.in", "lybrate.com", "whatclinic.com", "scribd.com",
            "justdial.com", "sulekha.com", "indiamart.com", "tradeindia.com",
            "yellowpages.in", "asklaila.com", "healthgrades.com", "zocdoc.com",
            "ambitionbox.com", "glassdoor.com", "indeed.com", "naukri.com",
            "zomato.com", "swiggy.com", "urbancompany.com", "urbanclap.com",
            "makemytrip.com",
        }

    async def discover(self, request: DiscoveryRequest) -> List[CandidateBusiness]:
        candidates: List[CandidateBusiness] = []
        seen_domains = set()

        all_queries = self.query_gen.generate_queries(request)
        dork_queries = [q for q in all_queries if q.family == "dork"]
        queries_by_location = {}
        for query in dork_queries:
            queries_by_location.setdefault(query.location, []).append(query)
        dork_queries = [
            query
            for location_queries in queries_by_location.values()
            for query in location_queries[:settings.MAX_DORK_QUERIES_PER_LOCATION]
        ]

        self.logger.info(f"Executing {len(dork_queries)} dork queries across {len(request.locations)} locations")

        headers = {
            "User-Agent": settings.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        async with httpx.AsyncClient(headers=headers, timeout=settings.SEARCH_REQUEST_TIMEOUT, follow_redirects=True) as client:
            for q_obj in dork_queries:
                try:
                    await self.rate_limiter.acquire()
                    results = await self._execute_dork_search(client, q_obj.query)
                    
                    for res in results:
                        url = res.get("url")
                        if not url or not is_valid_http_url(url):
                            continue
                        
                        domain = extract_domain(url)
                        if not domain or domain in self.domain_blocklist or domain in seen_domains:
                            continue
                        
                        seen_domains.add(domain)
                        title = res.get("title", "")
                        
                        cand = CandidateBusiness(
                            name=title,
                            website=url,
                            domain=domain,
                            industry=request.target.industry,
                            description=res.get("snippet", ""),
                            locations=[q_obj.location]
                        )
                        cand.add_evidence(
                            field_name="website",
                            value=url,
                            source_type="dorking",
                            source_url=url,
                            confidence=0.88,
                            context_snippet=f"Query: {q_obj.query}"
                        )
                        candidates.append(cand)

                except Exception as e:
                    self.logger.warning(f"Error executing dork '{q_obj.query}': {e}")
                    continue

        self.logger.info(f"Dorking source discovered {len(candidates)} candidates")
        return candidates

    async def _execute_dork_search(self, client: httpx.AsyncClient, query: str) -> List[dict]:
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
                        target_url = self._unwrap_ddg_url(raw_href)
                        if target_url:
                            results.append({
                                "title": clean_text(title_elem.get_text()),
                                "url": normalize_url(target_url),
                                "snippet": clean_text(snippet_elem.get_text()) if snippet_elem else ""
                            })
                if not result_blocks:
                    for link in soup.select("a.result-link, a.result__a"):
                        target_url = self._unwrap_ddg_url(link.get("href", ""))
                        if target_url:
                            results.append({
                                "title": clean_text(link.get_text()),
                                "url": normalize_url(target_url),
                                "snippet": "",
                            })
        except Exception as e:
            self.logger.debug(f"Dorking search error: {e}")
        return results

    def _unwrap_ddg_url(self, raw_href: str) -> Optional[str]:
        if not raw_href:
            return None
        if "uddg=" in raw_href:
            parsed = urllib.parse.urlparse(raw_href)
            params = urllib.parse.parse_qs(parsed.query)
            uddg = params.get("uddg")
            if uddg:
                return uddg[0]
        return raw_href if raw_href.startswith("http") else None
