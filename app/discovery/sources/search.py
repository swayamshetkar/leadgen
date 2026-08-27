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
from app.discovery.extractors.directory import DirectoryExtractor
from app.discovery.validation.business_validator import DIRECTORY_DOMAINS


class SearchDiscoverySource(BaseDiscoverySource):
    """
    Free public web search engine adapter.
    Executes expanded search queries against DuckDuckGo HTML/Lite,
    extracts organic result titles, URLs, and snippets, and converts them to candidate leads.
    """
    def __init__(self):
        super().__init__(name="search")
        self.rate_limiter = AsyncRateLimiter(
            min_delay=settings.SEARCH_DELAY_MIN,
            max_delay=settings.SEARCH_DELAY_MAX
        )
        self.query_gen = QueryGenerator()
        self.directory_extractor = DirectoryExtractor()
        # Domain blocklist (search engines, major aggregators, social networks handled separately)
        self.domain_blocklist = DIRECTORY_DOMAINS | {
            "duckduckgo.com", "google.com", "bing.com", "yahoo.com",
            "wikipedia.org", "youtube.com", "facebook.com", "instagram.com",
            "linkedin.com", "twitter.com", "x.com", "reddit.com", "pinterest.com",
            "yelp.com", "yellowpages.com", "tripadvisor.com", "justdial.com", "quora.com",
            "magicpin.in", "lybrate.com", "whatclinic.com", "scribd.com",
            "sulekha.com", "indiamart.com", "tradeindia.com", "yellowpages.in",
            "asklaila.com", "healthgrades.com", "zocdoc.com", "ambitionbox.com",
            "glassdoor.com", "indeed.com", "naukri.com", "zomato.com", "swiggy.com",
            "urbancompany.com", "urbanclap.com", "makemytrip.com", "booking.com",
        }

    async def discover(self, request: DiscoveryRequest) -> List[CandidateBusiness]:
        candidates: List[CandidateBusiness] = []
        seen_domains = set()

        queries = self.query_gen.generate_queries(request)
        # Search owns all public query families, including dorks and scoped social queries.
        search_queries = queries

        # Limit queries per location to avoid excessive requests
        max_queries_per_loc = settings.MAX_SEARCH_QUERIES_PER_LOCATION
        loc_queries: dict[str, list] = {}
        for q in search_queries:
            loc_queries.setdefault(q.location, []).append(q)

        selected_queries = []
        family_order = (
            "basic", "service", "contact", "intent", "dork", "social_dork",
        )
        for loc, q_list in loc_queries.items():
            by_family = {family: [q for q in q_list if q.family == family] for family in family_order}
            while len(selected_queries) < request.settings.max_search_queries:
                added = False
                for family in family_order:
                    if by_family[family] and len([q for q in selected_queries if q.location == loc]) < max_queries_per_loc:
                        selected_queries.append(by_family[family].pop(0))
                        added = True
                if not added or len([q for q in selected_queries if q.location == loc]) >= max_queries_per_loc:
                    break
            if len(selected_queries) >= request.settings.max_search_queries:
                break

        self.logger.info(f"Executing {len(selected_queries)} search queries across {len(request.locations)} locations")

        headers = {
            "User-Agent": settings.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": f"{request.settings.language},en-US;q=0.8,en;q=0.5",
        }

        async with httpx.AsyncClient(headers=headers, timeout=settings.SEARCH_REQUEST_TIMEOUT, follow_redirects=True) as client:
            for q_obj in selected_queries:
                try:
                    await self.rate_limiter.acquire()
                    search_results = await self._search_ddg(client, q_obj.query)
                    
                    for res in search_results:
                        url = res.get("url")
                        if not url or not is_valid_http_url(url):
                            continue
                        
                        domain = extract_domain(url)
                        if not domain:
                            continue

                        if self._is_directory_domain(domain):
                            extracted = await self._extract_directory_candidates(
                                client, url, request, q_obj.location
                            )
                            candidates.extend(extracted)
                            continue

                        if domain in self.domain_blocklist or domain in seen_domains:
                            continue
                        
                        seen_domains.add(domain)
                        
                        # Extract business name from title (e.g. "ABC Dental Clinic | Dentist in Bangalore")
                        raw_title = res.get("title", "")
                        clean_name = self._extract_business_name_from_title(raw_title, request.target.industry)
                        
                        cand = CandidateBusiness(
                            name=clean_name if clean_name else raw_title,
                            website=url,
                            domain=domain,
                            industry=request.target.industry,
                            description=res.get("snippet", ""),
                            locations=[q_obj.location]
                        )
                        cand.add_evidence(
                            field_name="website",
                            value=url,
                            source_type="search",
                            source_url="https://duckduckgo.com/html/",
                            confidence=0.85,
                            context_snippet=res.get("snippet")
                        )
                        if clean_name:
                            cand.add_evidence(
                                field_name="name",
                                value=clean_name,
                                source_type="search",
                                source_url=url,
                                confidence=0.80,
                                context_snippet=raw_title
                            )
                        
                        candidates.append(cand)

                except Exception as e:
                    self.logger.warning(f"Error querying search for '{q_obj.query}': {e}")
                    continue

        self.logger.info(f"Search source discovered {len(candidates)} unique candidates")
        return candidates

    async def _extract_directory_candidates(
        self,
        client: httpx.AsyncClient,
        url: str,
        request: DiscoveryRequest,
        location: str,
    ) -> List[CandidateBusiness]:
        try:
            resp = await client.get(url)
            if resp.status_code != 200 or not resp.text:
                return []

            candidates = self.directory_extractor.extract_businesses(
                resp.text,
                source_url=url,
                target_industry=request.target.industry,
                target_location=location,
            )
            for cand in candidates:
                cand.sources.append("directory_extraction")
                cand.add_evidence(
                    field_name="source_url",
                    value=url,
                    source_type="directory_extraction",
                    source_url=url,
                    confidence=0.70,
                )
            return candidates
        except Exception as e:
            self.logger.debug(f"Directory extraction failed for '{url}': {e}")
            return []

    async def _search_ddg(self, client: httpx.AsyncClient, query: str) -> List[dict]:
        """
        Queries DuckDuckGo HTML endpoint and parses organic search results.
        """
        results = []
        try:
            # DuckDuckGo HTML endpoint
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "b": ""},
                headers={"Referer": "https://html.duckduckgo.com/"}
            )
            if resp.status_code != 200:
                # Try Lite endpoint fallback
                resp = await client.post(
                    "https://lite.duckduckgo.com/lite/",
                    data={"q": query}
                )
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                
                # HTML format results
                result_blocks = soup.select(".result__body, .result")
                if result_blocks:
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
                else:
                    # Lite format results
                    rows = soup.select("table tbody tr")
                    curr_title = ""
                    curr_url = ""
                    for row in rows:
                        link = row.select_one("a.result-link")
                        if link:
                            curr_title = clean_text(link.get_text())
                            curr_url = self._unwrap_ddg_url(link.get("href", ""))
                        snippet = row.select_one("td.result-snippet")
                        if snippet and curr_url:
                            results.append({
                                "title": curr_title,
                                "url": normalize_url(curr_url),
                                "snippet": clean_text(snippet.get_text())
                            })
                            curr_title = ""
                            curr_url = ""

        except Exception as e:
            self.logger.debug(f"DuckDuckGo parse error: {e}")
        return results

    def _unwrap_ddg_url(self, raw_href: str) -> Optional[str]:
        """
        Unwraps DuckDuckGo redirect URLs e.g. //duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com
        """
        if not raw_href:
            return None
        if "uddg=" in raw_href:
            parsed = urllib.parse.urlparse(raw_href)
            params = urllib.parse.parse_qs(parsed.query)
            uddg = params.get("uddg")
            if uddg:
                return uddg[0]
        if raw_href.startswith("http://") or raw_href.startswith("https://"):
            return raw_href
        return None

    def _is_directory_domain(self, domain: str) -> bool:
        return domain in DIRECTORY_DOMAINS

    def _extract_business_name_from_title(self, title: str, industry: str) -> Optional[str]:
        """
        Clean common page title suffixes: 'ABC Dental Clinic | Top Dentist in Bangalore' -> 'ABC Dental Clinic'
        """
        if not title:
            return None
        # Split on common separators
        parts = re.split(r"[-|–—:•]", title)
        if parts:
            first_part = clean_text(parts[0])
            # If the first part is substantial and not just the industry name
            if len(first_part) >= 3 and first_part.lower() != industry.lower():
                return first_part
        return clean_text(title)
