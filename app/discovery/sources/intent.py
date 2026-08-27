import re
import urllib.parse
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.rate_limit import AsyncRateLimiter
from app.discovery.opportunities.service_profiles import get_display_name
from app.discovery.query_generator import QueryGenerator
from app.discovery.sources.base import BaseDiscoverySource
from app.models.candidate import CandidateBusiness, IntentEvidence
from app.schemas.discovery_request import DiscoveryRequest
from app.utils.text import clean_text
from app.utils.urls import is_valid_http_url, normalize_url


class ExplicitIntentDiscoverySource(BaseDiscoverySource):
    """
    Finds public pages where a business appears to ask for a service the user
    sells. A website is not required; the snippet/source URL is the lead evidence.
    """

    def __init__(self):
        super().__init__(name="explicit_intent")
        self.rate_limiter = AsyncRateLimiter(
            min_delay=settings.SEARCH_DELAY_MIN,
            max_delay=settings.SEARCH_DELAY_MAX,
        )
        self.query_gen = QueryGenerator()

    async def discover(self, request: DiscoveryRequest) -> List[CandidateBusiness]:
        if not request.services_offered:
            return []

        candidates: List[CandidateBusiness] = []
        queries = self.query_gen.generate_explicit_intent_queries(
            request.services_offered,
            request.locations,
            request.target.industry,
        )

        headers = {
            "User-Agent": settings.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": f"{request.settings.language},en-US;q=0.8,en;q=0.5",
        }

        async with httpx.AsyncClient(headers=headers, timeout=settings.REQUEST_TIMEOUT, follow_redirects=True) as client:
            for q_obj in queries:
                try:
                    await self.rate_limiter.acquire()
                    for res in await self._search_ddg(client, q_obj.query):
                        url = res.get("url")
                        if not url or not is_valid_http_url(url):
                            continue

                        snippet = clean_text(res.get("snippet", ""))
                        title = clean_text(res.get("title", ""))
                        evidence_text = snippet or title
                        if not evidence_text:
                            continue

                        service_display = get_display_name(q_obj.service) if q_obj.service else None
                        confidence = self._intent_confidence(q_obj.intent_type or "", evidence_text)
                        name = self._extract_business_name(title, snippet, request.target.industry)

                        cand = CandidateBusiness(
                            name=name,
                            industry=request.target.industry,
                            description=evidence_text,
                            locations=[q_obj.location],
                            sources=["explicit_intent"],
                            lead_type="explicit_intent",
                            service_requested=service_display,
                            intent_confidence=confidence,
                            intent_evidence=IntentEvidence(
                                source_url=normalize_url(url),
                                text=evidence_text[:500],
                                source_type=self._source_type(url),
                                confidence=confidence,
                            ),
                            short_reason=self._short_reason(service_display, evidence_text),
                        )
                        cand.add_evidence(
                            field_name="intent_evidence",
                            value=evidence_text[:500],
                            source_type="explicit_intent",
                            source_url=normalize_url(url),
                            confidence={"high": 0.9, "medium": 0.75, "low": 0.55}.get(confidence, 0.7),
                            context_snippet=f"Query: {q_obj.query}",
                        )
                        candidates.append(cand)
                except Exception as e:
                    self.logger.warning(f"Error querying explicit intent for '{q_obj.query}': {e}")

        self.logger.info(f"Explicit intent source discovered {len(candidates)} candidates")
        return candidates

    async def _search_ddg(self, client: httpx.AsyncClient, query: str) -> List[dict]:
        results: List[dict] = []
        try:
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "b": ""},
                headers={"Referer": "https://html.duckduckgo.com/"},
            )
            if resp.status_code != 200:
                resp = await client.post("https://lite.duckduckgo.com/lite/", data={"q": query})

            if resp.status_code != 200:
                return results

            soup = BeautifulSoup(resp.text, "lxml")
            bodies = soup.select(".result__body")
            if bodies:
                for body in bodies:
                    title_elem = body.select_one(".result__title a")
                    snippet_elem = body.select_one(".result__snippet")
                    if not title_elem:
                        continue
                    target_url = self._unwrap_ddg_url(title_elem.get("href", ""))
                    if target_url:
                        results.append({
                            "title": clean_text(title_elem.get_text()),
                            "url": normalize_url(target_url),
                            "snippet": clean_text(snippet_elem.get_text()) if snippet_elem else "",
                        })
            else:
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
                            "snippet": clean_text(snippet.get_text()),
                        })
                        curr_title = ""
                        curr_url = ""
        except Exception as e:
            self.logger.debug(f"Explicit intent search parse error: {e}")
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
        if raw_href.startswith("http://") or raw_href.startswith("https://"):
            return raw_href
        return None

    def _extract_business_name(self, title: str, snippet: str, industry: str) -> Optional[str]:
        text = title or snippet
        if not text:
            return None

        split_title = re.split(r"[-|:•–—]", title)
        if split_title:
            first = clean_text(split_title[0])
            if first and len(first) >= 3 and first.lower() != industry.lower():
                return first[:120]

        quoted = re.search(r'"([^"]{3,100})"', snippet)
        if quoted:
            return clean_text(quoted.group(1))
        return None

    def _intent_confidence(self, intent_type: str, evidence_text: str) -> str:
        evidence_lower = evidence_text.lower()
        high_markers = ("looking to hire", "hiring", "need help", "need", "seeking")
        if intent_type in {"hiring", "need", "looking_for"} and any(m in evidence_lower for m in high_markers):
            return "high"
        if intent_type in {"recommend", "want_to_improve"}:
            return "medium"
        return "low"

    def _source_type(self, url: str) -> str:
        url_lower = url.lower()
        if any(domain in url_lower for domain in ("indeed.", "naukri.", "glassdoor.", "linkedin.com/jobs")):
            return "job_board"
        if any(domain in url_lower for domain in ("facebook.", "instagram.", "x.com", "twitter.", "linkedin.")):
            return "social"
        if any(domain in url_lower for domain in ("reddit.", "quora.")):
            return "forum"
        return "public_web"

    def _short_reason(self, service_display: Optional[str], evidence_text: str) -> str:
        service_text = f" for {service_display}" if service_display else ""
        snippet = evidence_text.strip()
        if len(snippet) > 140:
            snippet = snippet[:137] + "..."
        return f"Public intent signal{service_text}: {snippet}"
