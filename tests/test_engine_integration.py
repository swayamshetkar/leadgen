import pytest
from unittest.mock import AsyncMock, patch
from app.schemas.discovery_request import DiscoveryRequest, TargetBusiness, Requirements
from app.models.candidate import CandidateBusiness, EmailRecord, PhoneRecord
from app.discovery.engine import DiscoveryEngine
from app.discovery.sources.base import BaseDiscoverySource


class MockSearchSource(BaseDiscoverySource):
    def __init__(self):
        super().__init__(name="search")

    async def discover(self, request: DiscoveryRequest):
        return [
            CandidateBusiness(
                name="Elite Dental Clinic",
                website="https://elitedental.com",
                domain="elitedental.com",
                industry="Dental clinics",
                locations=["Bangalore"],
                sources=["search"]
            ),
            CandidateBusiness(
                name="Bangalore Smiles",
                website="https://bangaloresmiles.com",
                domain="bangaloresmiles.com",
                industry="Dental clinics",
                locations=["Bangalore"],
                sources=["search"]
            )
        ]


class MockMapsSource(BaseDiscoverySource):
    def __init__(self):
        super().__init__(name="maps")

    async def discover(self, request: DiscoveryRequest):
        return [
            CandidateBusiness(
                name="Elite Dental Clinic Bangalore",
                website="https://elitedental.com",
                domain="elitedental.com",
                phone_numbers=[PhoneRecord(value="+918012345678", source_type="maps")],
                address="Indiranagar, Bangalore",
                locations=["Bangalore"],
                sources=["maps"]
            )
        ]


@pytest.mark.asyncio
async def test_discovery_engine_pipeline():
    request = DiscoveryRequest(
        target=TargetBusiness(
            industry="Dental clinics",
            services=["dental implants"],
            keywords=["dentist"]
        ),
        locations=["Bangalore"],
        requirements=Requirements(
            must_have=[],
            exclude=["hospital"]
        )
    )

    engine = DiscoveryEngine()
    engine.sources = [MockSearchSource(), MockMapsSource()]
    
    # Mock crawler to prevent real network fetches during unit test
    engine.crawler.crawl_domain = AsyncMock(return_value=[])

    result = await engine.execute_discovery(request)

    assert result["total_candidates"] == 3
    # 2 Elite Dental records should merge into 1, plus 1 Bangalore Smiles = 2 unique leads
    assert result["unique_businesses"] == 2

    leads = result["leads"]
    elite_lead = next(l for l in leads if "Elite Dental" in l.name)
    assert elite_lead.website == "https://elitedental.com"
    assert len(elite_lead.phone_numbers) == 1
    assert elite_lead.phone_numbers[0].value == "+918012345678"
    assert "search" in elite_lead.sources
    assert "maps" in elite_lead.sources
