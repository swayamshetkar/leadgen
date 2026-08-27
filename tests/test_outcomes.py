import pytest

from app.discovery.engine import DiscoveryEngine
from app.discovery.sources.base import BaseDiscoverySource
from app.models.candidate import CandidateBusiness, PhoneRecord
from app.schemas.discovery_request import DiscoveryRequest, TargetBusiness


class OutcomeSource(BaseDiscoverySource):
    def __init__(self):
        super().__init__("outcome_test")

    async def discover(self, request):
        return [
            CandidateBusiness(
                name="Good Restaurant",
                industry="Restaurants",
                locations=["Bangalore"],
                phone_numbers=[PhoneRecord(value="+911111111111")],
            ),
            CandidateBusiness(
                name="Wrong Location Restaurant",
                industry="Restaurants",
                locations=["Mumbai"],
                phone_numbers=[PhoneRecord(value="+912222222222")],
            ),
            CandidateBusiness(
                name="Good Restaurant Branch",
                industry="Restaurants",
                locations=["Bangalore"],
                phone_numbers=[PhoneRecord(value="+911111111111")],
            ),
        ]


@pytest.mark.asyncio
async def test_processed_candidates_have_reconciled_terminal_outcomes():
    engine = DiscoveryEngine()
    engine.sources = [OutcomeSource()]

    request = DiscoveryRequest(
        target=TargetBusiness(industry="Restaurants", keywords=["restaurant"]),
        locations=["Bangalore"],
        settings={
            "target_leads": 5,
            "max_candidates_checked": 10,
            "max_runtime_minutes": 1,
        },
    )
    result = await engine.execute_discovery(request)

    assert result["raw_candidates"] == 3
    assert result["candidates_checked"] == 3
    assert result["accepted_leads"] == 1
    assert result["rejected_candidates"] == 1
    assert result["duplicates"] == 1
    assert result["error_count"] == 0
    assert result["candidates_checked"] == (
        result["accepted_leads"]
        + result["rejected_candidates"]
        + result["duplicates"]
        + result["error_count"]
    )
    assert result["rejections"][0].reason_code == "WRONG_LOCATION"
    assert result["rejections"][0].stage == "location"
    assert [outcome["outcome"] for outcome in result["outcomes"]] == [
        "ACCEPTED", "REJECTED", "DUPLICATE"
    ]