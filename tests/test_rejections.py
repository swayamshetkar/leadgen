import pytest

from app.discovery.engine import DiscoveryEngine
from app.models.candidate import CandidateBusiness
from app.schemas.discovery_request import DiscoveryRequest, TargetBusiness


def _request(**settings):
    return DiscoveryRequest(
        target=TargetBusiness(industry="Restaurants", keywords=["restaurant"]),
        locations=["Bangalore"],
        settings=settings,
    )


def test_rejection_records_use_standard_reason_codes():
    engine = DiscoveryEngine()
    record = engine._rejection(
        CandidateBusiness(name="Top Restaurants in Bangalore", website="https://example.com"),
        "Business name appears to be a listing title",
    )

    assert record.reason_code == "NOT_A_BUSINESS"
    assert record.stage == "business_identity"


@pytest.mark.asyncio
async def test_target_leads_is_authoritative_and_partial_status_is_reported():
    engine = DiscoveryEngine()
    engine.sources = []

    result = await engine.execute_discovery(_request(target_leads=2, max_candidates_checked=10, max_runtime_minutes=1))

    assert result["accepted_leads"] == 0
    assert result["status"] == "completed_partial"
    assert result["target_leads"] == 2
    assert result["rejections"] == []