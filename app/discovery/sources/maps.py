from typing import List, Optional
import httpx
from app.discovery.sources.base import BaseDiscoverySource
from app.schemas.discovery_request import DiscoveryRequest
from app.models.candidate import CandidateBusiness, PhoneRecord
from app.models.evidence import EvidenceRecord
from app.core.rate_limit import AsyncRateLimiter
from app.core.config import settings
from app.utils.urls import normalize_url, extract_domain
from app.utils.text import clean_text


class MapsDiscoverySource(BaseDiscoverySource):
    """
    Maps & Local Business Discovery Source.
    Discovers physical business locations and POIs via OpenStreetMap / Nominatim
    and public local directory POI endpoints without paid API dependencies.
    """
    def __init__(self):
        super().__init__(name="maps")
        # Nominatim asks for at least 1 request/second and valid User-Agent
        self.rate_limiter = AsyncRateLimiter(min_delay=1.2, max_delay=2.0)

    async def discover(self, request: DiscoveryRequest) -> List[CandidateBusiness]:
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
                queries_to_try = [
                    f"{industry} in {loc}",
                    f"{target.keywords[0]} in {loc}" if target.keywords else f"{industry} {loc}"
                ]
                
                for q in queries_to_try:
                    try:
                        await self.rate_limiter.acquire()
                        params = {
                            "q": q,
                            "format": "jsonv2",
                            "addressdetails": 1,
                            "extratags": 1,
                            "namedetails": 1,
                            "limit": 30
                        }
                        resp = await client.get("https://nominatim.openstreetmap.org/search", params=params)
                        if resp.status_code != 200:
                            self.logger.debug(f"Nominatim returned status {resp.status_code} for query '{q}'")
                            continue

                        items = resp.json()
                        if not isinstance(items, list):
                            continue

                        for item in items:
                            namedetails = item.get("namedetails")
                            if not isinstance(namedetails, dict):
                                namedetails = {}
                            name = namedetails.get("name") or item.get("name")
                            if not name:
                                # Try extracting from display name
                                raw_disp = item.get("display_name", "")
                                name = raw_disp.split(",")[0] if raw_disp else None

                            if not name:
                                continue

                            extratags = item.get("extratags")
                            if not isinstance(extratags, dict):
                                extratags = {}
                            website = extratags.get("website") or extratags.get("contact:website") or extratags.get("url")
                            phone = extratags.get("phone") or extratags.get("contact:phone")
                            email = extratags.get("email") or extratags.get("contact:email")
                            
                            norm_website = normalize_url(website) if website else None
                            domain = extract_domain(norm_website) if norm_website else None

                            cand = CandidateBusiness(
                                name=clean_text(name),
                                website=norm_website,
                                domain=domain,
                                industry=industry,
                                address=item.get("display_name"),
                                locations=[loc]
                            )

                            if phone:
                                cand.phone_numbers.append(
                                    PhoneRecord(value=phone.strip(), source_type="maps", source_url="https://www.openstreetmap.org/")
                                )
                                cand.add_evidence(
                                    field_name="phone",
                                    value=phone.strip(),
                                    source_type="maps",
                                    source_url="https://www.openstreetmap.org/",
                                    confidence=0.90
                                )

                            if norm_website:
                                cand.add_evidence(
                                    field_name="website",
                                    value=norm_website,
                                    source_type="maps",
                                    source_url="https://www.openstreetmap.org/",
                                    confidence=0.90
                                )

                            cand.add_evidence(
                                field_name="name",
                                value=name,
                                source_type="maps",
                                source_url="https://www.openstreetmap.org/",
                                confidence=0.95,
                                context_snippet=item.get("display_name")
                            )

                            candidates.append(cand)

                    except Exception as e:
                        self.logger.warning(f"Error querying OSM maps for '{q}': {e}")
                        continue

        self.logger.info(f"Maps discovery source found {len(candidates)} local business candidates")
        return candidates
