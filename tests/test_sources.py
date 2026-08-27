from unittest.mock import AsyncMock

import pytest

from app.discovery.sources.dorking import DorkingDiscoverySource
from app.discovery.sources.instagram import InstagramDiscoverySource


DDG_RESULT_HTML = """
<div class="result">
  <h2><a class="result__a" href="https://example.com/contact">Mumbai Restaurant</a></h2>
  <a class="result__snippet">Restaurant in Mumbai. Contact us for reservations.</a>
</div>
"""

INSTAGRAM_RESULT_HTML = """
<div class="result">
  <h2><a class="result__a" href="https://www.instagram.com/mumbai_restaurant/">Mumbai Restaurant (@mumbai_restaurant)</a></h2>
  <a class="result__snippet">Restaurant in Mumbai. Call +91 9876543210.</a>
</div>
"""


@pytest.mark.asyncio
async def test_dorking_parser_supports_current_ddg_result_markup():
    response = AsyncMock(status_code=200, text=DDG_RESULT_HTML)
    client = AsyncMock()
    client.post.return_value = response

    results = await DorkingDiscoverySource()._execute_dork_search(client, '"restaurant" "Mumbai" "contact"')

    assert results == [{
        "title": "Mumbai Restaurant",
        "url": "https://example.com/contact",
        "snippet": "Restaurant in Mumbai. Contact us for reservations.",
    }]


@pytest.mark.asyncio
async def test_instagram_parser_supports_current_ddg_result_markup():
    response = AsyncMock(status_code=200, text=INSTAGRAM_RESULT_HTML)
    client = AsyncMock()
    client.post.return_value = response

    results = await InstagramDiscoverySource()._search_instagram_profiles(
        client, 'site:instagram.com "restaurant" "Mumbai"'
    )

    assert len(results) == 1
    assert results[0]["url"] == "https://www.instagram.com/mumbai_restaurant/"
    assert results[0]["title"].startswith("Mumbai Restaurant")
