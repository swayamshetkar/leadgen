from typing import List, Optional
import httpx
from app.discovery.sources.base import BaseDiscoverySource
from app.schemas.discovery_request import DiscoveryRequest
from app.models.candidate import CandidateBusiness
from app.core.config import settings
from app.core.rate_limit import AsyncRateLimiter
from app.utils.urls import normalize_url, extract_domain, is_valid_http_url


class HistoricalDiscoverySource(BaseDiscoverySource):
    """
    Public Historical Web / Wayback Machine CDX API adapter.
    Discovers historical website snapshots and domain context.
    All data is transparently marked as historical.
    """
    def __init__(self):
        super().__init__(name="historical")
        self.rate_limiter = AsyncRateLimiter(min_delay=1.0, max_delay=2.0)

    async def discover(self, request: DiscoveryRequest) -> List[CandidateBusiness]:
        if not request.settings.enable_historical:
            self.logger.debug("Historical discovery is disabled in settings. Skipping.")
            return []

        candidates: List[CandidateBusiness] = []
        target = request.target
        industry = target.industry
        locations = request.locations

        headers = {
            "User-Agent": f"LeadDiscoveryEngine/1.0 ({settings.USER_AGENT})",
            "Accept": "application/json"
        }

        async with httpx.AsyncClient(headers=headers, timeout=settings.REQUEST_TIMEOUT) as client:
            for loc in locations:
                # Query keyword matching domains from CDX
                clean_term = target.keywords[0] if target.keywords else industry
                query_url = f"*{clean_term.replace(' ', '')}*.com/*"
                
                try:
                    await self.rate_limiter.acquire()
                    params = {
                        "url": query_url,
                        "output": "json",
                        "fl": "original,timestamp,mimetype,statuscode",
                        "filter": "statuscode:200",
                        "collapse": "urlkey",
                        "limit": 20
                    }
                    resp = await client.get("http://web.archive.org/cdx/search/cdx", params=params)
                    if resp.status_code != 200:
                        continue

                    rows = resp.json()
                    if not rows or len(rows) <= 1:
                        continue

                    # First row is header
                    for row in rows[1:]:
                        orig_url = row[0]
                        if not is_valid_http_url(orig_url):
                            continue

                        domain = extract_domain(orig_url)
                        if not domain:
                            continue

                        cand = CandidateBusiness(
                            name=domain,
                            website=orig_url,
                            domain=domain,
                            industry=industry,
                            locations=[loc],
                            is_historical=True
                        )
                        cand.add_evidence(
                            field_name="website",
                            value=orig_url,
                            source_type="wayback",
                            source_url=f"https://web.archive.org/web/{row[1]}/{orig_url}",
                            confidence=0.70,
                            context_snippet=f"Wayback snapshot from {row[1]}"
                        )
                        candidates.append(cand)

                except Exception as e:
                    self.logger.warning(f"Error querying Wayback CDX: {e}")
                    continue

        self.logger.info(f"Historical source discovered {len(candidates)} records")
        return candidates
